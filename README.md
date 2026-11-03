# LIDMS

**Lab Information Digitalization and Management Systems**

[Live Website](https://lidms.vercel.app/)

## About

LIDMS is a group college minor project for laboratory management. It brings laboratory equipment, stock requests, borrowing and maintenance into one role-based web application. Administrators review requests and manage access, faculty request equipment and report issues, and technicians handle repairs and returns.

The application keeps inventory movements and decisions traceable, provides role-specific dashboards and notifications, and exports reports for record keeping. The interface supports desktop, tablet and mobile screens.

## Key Features

- Equipment records, categories, lab locations, stock adjustments and low-stock indicators.
- Requests for existing or new equipment, administrator approval and decision notes.
- Borrower tracking, partial/full returns and stock-movement history.
- Hardware/software complaints, technician assignments, priorities and resolution notes.
- Role-specific dashboards, activity history and read/unread notifications.
- Inventory, request and complaint CSV exports with permission checks.
- Account approval, role management, profiles and password changes.

To explore the fictional sample data, open the live website and select **Demo account credentials** on the login page. The sample accounts share editable records.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.14, Django 5.2 |
| Interface | Django templates, HTML, CSS and JavaScript |
| Database | Neon PostgreSQL; SQLite for standalone development and isolated tests |
| Hosting | Vercel |
| Checks | Django tests, Ruff and Playwright |

## Prerequisites

Use Python 3.14 (the configured deployment version), Git and the project source. A Neon connection is optional for standalone local use; it is required to use the existing shared database. The commands below use Windows PowerShell. On macOS/Linux, replace `.venv\Scripts\python.exe` with `.venv/bin/python`.

## Installation & Environment Setup

From the application directory (`LIDMS_Code` in this workspace; the repository root in a fresh checkout):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env.local
```

Run the copy command only for a fresh setup; keep existing configured environment files. Generate a signing key and set it as `DJANGO_SECRET_KEY` in `.env.local`:

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Leave `DATABASE_URL` blank for a standalone SQLite database. To connect Neon, copy `.env.neon.example` to `.env.neon` and set its pooled `DATABASE_URL` and direct `DATABASE_URL_UNPOOLED` for the same database. Normal startup reads these URLs automatically. Private environment files are excluded from Git.

This workspace's localhost app and deployed app share Neon. Changes affect the same records and require internet access. The initial data transfer is complete: do not import or seed the populated shared database again.

## Local Run, Build & Tests

For a new empty database, initialize the tables and create an administrator:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Start the application (also the only step needed for the configured workspace):

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`. For an empty local demonstration database, `manage.py seed_demo` creates sample scenarios and prompts for a password. To show the login-page credentials dialog locally, set `LIDMS_SHOW_DEMO_ACCOUNTS=true` and `LIDMS_DEMO_PASSWORD` to that same password in the private local environment file. Existing account passwords and workflow changes are preserved.

Django renders the interface directly; there is no frontend bundle step. Collect production static assets with:

```powershell
.\.venv\Scripts\python.exe manage.py --env-file .env.local collectstatic --noinput
```

Keep `.env.local` configured for SQLite when running tests, so they do not access the shared live database:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe manage.py --env-file .env.local test --noinput
.\.venv\Scripts\python.exe tools/verify_ui.py
```

The browser verifier needs the Chrome executable configured in `tools/verify_ui.py`, an existing local SQLite sample database and its `LIDMS_DEMO_PASSWORD` in `.env.local`. It uses a temporary SQLite snapshot. Screenshots and logs are saved in ignored `test-results/`; `LIDMS_Visuals` is reserved for future project visuals.

## Deployment

Use the Django preset in Vercel with Root Directory `./`. Connect Neon PostgreSQL and configure the settings in `.env.vercel.example`, including a private signing key and `DJANGO_DEBUG=false`. The Neon integration supplies `DATABASE_URL`; Vercel collects static assets automatically. Apply schema migrations deliberately when models change. Deploying code does not replace database records.

## Project Structure

```text
LIDMS/
|-- LIDMS_Code/             # Git repository root and application
|   |-- inventory/          # Models, workflows, permissions, migrations and tests
|   |-- lidms/              # Environment loading, settings, routes and entrypoints
|   |-- templates/          # Public, authentication and workspace pages
|   |-- static/             # Styles, scripts, fonts, icons and branding
|   `-- tools/              # Browser verification
|-- LIDMS_Docs/             # PROJECT_DETAILS.md and CASE_STUDY.md only
|-- LIDMS_College_Documents/ # Private college documents and assessment material
|-- LIDMS_Assets/           # Branding files and logo candidates
`-- LIDMS_Visuals/           # Reserved for future project visuals
```

The sibling documentation, college-materials, assets and visuals folders belong to the local workspace and are not included in the public repository. Secrets, database files, backups and test outputs are also excluded.

## Notes & Credits

Password recovery is administrator-assisted. Email delivery, disconnected offline synchronization and automatic demo resets are not configured. Historical SQL migration and concurrency/load testing remain outside the completed scope.

LIDMS was developed as a group college minor project. The later modernization used coding-assistant support. The interface styling was informed by the supplied community dashboard reference; current product content and branding follow the project's requirements. The bundled Mulish font retains its SIL Open Font License in `static/fonts/OFL.txt`. No application license has been selected.
