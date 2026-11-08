![LLocalMind — Local AI, on your PC.](docs/llocalmind-banner.png)

# LLocalMind

Local AI chat made in Italy 🇮🇹 for Windows PCs, with GGUF models,
image input and optional web research. Models are not included.

**Project goal:** make models larger than those normally recommended for a
PC’s available hardware practical to run locally. Quantization, selective MoE
expert activation and SSD-backed weight loading help reduce RAM pressure,
so the whole model does not have to stay in physical memory at once.

## Install and update

1. Download the installer from **[GitHub Releases](https://github.com/vin10122/LLocalMind/releases/latest)** and run it.
2. Open **Settings / Impostazioni**, select your GGUF and click **Install / update llama.cpp CPU runtime** if the runtime is not configured.
3. For text, leave **mmproj** empty; for images, select a compatible projector. Save.
4. Wait for **Ready / Pronto**, then send a message.

The installer includes Python and dependencies. Updates are available under
**Settings → Check for updates**, including public previews. You can also run
a newer installer over the existing installation: chats, settings and external
models are preserved. No uninstall or model download is needed.
Temporary GitHub API failures are retried; an official repository-hosted feed
is used if the API stays unavailable. Installer SHA-256 checks remain required.

For the portable edition, extract the **entire ZIP** and open
`LLocalMind\LLocalMind.exe`; keep its supporting files together. To update,
replace the application folder with the newly extracted version.

Requires **64-bit Windows 10/11**, a compatible model and enough free RAM.
The tested PC has an **Intel Core Ultra 5 226V, Arc 130V and 15.7 GiB RAM**.
Use AC power for best performance. **llama.cpp CPU is now the recommended
and default desktop engine**, for both text and images. The original Intel
native/OpenVINO engine remains an **experimental** choice in Settings.
Existing installations with llama-server already configured migrate once;
explicit experimental selections are kept. Legacy setups without an installed
runtime keep working until you install/select llama.cpp.

**AMD Ryzen:** CPU mode should also work on modern Ryzen processors supporting
AVX2, FMA and F16C. Intel GPU/NPU options belong to the experimental engine;
select CPU there on non-Intel systems. AMD-specific testing and benchmark data
are still insufficient to confirm broad compatibility or reliable speeds.

## Features

- **Text chat:** local inference with saved conversations, streaming, Copy,
  Regenerate, Stop and per-answer token counts/speed.
- **Images:** use the recommended llama.cpp engine and choose a compatible
  **mmproj** alongside your language GGUF, then attach an image. The encoder and language model run on CPU.
  Image history is kept with the chat. Matching filenames alone do not prove
  model/projector compatibility.
  In Vision mode choose **Fast / Rapida** for overviews or **Detailed /
  Dettagliata** for small text and documents. Fast limits transmitted image
  pixels without reloading the model; it can lose fine details. Originals and
  conversation history are preserved. Detailed remains the default.
- **English / Italian:** use the separate **Lingua / Language** button or the
  language selector in Settings. English mode guides new answers in English;
  existing messages keep their original text.
- **Italian Interface 🇮🇹:** a separate switch enables azure colours, a
  tricolour top bar and thick tricolour prompt borders. The large controls read
  **Dottore, parti 🍕** and **Fratello, fermati 🍝**. This saved appearance
  preference does not change language or inference.
- **Web research:** optional and off by default, available with either engine.
  When images are attached, only the question text goes to Tavily; images stay local.
  It sends only the current question to Tavily and uses up to three returned
  HTTPS sources; answers are generated locally. Set your personal API key as
  described below. **Settings → Web research** offers **Fast** (default: up
  to two 450-character excerpts) or **Full** (up to three 900-character excerpts).
  Fast reduces model input but can omit details; switch to Full when needed.
  Response timing details separate web lookup and model prefill. Search remains
  experimental: check sources and dates.

![Italian Interface preview](docs/llocalmind-italian-interface.png)

## Set up web search

1. Create an account at [Tavily](https://app.tavily.com/home), choose **Free**
   and generate your API key. Keep pay-as-you-go/automatic top-ups disabled.
   The documented Free allowance is **1,000 credits/month**; plan limits can change.
2. Run these commands in PowerShell to open the configuration file:

```powershell
New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\LLocalMind" | Out-Null
if (-not (Test-Path "$env:LOCALAPPDATA\LLocalMind\.env")) { New-Item -ItemType File "$env:LOCALAPPDATA\LLocalMind\.env" | Out-Null }
notepad "$env:LOCALAPPDATA\LLocalMind\.env"
```

3. Add this line, replacing the placeholder with your real key, then save:

```dotenv
TAVILY_API_KEY=tvly-YOUR-PERSONAL-KEY
```

The name must be **`.env`**, not `.env.txt`. Enable **Web research / Ricerca web**
and send a question. Changes to the key apply to the next search without a
model restart. This file stays outside the application and survives updates;
never share it or commit it to GitHub.

LLocalMind makes one **basic** request per search, with no automatic retries,
advanced searches or anonymous fallback. Quota/authentication failures stop the
request. **Billing is controlled by your Tavily account**: the app cannot verify
or disable a paid plan. Keep the account on Free to avoid charges.

## Performance and limits

Recent user-reported runs with Hermes 3.6 35B A3B on the PC above, on AC power,
show roughly **6–8 tok/s**, or **4–5 tok/s with a cold cache**. Warm-cache peaks
can be substantially higher. These observations are not guaranteed rates;
model, context, available RAM, temperature and execution engine affect results.

Generation tok/s exclude the wait for the first token. **Text prefill has been
negligible in recent local use; image prefill is still being measured for more
precise figures and can take much longer.** Large models and vision encoders
can put substantial pressure on a 16 GiB system.

This is a work in progress. Check important answers; component tests do not
guarantee general answer quality. Windows installers are currently unsigned.

## Your data

Settings and chats: `%LOCALAPPDATA%\LLocalMind\data`.
Logs and timing reports: `%LOCALAPPDATA%\LLocalMind\logs`.
Models remain at the paths you select. Back up the whole data directory to
preserve chats and their image attachments.

## From source

```powershell
git clone https://github.com/vin10122/LLocalMind.git
cd LLocalMind
py -3.14 -m pip install -r requirements-gui.txt
py -3.14 gui.py
```

Experimental native developer CLI: `py -3.14 chat.py default`; exit with `/exit`.
Use `--language en` for English response mode.
For native-kernel setup and builds, see [Development](docs/development.md).
All development tests, benchmarks and probes are in [test/](test/README.md).

## Inspiration

LLocalMind was inspired by **Flash-MoE**, as shown in
[this Instagram Reel](https://www.instagram.com/reel/DdqjqtAxAk6/).
It is an independent project, not affiliated with or endorsed by Apple.

## License

Code: [Apache 2.0](LICENSE). Models and external runtimes have their own licenses.
