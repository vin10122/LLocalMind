"""Windows CI: install the pinned real runtime and load its executable/DLLs."""
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from llocalmind.vision_runtime import RuntimeInstaller,PACKAGE

directory=Path(os.environ['RUNNER_TEMP'])/'LLocalMind-test-vision-runtime'
executable=RuntimeInstaller(directory).install()
print('Vision encoder device: CPU')
print(f'CPU vision runtime {PACKAGE.tag} verified and executable: {executable}')
if os.environ.get('GITHUB_ENV'):
    with open(os.environ['GITHUB_ENV'],'a',encoding='utf-8') as stream:
        stream.write(f'LLOCALMIND_TEST_RUNTIME_DIR={directory}\n')
