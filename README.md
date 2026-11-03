# LIDMS

## About

**Lab Information Digitalization and Management Systems** is a college minor project for managing lab equipment, requests and repairs. Administrators, faculty and technicians have separate access based on their responsibilities.

## Key Features

- Equipment inventory and stock tracking.
- Equipment requests, approvals and returns.
- Complaint reporting and repair assignments.
- Role-based dashboards and notifications.
- User management and CSV reports.

## Live Website

[Open LIDMS](https://lidms.vercel.app/)

Demo credentials are available on the login page.

## Tech Stack

Python 3.14, Django 5.2, HTML, CSS, JavaScript, Neon PostgreSQL and Vercel. SQLite is supported for local development.

## Prerequisites

- Python 3.14.
- Project source code.
- PowerShell for the commands below.

## Installation & Environment Setup

1. Open the repository root (`LIDMS_Code`) in a terminal.

2. Create a virtual environment and install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Create the local settings file for a fresh setup:

   ```powershell
   Copy-Item .env.example .env.local
   ```

4. Generate a key and paste it into `.env.local` as `DJANGO_SECRET_KEY`:

   ```powershell
   .\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

5. Leave `DATABASE_URL` blank to use SQLite. For Neon, copy `.env.neon.example` to `.env.neon` and enter the pooled and direct database URLs. Keep environment files private.

6. For a new database, create the tables and an administrator:

   ```powershell
   .\.venv\Scripts\python.exe manage.py migrate
   .\.venv\Scripts\python.exe manage.py createsuperuser
   ```

Keep existing environment files and accounts when using an already configured workspace. Connecting to the shared Neon database makes local changes visible on the live app.

## Local Run, Build & Test Commands

Start the app, then open `http://127.0.0.1:8000/`:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Collect static files:

```powershell
.\.venv\Scripts\python.exe manage.py --env-file .env.local collectstatic --noinput
```

Install test dependencies and run tests with `.env.local` configured for SQLite:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe manage.py --env-file .env.local test --noinput
```

## Project Structure

```text
LIDMS_Code/
|-- inventory/      # Models, workflows, permissions and tests
|-- lidms/          # Settings and routes
|-- templates/      # Page templates
|-- static/         # Styles, scripts and images
|-- tools/          # Browser checks
`-- manage.py
```

## Acknowledgements & Credits

Mulish font: SIL Open Font License, included in `static/fonts/OFL.txt`.
