"""Release-update command line; importing it does not load the model."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from llocalmind import __version__
from llocalmind.updater import UpdateError, UpdateManager


def main(argv=None):
    parser = argparse.ArgumentParser(description="Aggiornamenti LLocalMind da GitHub")
    parser.add_argument("action", choices=("check", "download", "install"), nargs="?", default="check")
    args = parser.parse_args(argv)
    manager = UpdateManager()
    print(f"LLocalMind {__version__}")
    try:
        if args.action == "install" and (sys.platform != "win32" or not getattr(sys, "frozen", False)):
            raise UpdateError("Dai sorgenti usa git pull; install e' riservato all'app Windows compilata")
        release = manager.check()
        if release is None:
            print("Nessun aggiornamento stabile disponibile.")
            return 0
        print(f"Disponibile: {release.version}\n{release.name}")
        if args.action == "check":
            return 0
        update = manager.download(release)
        print(f"Scaricato e verificato: {update.path}")
        if args.action == "install":
            manager.launch_installer(update)
        return 0
    except UpdateError as error:
        print(f"Aggiornamento: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
