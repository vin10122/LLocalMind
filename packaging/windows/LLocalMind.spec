# PyInstaller onedir app. Build on Windows with scripts/build_desktop.ps1.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

root = Path(SPECPATH).parents[1]
assets = root / "src/llocalmind/assets"
binaries = []
for name in ("moe_quant_dot.dll", "fast_dequant_k_parallel.dll"):
    source = root / "src/flash_moe" / name
    if not source.is_file():
        raise SystemExit(f"Missing {name}: run the native build commands in README first")
    binaries.append((str(source), "flash_moe"))
ov_data, ov_binaries, ov_hidden = collect_all("openvino")
notices = []
for distribution in ("PySide6-Essentials", "shiboken6", "numpy", "tokenizers", "gguf"):
    notices += copy_metadata(distribution)
analysis = Analysis(
    [str(root / "gui.py")],
    pathex=[str(root), str(root / "src")],
    binaries=binaries + ov_binaries,
    datas=[(str(assets), "llocalmind/assets"), (str(root / "LICENSE"), ".")] + ov_data + notices,
    hiddenimports=ov_hidden + collect_submodules("flash_moe")
                  + collect_submodules("llocalmind") + ["run_q4k_f16_openvino"],
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtPdf"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="LLocalMind", upx=False,
          console=False, icon=str(assets / "logo.png"))
app = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False,
              name="LLocalMind")
