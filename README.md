# Aftara

AI-assisted job discovery, factual resume tailoring, and application review.

**Status: private beta.** Deployed as a personal project; not yet hardened for a public multi-tenant launch. Aftara does not automatically submit job applications.

## Features

- Account-scoped job searches using a signed-in LinkedIn browser session.
- Gemini-assisted fit assessment and factual resume wording suggestions, with model selection.
- Overleaf ZIP/TAR/TeX imports and sandboxed PDF rendering; supported source templates retain their layout.
- PDF review and approval, plus manually recorded application status.
- Scheduled job reports with colourful HTML tables and plain-text alternatives.
- Encrypted server credentials and administrator-managed SMTP delivery.

## Stack

Python, SQLite, aiohttp, Playwright/Chromium, Gemini API, Tectonic, bubblewrap, noVNC, and Nginx. The current deployment uses a Google Compute Engine Linux VM.

## Local development

Python 3.12 is recommended. Use a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python -B app.py
```

Open http://127.0.0.1:8501. Register an account and configure your resume, search preferences, and Gemini key. On macOS credentials use Keychain. On Linux configure `LINKEDINAPPLY_DATA` and `LINKEDINAPPLY_VAULT_KEY` before storing credentials; the latter must point to a private Fernet key file. Never commit that file.

The simple development server does not supply a remote desktop. Full Overleaf compilation requires Linux, bubblewrap, Tectonic at `bin/tectonic`, Poppler (`pdftotext`), and template fonts. Bibliography projects may additionally require the matching Biber version; the current sandbox supports `bin/biber-2.17/biber`. Compiler downloads and cache files are intentionally excluded.

## Linux deployment

Install Python venv support, Chromium, Xvfb, xauth, x11vnc, noVNC, websockify, bubblewrap, Poppler, Nginx and the required fonts. Install the compiler separately from its official release.

`provision_user.py` is a first-install helper for a checkout at `~/linkedinapply`; it creates private local configuration and a user systemd service. Review it before running: it overwrites `service.env` and the service definition. Do not rerun it over a configured deployment.

The gateway (`python -B gateway.py`) listens on loopback port 8080 and runs the app internally on 8501. Configure Nginx with HTTPS, WebSocket proxy support and a 21 MB upload limit. Set `LINKEDINAPPLY_PUBLIC_ORIGIN` to the external HTTPS origin. Keep internal app and remote-desktop ports private.

Useful configuration:

| Variable | Purpose |
| --- | --- |
| `LINKEDINAPPLY_DATA` | Private account data directory |
| `LINKEDINAPPLY_VAULT_KEY` | Path to server encryption key |
| `LINKEDINAPPLY_PUBLIC_ORIGIN` | External origin, used for links and origin checks |
| `LINKEDINAPPLY_CHROMIUM` | Chromium executable path |
| `LINKEDINAPPLY_REMOTE_BROWSER` | Set to `yes` for hosted browser sessions |
| `LINKEDINAPPLY_MAX_BROWSERS` | Maximum concurrent remote browser sessions |
| `AFTARA_MAIL_SENDER_ACCOUNT` | Administrator account ID whose saved SMTP settings serve all report recipients |

Configure the administrator sender before enabling shared-sender mode. Once enabled, consumers see only their recipient address and schedule; consumer form submissions cannot replace the shared SMTP settings. Secrets remain in the encrypted credential store.

## Tests

```sh
python -B -m unittest discover -s tests
```

Tests cover account separation, settings persistence, application review, archive handling, shared email settings and report rendering. Live LinkedIn, Gemini, SMTP and full compiler integration require separate environment-specific checks.

## Current limitations

LinkedIn layouts and sessions can change. Discovery depends on an active browser login. Application status reflects locally recorded actions. Daily report retries, recipient verification, password recovery, abuse controls, monitoring, and backup restoration need further work before public launch. Review every generated resume and PDF before using it.

## Repository privacy

This repository contains source code and synthetic tests only. It excludes uploaded resumes, PDFs, database files, browser profiles, API keys, SMTP passwords, deployment keys, and production environment configuration.
