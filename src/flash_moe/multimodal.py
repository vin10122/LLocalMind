"""Real local multimodal inference; never project RGB averages as embeddings.

Native OpenVINO vision is not implemented. An explicitly selected llama.cpp
server executes the trained vision tower, projector and multimodal prefill.
"""
from __future__ import annotations
from llocalmind.i18n import tr
import http.client
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import threading
import time


class VisionCancelled(Exception):
    pass


class MultiModalProjector:
    """Guard against using the removed, mathematically invalid projector."""
    def __init__(self, *args, **kwargs):
        raise NotImplementedError('Encoder vision OpenVINO nativo non implementato. '
            'Usa --mmproj e --llama-server o la modalità Vision della GUI.')


class LocalVisionModel:
    def __init__(self, model, projector=None, executable=None, *, max_seq=2048,
                 threads=4, prefill_threads=4, log_path=None,image_max_tokens=768,
                 batch_tokens=512,ubatch_tokens=256,cache_mib=128,warmup=True):
        self.model=Path(model).expanduser().resolve()
        self.projector=Path(projector).expanduser().resolve() if projector else None
        found=shutil.which(str(executable)) if executable else shutil.which('llama-server')
        self.executable=Path(found or executable or '').expanduser().resolve()
        for label,path in (('modello',self.model),('mmproj',self.projector),('llama-server',self.executable)):
            if path is None:continue
            if not path.is_file():raise ValueError(tr('File {label} non trovato: {path}',label=label,path=path))
        if any(p is not None and p.suffix.lower()!='.gguf' for p in (self.model,self.projector)):
            raise ValueError(tr('Modello e mmproj devono essere file GGUF compatibili'))
        self.max_seq=max_seq
        self.threads=threads
        self.prefill_threads=prefill_threads
        if (not 64<=image_max_tokens<=8192 or not 32<=ubatch_tokens<=batch_tokens<=2048
                or not 0<=cache_mib<=1024 or type(warmup) is not bool):
            raise ValueError(tr('Profilo prestazioni vision non valido'))
        self.image_max_tokens=image_max_tokens
        self.batch_tokens=batch_tokens
        self.ubatch_tokens=ubatch_tokens
        self.cache_mib=cache_mib
        self.encoder_device='CPU' if self.projector else None
        self.warmup=warmup
        self.startup_seconds=None
        self.log_path=Path(log_path) if log_path else Path.cwd()/'vision.log'
        self.key=secrets.token_hex(32)
        self.alias='llocalmind-'+secrets.token_hex(16)
        self.process=None
        self.log=None
        self.port=None

    def _headers(self):
        return {'Content-Type':'application/json','Authorization':'Bearer '+self.key}

    def _connection(self,timeout=600):
        # Direct loopback: do not send image data through an HTTP proxy.
        return http.client.HTTPConnection('127.0.0.1',self.port,timeout=timeout)

    def start(self,stop=None,progress=lambda *_:None):
        started=time.perf_counter()
        stop=stop or threading.Event()
        if stop.is_set():raise VisionCancelled()
        try:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0))
                self.port=sock.getsockname()[1]
            progress(0,'Avvio encoder immagini CPU' if self.projector else 'Avvio llama.cpp CPU')
            self.log_path.parent.mkdir(parents=True,exist_ok=True)
            self.log=self.log_path.open('w',encoding='utf-8')
            from llocalmind.app_paths import child_environment
            command=[str(self.executable),'-m',str(self.model),
                '--host','127.0.0.1','--port',str(self.port),'--api-key',self.key,
                '--alias',self.alias,'-c',str(self.max_seq),'-np','1','-ngl','0',
                '--device','none','--no-webui','--jinja','--no-context-shift',
                '-b',str(self.batch_tokens),'-ub',str(self.ubatch_tokens),
                '--cache-ram',str(self.cache_mib),'--no-cache-idle-slots',
                '-t',str(self.threads),'-tb',str(self.prefill_threads)]
            if self.projector:
                command.extend(['--mmproj',str(self.projector),'--no-mmproj-offload',
                                '--image-min-tokens','64','--image-max-tokens',str(self.image_max_tokens)])
            if not self.warmup:command.append('--no-warmup')
            self.process=subprocess.Popen(command,cwd=self.executable.parent,
                env=child_environment(),
                stdin=subprocess.DEVNULL,stdout=self.log,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            progress(0,tr('Caricamento vision · encoder e modello CPU' if self.projector else 'Caricamento modello · llama.cpp CPU'))
            deadline=time.monotonic()+600
            while time.monotonic()<deadline:
                if stop.is_set():raise VisionCancelled()
                if self.process.poll() is not None:
                    raise RuntimeError(tr('Avvio vision fallito: verifica versione di llama.cpp e compatibilità modello/mmproj. Log: {path}',path=self.log_path))
                conn=self._connection(timeout=1)
                try:
                    conn.request('GET','/v1/models',headers=self._headers())
                    response=conn.getresponse()
                    if response.status==200:
                        data=json.loads(response.read(65536))
                        if any(m.get('id')==self.alias for m in data.get('data',[])):
                            self.startup_seconds=time.perf_counter()-started
                            progress(100,tr('Vision pronta · encoder CPU' if self.projector else 'Modello pronto · llama.cpp CPU'))
                            return
                except (OSError,http.client.HTTPException):pass
                finally:conn.close()
                stop.wait(.25)
            raise RuntimeError(tr('Tempo di caricamento vision superato. Log: {path}',path=self.log_path))
        except BaseException:
            self.close()
            raise

    def generate(self,messages,*,max_tokens=512,temperature=0,seed=0,
                 stop=None,on_text=lambda _:None,cache_prompt=True):
        stop=stop or threading.Event()
        if stop.is_set():raise VisionCancelled()
        if self.projector is None and any(
            isinstance(message.get('content'),list) and any(
                part.get('type') in ('image_url','input_image') for part in message['content'] if isinstance(part,dict))
            for message in messages):
            raise ValueError(tr('Per usare immagini seleziona un mmproj compatibile nelle impostazioni.'))
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError(tr('Motore vision chiuso: ricarica il modello'))
        if type(cache_prompt) is not bool:raise ValueError('Invalid prompt-cache option')
        payload=dict(messages=messages,stream=True,stream_options=dict(include_usage=True),
            max_tokens=max_tokens,temperature=temperature,seed=seed,
            cache_prompt=cache_prompt,id_slot=0,chat_template_kwargs=dict(enable_thinking=False))
        conn=self._connection()
        done=threading.Event()
        active_socket=None
        def cancel():
            while not done.wait(.1):
                sock=active_socket or conn.sock
                if stop.is_set() and sock is not None:
                    try:sock.shutdown(socket.SHUT_RDWR)
                    except OSError:pass
                    return
        watcher=threading.Thread(target=cancel,daemon=True)
        watcher.start()
        response=None
        first=None
        started=time.perf_counter()
        usage={}
        timings={}
        completed=False
        try:
            conn.connect()
            # HTTPConnection may close/detach its socket after reading a
            # Connection: close header while HTTPResponse keeps reading.
            # Retain an independently owned handle so cancellation can still
            # shutdown that connection on Windows as well as POSIX.
            active_socket=conn.sock.dup()
            conn.request('POST','/v1/chat/completions',json.dumps(payload).encode('utf-8'),self._headers())
            response=conn.getresponse()
            if response.status!=200:
                detail=response.read(8192).decode('utf-8',errors='replace')
                try:problem=json.loads(detail).get('error',{})
                except (ValueError,AttributeError):problem={}
                if isinstance(problem,dict) and problem.get('type')=='exceed_context_size_error':
                    raise ValueError(tr('Contesto insufficiente: richiesta {count} token, limite {limit}. Riduci i token visivi o la cronologia, oppure aumenta il contesto nelle impostazioni se la RAM lo consente.',count=problem.get('n_prompt_tokens','?'),limit=problem.get('n_ctx',self.max_seq)))
                raise ValueError(tr('Vision: richiesta rifiutata; verifica contesto e mmproj. ')+detail)
            while not stop.is_set():
                line=response.readline(2*1024**2)
                if not line:break
                if not line.startswith(b'data:'):continue
                value=line[5:].strip()
                if value==b'[DONE]':
                    completed=True
                    break
                event=json.loads(value)
                if event.get('error'):raise ValueError('Vision: '+str(event['error']))
                usage=event.get('usage') or usage
                timings=event.get('timings') or timings
                for choice in event.get('choices',[]):
                    text=choice.get('delta',{}).get('content')
                    if text:
                        if first is None:first=time.perf_counter()-started
                        on_text(text)
            if stop.is_set():raise VisionCancelled()
            if not completed:raise RuntimeError(tr('Risposta vision interrotta prima della fine'))
            tokens=usage.get('completion_tokens',timings.get('predicted_n',0))
            if type(tokens) is not int or tokens<0:tokens=0
            ms=timings.get('predicted_ms')
            seconds=ms/1000 if type(ms) in (int,float) and ms>0 else None
            prompt=timings.get('prompt_ms')
            return dict(tokens=tokens,first_token=first,decode_seconds=seconds,
                prompt_tokens=usage.get('prompt_tokens',timings.get('prompt_n')),
                evaluated_prompt_tokens=timings.get('prompt_n'),cached_tokens=timings.get('cache_n'),
                startup_seconds=self.startup_seconds,image_max_tokens=self.image_max_tokens,encoder_device=self.encoder_device,
                prefill=prompt/1000 if type(prompt) in (int,float) else None,
                rate=tokens/seconds if seconds and tokens>1 else None)
        except (OSError,http.client.HTTPException) as error:
            if stop.is_set():raise VisionCancelled() from error
            raise RuntimeError(tr('Connessione vision interrotta')) from error
        finally:
            done.set()
            watcher.join(timeout=1)
            if active_socket is not None:active_socket.close()
            if response is not None:response.close()
            conn.close()

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process=None
        if self.log is not None:
            self.log.close()
            self.log=None
