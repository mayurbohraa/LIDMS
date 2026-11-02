# LIDMS

**Lab Information Digitalization and Management Systems** helps colleges manage laboratory equipment, requests and maintenance.

[Live Demo](https://lidms.vercel.app/) | [GitHub Repository](https://github.com/mayurbohraa/LIDMS)

## Features

- Three roles: administrator, faculty and technician.
- Equipment inventory, stock requests, approvals and returns.
- Complaint reporting, technician assignments and repair tracking.
- Role-based dashboards, notifications and CSV reports.
- Account management, profiles and responsive layouts.

To explore the application, open the live demo and select **Demo account credentials** on the login page.

## Technology

Python 3.14, Django 5.2, HTML/CSS/JavaScript, Neon PostgreSQL and Vercel.

## Run locally

From the project directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env.local
```

For a fresh checkout, set `DJANGO_SECRET_KEY` in `.env.local`. To use Neon, copy `.env.neon.example` to `.env.neon` and fill in its pooled and direct database URLs. Keep these files private. Do not overwrite existing configured environment files.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`. Without a Neon connection, a fresh local setup uses SQLite. The configured localhost app and live demo share Neon, so changes affect the same records and require internet access.

## Deployment

Import the repository into Vercel using the **Django** preset and Root Directory `./`. Connect Neon and configure the variables in `.env.vercel.example`, including a private signing key and the database connection supplied by Neon. Keep `DJANGO_DEBUG=false`.

The existing shared database is already initialized. Do not reimport or seed it. Future schema changes require migrations; pushing code does not replace database records.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe manage.py --env-file .env.local test --noinput
```

Use the explicit local environment for tests to keep test writes out of the shared live database.

## Project structure

- `inventory/` - models, workflows, permissions, migrations and tests.
- `lidms/` - settings, environment loading and application entrypoints.
- `templates/` and `static/` - pages, styles, scripts and branding.
- `tools/` - browser verification.

Private academic material, the case study and project details are in the sibling `Documentation` folder. Secrets, database files and test outputs are excluded from Git.

The demo uses fictional shared data. Password recovery is administrator-assisted; email delivery and disconnected offline sync are not configured. The bundled Mulish font retains its license in `static/fonts/OFL.txt`.
