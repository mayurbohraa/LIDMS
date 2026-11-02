# LIDMS

**Lab Information Digitalization and Management Systems**

[Live Demo](https://lidms.vercel.app/) | [GitHub Repository](https://github.com/mayurbohraa/LIDMS)

## Overview

LIDMS is a web application for managing a college laboratory's equipment, stock requests and maintenance in one place. It connects faculty who need equipment, administrators who review requests, and technicians who maintain the lab. Each role has its own dashboard and access to the records and actions relevant to its work.

The application tracks equipment from available stock through approval, issue and return. It also records hardware/software complaints, technician assignments and repair resolutions. Notifications and reports help users follow progress without relying on separate spreadsheets or manual follow-ups.

## Highlights

- Connected workflows across three roles, with server-side permission checks.
- Traceable stock movements, partial returns and safeguards against invalid quantities.
- Responsive pages for desktop, tablet and mobile.
- A working public demo with sample records and credentials available on the login page.

## Key features

- **Inventory:** equipment records, categories, laboratory locations, stock adjustments, low-stock indicators and archiving.
- **Equipment requests:** requests for existing items or new equipment, administrator decisions and recorded decision notes.
- **Issues and returns:** borrower records, outstanding quantities, partial/full returns and movement history.
- **Maintenance:** hardware/software complaints, priorities, technician assignments, progress and resolution notes.
- **Dashboards and notifications:** role-specific counts, work queues, activity history and read/unread updates linked to their records.
- **Reports:** inventory and complaint views, plus permission-scoped inventory, request and complaint CSV exports.
- **Accounts:** administrator registration/approval, role management, editable profiles and password changes.

## User roles

| Role | Responsibilities |
| --- | --- |
| Administrator | Manage accounts and inventory, decide requests, assign complaints and review reports. |
| Faculty | Request equipment, report issues and track their own requests, complaints and borrowed items. |
| Technician | Handle assigned repairs, adjust stock and record equipment returns. |

To try a role, open the live demo, go to Login and select **Demo account credentials**. The demo contains fictional shared records; visitor actions can change them.

## Technology

| Layer | Technology |
| --- | --- |
| Backend | Python 3.14, Django 5.2 |
| Interface | Django templates, HTML, CSS and JavaScript |
| Database | Neon PostgreSQL; SQLite for standalone local setup and tests |
| Hosting | Vercel |
| Verification | Django tests, Ruff and Playwright |

## Setup and run locally

Install Python 3.14 and Git. For a fresh checkout, run these commands in PowerShell:

```powershell
git clone https://github.com/mayurbohraa/LIDMS.git
cd LIDMS
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env.local
```

Set `DJANGO_SECRET_KEY` in `.env.local`. You can generate a value with:

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Leave `DATABASE_URL` blank for a standalone SQLite setup, then initialize and start the app:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`. On macOS/Linux, use `.venv/bin/python` instead of the Windows executable path. For an empty local demo database, `manage.py seed_demo` adds sample accounts and workflows and prompts for their password.

### Connect to Neon

Copy `.env.neon.example` to `.env.neon`. Fill in `DATABASE_URL` with the pooled URL and `DATABASE_URL_UNPOOLED` with the direct URL for the same database. Normal local startup reads these connections automatically.

The configured project uses the same Neon database for localhost and the live app. Changes through either app affect the same records and require internet access. Its initial data transfer is complete: **do not reimport or seed the existing shared database**. Do not overwrite configured environment files when following fresh-checkout instructions.

Keep `.env.local`, `.env.neon` and other private environment files out of Git. Public `.example` files document the available settings without credentials.

## Deploy on Vercel

1. Import the GitHub repository, choose the **Django** preset and set Root Directory to `./`.
2. Connect Neon PostgreSQL and confirm `DATABASE_URL` is available in the deployment environment.
3. Configure the settings shown in `.env.vercel.example`, including a private `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=false`. Enable demo settings only for fictional sample installations.
4. For a new database, apply migrations through its direct connection before using the app. The current shared database is already initialized.
5. Deploy and verify login, permissions, requests, repairs, returns and reports. Vercel collects static files automatically.

Future pushes deploy code; they do not replace database records. Apply schema migrations deliberately when the models change.

## Development checks

Keep `.env.local` configured for SQLite when running isolated tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe manage.py --env-file .env.local test --noinput
```

The latest verification passed 64 automated tests. Browser checks covered role handoffs, responsive layouts, demo controls, reports and access restrictions. `tools/verify_ui.py` runs browser workflows against an isolated SQLite snapshot and saves output under ignored `test-results/`.

## Project structure

- `inventory/` - models, workflows, permissions, migrations, management commands and tests.
- `lidms/` - settings, environment loading, routes and application entrypoints.
- `templates/` - public, login and workspace pages.
- `static/` - styles, scripts, fonts, icons, robot branding and dashboard images.
- `tools/` - browser verification.

Academic material, the case study and detailed project documentation remain in the sibling `Documentation` folder, outside Git. Secrets, database files, backups and test outputs are excluded from the repository.

## Current limitations

Password recovery is administrator-assisted. External email delivery, disconnected offline synchronization and automatic demo resets are not configured. Historical SQL-data migration and concurrency/load testing remain outside the completed scope.

No application license has been selected. The bundled Mulish font retains its SIL Open Font License in `static/fonts/OFL.txt`.
