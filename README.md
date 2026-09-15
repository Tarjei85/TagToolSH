# TagToolSH!

**A portable NFC tag launcher for Windows, built around the ACR122U USB reader.**

TagToolSH! reads and writes NFC tags, launches games, applications, and services with a single tap, and can automatically terminate launched processes when you lift the tag off the reader. It's a self-contained toolkit you can carry on a USB stick and run on any Windows machine.

## Table of Contents

- [What It Does](#what-it-does)
- [What It Does Not Do](#what-it-does-not-do)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Using TagToolSH!](#using-tagtoolsh)
- [Supported Hardware](#supported-hardware)
- [Building a Portable .exe](#building-a-portable-exe)
- [File Layout](#file-layout)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Version Notes and Design Decisions](#version-notes-and-design-decisions)
- [License and Credits](#license-and-credits)

## What It Does

### Core functionality

- **Reads NFC tags** placed on an ACR122U reader and decodes their NDEF payloads into classified actions: Spotify links, Steam game IDs, direct executables, web URLs, and custom text.
- **Launches the associated action** automatically, or after confirmation, depending on your settings.
- **Writes NFC tags** with a built-in Tag Studio. Five action types are supported: Spotify, Steam, Direct Executable, Web/Custom URI, and Custom Text.
- **Stores a per-UID action library** so tags that can't be rewritten (key fobs, hotel cards, read-only NTAGs) can still trigger arbitrary actions.

### Execution control

- **Three execution modes** cycled by a single header button:
  - **Execution Mode** - tag taps launch their action immediately.
  - **Inspection Mode** - tag taps only display the parsed payload.
  - **Read-Only Mode** - the strongest safety; nothing can launch.
- **Debounce**: prevents multiple firings while a tag rests on the reader.
- **Confirm before .exe**: optional modal prompt before launching executables.

### Kill on tag removal

- **Terminate launched processes when the tag is lifted.** The process is killed with `taskkill /F /IM <name> /T`, which also terminates child processes.
- **Per-tag control.** Whether a tag should trigger a kill is stored either in the tag itself as a secondary NDEF record (`kill=1`) or in the Tag Library entry for that UID (for read-only tags).
- **Manual override**: if you set a specific process name in the Tag Library, that name is used, and auto-detection is skipped.
- **Sentinel values**: setting the manual override to `none` or `off` disables all tracking and killing for that tag.
- **Spotify is always excluded**, regardless of what any tag encodes.
- **Global master switch**: if "Terminate application on tag removal" is off in Settings, no tag will be killed, no matter what it encodes.

### Auto-detection for launcher-spawned games

When a tag launches a Steam game, Epic game, generic launcher URI, or a `.bat`/`.cmd`/`.lnk` wrapper, the real game process isn't knowable from the tag content alone. TagToolSH! handles this with process snapshot diffing:

1. Before the launch, it captures the current process list.
2. After a configurable delay (default 15 seconds), it captures the list again.
3. It computes the diff: processes that appeared during the window.
4. It filters out known launcher shells (`steam.exe`, `EpicGamesLauncher.exe`, browsers, OS helpers, antivirus processes).
5. It prioritizes candidates that descend from the launcher shell or from the specific process that was launched.
6. It picks the largest remaining candidate by memory footprint.
7. The result is stored in the Tag Library so future taps kill instantly without needing to re-detect.

Auto-detection runs in a background thread and is fully cancellable by lifting the tag before the detection window completes.

### BSOD Easter egg

- **Fullscreen image displayed after a successful kill.** Place a file named `bsod.png` in `app_data/` to enable it.
- Borderless, always-on-top, aspect-ratio preserved, hidden cursor.
- Dismissible by any key or mouse click.
- Safety auto-close timer (configurable, default 60 s).
- Toggleable in Settings.

### System tray and startup

- **Minimizes to the Windows system tray.** Tag detection continues in the background while the window is hidden.
- **Minimize button hides to tray.** The X button opens a modal with three options: Minimize to Tray, Exit Launcher, Cancel.
- **Optional autostart on Windows login**, running hidden in the tray.
- **Hidden startup via CLI flag** (`--minimized`).

### Portability

- **Script mode**: a `run.bat` launcher that downloads a portable Python runtime and installs dependencies into `app_data/libs` on first run. Copy the folder to a USB stick and run it anywhere.
- **Frozen mode**: a PyInstaller build produces a self-contained `TagToolSH.exe` that runs on any Windows machine without Python installed.

## What It Does Not Do

TagToolSH! is deliberately narrow in scope. It does **not**:

- Support Windows Hello, smart cards, or authentication protocols.
- Read or write MIFARE Classic data blocks (only UID-based library entries work for those cards).
- Handle NTAG21x password protection or permanent lock bits.
- Run on macOS or Linux. The process-kill mechanism, system tray, autostart, and file URI handling are all Windows-specific.
- Provide a cloud sync or backup for the tag library.
- Perform NDEF message signing or tag authentication.
- Support multi-reader operation on the same machine (it uses the first detected ACR122U, or falls back to the first PC/SC reader).
- Kill processes that weren't launched by the app itself.

## Requirements

### Hardware

- **ACS ACR122U USB NFC reader** (or any PC/SC-compatible reader with NFC Type 2 support).
- **NTAG213 / NTAG215 / NTAG216 / MIFARE Ultralight** tags for writable use.
- Any **ISO 14443-A card or fob** for read-only UID mapping in the Tag Library.

### Software

- **Windows 10 or Windows 11**, 64-bit.
- **Microsoft PC/SC driver** - pre-installed on every supported Windows version.
- **Python 3.12** if you're running in script mode. Not required for the frozen build.

### Network

- **Internet connection on first run** (script mode only), to download the portable Python runtime and the Python dependencies.
- **No internet needed after first run** - everything is cached in `app_data/`.

## Installation

### Option A - Portable Script Mode

The simplest setup if you don't want to build anything.

1. Download or clone the repository to a folder, e.g. `C:\TagToolSH`.
2. Double-click `run.bat`.
3. On first launch, `run.bat` will download a portable Python 3.12 embeddable runtime into `app_data/python/`, bootstrap `pip` inside that runtime, and install PySide6, pyscard, ndeflib, and psutil into `app_data/libs/`.
4. The app window opens.
5. To make it portable, copy the entire `TagToolSH` folder - including `app_data/` - to a USB stick. It runs from any folder on any Windows machine.

Subsequent launches skip the setup entirely and launch in under a second.

Hidden launch: pass `--minimized` to `run.bat`, or create a shortcut with `run.bat --minimized` as the target.

### Option B - Frozen .exe Build

For a fully self-contained distribution that doesn't need Python on the target machine. See the "Building a Portable .exe" section below.

## Quick Start

### 1. Connect the reader

Plug the ACR122U into a USB port. The status badge in the top-right of the window turns green.

### 2. Write your first tag

1. Open the **Tag Studio / Writer** tab.
2. Pick an action type: Spotify, Steam, Direct Executable, Web URI, or Custom Text.
3. Fill in the target. For Spotify, paste a `spotify:track:...` URI or an `https://open.spotify.com/...` link. For Steam, enter the App ID (e.g. `730`) or a `steam://rungameid/...` URI. For Executable, click Browse and pick a `.exe`, `.bat`, `.cmd`, or `.lnk`. For Web, paste a URL or custom protocol URI.
4. Optionally tick **Kill launched process when this tag is removed**.
5. Click **Write to NFC Tag**.
6. Place an NTAG on the reader. The reader writes and verifies the data.

### 3. Tap to launch

With Execution Mode active, place the tag on the reader. The action launches.

### 4. Lift to kill (if enabled)

If the tag was written with the kill flag, lifting the tag runs `taskkill` against the launched process. The BSOD image appears if enabled.

## Using TagToolSH!

### The Three Modes

The mode button in the header cycles through three execution states:

| Mode | Behavior |
|---|---|
| **Execution Mode** | Actions launch immediately on tag tap. |
| **Inspection Mode** | Tag content is displayed but nothing launches. |
| **Read-Only Mode** | Same as inspection, plus the executor refuses to launch anything even if called programmatically. |

Click the button to cycle. The Settings tab has matching checkboxes for precise control.

### Reading Tags

The **Live Scanner & Launcher** tab shows:

- **UID** of the current tag, with a Copy UID button.
- **Tag type** (NTAG213/215/216, MIFARE Ultralight, etc.) and memory size.
- **Detected action** with a color-coded badge (Spotify green, Steam blue, Executable purple, Web orange).
- **Recent activity log** with timestamps, UIDs, types, targets, and status.

Buttons at the bottom:

- **Launch Action Now** - manual one-shot execution.
- **Save to Tag Library** - assign a custom action to this UID.
- **Encode / Overwrite Tag** - jump to the writer tab with this tag's data pre-filled.

### Writing Tags (Tag Studio)

The Tag Studio has five tabs, one per action type.

**Spotify Music** - Paste a track, album, or playlist URI. A "Test Spotify Link" button verifies the link works before you commit it to a tag.

**Steam Game** - Enter the App ID (numeric) or paste a store URL. The app converts URLs to `steam://rungameid/<id>` automatically.

**Direct Executable** - Browse for a `.exe`, `.bat`, `.cmd`, or `.lnk`. Optional arguments can be supplied. Two encoding formats are available: Standard NFC URI (`file:///C:/...`) for best compatibility, or Text Path (`C:\...`) if you're using custom arguments.

**Web / Custom URI** - Paste any URL or custom protocol. Opens with the system default handler.

**Custom Text** - Write arbitrary text or a launch command like `launch:notepad.exe`. Text-only tags display their content but don't trigger actions.

The **"Kill launched process when this tag is removed"** checkbox writes a secondary NDEF record containing `kill=1`. When this tag is read back, the app knows to track the launched process for a later kill. Spotify tags ignore this setting by design.

### The Tag Library

The Tag Library maps UIDs to actions. This is how you use read-only tags, key fobs, or hotel cards.

- **Add Tag Mapping** - create a new UID entry manually.
- **Edit Selected** - modify the selected row.
- **Delete Selected** - remove the mapping.
- **Test Selected Action** - execute the mapping once for testing.

Columns: Tag Name, UID, Type, Target, Args, Kill, Auto-Detected, Last Used.

The edit dialog also has a **Manual process name to kill on card removal** field. If set, this is used directly and auto-detection is skipped. Set to `none` or `off` to disable tracking entirely for this tag. The dialog also has the **Kill launched process when this tag is removed** checkbox, which is the library equivalent of the writer checkbox.

### Kill on Tag Removal

The kill pipeline has three layers, checked in order:

1. **Global setting** (`Terminate application on tag removal` in Settings). If off, no tag is ever killed.
2. **Tag's own flag** - either the NDEF `kill=1` record or the Tag Library's `kill_on_removal` field.
3. **Hard exclusions** - Spotify actions are never tracked or killed.

When all layers agree, the process is tracked and killed on removal.

Which process gets killed depends on the action type:

| Action Type | Kill Target |
|---|---|
| `.exe` | The image name from the target path, or the manual override |
| `.bat`, `.cmd`, `.lnk` | The auto-detected game process, or the manual override |
| Steam URI | The auto-detected game process, or the manual override |
| Epic URI | The auto-detected game process, or the manual override |
| Other URIs | The manual override if set, otherwise nothing |
| Command | The image name of the command string's first token |
| Spotify | Never tracked |

### Auto-Detection of Launcher-Spawned Games

When the app can't know the game's process name from the tag content alone (Steam, Epic, `.bat` wrappers), it uses **process snapshot diffing** to find it after launch.

**How it works, step by step:**

1. Before the URI fires (or the wrapper runs), the app takes a snapshot of every running process - PID, image name, parent PID, and memory usage.
2. The action is launched.
3. A background thread waits for the configured delay (default 15 s).
4. A second snapshot is taken.
5. The difference between the snapshots is computed: processes that appeared during the window.
6. Filtering:
   - A **blocklist** removes known launcher shells, browsers, OS helpers, antivirus, and system processes.
   - **Ancestry**: candidates must be a descendant of the launched process's PID (strict), or a descendant of a known launcher shell (fallback).
   - A **memory threshold** (50 MB) rejects tiny helper processes.
7. The largest surviving candidate is chosen.
8. The result is written to the Tag Library under `auto_detected_process`.
9. On tag removal, the app runs `taskkill /F /IM <name> /T`.

**Cancellation:** if you lift the tag before the detection completes, nothing is killed and no library value is stored. This is deliberate.

**Second tap:** the auto-detected name is now cached. Subsequent taps kill immediately on lift, with no waiting.

**Timing guidance:** most Steam games take 5-10 seconds to spin up, so 15 s is a safe default. If you have a slow machine or a game with a long initialization, increase the delay in Settings. If the game launches fast, you can reduce it.

### The BSOD Easter Egg

When a kill succeeds, the app can display a fullscreen image named `bsod.png`, stored in `app_data/`.

- Borderless, always on top, no taskbar entry.
- Aspect-ratio scaled, black-letterboxed.
- Hidden cursor.
- Closes on any key press, mouse click, or wheel scroll.
- Safety auto-close after a configurable timeout (default 60 s).
- Toggleable in Settings, with a configurable timeout.

If `bsod.png` isn't present, the effect silently does nothing and a status message explains why.

### System Tray and Autostart

**Minimizing to tray:** the minimize button hides the window entirely. Tag detection continues in the background.

**Closing the window:** the X button opens a modal with three choices:

- **Minimize to Tray** - hides the window, keeps the app running.
- **Exit Launcher** - shuts down cleanly.
- **Cancel** - returns to the window.

**Tray icon menu:**

- **Open Launcher Window** - restores the window.
- **Exit** - quits immediately, no modal.

**Windows autostart:** enable "Launch automatically on Windows startup" in Settings. A registry entry is added under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` that launches the app with `--minimized` on login.

**Hidden startup via CLI:** run `TagToolSH.exe --minimized` or `run.bat --minimized`. Any of `--minimized`, `--tray`, `--hidden`, or `--no-window` triggers the same behavior.

### Settings Reference

All settings are stored in `app_data/config.json` and can be edited through the Settings tab.

**Action Execution Behavior**

| Setting | Default | Description |
|---|---|---|
| Enable Action Execution on Tag Tap | On | Master toggle for automatic action firing. |
| Read-Only Mode | Off | Strongest safety; nothing launches. |
| Ask for confirmation before launching .exe | Off | Modal prompt before executables. |
| Terminate application on tag removal | Off | Master kill switch. |
| Also terminate all tag-launched processes when the app exits | Off | Cleans up any tracked processes on app exit. |
| Tag Debounce / Hold Cooldown | 2.5 s | Delay before the same UID can fire again. |

**Launcher Auto-Detection**

| Setting | Default | Description |
|---|---|---|
| Auto-detect game process for Steam / Epic / URI launcher tags | On | Enables the snapshot-diff detection. |
| Auto-detection delay | 15 s | Time to wait before comparing process lists. |

**BSOD Effect**

| Setting | Default | Description |
|---|---|---|
| Show bsod.png fullscreen after kill | On | Enables the easter egg. |
| Auto-close after | 60 s | Safety timeout. |

**ACR122U Hardware Feedback**

| Setting | Default | Description |
|---|---|---|
| Sound hardware buzzer on tag tap | On | One beep per successful read. |
| Sound hardware buzzer on write success | On | One beep per successful write. |

Three rapid beeps always play on write failure, regardless of the setting.

**System Tray & Windows Startup**

| Setting | Default | Description |
|---|---|---|
| Minimize to system tray when minimized or closed | On | Enables tray behavior. |
| Start with the main window maximized | On | Opens maximized. |
| Launch automatically on Windows startup | Off | Registry-based autostart. |

## Supported Hardware

### Readers

- **ACS ACR122U** - primary target, all features work.
- **Any PC/SC reader** with ISO 14443-A and Type 2 NDEF support - basic reading and writing work, but the ACR122U's hardware buzzer control is unavailable.

### Tags

| Tag | User Memory | Notes |
|---|---|---|
| NTAG213 | 144 bytes | Enough for a URI plus the kill=1 record. |
| NTAG215 | 504 bytes | Standard size for many products. |
| NTAG216 | 888 bytes | Largest Type 2 tag commonly available. |
| MIFARE Ultralight | 48 bytes | Minimum for a simple URI. |
| MIFARE Classic 1K/4K | n/a | Not NDEF-addressable. Use UID mapping only. |
| Any ISO 14443-A card | n/a | UID mapping via the Tag Library. |

## Building a Portable .exe

This produces a single-folder distribution that runs on any Windows machine without Python installed. Only the build machine needs Python and the project dependencies.

### Prerequisites

1. Python 3.12 installed on the build machine. 3.13 may work; 3.14 is not recommended because PySide6's wheel availability can be spotty.
2. The project's virtual environment activated. On a fresh clone, run these commands in cmd:

    py -3.12 -m venv .venv
    .venv\Scripts\activate
    pip install PySide6 pyscard ndeflib psutil pyinstaller

3. A `.ico` file at `app_data/icon.ico` (used for both the .exe icon and the runtime window icon). It must be a real multi-resolution ICO, not a PNG renamed. If you don't have one, remove the `icon=` line from the spec and the app will fall back to a vector-drawn icon.
4. A `bsod.png` at the project root or in `app_data/` if you want the BSOD effect.

### The spec file

The build uses `TagToolSH.spec`. Its key parts:

- **Analysis**: entry point `main.py`, `datas` includes `bsod.png` and `app_data/icon.ico`.
- **hiddenimports**: `smartcard`, `ndeflib`, `psutil` and its native submodules, plus the Qt modules the app uses.
- **excludes**: removes unused frameworks like tkinter, PyQt5/6, PySide2, matplotlib, numpy.
- **EXE**: single windowed executable with `icon='app_data/icon.ico'`.
- **COLLECT**: bundles everything into `dist/TagToolSH/`.

Every path in the spec must use forward slashes. Windows backslashes in Python string literals are treated as escape sequences, and `\b` in particular will corrupt paths during the build.

### Build command

From cmd, in the project root:

    rmdir /s /q build
    rmdir /s /q dist
    .venv\Scripts\python.exe -m PyInstaller --noconfirm "TagToolSH.spec"

The build takes 1-3 minutes and produces:

    dist/
    └── TagToolSH/
        ├── TagToolSH.exe
        └── _internal/        <- bundled Python, Qt, dependencies

The `dist/TagToolSH/` folder is the complete distribution. Copy it anywhere.

### First-run smoke test

    dist\TagToolSH\TagToolSH.exe

Verify the window opens maximized, the window/taskbar icon is your `icon.ico`, the header and tray tooltip read "TagToolSH!", tag taps work as expected, and a successful kill shows the BSOD image.

### Distributing

Copy the whole `dist/TagToolSH/` folder to a USB stick or another machine. The recipient double-clicks `TagToolSH.exe`. No install, no Python, no first-run downloads.

When the user first runs the app, an `app_data/` folder is created next to `TagToolSH.exe`, holding their settings, tag library, and logs. This folder is portable - copy it along with the .exe to move settings between machines.

### Rebuilding after changes

Every code change requires a full rebuild. From cmd, in the project root:

    rmdir /s /q build
    rmdir /s /q dist
    .venv\Scripts\python.exe -m PyInstaller --noconfirm "TagToolSH.spec"

Changes to `bsod.png` or `icon.ico` also require a rebuild because those files are copied into `dist/` at build time.

### Antivirus caveat

PyInstaller executables are self-extracting archives and sometimes trigger heuristic antivirus warnings. For personal use this is cosmetic; for wider distribution, code signing is the real solution.

## File Layout

### Source project

    TagToolSH/
    ├── main.py                 Application entry point
    ├── run.bat                 Portable Python bootstrap launcher
    ├── requirements.txt        Pinned dependency versions
    ├── README.md               This file
    ├── TagToolSH.spec          PyInstaller build spec
    ├── bsod.png                Optional BSOD image
    │
    ├── database.py             Settings + tag library persistence
    ├── action_executor.py      Launch, tracking, kill, auto-detection
    ├── ndef_handler.py         NDEF record encoding/decoding
    ├── nfc_reader.py           PC/SC worker thread
    ├── autostart.py            Windows registry autostart helper
    │
    ├── app_data/               User data (auto-created, portable)
    │   ├── icon.ico            App icon
    │   ├── bsod.png            Alternative BSOD location
    │   ├── config.json         Settings
    │   ├── tags_db.json        Tag Library
    │   ├── logs/               Log files
    │   ├── python/             Portable Python (script mode only)
    │   └── libs/               Installed deps (script mode only)
    │
    └── ui/
        ├── __init__.py
        ├── main_window.py      Main window, tray, signals
        ├── theme.py            Dark theme stylesheet
        ├── scanner_tab.py      Live Scanner tab
        ├── writer_tab.py       Tag Studio tab
        ├── library_tab.py      Tag Library tab
        ├── settings_tab.py     Settings tab
        ├── info_tab.py         Info tab
        └── bsod_viewer.py      Fullscreen BSOD viewer

### Frozen distribution

    TagToolSH/
    ├── TagToolSH.exe
    ├── _internal/              Bundled runtime and dependencies
    └── app_data/               Created on first run
        ├── config.json
        ├── tags_db.json
        └── logs/

## Troubleshooting

### The reader isn't detected

Confirm the ACR122U is plugged in and its LED is on. Check Device Manager for the smart card reader under **Smart card readers**. If it's missing, install the ACS PC/SC driver. Run the app with `--minimized` off and check the terminal for reader worker errors.

### A tag reads but nothing launches

Check the mode button. It must read **Execution Mode: Active**. Verify the tag's NDEF payload in the Live Scanner tab. If it shows **BLANK / NO NDEF**, the tag is empty - write to it first. If the action is a text record, nothing will launch. Only URI and executable actions trigger launches.

### A tag launches the wrong thing, or nothing at all

Check whether the UID has a Tag Library entry that overrides the NDEF. The library always wins. Delete or edit the entry to remove the override. Confirm the target path still exists if it's an executable.

### Auto-detection picks the wrong process

Open Tag Library, select the tag, click Edit. Clear the `auto_detected_process` by setting the manual override to a placeholder, saving, then re-editing and clearing it. Alternatively, set the manual `process_to_kill` to the correct image name, which bypasses auto-detection entirely.

### Auto-detection finds no candidate

Common causes:

- **You lifted the tag before the delay finished.** Keep the tag on the reader for the full duration shown in the status bar.
- **The game uses a .bat launcher that spawns with start.** Windows detaches the game from the launcher, breaking the ancestry link. Set the manual `process_to_kill` for that tag.
- **The candidate is under 50 MB.** Small games or utilities may be filtered. Set the manual override.

### Kill fires but the game survives

The image name might not match exactly. Open Task Manager while the game runs, check the **Details** tab, and use the exact Image Name. Some games spawn a launcher stub that exits immediately, leaving a differently named child running. Set the manual override to the child's image name.

### The BSOD doesn't appear

Confirm the setting is enabled in Settings - BSOD Effect. Confirm `bsod.png` exists in `app_data/` or the project root. The BSOD only fires on a successful kill attempt or when a kill was requested but no target was tracked.

### The process stays in Task Manager after closing the app

Confirm you're running the latest build. The X modal's **Exit Launcher** button and the tray menu's **Exit** both call `QApplication.quit()` and an `os._exit()` fallback. If the process still lingers, use Task Manager - Details - Analyze wait chain on the stuck process to identify the blocking thread.

### Frozen build: psutil = None and auto-detection doesn't work

The `TagToolSH.spec` file must list `psutil`, `psutil._common`, `psutil._psutil_windows`, and `psutil._pswindows` in `hiddenimports`. `action_executor.py` must have a plain `import psutil` at the top (not inside a `try/except` that PyInstaller can strip).

### Icons aren't shown in Explorer

The `.ico` must be a real multi-resolution icon, not a renamed PNG. Check that the file starts with bytes `00 00 01 00`. Windows caches icons by file path. Copy the `.exe` to a new name or run `ie4uinit.exe -show` from cmd.

## Known Limitations

TagToolSH! is a focused tool, not a general-purpose NFC platform. Its limitations are:

- **Windows-only.** The process kill, system tray, and file URI handling are all Windows-specific.
- **Single reader.** Only one PC/SC reader is used at a time.
- **.bat wrappers using start + exit** cannot be auto-detected, because Windows detaches the child from the wrapper shell. A manual `process_to_kill` is required for these.
- **No NTAG password protection.** Password-locked tags can't be written.
- **No MIFARE Classic data blocks.** Only UID-based library mapping works.
- **Manual library deletion** is required to fully reset an auto-detected process. There is no "clear auto-detection" button in the UI.
- **Auto-detection has a 15-second default wait.** Tags must stay on the reader for the full duration on the first tap. Subsequent taps are instant once detection has completed.
- **Auto-detection may pick a wrong process** if an unrelated large process appears in the same window. The blocklist and ancestry filters mitigate this, but it isn't impossible.
- **The kill command uses image name, not PID** (unless the tag mapping explicitly uses a manual PID). This means `taskkill /IM` affects all processes with that image name - if you launched the same game manually, lifting the tag will kill that too. This is generally desired behavior, but be aware.

## Version Notes and Design Decisions

A few decisions worth documenting.

**Why the tag carries kill=1 as a separate NDEF record.** Embedding the kill flag in the URI as a query string would break the Windows shell (`file:///...?kill=1` is not a valid file path). A separate record keeps the URI clean and compatible with every URI handler.

**Why taskkill /F /IM name /T instead of /PID.** Using `/T` terminates the process and all children. Using `/IM` matches whatever is running with that image name, which is what you want for most games. A per-PID variant exists in the code but is only used when the library explicitly provides a PID.

**Why the global kill_on_removal setting gates everything.** Disabling it in Settings prevents any kill, regardless of what a tag encodes. This is enforced at the top of both `execute_action` (no tracking when disabled) and `_on_tag_removed` (no kill when disabled).

**Why Spotify is hard-excluded.** Spotify runs as a persistent background application. Killing `Spotify.exe` on tag removal would disrupt the user's listening if they lift a tag while music plays. Spotify tags launch a track or playlist; they never launch a game or application that should be terminated on removal.

**Why auto-detection requires a snapshot diff instead of a static lookup.** There is no reliable programmatic mapping from `steam://rungameid/730` to `cs2.exe`. Steam's app manifests don't always contain the executable name, and games with mod loaders or anti-cheat launch through intermediary processes. A snapshot diff of the process tree after launch is the only approach that works uniformly across launchers.

**Why library overrides exist.** Not every process can be reliably auto-detected. Read-only tags can't be rewritten to carry flags. Some games use wrappers that break ancestry. The Tag Library is the universal fallback for all these cases.

## License and Credits

TagToolSH! is released under the MIT License. See `LICENSE` for the full text.

Written by **Tarjei S. H.**

The application is bundled with the following third-party libraries, each under its own license:

- **PySide6** - LGPL v3 - Qt for Python bindings
- **pyscard** - LGPL v2.1 - PC/SC smart card access
- **ndeflib** - MIT - NFC Forum NDEF record parsing
- **psutil** - BSD 3-Clause - cross-platform process inspection

The ACR122U is a product of Advanced Card Systems Ltd. TagToolSH! is not affiliated with ACS.
