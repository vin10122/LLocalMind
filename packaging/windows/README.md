# LLocalMind installer and update contract

The Qt GUI is implemented in `src/llocalmind/app.py`, with a PyInstaller
definition and a per-user Inno Setup installer. The complete frozen-app update
flow must be validated on Windows before shipping a release. Linux/offscreen
tests do not produce or validate a Windows EXE. No release is published by
the local build tools. The GitHub Actions tagged-build workflow can publish
a preview release after its Windows checks succeed.

## Automated Windows build

`.github/workflows/windows-release.yml` uses a Windows 2022 runner and Python
3.14 x64. It builds both native DLLs and the PyInstaller folder, tests the EXE
with `tools/smoke_windows.ps1`, builds Inno Setup and tests the installed EXE.
Smoke tests import the packaged dependencies, compile a CPU OpenVINO graph,
call both native kernels and conversion, and capture the rendered GUI.
They do not download a model or establish Intel GPU/NPU driver support.

Branch builds upload `LLocalMind-Windows-x64` artifacts. A matching version
tag also publishes the assets as a **prerelease**. After checking a compatible
GGUF on the target PC, maintainers can promote it to a stable GitHub release
but the updater already includes public prereleases from v0.1.5 onward. Do not change the app version
without building the matching executable.

## User files

- Program: `%LOCALAPPDATA%\Programs\LLocalMind`.
- Settings and conversations: `%LOCALAPPDATA%\LLocalMind\data`.
- Default external model location: `%LOCALAPPDATA%\LLocalMind\models`.
- Downloaded installers/logs: `%LOCALAPPDATA%\LLocalMind\updates`.

The GUI uses `llocalmind.app_paths`, saves its selected GGUF path in user
settings and passes that path to the model. Users can keep large GGUFs
on another drive. The source CLI's existing model discovery is unchanged.
The installer does not write to or remove the data/model directories. Its
stable per-user AppId allows a newer installer to upgrade the same app without
uninstalling. Do not change that AppId for subsequent releases.

## Build a release on Windows

1. Bump `src/llocalmind/__init__.py::__version__` to a stable `MAJOR.MINOR.PATCH`.
2. Build the matching application folder (Python, OpenVINO and kernels):

   ```powershell
   py -3.14 -m pip install -r requirements-build.txt
   .\scripts\compile_dequant_k.bat
   .\scripts\compile_native_expert.bat
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_desktop.ps1
   ```

   The result is `dist\LLocalMind\LLocalMind.exe` plus its libraries. The
   installer-only Python tool below does not compile Python or native DLLs.
3. Install **Inno Setup 6.3+** and run:

   ```powershell
   py -3.14 tools\build_windows_installer.py --app-dir .\dist\LLocalMind
   ```

4. Publish a public GitHub release (stable or prerelease) tagged `vMAJOR.MINOR.PATCH` in
   `vin10122/LLocalMind`, attaching both emitted files:

   ```text
   LLocalMind-Setup-MAJOR.MINOR.PATCH-windows-x64.exe
   LLocalMind-Setup-MAJOR.MINOR.PATCH-windows-x64.exe.sha256
   ```

The sidecar contains `HASH`, two spaces, and the exact installer filename.
GitHub's asset `sha256:` digest is preferred when available; the sidecar is
the fallback. Checksums verify integrity of downloads from the configured
GitHub repository, not Authenticode identity. Code signing is a separate
release step. Drafts and downgrades are not offered. Public prereleases are included and labelled as previews.

## GUI integration

The settings update button is connected through `update_worker.py`; model
shutdown and installer handoff are managed by `MainWindow` in `app.py`.

`llocalmind.updater.UpdateManager` imports only the standard library.
It has no model dependency and never executes an installer automatically:

1. Call `manager.check()` in a background worker. `None` means no newer
   published release (including previews); `UpdateError` is a network/metadata error, not "up to date".
2. Show the version and release notes as plain text. Let the user choose
   **Download and update**.
3. Call `manager.download(release, progress=callback, cancel=event)` in the
   worker. Marshal callbacks to the GUI thread; `progress` receives received
   and total byte counts. Cancellation/corruption removes the partial file.
4. Save conversations, stop generation and close the model/store/executors.
5. Call `manager.launch_installer(downloaded_update)`, then exit the GUI.
   This method is restricted to a frozen Windows application. It rechecks the
   file hash before launching Inno Setup. The installer updates in place and
   relaunches the app after successful silent installation.

The installer handles file replacement outside the app process. Files locked
by another running instance can require closing that instance. Failures must
be shown by the GUI and can be diagnosed in `updates\install.log`; automatic
rollback of application data is not implemented.

## Exercise from a source checkout

These commands do not import or load the model:

```powershell
py -3.14 update.py check
py -3.14 update.py download
```

`check` performs metadata lookup only. `download` requires a valid release,
checks the complete installer and saves it without executing it. Source
checkouts continue to update through Git; `install` refuses source mode.
Ordinary GitHub source-code archives are not considered Windows installers.

Run the offline tests without contacting GitHub or executing an installer:

```powershell
py -3.14 tools\test_updater.py
```
