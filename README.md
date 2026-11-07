![LLocalMind — Local AI, on your PC.](docs/llocalmind-banner.png)

# LLocalMind

**An experimental project for running MoE language models locally on Intel
hardware with OpenVINO.**

This project explores splitting inference work between the CPU and integrated
graphics, while loading only some of the model weights from disk at a time.
The goal is to explore what may be possible on a regular PC without a
high-memory discrete graphics card.

> **Status: work in progress.** The program has generated answers to real
> prompts, but speed, answer quality, and stability still need more testing.
> Expect long wait times, changes, and possible issues.

**[Install](#install-on-windows) · [Update](#update-llocalmind) · [Desktop app](#llocalmind-desktop-app) · [Results](#status-and-results)**

## Install on Windows

The latest Windows preview is available in [release v0.1.1](https://github.com/vin10122/Intel-optimized-MoE-streaming/releases/tag/v0.1.1):

### Recommended: Windows installer

1. Download **[LLocalMind-Setup-0.1.1-windows-x64.exe](https://github.com/vin10122/Intel-optimized-MoE-streaming/releases/download/v0.1.1/LLocalMind-Setup-0.1.1-windows-x64.exe)**.
2. Run the installer, then open **LLocalMind** from the Start menu.
3. Open **Impostazioni → Sfoglia**, select your compatible local **GGUF** file,
   and save. Wait for the model status to become **Pronto**, then send a message.

**No Python installation, Visual Studio or DLL compilation is needed.** The
installer includes the application runtime, OpenVINO, fonts and native kernels.
The application is installed for your Windows user. Keep the GGUF in a separate
model folder or on another drive; the app remembers the path you selected.

Use 64-bit Windows 10/11 and current Intel drivers for the GPU/NPU. The default
configuration uses CPU experts and GPU projections. If the GPU is unavailable,
select CPU for DeltaNet and Full attention under advanced settings.

### Portable version

1. Download **[LLocalMind-0.1.1-windows-x64-portable.zip](https://github.com/vin10122/Intel-optimized-MoE-streaming/releases/download/v0.1.1/LLocalMind-0.1.1-windows-x64-portable.zip)**.
2. Extract the **whole ZIP**, then open `LLocalMind\LLocalMind.exe`.
3. Select the GGUF in settings as described above.

Keep the `_internal` directory and the other bundled files beside the EXE;
copying only `LLocalMind.exe` will not work. The portable version also includes
Python and the libraries, so it requires no Python setup.

GGUF model files are **not included**. This preview passed GUI, CPU OpenVINO,
native-kernel and installer startup checks on Windows; full-model quality,
Intel GPU/NPU support and performance still need testing on the target PC.
SHA-256 sidecars are attached to the release; the preview is not code-signed.

## Update LLocalMind

### Installed app: update without uninstalling

For a newer **stable release**, open **Impostazioni → Controlla aggiornamenti**,
choose the download, then confirm installation. LLocalMind verifies the
installer's SHA-256, saves the conversation, closes the model and exits. The
installer updates the same application and reopens it when complete.

**v0.1.1 is a preview.** The in-app checker offers stable releases only; it
does not offer newer previews. To install another preview, or to update
manually, download the new setup EXE from [Releases](https://github.com/vin10122/Intel-optimized-MoE-streaming/releases),
close LLocalMind and run it over the existing installation. **Do not uninstall
first.** Settings, conversations and external GGUFs are preserved; the model
does not need to be downloaded again.

### Portable app: replace the application folder

Close LLocalMind, download the newer portable ZIP and extract it into a **new
folder**. Open the new `LLocalMind.exe`. Settings and conversations are stored
outside the portable folder and will be reused by the same Windows user.
Keep the previous folder until you have checked that the new version works.

The in-app updater downloads an **installer**, not a portable ZIP. To remain
portable, use the ZIP procedure above; accepting the in-app installer creates
the normal installed application instead of updating the portable folder.

### Source checkout: update through Git

From PowerShell in the repository folder:

```powershell
git pull --ff-only origin master
py -3.14 -m pip install -r requirements-gui.txt
```

If the update changes native C++ code, close the app and rebuild the kernels
before launching it:

```powershell
.\scripts\compile_dequant_k.bat
.\scripts\compile_native_expert.bat
```

Then launch the GUI:

```powershell
py -3.14 gui.py
```

Rebuilding is not necessary merely because you reopened PowerShell. The
GUI updater does not update a Git checkout. For a CLI-only checkout, use
`requirements.txt` and launch `py -3.14 chat.py default` instead.

### Where your files are stored

| Files | Location |
|---|---|
| Installed program | `%LOCALAPPDATA%\Programs\LLocalMind` |
| Settings and conversations | `%LOCALAPPDATA%\LLocalMind\data` |
| Downloaded updates | `%LOCALAPPDATA%\LLocalMind\updates` |
| Packaged-app logs | `%LOCALAPPDATA%\LLocalMind\logs` |
| GGUF models | The external path you choose in settings |

Application updates replace program files separately from user data and models.

## Inspiration

This project was inspired by Apple's **Flash-MoE** app, as seen in
[this Instagram Reel](https://www.instagram.com/reel/DdqjqtAxAk6/). It is an
independent software project and is not affiliated with, endorsed by, or
sponsored by Apple.

## At a glance

- Reads models in GGUF format and lets you chat through the desktop GUI or PowerShell.
- Uses OpenVINO to run calculations on the CPU or a supported Intel device.
- The model uses a **Mixture of Experts (MoE)** architecture: for each step,
  it activates only some groups of model weights, called *experts*, rather
  than all of them.
- The command-line interface reports prompt processing time and generation
  speed separately.

## Status and results

The first model tested was **Hermes 3.6 35B A3B**, a Qwen3.6-MoE-based model
in GGUF format. The model file is not included in this repository; you need
to obtain it separately.

The current configuration combines **native quantized CPU decode with four
expert workers**, OpenVINO expert prefill with four CPU threads, batched
DeltaNet projections on the GPU, a sliding eight-expert prefetch window,
router weights promoted to FP32 once per layer, and native FP32 DeltaNet
recurrence during decode. The recurrence and its
state remain sequential FP32 operations. Raw expert cache: **320**; converted
weight cache: **1**. Native batched expert prefill was tested and excluded
because the complete prompt ran slower.

Manual runs used an **Intel Core Ultra 5 226V, integrated Arc 130V graphics,
15.7 GiB usable RAM, and Python 3.14 on Windows**:

| Power / request | Prompt tokens | Prefill | Generated tokens | Generation time | Generation speed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Battery, first request | 88 | 57.0 s | 95 | 101.7 s | 0.934 tok/s |
| AC adapter, first request | 88 | 43.1 s | 95 | 82.8 s | 1.148 tok/s |
| AC adapter, repeated request in the same process | 88 | 22.8 s | 95 | 55.8 s | 1.702 tok/s |
| AC adapter, different question in the same process | 81 | 22.7 s | 94 | 56.1 s | 1.677 tok/s |

**Connecting the AC adapter improved the observed performance.** Comparing
the two first requests, prefill fell by about 24% and generation speed rose
by about 23%. These are observations from manual runs, not a controlled
power benchmark. Compilation, OS file cache, power settings, temperature,
and prompt routing also affect the results. The faster repeated request
benefits from warm-up as well; do not attribute its entire gain to AC power.
For comparisons, keep the power source and performance mode consistent and
report first-request and warmed-request timings separately.

The earlier measurements above came from the first temporary native-decode
configuration; the newer Q3_K/DeltaNet results are recorded below. Full-model measurements of this final
integration still need to be repeated on the target Windows PC. A native
decode comparison matched 16 greedy token IDs; four forced-input logits
checks had maximum relative error below 0.0006. The same 95-token answer
was observed with the optimized DeltaNet prefill. This is a numerical smoke
check, not proof of general answer-quality parity. The first generated token
comes from prefill logits: a one-token run does **not** measure decode speed.

### Q3_K and DeltaNet update: all new measurements on AC power

The latest tests below were **all run with the AC adapter connected**, on
that same Intel PC, using four expert workers, raw cache 320 and converted
cache 1. They used temporary launchers with the kernels now integrated here:

| Run | Input tokens | Prefill | Generated tokens | Generation time | CLI rate | Decode-step rate, approximately |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| First request with checks | 101 | 32.4 s | 64 | 31.9 s | 2.004 tok/s | 1.97 tok/s |
| Second request, same session | 98 | 26.6 s | 64 | 31.8 s | 2.010 tok/s | 1.98 tok/s |
| Longer generation, new session | 117 | 32.2 s | 351 | 186.9 s | 1.878 tok/s | 1.87 tok/s |

The approximate decode-step rate uses `(generated_tokens - 1) / generation_time`,
because the first token comes from prefill. The timer also includes sampling
and, on the first request, temporary numerical checks/microbenchmarks. These
are manual observations with varying cache and thermal conditions; **stable
2+ tok/s has not been established**. The long test used a 512-token output
limit and stopped at EOS after 351 tokens. Its input contained 117 tokens,
so this measures sustained generation rather than long-context performance.

The Q3_K kernel extracts signed values before widening to AVX2 32-bit lanes
and uses constant shifts, retaining the original FMA accumulation order and
FP16 rounding. All tested Q3 expert samples from layers 5–34 matched the old
native kernel bit for bit. A same-expert Windows microbenchmark measured
1.502 to 0.750 ms (2.00x); another measured 1.390 to 0.607 ms (2.29x).
These single-expert ratios are **not** whole-model speedups.

The DeltaNet kernel processes all value heads in one native call, leaving
convolution, normalization, projection devices and token recurrence order
unchanged. Target-PC checks compared local outputs, recurrent state and
convolution state with the previous path, with observed maximum relative
errors below 5e-7. This does not prove general answer-quality parity.
The native recurrence is enabled only after prefill; OpenVINO/NumPy prefill
is retained. `--native-decode openvino` also retains the NumPy recurrence.

A larger raw cache of 640 was rejected: in one 32-token diagnostic run,
generation increased from 18.1 to 24.0 seconds. Cache misses, logical read
bytes and physical storage traffic are different quantities; zero demand
misses does not imply no prefetch waits or memory pressure.

### Long-context update (AC power)

The current CLI also uses **FP32 grouped matrix attention without replicated
KV heads**, preallocated FP16 KV buffers, and **one BLAS thread**. Expert
workers remain **4**, raw cache **320**, converted cache **1**. All tests in
this section used the AC adapter. The last baseline run additionally
confirmed Windows' AC performance mode and AcerSense Performance mode;
earlier runs did not consistently record both settings.

| Execution policy | Input tokens | Generated tokens | Prefill | Generation time | Effective decode rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Previous published attention | 1155 | 413 | 207.6 s | 374.8 s | 1.100 tok/s |
| GQA without replicated KV, einsum | 1155 | 413 | 179.4 s | 259.3 s | 1.589 tok/s |
| FP32 grouped matmul + preallocated KV + BLAS=1 | 1155 | 425 | 153.2 s | 236.3 s | 1.795 tok/s |

The effective decode rate excludes the first token from prefill. These are
separate manual runs, not a controlled isolated attribution of each gain.
For the long FP32/KV run, full 64-step windows ranged from **1.680 to 1.912
tok/s**, median step time was **539.3 ms** and p95 was **640.8 ms**. Shorter
128-step trials ranged around **1.82–1.94 tok/s** overall, sometimes exceeding
2 tok/s in a single window. **2+ tok/s sustained on long inputs remains a
goal, not a demonstrated result.** FP32 attention changes rounding; synthetic
comparisons with the replicated reference passed, but general answer-quality
parity is not established.

The CLI sets `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, and
`BLIS_NUM_THREADS` before loading NumPy, using **1** by default. This affects
the process only and leaves OpenVINO's explicit thread settings separate.
To experiment, set `FLASH_MOE_BLAS_THREADS` before launching the CLI.
When importing the model directly, configure BLAS before importing NumPy.
Unrestricted BLAS threading severely slowed one grouped-matmul trial.
KV storage is allocated for `--max-seq` up front: at 2048 positions, ten
layers with 2 KV heads and head dimension 256 reserve about **40 MiB** in
total. Very large maximum contexts therefore increase reserved storage.

Rejected experiments include six expert workers, overlapping shared-expert
execution, persistent GGUF handles, and mmap for the measured read workload.
A SIMD Q3 scale variant remained experimental: a 62-pair decode A/B test
showed **1.027x mean forward throughput**, zero compared-output error, and
only **31/62 candidate wins**. It is not enabled in this update.

#### Run a complete multiline input and check stability

Save a UTF-8 input file, then run the normal chat:

```powershell
py -3.14 chat.py default --prompt-file .\input.txt --max-tokens 512 --max-seq 2048 --native-decode native
```

For timing windows, use the included benchmark, with the same input file:

```powershell
py -3.14 tools\bench_stability.py --prompt-file .\input.txt default --native-decode native --max-tokens 512 --max-seq 2048
```

The benchmark reports 64-step windows, median and p95 decode latency,
excluding the first token. A partial final window is identified separately.
The output limit does not force generation to continue past EOS. The input
plus output budget must fit `--max-seq`; the CLI checks this before prefill.
A final benchmark of this source integration should still be repeated on the
Windows target; the measurements above used temporary equivalent variants.

Automated tests check individual components such as attention,
dequantization, and the DeltaNet path. They are not a full validation of
answer quality or reliability across different PCs.

### Short-prompt Q6 update (AC power)

The integrated native kernel now computes Q6_K dot products directly with
AVX2, retaining FP16 weight/graph rounding and the existing accumulation
order. Shared experts run as FP32 matrix batches for **16–128 prompt tokens**,
including the chat template. Longer inputs and single-token shared-expert
decode retain their previous paths. The normal four-worker expert prefetch
is retained.

Manual Windows measurements on the same Intel Core Ultra 5 226V / Arc 130V
PC, **with the AC adapter connected**, used repeated requests in the same
process. Each row below generated the same 89-token response from a
94-token input:

| Variant / repeated run | Prefill | Generation | CLI rate | Approx. effective decode rate |
|---|---:|---:|---:|---:|
| Batched shared prefill, previous native kernel | 19.1 s | 38.0 s | 2.344 tok/s | 2.32 tok/s |
| Batched shared prefill + fused Q6, run 1 | 19.0 s | 35.4 s | 2.513 tok/s | 2.49 tok/s |
| Batched shared prefill + fused Q6, run 2 | 18.8 s | 35.0 s | 2.545 tok/s | 2.51 tok/s |
| Batched shared prefill + fused Q6, later run | 20.2 s | 37.6 s | 2.368 tok/s | 2.34 tok/s |

Effective rates use 88 decode steps, excluding the first token supplied by
prefill; generation timing also includes sampling. These are separate manual
runs, not a controlled paired benchmark. Warm-up, file cache and PC conditions
affect results: **3 tok/s and these rates on long prompts are not established**.
The shared batch affects prefill only; it does not directly accelerate decode.

All nine Q6-layer checks matched the previous native expert output bit for
bit for the checked real-expert inputs. Shared-expert batch checks across
40 layers had relative error below `1e-6`; batching can change rounding and
does not establish general answer-quality parity. Synthetic native checks and
integration tests also pass; final source integration should be checked again
on the target Windows PC.

The Q4+Q6 and direct-read-without-prefetch experiments are **not enabled**:
their measured whole-chat runs did not improve the selected Q6 configuration.
No temporary Python launchers are needed after updating. Close running chats,
update and rebuild the native decode DLL once:

```powershell
git pull --ff-only origin master
scripts\compile_native_expert.bat
py -3.14 chat.py default --native-decode native --expert-workers 4 --max-tokens 128
```

## LLocalMind desktop app

The **LLocalMind** Qt desktop interface follows the approved rounded blue
design, with the LL/M logo and bundled Sora/Manrope fonts. It includes saved
conversations, multi-turn context, streaming answers, Copy, Regenerate, Stop,
local text-file attachment and model/settings selection. User data is stored
outside the program directory. The existing PowerShell chat remains available.

![LLocalMind desktop preview](docs/llocalmind-desktop.png)

To run the GUI **from source**, install its dependencies once, then open it
(installer and portable users can skip this step):

```powershell
py -3.14 -m pip install -r requirements-gui.txt
py -3.14 gui.py
```

Select a GGUF in **Impostazioni → Sfoglia**. The app remembers the selection
and loads it on subsequent starts. The measured CPU expert / GPU projection
defaults are preselected; advanced settings expose cache, worker, context and
output limits. Stop is cooperative: during a long prefill, cancellation or
closing the window waits for the next token boundary before releasing the
model. Increasing conversation history also increases prompt processing work.

To view the design without importing the inference runtime or reading a GGUF:

```powershell
py -3.14 gui.py --demo
```

The preview uses temporary conversations and labels its status as an
**anteprima**; it reports no fabricated live performance. Normal sessions
display measured effective decode speed and time to the first token.

Each generated answer also shows **tok/s and token count below that answer**.
These measurements are saved with the conversation and restored when it is
reopened. The rate excludes prompt processing and the first token's sampling;
a one-token answer is marked as unmeasurable. Older answers with no recorded
measurements do not receive estimated numbers. Regenerating an answer replaces
its measurements; interrupted answers retain their available measured stats.

### Windows EXE builds (developers)

GitHub Actions builds Windows downloads on pushes to `master` and matching
`vMAJOR.MINOR.PATCH` tags. Each build compiles the kernels, runs source tests,
then smoke-tests both the portable EXE and an installed copy without a GGUF.
The run's `LLocalMind-Windows-x64` artifact contains an installer, portable
ZIP and SHA-256 sidecars. Tagged builds also publish a **preview release**
after all checks pass. Preview releases are not offered by the stable updater;
maintainers can promote one after manual target-PC validation.

The build definition bundles Python, OpenVINO, the native kernels, icons and
fonts into a portable application folder. GGUFs stay external. On Windows:

```powershell
py -3.14 -m pip install -r requirements-build.txt
.\scripts\compile_dequant_k.bat
.\scripts\compile_native_expert.bat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_desktop.ps1
```

The executable is `dist\LLocalMind\LLocalMind.exe`; distribute the **whole
LLocalMind folder**, not just the EXE. With Inno Setup 6.3+ installed, add
`-Installer` to the build script to also create the per-user setup EXE and
its checksum. GitHub Actions verifies both packaged and installed startup on
Windows, including a CPU OpenVINO graph and native kernels. Full-GGUF GUI
performance and Intel GPU/NPU driver behavior still need validation on the
target PC. The Windows EXE is built on a Windows runner, not cross-compiled
by the Linux tests.

**Impostazioni → Controlla aggiornamenti** checks stable GitHub releases,
downloads with SHA-256 verification and, in the frozen Windows app, offers
installation after saving chats and closing inference resources. Program files
are replaced independently of conversations and external models. Source mode
can download the installer but does not install over a Git checkout.

From a source checkout, `py -3.14 update.py check` checks for a newer stable
application release without loading the model. This does not replace `git pull`
for source updates. See [Windows packaging and updates](packaging/windows/README.md)
for release assets, checksum verification and installer details.

## Source requirements

The following requirements are for running or building from a source checkout.
The installer and portable downloads already include Python and the libraries.

- 64-bit Windows 10 or 11.
- Python 3.14 and the packages listed in `requirements.txt` for the CLI,
  `requirements-gui.txt` for the desktop GUI, or `requirements-build.txt`
  for packaging. Windows release builds use Python 3.14 x64 and bundle it.
- A compatible GGUF model file. The model used in testing is described
  below.
- Up-to-date Intel drivers if you want to use integrated graphics.

From PowerShell, in the project directory, install the dependencies with:

```powershell
py -3.14 -m pip install -r requirements.txt
```

If the `py` command is not available, use `python` instead.

## Set up the model

For the desktop GUI, select the GGUF in settings. The following discovery and
environment-variable instructions apply to the command-line client.

If the GGUF file is in the project directory, the program will try to find it
automatically. Otherwise, set its path before starting the chat:

```powershell
$env:FLASH_MOE_GGUF = "D:\models\model.gguf"
```

This project **does not distribute the model**. Obtain it from an authorized
source and check the terms provided by its author. The model's license and
the code's license are separate.

### Source and attribution for the tested model

The closest public match to the filename used in testing is
[`LuffyTheFox/Qwen3.6-35B-A3B-Uncensored-Genesis-Hermes-GGUF`](https://huggingface.co/LuffyTheFox/Qwen3.6-35B-A3B-Uncensored-Genesis-Hermes-GGUF).
Its model card describes it as based on
[`HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive`](https://huggingface.co/HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive),
with a Hermes contribution attributed to
[`DJLougen`](https://huggingface.co/DJLougen/hermes-qwen3.5-35b-a3b-GGUF).
The LuffyTheFox and HauhauCS model cards declare Apache-2.0 for their
respective repositories.

The file used in testing is named
`Hermes3.6-35B-A3B-Uncensored-Genesis-Final-APEX-Compact.gguf`, while the
corresponding variant listed in the LuffyTheFox repository omits `Final`
from its name. The match is likely, but this alone does not confirm that
both files are the same revision or contain the same weights. The model is
excluded from this project repository; before using or redistributing it,
verify the source and terms for the exact file you obtained.

## Start a chat

```powershell
py -3.14 chat.py default
```

Enter a prompt after the `>` symbol. To exit, type `/exit` or press
`Ctrl+C`.

The preset runs the main model on the CPU and uses the Intel GPU for DeltaNet
projections and full attention. If the GPU or its driver is unavailable, use
`--ssm-device CPU --attention-device CPU` instead, including after `default`.

The `default` preset selects CPU for the main device, GPU for DeltaNet and
full-attention projections, cache sizes of 320 and 1, deterministic
sampling, and a 128-token maximum. It uses native expert decode automatically
when the CPU and compiled DLL support it; otherwise it reports an OpenVINO
fallback. Explicit command-line flags override the preset. Append a prompt after `default` for a
one-shot run.

The assistant is instructed to keep its answers concise. `--max-tokens` is
a **maximum limit**, not a required answer length: generation stops earlier
if the model emits its end-of-response token. If it reaches the limit, the
answer may be incomplete; in that case, raise the limit further.

After each answer, the program reports generated tokens per second, prompt
processing time, and some cache statistics. Initial model loading may take
a long time. Logical read bytes and cache counters in the footer are
cumulative for the process; they do not measure physical SSD traffic. Each
question currently starts a fresh model context, retaining reusable caches.

### Useful options

- `--device CPU`, `GPU`, or `NPU`: selects the main OpenVINO device.
  Availability depends on your hardware and drivers.
- `--max-tokens 512`: sets the maximum number of tokens to generate per
  answer.
- `--cache 320`: limits how many quantized expert weight groups to keep in
  memory.
- `--weight-cache 1`: limits how many converted expert weight groups to
  keep in memory. The recommended value is 1 for the measured native-decode
  configuration; larger values can consume substantial RAM.
- `--temp 0`: uses deterministic token selection; higher values introduce
  more variation.
- `--max-seq 512`: sets the maximum supported context length. For a larger
  context, for example use `--max-seq 2048 --max-tokens 512`. This increases
  context capacity; it does not force the model to generate 512 tokens.

## Build the native decode kernel

Install Visual Studio Build Tools with the x64 C++ tools, then run from
PowerShell in the project root:

```powershell
scripts\compile_dequant_k.bat
scripts\compile_native_expert.bat
py -3.14 chat.py default --native-decode native
```

After updating the C++ sources, close running chats and rebuild with
`scripts\compile_native_expert.bat`; a DLL built before this update does not
contain the latest fused Q6_K code (and older builds may lack the Q3_K
optimization or DeltaNet entry point). Recompilation is not
needed merely because you reopened PowerShell. Startup reports whether the
native DeltaNet entry point is present; older DLLs retain NumPy recurrence.

The first DLL accelerates weight conversion during prefill. The second
(`src/flash_moe/moe_quant_dot.dll`) reads quantized expert weights directly
during single-token decode, avoiding full FP16 expert materialization. It
requires AVX2, FMA and F16C and supports Q8_0, Q3_K, Q4_K, Q5_K and Q6_K.
The same native DLL also contains the FP32 DeltaNet recurrence kernel.
The build does not replace the weight-conversion DLL. Binaries and model
files are excluded from Git; each Windows installation builds its own DLLs.

`--native-decode native` requires the kernel and reports an error if it
cannot be used. The default `auto` falls back to OpenVINO if unavailable;
`--native-decode openvino` explicitly selects the reference expert path.
The prefill uses OpenVINO in all three modes. `--expert-workers 4` and
`--prefill-threads 4` expose the measured thread settings for other PCs.

## Optional C++ weight-conversion acceleration

On Windows, you can compile the C++ module used to convert some weight
formats:

```powershell
scripts\compile_dequant_k.bat
```

This requires Visual Studio Build Tools with the x64 C++ compiler. The
generated file is not included in the repository. If the DLL is unavailable,
the program uses a Python-based fallback, which may be slower but does not
require the DLL.

## Run some checks

Tests are Python scripts. For example, run these from the project root:

```powershell
py -3.14 tools\test_long_context.py
py -3.14 tools\test_optimized_inference.py
py -3.14 tools\test_attention.py
py -3.14 tools\test_gated_deltanet_real.py
```

Some tests require the configured GGUF model and may take a long time. The
second test uses the configured model; set it up as described above first.
These checks cover individual components and do not replace a full chat
test.

Scripts that compare results with `llama.cpp` dumps look for
`lcpp_eval.txt` in the project directory by default. To use a dump elsewhere,
set `FLASH_MOE_LCPP_EVAL` to its path before running the script.

## Current limitations

- Testing has mainly been done on one Intel PC; performance and compatibility
  may differ on other hardware.
- Generation is slow compared with online services and systems with a
  discrete GPU.
- Performance depends heavily on model-file access and available memory.
- The concise-answer instruction can help limit answer length, but the
  model's behavior varies; the token limit can still cut off a long answer.
- This is not yet ready for production use.

## Code license

The code in this repository is distributed under the
[Apache-2.0 license](./LICENSE). This license applies to the project code,
not to external model weights or data.
