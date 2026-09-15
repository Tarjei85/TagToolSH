Contributing to TagToolSH!
First off, thank you for considering a contribution. TagToolSH! is a small, focused project, and every bug report, feature suggestion, and pull request helps make it better.

This document explains how to report issues, suggest features, and submit code. It's written to be practical, not bureaucratic.

Table of Contents
Code of Conduct

Ways to Contribute

Reporting Bugs

Suggesting Features

Development Setup

Coding Guidelines

Pull Request Process

Testing Checklist

Commit Message Conventions

License

Code of Conduct
Be kind. Assume good faith. Disagreements about technical decisions are fine; personal attacks are not. Anything that would make a contributor feel unwelcome is grounds for removal from the project.

Ways to Contribute
You don't have to write code to help. Useful contributions include:

Bug reports with reproduction steps.

Feature suggestions with a clear description of the problem they solve.

Documentation improvements — the README, docstrings, inline comments.

Tag profiles for specific games or applications — a shared library of known kill-target process names would be genuinely useful.

Testing on different hardware — different ACR122U firmware revisions, different tag brands, different Windows versions.

Translations of the UI or documentation.

Reporting Bugs
Open an issue using the Bug Report template. The template asks for the details needed to reproduce the problem, so please fill it in as completely as you can. The most useful bug reports include:

A clear description of what you expected and what actually happened.

Exact reproduction steps. "Tap a tag" is not enough — describe the tag contents, the settings, and the sequence of actions.

Your environment: Windows version, Python version (if script mode), ACR122U firmware revision (if known), tag type.

Console output or logs. In script mode, run from a terminal to see the output. In frozen mode, check app_data/logs/launcher.log.

The state of app_data/config.json and app_data/tags_db.json if the bug involves settings or the tag library. Redact your UIDs if you consider them sensitive.

Screenshots if the issue is visual.

If you can't provide all of this, file the report anyway. A partial report is better than none.

Suggesting Features
Open an issue using the Feature Request template. Good feature requests describe:

The problem you're trying to solve, not just the solution you have in mind.

Why the current behavior doesn't work for your case.

Any workarounds you've tried.

How you'd expect it to work if you could design it.

Features that fit the project's scope (NFC-triggered Windows automation with process management) are more likely to be accepted than features that push it toward becoming a general-purpose task runner. If you're unsure, open a discussion issue first.

Development Setup
Prerequisites
Windows 10 or 11, 64-bit.

Python 3.12 — 3.13 may work, 3.14 is not recommended due to PySide6 wheel availability.

Git for cloning.

An ACR122U reader and some NFC tags for testing. Development is possible without hardware, but you can't test the reader interactions.

Clone and set up
Run these commands in cmd:

git clone https://github.com/YOUR-USERNAME/TagToolSH.git
cd TagToolSH
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install PySide6 pyscard ndeflib psutil pyinstaller

Run in script mode
From cmd:

python main.py

Or with the portable launcher (which installs into app_data/libs):

run.bat

Run in frozen mode (for testing the build)
From cmd:

rmdir /s /q build
rmdir /s /q dist
.venv\Scripts\python.exe -m PyInstaller --noconfirm "TagToolSH.spec"
dist\TagToolSH\TagToolSH.exe

Coding Guidelines
The project is small and consistent. Keep it that way.

Style
Python 3.12+ syntax. No compatibility shims for older versions.

PEP 8 for general formatting, but don't obsess over line length — long lines in UI construction or logging strings are fine.

Type hints on function signatures where they add clarity, especially for public methods and cross-module APIs.

Docstrings on every module, class, and public method. One sentence is enough for simple things; use multi-line when the behavior needs explanation.

Architecture
No global state. Everything lives on objects passed through constructors or signals.

Separation of concerns. UI code goes in ui/. Business logic goes in action_executor.py, ndef_handler.py, database.py. Do not mix them.

Signals, not callbacks. Cross-component communication uses Qt signals. If you're tempted to import one UI module from another, stop and use a signal.

Thread safety. The NFC reader and auto-detection threads must never touch Qt widgets directly. Use signals to marshal data back to the main thread.

No unnecessary dependencies. Adding a library needs justification. The current dependency set is intentionally minimal.

Logging
Do not leave print() statements in the final code for diagnostic purposes. Use the app's logging infrastructure or the status bar.

Diagnostic code must be clearly marked with a comment like # --- temporary diagnostic --- so it's easy to find and remove.

UI conventions
Every widget gets an objectName if it needs custom styling.

Every user-facing string is written in clear English, not abbreviated.

Emojis are used sparingly — checkboxes, buttons, and status badges, not body text.

Layout uses explicit spacing and margins. Relying on default sizes causes the collapsing bugs we've already fought through.

Dependency policy
The current runtime dependencies are PySide6, pyscard, ndeflib, and psutil. Any new dependency must be:

Actively maintained.

Available on PyPI for Windows.

Compatible with the MIT license of this project.

Bundlable by PyInstaller without hooks or special handling.

If you're unsure, open an issue to discuss before writing code that depends on a new library.

Pull Request Process
Fork the repository and create a branch from main. Use a descriptive branch name: fix/steam-kill-target, feature/epic-auto-detect, docs/readme-clarifications.

Keep changes focused. One logical change per pull request. If you're fixing a bug and also refactoring nearby code, split it into two PRs. Large mixed PRs are hard to review and often get postponed.

Write a clear description. Explain what the change does, why it's needed, and how you tested it. Reference any related issues with Fixes #123 or Relates to #456.

Update the documentation. If your change affects user-visible behavior, update README.md. If it changes internal structure, update the relevant docstrings.

Test the change manually using the checklist below. Automated tests aren't part of the project yet, so a clear manual test description is required.

Open the pull request against main. A maintainer will review it and either merge it, request changes, or explain why it's not a fit.

What gets a PR rejected quickly
Unrelated changes bundled together.

Large refactors that aren't tied to a specific issue.

New dependencies without prior discussion.

Code that breaks the Windows-only assumption, the portable-build mechanism, or the settings-driven kill gating.

Style inconsistencies with the rest of the codebase.

No description, or a description that says only "fixed bug."

Testing Checklist
Before opening a pull request, verify these behaviors manually. The exact steps depend on your change; use judgment about which apply.

Core functionality
The app launches in script mode (python main.py).

The app launches in frozen mode after a rebuild.

The window opens maximized.

The reader is detected and the status badge turns green.

Tapping a tag reads its UID, type, and NDEF payload.

Tapping a tag with a URI in Execution Mode launches the action.

Tapping a tag in Inspection Mode does not launch anything.

Tapping a tag in Read-Only Mode does not launch anything.

Writing
Writing a Spotify tag succeeds.

Writing a Steam tag succeeds.

Writing an executable tag (URI format) succeeds.

Writing an executable tag (text format) succeeds.

Writing a Web URI tag succeeds.

Writing a tag with the kill flag records kill=1 (visible in the scanner tab's payload display).

Kill on removal
A .exe tag with kill=1 kills the process on lift.

The same tag with the global setting off does not kill.

A Spotify tag never kills.

A tag with manual process_to_kill uses the manual name.

A tag with manual process_to_kill = none is not tracked.

The BSOD image displays on a successful kill (if enabled).

Lifting a tag with no tracked process shows the "no target" status message and fires the BSOD.

Auto-detection
First tap of a fresh Steam tag, held for the full delay, detects the game process.

The detected process is stored in the Tag Library.

Second tap kills immediately on lift without waiting.

Lifting before the delay cancels detection with a status message.

Settings and persistence
Toggling each setting persists across app restarts.

The debounce slider, detection delay spinbox, and BSOD timer spinbox do not respond to wheel scrolling unless clicked first.

The Settings tab scrolls when the window is small.

Collapsible sections expand and collapse.

Tray and exit
Minimize button hides to tray.

X button opens the modal.

Minimize to Tray hides the window and keeps the app running.

Exit Launcher terminates the process (check Task Manager).

Tray Exit terminates the process.

--minimized starts the app in the tray only.

If any of these fail on your branch but work on main, investigate before submitting. If they fail on both, that's a pre-existing bug — mention it in your PR description.

Commit Message Conventions
Use short, imperative subject lines. A prefix helps with scanning history:

fix: for bug fixes — fix: prevent Steam launcher from being killed

feat: for new features — feat: add Epic Games auto-detection

docs: for documentation — docs: clarify manual override usage

refactor: for internal changes — refactor: extract process picker

chore: for build, deps, tooling — chore: bump PySide6 to 6.8

The body of the commit should explain why the change was made, not what the diff already shows. Reference issues with #123.

Example:

fix: exclude cmd.exe from game candidate list

When a .bat launcher exits before auto-detection completes, cmd.exe was
being picked as the kill target because it matched the "launcher shell"
heuristic. Added cmd.exe, conhost.exe, and WindowsTerminal.exe to the
permanent blocklist.

Fixes #42

License
By contributing to TagToolSH!, you agree that your contributions will be licensed under the MIT License, the same license that covers the project. See the LICENSE file for the full text.

Thank you again for your interest in TagToolSH!. If anything in this document is unclear, open an issue and I'll clarify it — the process should be approachable, not intimidating.
