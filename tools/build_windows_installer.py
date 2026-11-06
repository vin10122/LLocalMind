"""Package an existing Windows app folder with Inno Setup; emit its SHA-256."""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from llocalmind import __version__
from llocalmind.updater import version_tuple


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dir", type=Path, required=True, help="Cartella dell'app gia' compilata")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist/releases")
    parser.add_argument("--iscc", type=Path, help="Percorso di ISCC.exe (Inno Setup 6.3+)")
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        parser.error("L'installer Windows deve essere compilato su Windows")
    version_tuple(__version__)
    source = args.app_dir.resolve()
    if not (source / "LLocalMind.exe").is_file():
        parser.error("La cartella deve contenere LLocalMind.exe e le sue librerie")
    if next(source.rglob("*.gguf"), None) is not None:
        parser.error("Sposta i GGUF fuori dalla cartella dell'app prima di creare l'installer")
    compiler = args.iscc or shutil.which("ISCC.exe")
    if compiler is None:
        for env in ("ProgramFiles(x86)", "ProgramFiles"):
            candidate = Path(os.environ.get(env, "C:/Program Files")) / "Inno Setup 6/ISCC.exe"
            if candidate.is_file():
                compiler = candidate
                break
    if compiler is None:
        parser.error("Installa Inno Setup 6.3+ oppure specifica --iscc")
    output = args.output_dir.resolve()
    if output == source or output.is_relative_to(source):
        parser.error("La cartella release deve essere esterna alla cartella dell'app")
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        str(compiler), f"/DAppVersion={__version__}", f"/DSourceDir={source}",
        f"/DReleaseDir={output}", str(ROOT / "packaging/windows/LLocalMind.iss"),
    ], check=True)
    installer = output / f"LLocalMind-Setup-{__version__}-windows-x64.exe"
    with installer.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    checksum = installer.with_name(installer.name + ".sha256")
    checksum.write_text(f"{digest}  {installer.name}\n", encoding="ascii")
    print(f"Pubblica entrambi gli asset nella release v{__version__}:")
    print(installer)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
