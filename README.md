# LIDMS

**Lab Information Digitalization and Management Systems** - a Django application for laboratory equipment, stock requests, maintenance and role-based administration.

## Features

- Administrator, faculty and technician dashboards with permission-scoped records.
- Equipment inventory, stock adjustments, approvals, borrower tracking and partial/full returns.
- Hardware/software complaints, technician assignments and repair resolutions.
- Notifications with unread counts and links to related records, plus activity history.
- Inventory and complaint reports with CSV exports.
- Account approval, profile editing, password changes and administrator inquiries.
- Responsive landing page, accessible role tabs, FAQs and actual dashboard previews.
- Compact demo-credentials pop-up and connected fictional sample records.

## Stack

Python 3.14, Django 5.2, server-rendered templates, CSS/JavaScript and PostgreSQL on Neon. Vercel runs the Django application and serves static assets. No separate frontend or Render service is required.

## One database for localhost and the hosted app

The intended setup uses **the same Neon database for localhost and Vercel**. A change made through either app is visible through the other after a page refresh. Both need internet access; this is not offline synchronization.

Before Neon is connected, the existing records remain in the ignored local `db.sqlite3`. They will be transferred once into an empty Neon database, preserving IDs, password hashes, requests, returns, repairs, history and notification read states. After connection, normal local startup automatically reads the pooled Neon URL from `.env.neon`. A connection failure does not silently switch back to SQLite.

The old `lidms.sql` backup is separate historical material and has not been imported. GitHub contains source and migration commands, never database records or credentials.

## Local setup

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy `.env.example` to `.env.local` for a new checkout and configure a private development secret. Until the initial transfer, leave its `DATABASE_URL` blank to retain the original SQLite source. Then:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`. On macOS/Linux use `.venv/bin/python`. For a new empty local sample database, `seed_demo` creates the sample accounts and workflows; it preserves existing passwords and decisions. Do not seed Neon when importing an existing workspace.

## Private environment files

| File | Purpose |
| --- | --- |
| `.env.local` | Local debug settings and original SQLite source for export/testing |
| `.env.neon` | Pooled/direct shared database connections; normal startup reads only its connection URLs |
| `.env.vercel` | Importable Production settings for Vercel; excludes the unknown database URL to preserve the Neon integration's value |
| `.env.*.example` | Public blank templates; contain no working secrets |

The private files and `local-data/` are ignored by both Git and Vercel packaging. This checkout has prepared private files; on another machine create them from the templates.

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Private signing key; use the prepared new key, not a value shared in chat |
| `DJANGO_DEBUG` | `true` only locally; `false` on Vercel |
| `DATABASE_URL` | The same SSL-enabled pooled Neon URL locally and on Vercel |
| `DATABASE_URL_UNPOOLED` | Direct connection to that same database for migration/import commands |
| `LIDMS_REQUIRE_POSTGRES` | Refuse SQLite fallback for hosted/maintenance settings |
| `LIDMS_DEMO_MODE` | Enables explicit sample seeding for fictional demo installations only |
| `LIDMS_SHOW_DEMO_ACCOUNTS` | Shows the demo-credentials pop-up |
| `LIDMS_DEMO_PASSWORD` | Must match the imported demo accounts; intentionally public in the pop-up |
| `DJANGO_ALLOWED_HOSTS` | Add custom hostnames if needed; Vercel-assigned deployment/production hosts are added automatically |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Add exact custom HTTPS origins; assigned Vercel origins are added automatically |

Never import `.env.local` into Vercel. Import `.env.vercel` for Production; Neon supplies `DATABASE_URL` through its integration. Do not overwrite that value with a blank variable.

## Connect Neon, transfer once, then deploy

1. Use the existing Vercel project linked to `mayurbohraa/LIDMS`, or import it using the **Django** preset and Root Directory `./`. A failed first build does not prevent linking a database.
2. Import the private `.env.vercel` under the project's **Settings > Environment Variables**, selecting **Production**.
3. In **Storage / Marketplace**, connect **Neon PostgreSQL**, selecting the **Free** plan if available. Django already handles authentication; Neon Auth and Realtime are not needed. Connect the database to this Vercel project's Production environment.
4. Verify the integration set `DATABASE_URL`. Save its pooled URL as `DATABASE_URL` and its direct/unpooled URL as `DATABASE_URL_UNPOOLED` in the private local `.env.neon`. Both must point to the same Neon database/branch as Vercel.
5. Pause local edits and back up SQLite. Export the latest workspace using the explicit local environment so `.env.neon` cannot change the source:

```powershell
.\.venv\Scripts\python.exe manage.py --env-file .env.local export_workspace --output local-data/exports/neon-initial.json
```

The export refuses to replace an existing file. Use a new filename for a fresh export. It contains account password hashes and must remain private.

6. Create the Neon schema, then import into the empty target:

```powershell
.\.venv\Scripts\python.exe manage.py --env-file .env.neon --direct-db migrate --noinput
.\.venv\Scripts\python.exe manage.py --env-file .env.neon --direct-db import_workspace local-data/exports/neon-initial.json
```

The importer checks the export digest, allowed models, record counts and stock balances. It refuses a populated target, restores relationships and ID sequences, and rolls back if validation fails. Sessions and login-throttling records are excluded; users log in again. It is a one-time migration, not a repeated merge/sync command. Do not run `seed_demo` or create target users first.

7. Restart local `runserver` normally; it now uses pooled Neon automatically. Redeploy Vercel with the saved variables. Vercel collects static files automatically; no custom build script is needed.
8. Verify all three logins, request approval, repair assignment/resolution, returns, notification links and CSV exports. Make a small change locally and confirm it online, then check the reverse direction. Add the verified live URL below.

The current local demo includes 12 equipment types, 12 requests, 8 complaints, returns, inquiries and 6 accounts, including one awaiting approval. Shared demo users can change sample records; there is no automatic reset. Future GitHub pushes update code, not data. Apply new schema migrations deliberately to Neon before deploying code that depends on them.

Neon is not connected yet and the cloud transfer has not run. Free plans have quotas and may have cold starts. A real college installation must use private accounts and disable public demo credentials.

## Verification

Run tests explicitly against SQLite so they do not access the shared live database:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe manage.py --env-file .env.local test --noinput
.\.venv\Scripts\python.exe manage.py --env-file .env.local makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py --env-file .env.local collectstatic --noinput
.\.venv\Scripts\python.exe tools/verify_ui.py
```

The browser verifier uses an isolated SQLite snapshot and saves screenshots outside Git. Environment and transfer tests cover shared connection selection, exact record restoration, password/read-state preservation, nonempty-target refusal and rollback. Actual Neon/PostgreSQL verification remains pending connection.

## Structure

```text
LIDMS_Code/                  # Git repository root
|-- inventory/               # Domain models, workflows, notifications and tests
|   |-- management/commands/ # Sample data, export and protected initial import
|   `-- migrations/          # Versioned database schema
|-- lidms/                   # Environment loading, settings and entrypoints
|-- static/
|   |-- Redmask/             # Robot logo and hero mascot
|   |-- project/             # Real role-dashboard screenshots
|   |-- project-icons/       # Original navigation icons
|   `-- css/, js/, fonts/    # Shared UI and bundled font/license
|-- templates/               # Public, authentication and workspace pages
|-- tools/                   # Isolated browser verification
|-- local-data/              # Ignored private backups and transfer exports
|-- manage.py
|-- pyproject.toml
`-- vercel.json
```

Private case study, project details, previews and original-source archives remain in the sibling `Documentation` directory, outside Git. Unused original imagery has been removed from the application after archive verification.

## Limitations and links

Historical-data migration, actual Neon verification and successful Vercel deployment remain pending. Password recovery is administrator-assisted. Contact messages are stored for administrators; email delivery is not configured. Completely disconnected offline edits are not synchronized.

[GitHub Repository](https://github.com/mayurbohraa/LIDMS) | Live Demo: deployment pending.

No application license has been selected. The Mulish font retains its SIL Open Font License in `static/fonts/OFL.txt`.
