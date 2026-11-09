![LLocalMind — Local AI, on your PC.](docs/llocalmind-banner.png)

# LLocalMind

Local AI chat made in Italy 🇮🇹 for Windows, with GGUF models, image input
and optional web research.

**Our goal:** run models larger than normally recommended for the PC’s hardware,
using quantization, selective MoE expert activation and SSD-backed weight loading
to reduce RAM pressure.

## Requirements

| Component | Absolute minimum | Minimum | Recommended |
| --- | --- | --- | --- |
| **RAM** | **8 GB** | **12 GB** | **32 GB or more** |
| OS | Windows 10/11, 64-bit | Windows 10/11, 64-bit | Windows 11, 64-bit |
| CPU | Compatible Intel/AMD x86-64 CPU | Compatible Intel/AMD x86-64 CPU | Recent CPU with good memory bandwidth |
| Storage | SSD with room for the app and model files | SSD | NVMe SSD with free space |
| Dedicated GPU | Not required | Not required | Not required for the default CPU engine |

**RAM figures are indicative targets, not guarantees for every model.** The
8 GB tier is an experimental lower limit for quantized MoE models with SSD-backed
loading, limited caching and a short context. **Hermes 35B has not yet been
validated on 8 or 12 GB**; the tested machine has 15.7 GiB RAM. Images and longer
contexts may need more memory. llama.cpp uses memory mapping and OS paging;
the experimental native engine manages its own expert cache.

## Install and update

1. Download and run the installer from **[GitHub Releases](https://github.com/vin10122/LLocalMind/releases/latest)**.
2. Open **Settings / Impostazioni** and select your compatible **GGUF**.
3. Click **Install / update llama.cpp CPU runtime** if the runtime is not configured.
4. Leave **mmproj** empty for text only, or select a compatible projector for images. Save and wait for **Ready / Pronto**.

The installer includes Python and application dependencies. **Models and mmproj
files are not included; the llama.cpp runtime is downloaded separately during
setup.** Once configured, ordinary chat and image processing run locally;
optional web research requires Internet access.

Update through **Settings → Check for updates**, which also includes public
previews. If the updater cannot connect, download the newer installer and run
it over the existing installation. **Chats, settings, models and `.env` are
preserved; no uninstall is needed.** The updater retries API errors, supports an official fallback feed and verifies
installer SHA-256 checksums.

For the portable edition, extract the **entire ZIP** and open
`LLocalMind\LLocalMind.exe`. To update, close the app and replace its application
folder with the newly extracted version; keep the supporting files together.

## Engines and hardware

Requires **64-bit Windows 10/11**, a compatible GGUF and enough free RAM and
storage. The tested PC has an **Intel Core Ultra 5 226V, Arc 130V and 15.7 GiB
RAM**. Use AC power for best performance.

**llama.cpp CPU is the recommended and default desktop engine** for text and
images. The Intel native/OpenVINO engine remains **experimental** in Settings.
Configured native setups migrate once when llama-server is available; explicit
experimental choices are preserved.

**AMD Ryzen:** CPU mode should also work on modern Ryzen processors supporting
AVX2, FMA and F16C, but AMD-specific testing and performance data are still
insufficient. Intel GPU/NPU options apply only to the experimental engine;
select CPU there on non-Intel systems.

## Features

- **Chat:** saved conversations, streaming, Copy, Regenerate, Stop and per-answer
  token counts and generation speed.
- **Images:** attach an image after selecting a compatible **mmproj** with your
  language GGUF. Matching filenames alone do not establish compatibility.
  The encoder and model run on CPU. **Detailed / Dettagliata** keeps detail;
  **Fast / Rapida** reduces pixels and may lose small text. Saved copies remain
  unchanged.
- **Web research:** optional, off by default and available with either engine.
  One Tavily basic request sends the current question; image attachments stay
  local and the answer is generated on the PC. **Settings → Web research** offers
  **Fast** (default: up to two 450-character excerpts) or **Full** (up to three
  900-character excerpts). Fast can omit details. The app uses returned excerpts
  without downloading each source page. Timing details separate web lookup and
  model prefill. **Search remains experimental: check sources and dates.**
- **English / Italian:** use **Lingua / Language** or Settings. English mode
  guides new answers in English; saved messages are unchanged.
- **Dark mode:** **Settings → Appearance → Dark mode · black and green** enables
  a `#000000` background and dark-green sidebar. The saved choice applies
  without reloading the model.
- **Italian Interface 🇮🇹:** the sidebar switch enables tricolour accents and
  large **Dottore, parti 🍕 / Fratello, fermati 🍝** controls. It changes appearance,
  not language or inference, and can be combined with dark mode.

![Italian Interface preview](docs/llocalmind-italian-interface.png)

## Set up Tavily web search

Create an account at [Tavily](https://app.tavily.com/home), select **Free** and
generate your personal API key. The documented allowance is **1,000 credits per
month**; provider limits can change. Keep pay-as-you-go and automatic top-ups
disabled. Billing belongs to Tavily: LLocalMind cannot verify or disable a paid
account plan.

Run these commands in **PowerShell** to create and open the configuration file:

```powershell
New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\LLocalMind" | Out-Null
if (-not (Test-Path "$env:LOCALAPPDATA\LLocalMind\.env")) { New-Item -ItemType File "$env:LOCALAPPDATA\LLocalMind\.env" | Out-Null }
notepad "$env:LOCALAPPDATA\LLocalMind\.env"
```

In **Notepad**, add this line, replacing everything after `=` with your complete
key, then save:

```dotenv
TAVILY_API_KEY=tvly-YOUR-PERSONAL-KEY
```

The filename must be **`.env`**, not `.env.txt`. Enable **Web research / Ricerca
web** and send a question, or use **Regenerate** after a configuration error.
The key is read on each search, so no model restart is needed. Never share the
file or commit it to GitHub. Authentication/quota errors stop the request;
there are no automatic search retries or anonymous/advanced fallbacks.

## Performance and limits

User-reported llama.cpp runs with **Hermes 3.6 35B A3B** on the PC above, on AC
power, show roughly **6–8 tok/s**, or **4–5 tok/s with a cold cache**. Warm-cache
peaks can be substantially higher. These are observations, not guaranteed rates
or a controlled comparison between engines.

Generation tok/s exclude the wait for the first token. Recent short text
requests have shown little prefill delay; long contexts can take longer.
**Image prefill is still being measured and can involve substantial waiting.**
Large models and encoders put pressure on 16 GiB systems. Lower image/excerpt
quality reduces input work; actual speed gains need target-PC measurement.

This is a work in progress. Check important answers; component tests do not
guarantee general answer quality. Windows installers are currently unsigned.

## Your data

- Settings, chats and saved image copies: `%LOCALAPPDATA%\LLocalMind\data`.
- Logs and timing reports: `%LOCALAPPDATA%\LLocalMind\logs`.
- Tavily key: `%LOCALAPPDATA%\LLocalMind\.env`.

Models remain at the paths you select. Back up the data directory to preserve
conversations and attachments; keep any backup of `.env` private.

## From source

```powershell
git clone https://github.com/vin10122/LLocalMind.git
cd LLocalMind
py -3.14 -m pip install -r requirements-gui.txt
py -3.14 gui.py
```

Configure the runtime/model in Settings. Experimental native CLI:
`py -3.14 chat.py default` (`/exit` to quit, `--language en` for English).
See [Development](docs/development.md) for builds and packaging, and
[test/](test/README.md) for tests and diagnostics.

## Future direction

We are exploring structured responses such as cards, tables and interactive
charts. A general model-driven UI is a future idea, not a released feature.

## Inspiration

LLocalMind was inspired by **Flash-MoE**, as shown in
[this Instagram Reel](https://www.instagram.com/reel/DdqjqtAxAk6/).
It is an independent project, not affiliated with or endorsed by Apple.

## License

Code: [Apache 2.0](LICENSE). Models and external runtimes have their own licenses.
