# Performance audit — v0.1.7 preview

Target: Windows, Intel Core Ultra 5 226V, Arc 130V, approximately 16 GiB shared
RAM, on AC power. The large Hermes GGUF and mmproj are not available in CI.
This audit identifies avoidable work; it does not establish a new whole-model
speed or guarantee interactive image latency.

## v0.1.9 stable: CPU-only vision runtime

The optional image-encoder GPU offload from the v0.1.8 preview is removed.
Vision now uses the pinned official b12110 Windows CPU runtime and explicitly
disables encoder offload, while language-model layers remain on CPU
(`--device none -ngl 0`). A target-PC screenshot had shown 305 s to first token
and 6.18 tok/s generation; these are distinct measurements, and neither
establishes image-encoder performance. No controlled target-PC comparison is
available, so this release makes no vision speed claim. Existing external
runtime files are preserved; users upgrading from the preview can use Settings
to install and select the CPU runtime.

## Measured CPU prefill profile

On the Core Ultra 5 226V / 16 GiB target, one local image request with the
35B GGUF and F16 mmproj reached its first token in 91.9 s (808 prompt tokens),
using eight generation/prompt threads, batch 2048, microbatch 1024, and the
768 visual-token limit. The earlier four-thread, batch-512/microbatch-256
request had reached 76 prompt tokens in 29 s before it was cancelled. This
suggests a substantial improvement, but is not a controlled comparison:
the earlier request was incomplete. A no-image text control processed 823
tokens in 39.5 s, showing that most of the measured image request time is
shared with the slow CPU language-model prefill; shrinking the input image
from 2048 to 1024 pixels did not measurably improve total latency.

The measured 8/2048/1024 profile is now the Vision default. A 2048-token
microbatch was not tested: only about 625 MiB of RAM remained free after model
startup, so that run was skipped to avoid excessive paging. Actual latency
depends on RAM pressure, thermal state, image/model and runtime. The 8-thread
setting is specific to the measured 8-core target; reduce it in Settings on
machines that become less responsive or perform worse.

The following table describes the earlier v0.1.7 CPU baseline.

## Main findings

| Path | Bottleneck | Change | Tradeoff / remaining limit |
| --- | --- | --- | --- |
| Vision inference | Full 35B model and F16 vision encoder on CPU, sharing a small RAM budget with Windows | Explicit visual budget: 768 maximum tokens per image, minimum 64; configurable in Settings | Fewer tokens can lose small text and fine details. Exact image encoding/token count depends on architecture. The CPU runtime still cannot use Arc. |
| Vision startup / prefill | Runtime defaults allow batch 2048, microbatch 512 and an 8192 MiB prompt-cache ceiling | Batch 512, microbatch 256, cache ceiling 128 MiB; one active slot; no idle-slot snapshots | The old cache ceiling was not an immediate 8 GiB allocation. Smaller batches may reduce throughput on machines with more RAM. Switching conversations may require recomputation. |
| Vision conversation | Repeated prefix evaluation and reading/encoding the same image again | Explicit prompt caching in slot 0; bounded 16 MiB image payload LRU with file-change checks | Prefix reuse depends on llama.cpp and the actual conversation; encoded-image reuse does not imply cached vision embeddings. |
| Image import | Full-resolution color conversion before resizing | JPEG draft decode and resize before RGB/RGBA copies | Existing 2048-pixel limit can discard fine detail; originals remain external. |
| Python startup | Importing the vision module also imported NumPy, GGUF and OpenVINO | Lazy package exports; defer native CLI dependencies until text mode is selected | Removes Python overhead; does not eliminate GGUF reads or encoder warm-up. |
| Model reload | Settings unused by the selected engine triggered a reload | Compare only options actually consumed by that engine | Model, context and relevant execution settings still require a reload. |
| Native text prefill | Shared experts for sequences over 128 tokens ran one token at a time | Batch shared experts in bounded chunks of 128 for sequences of at least 16 tokens | GEMM can introduce small floating-point differences. Routed experts and decode order remain unchanged. Full-model quality parity is not established. |
| Native text allocation | KV storage was allocated again for each request; F16 arrays copied unnecessarily | Reuse compatible KV storage, reset visible length, keep existing F16 storage | The KV allocation remains reserved while the model is loaded. Configuration changes still allocate new storage. |
| GUI streaming | Rebuilding the response widget on every text fragment | Immediate first fragment, then coalesce renders at 40 ms; always render the final result | Up to 40 ms display delay for intermediate fragments. |

Warm-up remains enabled by default. Disabling it can shorten the wait for
“Pronto” while moving work to the first request; it is an explicit advanced
option, not a free speedup.

## What still dominates

Loading a model larger than available physical RAM depends on storage, OS
file caching and working-set pressure. The image request also runs the actual
vision tower and multimodal prefill on CPU. These costs cannot be removed by
an animation, an import change or reporting decode tok/s alone. Target-PC
memory/correctness measurements remain necessary.

The native text route still spends time on routed expert reads, dequantization,
kernels, DeltaNet and attention. Cold GPU graph compilation remains. Earlier
local tests found that more expert workers, a larger raw cache, mmap and some
kernel micro-optimizations did not reliably improve whole-model throughput;
this release does not enable those changes indiscriminately. Summed worker
timings overlap and must not be treated as sequential wall time.

## Measurements available here

Linux development environment, not the target laptop:

- Vision module import: roughly 0.18 s to 0.027 s, with peak process RSS about
  50 MiB to 12 MiB. This measures the import, not the application/model startup.
- Synthetic shared-expert prefill (1155 tokens, hidden 2048, intermediate 512,
  one BLAS thread, median of three): 278 ms scalar versus 110 ms with chunks
  of 128, approximately 2.52x for that component. Maximum absolute difference
  was approximately 6.1e-9. This is not a chat tok/s measurement.
- Automated checks cover image bytes/cache invalidation, KV isolation after
  reset, numerical shared-expert equivalence, GUI streaming, process cleanup,
  cancellation and saved settings. Windows CI additionally builds the EXE,
  tests native kernels and probes the actual pinned llama.cpp runtime.

## Measure on the target PC

The app automatically saves the latest load/request timings under
`%LOCALAPPDATA%\LLocalMind\logs\performance-load.json` and
`performance-request.json`. They contain timings, counters and profile values,
not prompts, images or model paths. Server details remain in `vision.log`.
Memory counters include available RAM and process working set where supported.
Page faults include soft faults: their count alone does not prove SSD paging.

For a repeatable image test, close the GUI first, keep AC connected and run:

```powershell
& "$env:LOCALAPPDATA\Programs\LLocalMind\LLocalMind-Diagnostics.exe" --benchmark-vision --image "C:\path\image.jpg"
```

For the portable edition, run `LLocalMind-Diagnostics.exe` beside the app. From
source: `py -3.14 test\bench_vision.py --image "C:\path\image.jpg"`.
The tool uses saved model/runtime settings, changes no settings and downloads
nothing. It measures one startup and two identical requests. The second can
benefit from prefix/cache warm-up; it is not an independent cold comparison.
Output: `%LOCALAPPDATA%\LLocalMind\logs\vision-benchmark.json`.

Compare startup, first-token latency, prompt evaluation and generation
separately, using the same image, context, output limit, power and thermal
conditions. `--image-tokens 512` can test a smaller visual budget; inspect
answer detail as well as time. Exact Hermes/projector compatibility and real
image-answer quality still require validation on the laptop.
