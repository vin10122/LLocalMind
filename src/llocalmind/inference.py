"""Serial model operations on a Qt worker; no inference imports at GUI startup."""
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
    reply_finished = Signal(str)
    finished = Signal()

    def __init__(self, stop=None):
        super().__init__()
        self.stop = stop or threading.Event()
        self.model = None
        self.tokenizer = None

    def _close_model(self):
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
        try:
            self._close_model()
            gc.collect()
            if self.stop.is_set():
                return
            path = Path(filename).expanduser().resolve()
            if not path.is_file() or path.suffix.lower() != '.gguf':
                raise ValueError('Seleziona un file GGUF esistente')
            os.environ['FLASH_MOE_GGUF'] = str(path)
            self.progress.emit(0, 'Preparazione del modello')
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
            self.progress.emit(99, 'Preparazione del tokenizer')
            self.tokenizer = GGUFTokenizer(self.model.reader)
            self.progress.emit(100, 'Modello pronto')
            self.loaded.emit(path.stem)
        except Exception as error:
            try:
                self._close_model()
            except Exception:
                pass
            self.error.emit(str(error))

    @Slot(list, dict)
    def generate(self, messages, options):
        status = 'complete'
        stream = None
        try:
            if self.model is None or self.tokenizer is None:
                raise RuntimeError('Carica prima un modello')
            from flash_moe.tokenizer import StreamingDetokenizer
            ids = self.tokenizer.encode(format_conversation(messages), add_bos=False)
            if len(ids) + options['max_tokens'] - 1 > self.model.max_seq_len:
                raise ValueError('La conversazione supera il contesto disponibile. '
                                 'Apri una nuova chat o aumenta il contesto nelle impostazioni.')
            decoder = StreamingDetokenizer(self.tokenizer)
            started = time.perf_counter()
            first = None
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
                if first is None:
                    first = time.perf_counter() - started
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
            seconds = float(timings['generation_seconds'])
            self.stats.emit(dict(tokens=produced, first_token=first,
                                 prefill=float(timings['prefill_seconds']),
                                 rate=(produced-1)/seconds if produced > 1 and seconds > 0 else None))
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
