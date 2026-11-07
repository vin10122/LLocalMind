"""Pinned official Windows CPU runtime, installed outside the application tree."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid
import zipfile

from .app_paths import data_root, child_environment


@dataclass(frozen=True)
class RuntimePackage:
    tag: str
    url: str
    sha256: str
    size: int


# Downloaded from the official ggml-org release and hashed before pinning.
# Updating this requires reviewing a new official archive and running the
# Windows runtime probe. Never resolve an unverified "latest" ZIP at runtime.
PACKAGE=RuntimePackage('b12110',
    'https://github.com/ggml-org/llama.cpp/releases/download/b12110/llama-b12110-bin-win-cpu-x64.zip',
    '98901e327c252875accaf2d1bf364e10e868843b0b63468baad1aa945cdc5da2',24708445)
MAX_UNPACKED=512*1024**2


class RuntimeInstallError(RuntimeError):pass
class RuntimeInstallCancelled(RuntimeInstallError):pass


def supported_platform():
    return sys.platform=='win32' and platform.machine().lower() in ('amd64','x86_64') and struct.calcsize('P')==8


class HTTPSOnly(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urlparse(newurl).scheme!='https':raise RuntimeInstallError('Redirect del download senza HTTPS')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def _cancel(event):
    if event.is_set():raise RuntimeInstallCancelled('Installazione annullata')


def _relative(name):
    path=PurePosixPath(name)
    if (not name or '\\' in name or path.is_absolute() or '..' in path.parts
            or not path.parts or any(re.search(r'[<>:"|?*\x00-\x1f]',p)
            or p.endswith(('.', ' ')) or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?',p,re.I)
            for p in path.parts)):
        raise RuntimeInstallError('Percorso ZIP non valido')
    return path


def _hash(path,cancel):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        while block:=source.read(1024*1024):
            _cancel(cancel)
            digest.update(block)
    return digest.hexdigest()


def _windows_exe(path):
    with path.open('rb') as source:
        header=source.read(64)
        if len(header)!=64 or header[:2]!=b'MZ':return False
        offset=struct.unpack_from('<I',header,60)[0]
        if offset>path.stat().st_size-6:return False
        source.seek(offset)
        return source.read(6)==b'PE\x00\x00\x64\x86'


def probe_runtime(executable,cancel):
    """Check executable/DLL loading without loading a language model."""
    _cancel(cancel)
    with subprocess.Popen([str(executable),'--version'],cwd=executable.parent,
            env=child_environment(),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0) as process:
        deadline=time.monotonic()+20
        try:
            while time.monotonic()<deadline:
                _cancel(cancel)
                try:
                    output,_=process.communicate(timeout=.2)
                    if process.returncode:
                        raise RuntimeInstallError('Il motore scaricato non si avvia: '+output.decode('utf-8',errors='replace')[-1000:])
                    return
                except subprocess.TimeoutExpired:pass
            raise RuntimeInstallError('Verifica del motore vision scaduta')
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


class RuntimeInstaller:
    def __init__(self,directory=None,*,package=PACKAGE,opener=None,probe=probe_runtime):
        self.directory=Path(directory) if directory is not None else data_root()/'runtimes'/'llama.cpp'
        self.package=package
        expected=(f'https://github.com/ggml-org/llama.cpp/releases/download/{package.tag}/'
                  f'llama-{package.tag}-bin-win-cpu-x64.zip')
        if (not re.fullmatch(r'b[0-9]+',package.tag) or package.url!=expected
                or not re.fullmatch(r'[0-9a-f]{64}',package.sha256)
                or not 0<package.size<512*1024**2):
            raise RuntimeInstallError('Manifest del motore non valido')
        self.open=opener or build_opener(HTTPSOnly()).open
        self.probe=probe

    def _existing(self,cancel):
        for folder in sorted(self.directory.glob('llama-'+self.package.tag+'-cpu-x64-*'),reverse=True):
            _cancel(cancel)
            try:
                if not folder.is_dir() or folder.is_symlink():continue
                marker=json.loads((folder/'runtime.json').read_text())
                if marker['sha256']!=self.package.sha256:continue
                files=marker['files']
                if not isinstance(files,dict) or not 1<=len(files)<=512:continue
                server=folder/str(_relative(marker['server']))
                valid=True
                for name,digest in files.items():
                    path=folder/str(_relative(name))
                    if path.is_symlink() or _hash(path,cancel)!=digest:
                        valid=False
                        break
                if valid and marker['server'] in files and _windows_exe(server):return server
            except (OSError,KeyError,TypeError,ValueError,RuntimeInstallError):
                _cancel(cancel)
                continue
        return None

    def install(self,*,cancel=None,progress=lambda _:None):
        cancel=cancel or threading.Event()
        _cancel(cancel)
        if not supported_platform():raise RuntimeInstallError('Installazione automatica disponibile su Windows x64')
        existing=self._existing(cancel)
        if existing is not None:
            self.probe(existing,cancel)
            progress(100)
            return existing
        self.directory.mkdir(parents=True,exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix='.install-',dir=self.directory) as temporary:
                root=Path(temporary)
                archive=root/'download.zip'
                request=Request(self.package.url,headers={'User-Agent':'LLocalMind-runtime-installer'})
                received=0
                digest=hashlib.sha256()
                progress(0)
                with self.open(request,timeout=30) as source,archive.open('wb') as target:
                    while block:=source.read(256*1024):
                        _cancel(cancel)
                        received+=len(block)
                        if received>self.package.size:raise RuntimeInstallError('Dimensione del download non valida')
                        target.write(block)
                        digest.update(block)
                        progress(int(received*75/self.package.size))
                _cancel(cancel)
                if received!=self.package.size or digest.hexdigest()!=self.package.sha256:
                    raise RuntimeInstallError('Verifica SHA-256 del motore fallita: download incompleto o modificato')
                payload=root/'payload'
                payload.mkdir()
                files={}
                with zipfile.ZipFile(archive) as bundle:
                    entries=bundle.infolist()
                    if len(entries)>512 or sum(e.file_size for e in entries)>MAX_UNPACKED:
                        raise RuntimeInstallError('Archivio del motore troppo grande')
                    seen=set()
                    for index,entry in enumerate(entries):
                        _cancel(cancel)
                        # Validate before ZipInfo's platform-specific name
                        # normalization (including Windows backslashes/NULs).
                        name=_relative(entry.orig_filename).as_posix()
                        if name.casefold() in seen or stat.S_ISLNK(entry.external_attr>>16):
                            raise RuntimeInstallError('Archivio ZIP ambiguo o con collegamenti')
                        seen.add(name.casefold())
                        target=payload/name
                        if entry.is_dir():target.mkdir(parents=True,exist_ok=True)
                        else:
                            target.parent.mkdir(parents=True,exist_ok=True)
                            h=hashlib.sha256()
                            with bundle.open(entry) as source,target.open('xb') as output:
                                while block:=source.read(256*1024):
                                    _cancel(cancel)
                                    h.update(block)
                                    output.write(block)
                            files[name]=h.hexdigest()
                        progress(75+int((index+1)*20/max(1,len(entries))))
                servers=[name for name in files if PurePosixPath(name).name=='llama-server.exe']
                if len(servers)!=1 or not any(name.lower().endswith('.dll') for name in files):
                    raise RuntimeInstallError('llama-server.exe o DLL mancanti nell’archivio')
                server=payload/servers[0]
                if not _windows_exe(server):raise RuntimeInstallError('Eseguibile Windows x64 non valido')
                self.probe(server,cancel)
                _cancel(cancel)
                (payload/'runtime.json').write_text(json.dumps(dict(sha256=self.package.sha256,
                    server=servers[0],files=files)),encoding='utf-8')
                destination=self.directory/f'llama-{self.package.tag}-cpu-x64-{uuid.uuid4().hex[:12]}'
                payload.rename(destination)
                progress(100)
                return destination/servers[0]
        except (OSError,zipfile.BadZipFile) as error:
            raise RuntimeInstallError('Installazione motore vision non riuscita: '+str(error)) from error
