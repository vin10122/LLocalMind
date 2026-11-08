"""Windows CI: install the pinned real runtime and load its executable/DLLs."""
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from llocalmind.vision_runtime import RuntimeInstaller,PACKAGE

directory=Path(os.environ['RUNNER_TEMP'])/'LLocalMind-test-vision-runtime'
archive=os.environ.get('LLOCALMIND_TEST_RUNTIME_ARCHIVE')
# CI may download via curl for its retry/timeout diagnostics. The installer
# still verifies the pinned size, SHA-256, ZIP contents and real executable.
opener=(lambda request,timeout:Path(archive).open('rb')) if archive else None
try:
    executable=RuntimeInstaller(directory,opener=opener).install()
except Exception as error:
    # Surface the actual failure in the Actions summary, even when full job
    # logs require authentication. Keep the real runtime check mandatory.
    message=f'{type(error).__name__}: {error}'
    message=message.replace('%','%25').replace('\r','%0D').replace('\n','%0A')
    print(f'::error title=Vision runtime verification::{message}',flush=True)
    raise
print('Vision encoder device: CPU')
print(f'CPU vision runtime {PACKAGE.tag} verified and executable: {executable}')
if os.environ.get('GITHUB_ENV'):
    with open(os.environ['GITHUB_ENV'],'a',encoding='utf-8') as stream:
        stream.write(f'LLOCALMIND_TEST_RUNTIME_DIR={directory}\n')
