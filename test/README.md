# Tests, benchmarks and diagnostics

Run from the repository root after installing `requirements-gui.txt`.
The scripts in this directory include both model-free regressions and manual
experiments requiring a compatible GGUF. Do not run every file through blanket
test discovery: some legacy experiments execute model work when imported.

## Model-free regression suite

On Windows, build the native kernels, then run the same suite as CI:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File test\run_source_tests.ps1
```

It covers updater behavior, language, GUI, web transport, vision attachments,
runtime installation, optimized inference and memory/cache policy. Real-GGUF
quality and target-PC throughput are not established by these synthetic checks.
The `probe_vision_runtime.py` integration check downloads and verifies the pinned
runtime and requires Windows; it is run separately by CI.

Individual Python scripts can also be run directly:

```powershell
py -3.14 test\test_gui.py
py -3.14 test\test_optimized_inference.py
py -3.14 test\test_attention.py
```

The native checks in `test_optimized_inference.py` require the compiled DLL;
without it those checks skip. GUI checks can run offscreen. PowerShell runner
checks include Windows installer/launcher syntax.

## Real-model benchmarks

Set `FLASH_MOE_GGUF` to your local model and use a UTF-8 input file:

```powershell
py -3.14 test\bench_stability.py --prompt-file .\input.txt default --native-decode native --max-tokens 512 --max-seq 2048
py -3.14 test\profile_decode.py --help
```

For image timings, close the GUI first and use its saved model/runtime settings:

```powershell
py -3.14 test\bench_vision.py --image "C:\path\image.jpg"
```

Installed builds retain the equivalent `LLocalMind-Diagnostics.exe
--benchmark-vision --image PATH` command. The report is written to
`%LOCALAPPDATA%\LLocalMind\logs\vision-benchmark.json`. Repeated image requests
can benefit from prefix caching; compare startup, first-token latency, prefill
and generation separately, keeping power, context and image conditions fixed.

## Compare image modes on the target PC

Close the GUI and compare the same image in the same loaded engine:

```powershell
py -3.14 test\bench_vision.py --image "C:\path\image.jpg" --compare-image-profiles --runs 2 --show-answers --max-tokens 128
```

The diagnostics EXE accepts the same flags after `--benchmark-vision`.
Comparison mode alternates Detailed/Fast order and disables prompt-prefix reuse
for both profiles. It still shares OS caches and the loaded model: this is not
a cold-machine comparison. The report includes profile labels, first-token and
prefill medians, processed/cached prompt tokens when supplied by llama.cpp,
and memory snapshots. Console answers are opt-in; the JSON report contains no
answer text. Compare readability/accuracy as well as latency.

Fast bounds the transmitted image area to 262,144 pixels without cropping or
upscaling. It preserves small/low-area images and keeps the saved original.
Dynamic-resolution encoders can process fewer visual tokens; fixed-resolution
encoders may not get faster. The model's startup buffers and configured maximum
visual-token budget are unchanged. Changing profile can invalidate an existing
prompt prefix, so avoid treating an ordinary warm/cold chat pair as a fair A/B.

## Other files

- `test_*.py`: component regressions and model-dependent comparisons.
- `bench_*.py`, `profile_decode.py`: timing experiments.
- `probe_*.py`, `check_*.py`, `bisect_*.py`: targeted model diagnostics.
- `golden_reference.json`, `_kquant_ref.txt`: reference fixtures; keep them with
  their consuming scripts. `make_golden_reference.py` and `parse_eval_dump.py`
  prepare reference data; `derive_k_tables.py` regenerates native lookup tables.
- `run_*.py`, `flash-moe-prototype.ipynb`, `notes/`: historical experiments.

Use each script's instructions and model requirements before running it.
`smoke_windows.ps1` verifies a packaged EXE; installer creation remains in
`tools/build_windows_installer.py`.
