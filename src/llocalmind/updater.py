"""GitHub release updates using a per-user Windows installer.

No inference imports, automatic execution, or edits to the application tree.
The GUI should call check/download in a background worker. Before launching
the installer it must save chats, close the model, then exit the application.
"""

from __future__ import annotations
from .i18n import tr

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import __version__
from .app_paths import updates_dir

REPOSITORY = "vin10122/LLocalMind"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=100"
FEED_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/master/.github/update-feed.json"
MAX_INSTALLER_BYTES = 4 * 1024**3


class UpdateError(RuntimeError):
    pass


class DownloadCancelled(UpdateError):
    pass


def version_tuple(version: str) -> tuple[int, int, int]:
    if not isinstance(version, str) or not re.fullmatch(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise UpdateError(tr('Versione non valida: {version}',version=repr(version)))
    return tuple(map(int, version.removeprefix("v").split(".")))


class _HTTPSRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme != "https":
            raise UpdateError(tr("Redirect dell'aggiornamento senza HTTPS"))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class Release:
    version: str
    tag: str
    name: str
    notes: str
    asset_name: str
    download_url: str
    size: int
    sha256: str | None
    checksum_url: str | None
    prerelease: bool = False


@dataclass(frozen=True)
class DownloadedUpdate:
    release: Release
    path: Path
    sha256: str


class UpdateManager:
    def __init__(self, current_version=__version__, *, directory=None, opener=None):
        self.current_version = current_version
        version_tuple(current_version)
        self.directory = Path(directory) if directory is not None else updates_dir()
        self._open = opener or build_opener(_HTTPSRedirects()).open

    def _request(self, url, accept="application/octet-stream", *, cancel=None):
        if urlparse(url).scheme != "https":
            raise UpdateError(tr("URL dell'aggiornamento senza HTTPS"))
        request = Request(url, headers={
            "User-Agent": f"LLocalMind/{self.current_version}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            **({'Cache-Control':'no-cache'} if url in (API_URL,FEED_URL) else {}),
        })
        metadata=url in (API_URL,FEED_URL)
        attempts=2 if metadata else 3
        for attempt in range(attempts):
            if cancel is not None and cancel.is_set():raise DownloadCancelled('Download annullato')
            try:
                return self._open(request, timeout=10 if metadata else 30)
            except (HTTPError,URLError,TimeoutError) as error:
                delay=1+2*attempt
                if isinstance(error,HTTPError):
                    transient=error.code in (408,429,500,502,503,504)
                    retry_after=error.headers.get('Retry-After') if error.headers else None
                    error.close()
                    if not transient:raise
                    if retry_after is not None:
                        if not retry_after.isdecimal() or int(retry_after)>5:raise
                        delay=max(delay,int(retry_after))
                if attempt==attempts-1:raise
                if cancel is None:time.sleep(delay)
                else:cancel.wait(delay)

    @staticmethod
    def _asset_url(asset, tag):
        name = asset.get("name", "")
        expected = (f"https://github.com/{REPOSITORY}/releases/download/"
                    f"{quote(tag, safe='')}/{quote(name, safe='')}")
        if asset.get("browser_download_url") != expected:
            raise UpdateError(tr("L'asset non appartiene alla release GitHub prevista"))
        return expected

    def check(self, *, cancel=None) -> Release | None:
        """Highest newer published version, including previews; exclude drafts."""
        try:
            with self._request(API_URL, "application/vnd.github+json",cancel=cancel) as response:
                raw = response.read(2 * 1024**2 + 1)
        except HTTPError as error:
            error.close()
            if error.code == 404:
                return None
            if error.code not in (403,408,429,500,502,503,504):
                raise UpdateError(tr('Controllo GitHub fallito (HTTP {code})',code=error.code)) from error
            return self._feed_check(cancel=cancel)
        except (OSError, URLError,IncompleteRead) as error:
            return self._feed_check(cancel=cancel)
        if cancel is not None and cancel.is_set():raise DownloadCancelled('Download annullato')
        return self._parse_releases(raw)

    def _feed_check(self, *, cancel=None):
        try:
            with self._request(FEED_URL,'application/json',cancel=cancel) as response:
                raw=response.read(2*1024**2+1)
            if cancel is not None and cancel.is_set():raise DownloadCancelled('Download annullato')
            if len(raw)>2*1024**2:raise ValueError('Oversized feed')
            feed=json.loads(raw)
            if not isinstance(feed,dict) or type(feed.get('schema')) is not int or feed['schema']!=1:
                raise ValueError('Invalid feed schema')
            return self._parse_releases(json.dumps(feed['releases']).encode())
        except HTTPError as error:
            error.close()
            raise UpdateError(tr('GitHub è temporaneamente irraggiungibile anche dalla fonte alternativa. Riprova più tardi oppure scarica l’installer da GitHub Releases.')) from None
        except (OSError,URLError,IncompleteRead):
            raise UpdateError(tr('GitHub è temporaneamente irraggiungibile anche dalla fonte alternativa. Riprova più tardi oppure scarica l’installer da GitHub Releases.')) from None
        except (ValueError,KeyError,TypeError) as error:
            raise UpdateError(tr('File aggiornamenti ufficiale non valido. Nessun installer è stato scaricato.')) from error

    def _parse_releases(self,raw):
        if len(raw) > 2 * 1024**2:
            raise UpdateError("Risposta GitHub troppo grande")
        try:
            data = json.loads(raw)
            if not isinstance(data,list) or any(not isinstance(r,dict) for r in data):
                raise ValueError("invalid release list")
            candidates=[]
            for item in data:
                if item.get('draft'):continue
                try:version=version_tuple(item.get('tag_name'))
                except UpdateError:continue
                if version>version_tuple(self.current_version):candidates.append((version,item))
            if not candidates:return None
            latest,data=max(candidates,key=lambda candidate:candidate[0])
            tag=data['tag_name']
            version = ".".join(map(str, latest))
            name = f"LLocalMind-Setup-{version}-windows-x64.exe"
            assets = data["assets"]
            if not isinstance(assets, list) or any(not isinstance(a, dict) for a in assets):
                raise ValueError("invalid assets")
            asset = next(a for a in assets if a.get("name") == name)
            url = self._asset_url(asset, tag)
            size = asset["size"]
            if type(size) is not int or not 0 < size <= MAX_INSTALLER_BYTES:
                raise ValueError("invalid installer size")
            digest = asset.get("digest")
            sha256 = None
            if digest:
                if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
                    raise ValueError("invalid installer digest")
                sha256 = digest.split(":", 1)[1].lower()
            sidecar = next((a for a in assets if a.get("name") == name + ".sha256"), None)
            checksum_url = self._asset_url(sidecar, tag) if sidecar else None
            if sha256 is None and checksum_url is None:
                raise UpdateError(tr("La release non contiene un checksum SHA-256"))
            return Release(version, tag, str(data.get("name") or tag),
                           str(data.get("body") or ""), name, url, size,
                           sha256, checksum_url, data.get('prerelease') is True)
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            raise UpdateError(tr("Release senza installer Windows valido per LLocalMind")) from error

    def _checksum(self, release, *, cancel=None):
        if release.sha256 is not None:
            return release.sha256
        with self._request(release.checksum_url,cancel=cancel) as response:
            raw = response.read(8193)
        if len(raw) > 8192:
            raise UpdateError(tr("File checksum troppo grande"))
        try:
            text = raw.decode("ascii").strip()
        except UnicodeDecodeError as error:
            raise UpdateError(tr("Checksum non valido")) from error
        match = re.fullmatch(r"([0-9a-fA-F]{64})  " + re.escape(release.asset_name), text)
        if not match:
            raise UpdateError(tr("Checksum non valido o riferito a un altro file"))
        return match[1].lower()

    def _validate_release(self, release):
        version = ".".join(map(str, version_tuple(release.version)))
        if version_tuple(release.tag) != version_tuple(version):
            raise UpdateError(tr("Tag e versione della release non corrispondenti"))
        name = f"LLocalMind-Setup-{version}-windows-x64.exe"
        if release.asset_name != name:
            raise UpdateError(tr("Nome installer non valido"))
        self._asset_url({"name": name, "browser_download_url": release.download_url}, release.tag)
        if type(release.size) is not int or not 0 < release.size <= MAX_INSTALLER_BYTES:
            raise UpdateError(tr("Dimensione installer non valida"))
        if release.sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", release.sha256):
            raise UpdateError(tr("Checksum non valido"))
        if release.checksum_url:
            self._asset_url({"name": name + ".sha256", "browser_download_url": release.checksum_url}, release.tag)
        if release.sha256 is None and release.checksum_url is None:
            raise UpdateError("Checksum mancante")

    def download(self, release: Release, *, progress=None, cancel=None) -> DownloadedUpdate:
        """Verified atomic download. progress(received, total); optional Event cancellation."""
        self._validate_release(release)
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            if cancel is not None and cancel.is_set():
                raise DownloadCancelled("Download annullato")
            expected = self._checksum(release,cancel=cancel)
            digest = hashlib.sha256()
            received = 0
            with tempfile.NamedTemporaryFile(dir=self.directory, suffix=".part", delete=False) as output:
                temporary = Path(output.name)
                with self._request(release.download_url,cancel=cancel) as response:
                    if progress:
                        progress(0, release.size)
                    while True:
                        if cancel is not None and cancel.is_set():
                            raise DownloadCancelled("Download annullato")
                        chunk = response.read(1024**2)
                        if not chunk:
                            break
                        received += len(chunk)
                        if received > release.size:
                            raise UpdateError(tr("Installer piu' grande del previsto"))
                        output.write(chunk)
                        digest.update(chunk)
                        if progress:
                            progress(received, release.size)
            if received != release.size:
                raise UpdateError("Download incompleto")
            if digest.hexdigest() != expected:
                raise UpdateError(tr("Checksum SHA-256 dell'installer non corrispondente"))
            if cancel is not None and cancel.is_set():
                raise DownloadCancelled("Download annullato")
            destination = self.directory / release.asset_name
            os.replace(temporary, destination)
            temporary = None
            return DownloadedUpdate(release, destination, expected)
        except (OSError, URLError) as error:
            if isinstance(error, HTTPError):
                error.close()
            raise UpdateError(tr("Download dell'aggiornamento fallito")) from error
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def launch_installer(self, update: DownloadedUpdate):
        """Explicit installation only, after saving data/closing inference resources.

        The caller must exit its UI after this returns. Inno Setup handles
        Windows file replacement; no running EXE is overwritten by Python.
        """
        if sys.platform != "win32" or not getattr(sys, "frozen", False):
            raise UpdateError("Installazione disponibile solo nell'app Windows compilata")
        self._validate_release(update.release)
        if version_tuple(update.release.version) <= version_tuple(self.current_version):
            raise UpdateError(tr("L'aggiornamento non e' piu' recente"))
        path = update.path.resolve()
        if path != self.directory.resolve() / update.release.asset_name:
            raise UpdateError(tr("Installer fuori dalla cartella aggiornamenti"))
        try:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != update.sha256 or (update.release.sha256 and digest != update.release.sha256):
                raise UpdateError(tr("L'installer e' cambiato dopo il download"))
            # Inno Setup uses a stable AppId to upgrade in place, per user.
            return subprocess.Popen([
                str(path), "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS", "/RELAUNCH=1",
                f"/LOG={self.directory / 'install.log'}",
            ], cwd=self.directory)
        except OSError as error:
            raise UpdateError("Impossibile avviare l'installer") from error
