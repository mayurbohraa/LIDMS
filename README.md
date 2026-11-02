# LIDMS

**Experience the new way.** Lab Information Digitalization and Management Systems helps manage laboratory equipment, stock requests, users and complaints.

The application retains the original project's workflows and navigation, with a new front-facing 2D robot logo derived from its updated mascot. The UI reference is used only for typography, colors, spacing and component styling.

## Features

- Administrator, faculty and technician accounts with email login and role-based access.
- Role-specific dashboards with live counts, review queues, maintenance priorities and complaint progress.
- New Registration and User Details for laboratory administration.
- Stock Manager with inventory, equipment requests, borrower tracking and partial returns.
- Post Stock Request with equipment requirements and description.
- Post Complaint with hardware/software types, priority and resolution tracking.
- Stock and complaint reports with permission-scoped CSV exports.
- Dark-and-white landing page with real dashboard previews, features, role explanations and FAQs.
- Private in-app updates for request decisions, maintenance assignments and account changes.
- Responsive navigation, switchable dashboard screenshots with zoom, keyboard-accessible role tabs and expandable FAQs.
- Profile management and the original Contact Us page for lab inquiries.

## Technology

Python 3.14, Django 5.2, Django templates, CSS and JavaScript. SQLite is used locally; PostgreSQL is required for deployment on Vercel.

## Run locally

From this repository directory, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`. On macOS/Linux, use `.venv/bin/python` instead of the Windows executable path.

Optional local demonstration accounts:

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo
```

The command prompts for a password and creates `demo.admin`, `demo.faculty` and `demo.technician`. By default it refuses non-debug environments and preserves existing demo passwords. Usernames remain supported alongside email login.

Sample data includes 12 equipment types (available, low stock, out of stock and archived), requests in every decision state, partial and complete returns, open/in-progress/resolved repairs, read and unread notifications, activity history, sample inquiries and an account awaiting approval. Additional sample faculty and technician accounts make assignments and borrower records easier to follow. Approvals and returns use the normal application services, keeping inventory balances and history consistent. Rerunning the command adds missing examples without resetting existing decisions, returns, passwords or notification read states.

To show the demo accounts on the login page, set `LIDMS_SHOW_DEMO_ACCOUNTS=true` and `LIDMS_DEMO_PASSWORD` to the password used when seeding. The “Demo account credentials” button opens a compact pop-up with each role's email and the shared password, plus copy buttons. Only active, matching demo accounts appear. Keep this disabled for installations with real college records; the displayed password is intentionally public. After changing environment values, restart the server.

## Where the data lives

| Environment | Database | Purpose |
| --- | --- | --- |
| Local development | Ignored `db.sqlite3` on your computer | Current sample data and development |
| Vercel Preview / staging | Separate Neon database or preview branch | Test changes without editing the live demo |
| Vercel Production | Dedicated Neon PostgreSQL database | Public portfolio demo with fictional records |

The current data is local only. GitHub stores code, migrations and the sample-data command; pushing code does not upload SQLite records. The hosted demo will recreate the sample scenarios in Neon. The original SQL backup remains private and has not been imported. An installation with real college records must use a different database with public demo credentials disabled.

## Environment configuration

Copy `.env.example` to an ignored `.env` file for local overrides. `manage.py` also loads ignored `.env.local`. Keep secrets out of Git.

| Variable | Purpose |
| --- | --- |
| `DJANGO_DEBUG` | `true` locally; `false` in production |
| `DJANGO_SECRET_KEY` | Unique production secret |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Exact trusted HTTPS origins |
| `DATABASE_URL` | Pooled Neon PostgreSQL URL with SSL; direct URL for maintenance commands |
| `LIDMS_DEMO_MODE` | `true` only for an installation containing fictional demo records |
| `LIDMS_SHOW_DEMO_ACCOUNTS` | Show the credentials pop-up on demo installations |
| `LIDMS_DEMO_PASSWORD` | Shared sample password; public when the credentials pop-up is enabled |

## Development checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

`tools/verify_ui.py` checks the original content, branding, navigation and workflows in Chrome. It uses local demo credentials from `LIDMS_DEMO_PASSWORD`, runs against an isolated SQLite snapshot on port 8001 and saves previews outside the repository.

## Deploy the public demo

1. In Vercel, select **Add New > Project**, import `mayurbohraa/LIDMS`, choose **Django** and leave Root Directory as `./`. Create the project first; its initial deployment can fail until a database is connected. Keep the default build settings: the WSGI entrypoint is configured and Vercel collects static files automatically.
2. Open that project's **Storage / Marketplace**, select **Neon PostgreSQL**, choose the **Free** plan and connect it to the Vercel project. No Neon Auth or Realtime service is required; Django handles login. Choose a nearby region for the app and database. Connect an existing Neon project if you already created one.
3. Configure **Production** variables: `DJANGO_DEBUG=false`, a new `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` containing the project's `.vercel.app` hostname, `DJANGO_CSRF_TRUSTED_ORIGINS=https://<project>.vercel.app`, and the integration's SSL-enabled `DATABASE_URL`. For this public sample installation also set `LIDMS_DEMO_MODE=true`, `LIDMS_SHOW_DEMO_ACCOUNTS=true` and a strong `LIDMS_DEMO_PASSWORD`.
4. Give **Preview** its own Neon database/branch and credentials. Do not connect Preview to the live demo database. Integration-created preview branches may have deployment-specific credentials; use that deployment's connection details when preparing its schema.
5. Initialize the hosted demo once from a trusted local terminal. Use the same secret and demo password as Vercel and Neon's **direct/unpooled** connection string for the target database. Follow the commands below using a dedicated ignored environment file.
6. Redeploy after saving environment variables and preparing the database. Check all three logins, request approval, repair assignment/resolution, equipment return, notification links and CSV exports on the live URL.
7. Add the verified live URL to Links. Future pushes to the production branch deploy code automatically; apply database migrations deliberately to the matching database before deploying code that requires them.

Create an ignored `.env.hosted-demo` locally with these keys filled from the intended **demo** database and Vercel settings:

```dotenv
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=
DATABASE_URL=
LIDMS_DEMO_MODE=true
LIDMS_DEMO_PASSWORD=
```

Keep this file outside version control. From the repository root:

```powershell
.\.venv\Scripts\python.exe manage.py --env-file .env.hosted-demo migrate --noinput
.\.venv\Scripts\python.exe manage.py --env-file .env.hosted-demo seed_demo --allow-hosted-demo
```

Both `LIDMS_DEMO_MODE=true` and `--allow-hosted-demo` are required for non-debug sample seeding. Rerunning preserves passwords and visitor changes; it does not reset the demo. Never run this against real college records. For a real installation, leave demo flags disabled, run migrations and create a private administrator with `createsuperuser` instead.

The application runs on Vercel; persistent database storage is provided by Neon. No Render service is needed. Free plans have quotas and may have cold starts; they are not an always-on performance guarantee. The hosted connection and live deployment have not yet been verified.

## Structure

```text
LIDMS_Code/                 # Git repository root
├── inventory/              # Models, forms, permissions, workflows and tests
├── lidms/                  # Settings, routes and application entrypoints
├── static/                 # Styles, original project assets and bundled font
├── templates/              # Original LIDMS pages in shared Django layouts
├── tools/                  # Local browser verification
├── manage.py
├── requirements.txt
└── vercel.json
```

Private documentation and the original-project archive are stored in the sibling `Documentation` directory, outside Git.

## Limitations

Historical SQL/SQLite data is preserved but has not been imported. Password recovery is administrator-assisted. Contact messages are saved for administrators; no email delivery service is configured. Live PostgreSQL and Vercel verification remains pending.

## Links

[GitHub Repository](https://github.com/mayurbohraa/LIDMS) · Live Demo: deployment pending.

No application license has been selected. The bundled Mulish font retains its SIL Open Font License in `static/fonts/OFL.txt`.
