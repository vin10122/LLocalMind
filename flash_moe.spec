# Legacy entry point: use the same supported spec as the Windows release build.
from pathlib import Path
_target = Path(SPECPATH) / 'packaging' / 'windows' / 'LLocalMind.spec'
SPECPATH = str(_target.parent)
exec(compile(_target.read_text(encoding='utf-8'), str(_target), 'exec'))
