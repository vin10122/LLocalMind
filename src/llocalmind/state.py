"""Small, atomic user settings and conversation store (outside the app)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import uuid

from .app_paths import user_data_dir
from .metrics import clean_stats
from .images import validate_images

DEFAULTS = dict(model_path='', max_tokens=128, max_seq=2048, cache=320,
                weight_cache=1, expert_workers=4, prefill_threads=4,
                ssm_device='GPU', attention_device='GPU', temperature=0.0,
                engine='optimized',vision_executable='',vision_projector='',
                vision_image_tokens=768,vision_batch=512,vision_ubatch=256,
                vision_cache_mib=128,vision_warmup=True)


def validate_settings(values):
    if not isinstance(values,dict):
        raise ValueError('Impostazioni non valide')
    result = dict(DEFAULTS)
    for key in result:
        if key in values:
            result[key] = values[key]
    for key in ('model_path','vision_executable','vision_projector'):
        if not isinstance(result[key],str):raise ValueError('Percorso non valido')
    if result['engine'] not in ('optimized','vision'):raise ValueError('Motore non valido')
    for key, low, high in [('max_tokens',1,4096), ('max_seq',256,16384),
                           ('cache',1,2048), ('weight_cache',1,2048),
                           ('expert_workers',1,16), ('prefill_threads',1,16)]:
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError(f'Impostazione non valida: {key}')
    if result['max_tokens'] >= result['max_seq']:
        raise ValueError('Il limite di output deve essere inferiore al contesto')
    for key,low,high in (('vision_image_tokens',64,8192),('vision_batch',32,2048),
                        ('vision_ubatch',32,2048),('vision_cache_mib',0,1024)):
        if type(result[key]) is not int or not low<=result[key]<=high:
            raise ValueError('Impostazione vision non valida: '+key)
    if result['vision_ubatch']>result['vision_batch'] or type(result['vision_warmup']) is not bool:
        raise ValueError('Profilo vision non valido')
    for key in ('ssm_device','attention_device'):
        if result[key] not in ('CPU','GPU','NPU'):
            raise ValueError('Dispositivo non valido')
    if type(result['temperature']) not in (int,float) or not 0 <= result['temperature'] <= 2:
        raise ValueError('Temperatura non valida')
    return result


def engine_signature(values):
    """Only options actually consumed by the selected engine cause a reload."""
    common=('engine','model_path','max_seq','expert_workers','prefill_threads')
    if values['engine']=='vision':
        keys=common+('vision_executable','vision_projector','vision_image_tokens',
                     'vision_batch','vision_ubatch','vision_cache_mib','vision_warmup')
    else:
        keys=common+('cache','weight_cache','ssm_device','attention_device')
    return tuple((key,values[key]) for key in keys)


def new_chat():
    return dict(id=uuid.uuid4().hex, title='Nuova conversazione', messages=[])


class LocalState:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else user_data_dir()
        self.settings = dict(DEFAULTS)
        self.chats = []
        self.warning = ''
        self.read_only = False
        try:
            config = self._read('settings.json', {})
            self.settings = validate_settings(config)
            chats = self._read('conversations.json', [])
            if not isinstance(chats, list):
                raise ValueError('Archivio conversazioni non valido')
            for chat in chats:
                if not isinstance(chat, dict) or not all(isinstance(chat.get(k),str) for k in ('id','title')):
                    raise ValueError('Conversazione non valida')
                if not isinstance(chat.get('messages'),list):
                    raise ValueError('Messaggi non validi')
                for message in chat['messages']:
                    if (not isinstance(message,dict) or message.get('role') not in ('user','assistant')
                            or not isinstance(message.get('content'),str)):
                        raise ValueError('Messaggio non valido')
                    validate_images(message.get('images',[]))
                    if message.get('images') and message['role']!='user':
                        raise ValueError('Le immagini devono essere associate a una domanda')
                    if 'stats' in message:
                        stats=clean_stats(message['stats'])
                        if stats is None:
                            message.pop('stats')
                        else:
                            message['stats']=stats
            if len({c['id'] for c in chats}) != len(chats):
                raise ValueError('Identificatori duplicati')
            self.chats = chats
        except (OSError, ValueError, TypeError) as error:
            # Do not silently overwrite an archive that could not be read.
            self.warning = f'Archivio locale non leggibile: {error}. I file originali non saranno sovrascritti.'
            self.read_only = True
        if not self.chats:
            self.chats = [new_chat()]

    def _read(self, name, default):
        path = self.directory / name
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding='utf-8'))

    def _write(self, name, value):
        if self.read_only:
            raise ValueError(self.warning)
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.directory,
                                             suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.directory / name)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def save_chats(self):
        self._write('conversations.json', self.chats)

    def save_settings(self, values):
        values = validate_settings(values)
        self._write('settings.json', values)
        self.settings = values
