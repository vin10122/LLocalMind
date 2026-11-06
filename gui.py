"""LLocalMind desktop entry point. --demo opens the design without a model."""
import multiprocessing
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
# Match CLI policy before any inference dependency can import NumPy.
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[key] = os.environ.get('FLASH_MOE_BLAS_THREADS', '1')


def main():
    if sys.stdout is None or sys.stderr is None:
        from llocalmind.app_paths import data_root
        folder = data_root() / 'logs'
        folder.mkdir(parents=True, exist_ok=True)
        stream = (folder / 'application.log').open('a', encoding='utf-8', buffering=1)
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream
    from llocalmind.app import main as run
    return run()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(main())
