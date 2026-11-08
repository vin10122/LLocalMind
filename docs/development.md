# Development

Use Python 3.14 x64. Run commands from the repository root.

## Source setup

```powershell
py -3.14 -m pip install -r requirements-gui.txt
py -3.14 gui.py
```

The experimental native CLI is `py -3.14 chat.py default`; `/exit` closes it. Use `--help` for model,
context and device options. Set `FLASH_MOE_GGUF` to a GGUF path if automatic
model discovery does not find your file. GUI model selection is independent.

The optional `install.ps1` / `quick_install.bat` source setup and `run_chat.bat`
CLI launcher remain available for Windows convenience.

For optimized CPU decode on Windows, install Visual Studio Build Tools with
the x64 C++ tools, then build both native libraries once:

```powershell
scripts\compile_dequant_k.bat
scripts\compile_native_expert.bat
```

Rebuild after changes to the C++ sources. A required native-mode launch fails
if the matching DLL is unavailable; automatic mode can fall back to OpenVINO.
For the Python BLAS thread policy, configure `FLASH_MOE_BLAS_THREADS` before
launch; the default is one thread. GPU/NPU support requires compatible drivers.

## Layout

- `src/llocalmind/`: desktop UI, settings, updater and application services.
- `src/flash_moe/`: optimized text inference and local vision transport.
- `cpp/`: native kernels; `scripts/`: build and setup entry points.
- `packaging/windows/`: PyInstaller/Inno Setup definitions and release contract.
- `tools/build_windows_installer.py`: installer builder.
- `test/`: regression scripts, benchmarks, model probes, references and prototype.

The application includes diagnostic commands used by its diagnostics EXE;
standalone development entry points live in `test/`.

## Tests and measurements

See [test/README.md](../test/README.md) for the model-free regression suite,
real-model diagnostics and timing commands. Model-dependent experiments are
not a blanket test-discovery target. Results depend on the actual hardware,
model, power mode, cache and thermal conditions.

See the [performance audit](../test/notes/performance-audit.md) for remaining bottlenecks and
measurement limits. The desktop defaults to llama.cpp CPU for text and optional images. The original
Intel/OpenVINO route remains experimental; its rates are not interchangeable.
A configured mmproj is optional for text-only inference. `vision` remains the
internal settings value for the recommended engine to preserve saved settings.
Web evidence is attached with the same untrusted-data/citation rules in both
transports; only question text is sent to the search provider.

## Windows builds

```powershell
py -3.14 -m pip install -r requirements-build.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build_desktop.ps1 -Installer
```

Build native DLLs first and install Inno Setup. Output is under `dist/`.
[Windows packaging](../packaging/windows/README.md) documents installer and
updater requirements. `.github/workflows/windows-release.yml` runs regression,
real-runtime and packaged/installed EXE checks on Windows. A matching version
tag publishes a preview; stable promotion uses `.github/stable-release.json`.
Changing only documentation or test locations does not require a new app version.

## Web search transport

The GUI uses Tavily's authenticated search API with the user's `.env` key:
POST `https://api.tavily.com/search`, `Authorization: Bearer KEY`, basic search,
at most three results, no remote generated answer. The known configuration
path is `data_root() / '.env'` (on Windows `%LOCALAPPDATA%\LLocalMind\.env`).
It is read for each request, supports UTF-8/BOM, quoted values, comments and an
optional `export` prefix. It does not execute expressions, search the working
directory, read a global `TAVILY_API_KEY`, or export the file into child engines.
Missing/malformed/duplicate keys fail locally before any API request.

The client does not retry quota failures, switch accounts, use anonymous access,
or request upgrades. It cannot enforce server-side billing: users must choose
Free and disable pay-as-you-go/top-ups in Tavily. Error messages do not contain
the key or echo remote error bodies. HTTPS redirects are refused so credentials
and query text are not forwarded to other endpoints.

Only validated public HTTPS source URLs and bounded excerpts are passed to the
local model as untrusted evidence. Source pages are not fetched directly on
this path. Explicit legacy DuckDuckGo parsing remains covered by regressions.
`test/test_web_search.py` checks file parsing, auth headers, quota/error handling,
no credential leakage, cancellation and source validation. Synthetic tests do
not prove live account/service availability. Real requests need provider access
and a user-owned key; never put real keys in CI fixtures, reports or chat.

## Update availability

Update checks retry temporary failures with bounded waits and 10-second metadata
request timeouts. If the GitHub releases API is unavailable or rate-limited, the
client reads the fixed official `.github/update-feed.json` through
`raw.githubusercontent.com`. The same version, repository URL, size and SHA-256
validation runs for both sources. Malformed metadata never triggers a download.
Both sources failing produces an error, never a false "no updates" result.

`.github/scripts/publish_update_feed.py` runs after complete release uploads and
stable promotion, excluding drafts/incomplete packages and preserving preview
selection. It writes the manifest with conditional file revisions and rebuilds
on write conflicts. Real fallback checks can simulate only the API failure and
read the allowed public feed; no installer is executed by an update check.
Cancellation interrupts retry backoff; in-flight requests finish or time out.
Transient installer/checksum connection failures retry, but corrupt or truncated
installer content is still rejected and the partial file is removed.

## Web latency and input budget

The Tavily path performs one basic API call and consumes returned excerpts;
it does not open source pages. Fast uses up to two excerpts of 450 characters;
Full keeps the prior three excerpts of 900 characters. Both keep URLs/titles,
use basic search with remote answer generation disabled, and make no automatic
retries. There is no new query cache or hidden reuse of live-event results.

Citation references undergo static HTTPS, credential, local-host and literal-IP
checks without DNS requests. They are not automatic connection targets. The
legacy page-fetch/redirect paths retain DNS resolution and public-address checks.

`web_seconds`, `web_sources` and `web_profile` are stored with response metrics
and the local request report, without queries or keys. First-token latency now
includes web lookup and input preparation; model prefill and decode speed keep
their own definitions. Older saved metrics are left unchanged. The Full/Fast
setting does not reload the inference engine. Actual latency gains and evidence
quality still need a target-PC comparison; smaller excerpts are not a measured
whole-model speedup.
