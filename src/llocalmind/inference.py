"""Serial model operations on a Qt worker; no inference imports at GUI startup."""
from .i18n import tr
import threading
import time
import os
import gc
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot
from .prompts import format_conversation


class ModelWorker(QObject):
    progress = Signal(int, str)
    loaded = Signal(str)
    token = Signal(str)
    stats = Signal(dict)
    error = Signal(str)
    search_status = Signal(str)
    reply_finished = Signal(str)
    finished = Signal()

    def __init__(self, stop=None):
        super().__init__()
        self.stop = stop or threading.Event()
        self.model = None
        self.tokenizer = None
        self.vision = None
        self.image_cache = None

    def _close_model(self):
        self.image_cache=None
        if self.vision is not None:
            engine,self.vision=self.vision,None
            engine.close()
        model, self.model = self.model, None
        self.tokenizer = None
        if model is not None:
            backend = getattr(model, 'backend', None)
            store = getattr(model, 'store', None)
            try:
                if backend is not None:
                    backend.close()
            finally:
                if store is not None:
                    store.close()

    @Slot(str, dict)
    def load(self, filename, options):
        started=time.perf_counter()
        try:
            self._close_model()
            gc.collect()
            if self.stop.is_set():
                return
            path = Path(filename).expanduser().resolve()
            if not path.is_file() or path.suffix.lower() != '.gguf':
                raise ValueError('Seleziona un file GGUF esistente')
            if options.get('engine')=='vision':
                from flash_moe.multimodal import LocalVisionModel,VisionCancelled
                from .app_paths import data_root
                self.vision=LocalVisionModel(path,options['vision_projector'],options['vision_executable'],
                    max_seq=options['max_seq'],threads=options['vision_threads'],
                    prefill_threads=options['vision_threads'],log_path=data_root()/'logs/vision.log',
                    image_max_tokens=options['vision_image_tokens'],batch_tokens=options['vision_batch'],
                    ubatch_tokens=options['vision_ubatch'],cache_mib=options['vision_cache_mib'],
                    warmup=options['vision_warmup'])
                from .images import ImagePayloadCache
                self.image_cache=ImagePayloadCache()
                try:self.vision.start(self.stop,self.progress.emit)
                except VisionCancelled:
                    self._close_model()
                    return
                from .performance import record,memory_snapshot
                record('load','vision',dict(encoder_device=self.vision.encoder_device,seconds=time.perf_counter()-started,
                    image_max_tokens=options['vision_image_tokens'],batch=options['vision_batch'],
                    ubatch=options['vision_ubatch'],cache_mib=options['vision_cache_mib'],warmup=options['vision_warmup'],
                    memory=memory_snapshot(self.vision.process.pid)))
                self.loaded.emit(path.stem+(' · llama.cpp · immagini · CPU' if options['vision_projector'] else ' · llama.cpp · testo · CPU'))
                return
            os.environ['FLASH_MOE_GGUF'] = str(path)
            self.progress.emit(0, tr('Preparazione del modello'))
            from flash_moe.model import Qwen3MoEModel
            from flash_moe.tokenizer import GGUFTokenizer
            from run_q4k_f16_openvino import dequant_to_f16
            # Retain a partially initialized object so failures can close any
            # store/backend worker pools that were already allocated.
            self.model = Qwen3MoEModel.__new__(Qwen3MoEModel)
            self.model.__init__(
                path, device='CPU', max_seq_len=options['max_seq'],
                cache_capacity=options['cache'], weight_cache_capacity=options['weight_cache'],
                native_decode='auto', expert_workers=options['expert_workers'],
                prefill_threads=options['prefill_threads'], dequant_fn=dequant_to_f16,
                ssm_device=options['ssm_device'], attention_device=options['attention_device'],
                startup_progress=lambda n, label: self.progress.emit(n, label),
            )
            if self.stop.is_set():
                self._close_model()
                return
            self.progress.emit(99, tr('Preparazione del tokenizer'))
            self.tokenizer = GGUFTokenizer(self.model.reader)
            from .performance import record
            record('load','optimized',dict(seconds=time.perf_counter()-started))
            self.progress.emit(100, tr('Modello pronto'))
            self.loaded.emit(path.stem)
        except Exception as error:
            try:
                self._close_model()
            except Exception:
                pass
            self.error.emit(str(error))

    @Slot(list, dict)
    def generate(self, messages, options):
        request_started=time.perf_counter()
        status = 'complete'
        stream = None
        try:
            if self.vision is None and (self.model is None or self.tokenizer is None):
                raise RuntimeError(tr('Carica prima un modello'))
            if self.vision is not None and self.vision.projector is None and any(message.get('images') for message in messages):
                raise ValueError(tr('Per usare immagini seleziona un mmproj compatibile nelle impostazioni.'))
            web_research = None
            web_stats={}
            if options.get('_web_search'):
                from .web_search import WebSearchCancelled, format_research, search_and_fetch
                try:
                    web_started=time.perf_counter()
                    query = next(message['content'] for message in reversed(messages)
                                 if message['role'] == 'user')
                    results = search_and_fetch(query, stop=self.stop,
                                               on_status=self.search_status.emit,profile=options.get('web_profile','fast'))
                except WebSearchCancelled:
                    status = 'stopped'
                    return
                web_research = format_research(results)
                web_stats=dict(web_seconds=time.perf_counter()-web_started,
                               web_sources=len(results),web_profile=options.get('web_profile','fast'))
                self.search_status.emit(tr('Analisi locale'))
            if self.vision is not None:
                from flash_moe.multimodal import VisionCancelled
                from .images import chat_messages
                try:
                    prepared=time.perf_counter()
                    request=chat_messages(messages,options['_attachment_directory'],cache=self.image_cache,language=options.get('language','it'),
                        image_profile=options.get('vision_image_profile','detail'),web_research=web_research)
                    prepare_seconds=time.perf_counter()-prepared
                    generate_started=time.perf_counter()
                    stats=dict(self.vision.generate(request,
                        max_tokens=options['max_tokens'],temperature=options['temperature'],
                        stop=self.stop,on_text=self.token.emit))
                    stats['input_seconds']=prepare_seconds
                    stats['image_profile']=options.get('vision_image_profile','detail')
                    stats['input_images']=sum(len(message.get('images',[])) for message in messages)
                    stats.update(web_stats)
                    if stats.get('first_token') is not None:stats['first_token']+=generate_started-request_started
                    from .performance import record,memory_snapshot
                    from .metrics import clean_stats
                    record('request','vision',dict(clean_stats(stats) or {},memory=memory_snapshot(self.vision.process.pid)))
                    self.stats.emit(stats)
                except VisionCancelled:status='stopped'
                return
            from flash_moe.tokenizer import StreamingDetokenizer
            ids = self.tokenizer.encode(
                format_conversation(messages, web_research=web_research,language=options.get('language','it')), add_bos=False)
            if len(ids) + options['max_tokens'] - 1 > self.model.max_seq_len:
                raise ValueError(tr('La conversazione supera il contesto disponibile. '
                                 'Apri una nuova chat o aumenta il contesto nelle impostazioni.'))
            decoder = StreamingDetokenizer(self.tokenizer)
            first = None
            first_generation = None
            last_generation = 0.0
            produced = 0
            stream = self.model.stream(ids, max_new_tokens=options['max_tokens'],
                                       temperature=options['temperature'],
                                       top_k=0 if options['temperature'] == 0 else 20,
                                       top_p=0 if options['temperature'] == 0 else .95)
            for count, token in stream:
                if self.stop.is_set():
                    status = 'stopped'
                    break
                produced = count
                last_generation=float(self.model.last_stream_timings['generation_seconds'])
                if first is None:
                    first = time.perf_counter() - request_started
                    first_generation = last_generation
                text = decoder.push(token)
                if text:
                    self.token.emit(text)
            else:
                if self.stop.is_set():
                    status = 'stopped'
            final = decoder.flush() if status != 'stopped' else ''
            if final:
                self.token.emit(final)
            timings = self.model.last_stream_timings
            # Exclude the first token's sampling, and any discarded token
            # generated while a cooperative stop was being requested.
            seconds=max(0.0,last_generation-first_generation) if first_generation is not None else 0.0
            stats=dict(tokens=produced, first_token=first,
                                 prefill=float(timings['prefill_seconds']),
                                 decode_seconds=seconds,
                                 rate=(produced-1)/seconds if produced > 1 and seconds > 0 else None)
            stats.update(web_stats)
            from .performance import record
            record('request','optimized',stats)
            self.stats.emit(stats)
        except Exception as error:
            status = 'error'
            self.error.emit(str(error))
        finally:
            try:
                if stream is not None:
                    stream.close()
            finally:
                self.reply_finished.emit(status)

    @Slot()
    def shutdown(self):
        try:
            self._close_model()
        except Exception as error:
            self.error.emit(str(error))
        finally:
            self.finished.emit()
