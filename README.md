# Adem

Adem is a local, open-source Linux process dashboard. It shows live CPU, RAM, swap, storage and per-user process data, then lets you close selected, recognised desktop apps after an explicit review.

It is designed for everyday Linux users who want a calmer way to reclaim attention and memory without a cleaner that deletes files behind their back.

## Features

- Live CPU, memory, swap, storage and uptime metrics from `/proc`.
- Searchable process list with RAM and CPU estimates.
- Multi-select close flow with a review dialog and a 60-second, single-use plan.
- SIGTERM only: no forced kill and no shell commands from the web API.
- Browser, Codex/agent sessions, password managers, recording software, system services and unknown processes stay protected.
- No file deletion, cache deletion, sudo, cloud account or external connection.
- Loopback-only web server with Origin and session-token checks for mutations.
- Responsive English interface with keyboard support and reduced-motion handling.

## Requirements

- Linux with `/proc` and Python 3.9 or newer.
- Linux 5.3+ with pidfd support is required for closing processes. If pidfd is unavailable, Adem fails closed and does not close anything.
- A modern browser. No npm, pip or runtime dependency is needed.

## Install

```bash
tar -xzf adem-linux.tar.gz
cd adem-linux
bash install.sh
```

The installer copies Adem to `~/.local/share/adem-optimizer`, registers a per-user systemd service and adds **Adem — Linux optimizer** to the application menu. It does not require sudo. Open <http://127.0.0.1:8765> or launch it from the application menu.

To run without installing:

```bash
python3 server.py
```

To install on another Linux computer, copy this repository or release archive there and run `bash install.sh`. Each computer has its own local dashboard; there is no central control.

## Closing apps safely

1. Select recognised apps in **Apps & processes**.
2. Choose **Review & close selection**.
3. Save your work and read the list in the confirmation dialog.
4. Confirm. Adem re-checks the process identity and sends SIGTERM only to processes owned by your user.

An app may not show a save prompt. Self-restarting services can return. RSS may count shared memory more than once, and closing an app does not guarantee a speed improvement. Adem reports what happened; it does not invent an optimisation score.

Only explicit names in `APPS` are closable. If your distribution uses a different executable name, the process stays protected until that name is reviewed and added.

## Development

```bash
python3 -m unittest discover -s tests -v
node --check web/app.js
bash -n install.sh
```

The optional browser QA script uses Playwright and axe-core when those tools are installed:

```bash
PLAYWRIGHT_PATH=/path/to/playwright \
AXE_PATH=/path/to/axe.min.js \
node tests/browser.cjs
```

The test suite starts only a disposable copy of `sleep` named `vlc`; it never closes an existing user app.

## Security model

Adem is a local desktop utility, not a sandbox. Code running as your Linux user can already inspect or signal your processes. The loopback server protects against ordinary cross-site requests and refuses cross-origin mutation requests, but it cannot protect against malware running as your user.

The process plan records PID, executable, UID and start time, then revalidates them before signalling. Plans expire after 60 seconds and can only be used once. No passwords, vault data, browser databases or file contents are read.

Please report security issues privately through GitHub Security Advisories rather than opening a public issue with exploit details.

## License

Adem is released under the MIT License. See [LICENSE](LICENSE).
