# MCA Legal Signal Engine

MCA Legal Signal Engine is a compliant legal-market intelligence and opt-in
lead-routing MVP for Merchant Cash Advance defense opportunities in New York
and Florida.

It ingests mock or manually imported public/legal records, normalizes cases and
UCC filings, classifies MCA-related records, scores them, and exposes them
through a FastAPI API plus a simple dashboard for review, suppression, and
buyer routing.

## What The Product Does

- Tracks MCA litigation and UCC signals for attorney intelligence.
- Preserves source URL, access method, source timestamp, artifacts, and audit logs.
- Classifies MCA keywords and known MCA funders.
- Scores records into `A_PLUS`, `A`, `B`, `C`, `D`, or `EXCLUDE`.
- Supports buyer accounts and buyer rules for reviewed leads.
- Captures separate opt-in MCA defense form leads with express consent evidence.
- Provides demo-ready seed data for investor and client walkthroughs.

## Compliance Guardrails

- Do not bypass CAPTCHAs, logins, paywalls, or access controls.
- Do not create fake accounts.
- Do not automate sources when source terms prohibit automation.
- Live adapters are disabled by default with `ENABLE_LIVE_ADAPTERS=false`.
- Every adapter supports `mock`, `manual_import`, and gated `live_if_allowed` modes.
- Do not store SSNs, bank account numbers, full DOBs, or sensitive identifiers.
- Sensitive values such as IP addresses are hashed before storage.
- Suppression, exclusion, consent, and audit records are first-class workflow data.
- This product is for attorney intelligence and opt-in leads, not cold-call or
  cold-text solicitation.
- Public-record signals and opt-in form leads are separate data paths.

## Local Setup

Prerequisites:

- Docker Desktop with Docker Compose
- Python 3.12 for local testing
- `make` for the Makefile commands

Start from a fresh checkout:

```bash
cp .env.example .env
make up
make migrate
make seed
```

Open:

- Dashboard: <http://localhost:8000/dashboard>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

For local Python-only checks:

```bash
make install
make test
make lint
```

If running the backend outside Docker, set `DATABASE_URL` to use `localhost`
instead of the Compose service hostname `postgres`.

## Using This Project In Visual Studio Code

1. Install VS Code.
2. Install the OpenAI Codex IDE extension from the official VS Code Marketplace
   or current OpenAI instructions.
3. Open `mca-legal-signal-engine.code-workspace`, or open the project root folder.
4. Copy `.env.example` to `.env`.
5. Run **Tasks: Run Task > Docker Compose Up**.
6. Run **Tasks: Run Task > Alembic Migrate**.
7. Run **Tasks: Run Task > Seed Demo Data**.
8. Open FastAPI docs at <http://localhost:8000/docs>.
9. Run tests with **Tasks: Run Task > Run Tests**.
10. Run exports with **Export Leads CSV** or **Export Leads XLSX**.

CSV and XLSX files created by VS Code export tasks are saved in `exports/`.
See [docs/VSCODE_SETUP.md](docs/VSCODE_SETUP.md) for a beginner-friendly guide.

## Makefile Commands

```bash
make install   # Install backend package and dev tools locally
make up        # Build and start backend, postgres, and redis
make down      # Stop the local stack
make migrate   # Run Alembic migrations inside the backend container
make seed      # Seed demo data inside the backend container
make test      # Run pytest locally
make lint      # Run Ruff and Mypy locally
make demo      # Reset DB, migrate, seed, and print demo walkthrough data
make export-csv
make export-xlsx
make export-form-leads-csv
make export-form-leads-xlsx
```

## Environment Variables

`.env.example` includes safe local defaults:

- `DATABASE_URL`
- `REDIS_URL`
- `APP_ENV`
- `ENABLE_LIVE_ADAPTERS=false`
- `STORAGE_PATH=/data/artifacts`
- `SECRET_KEY`
- `ALLOWED_ORIGINS`
- `SENSITIVE_HASH_PEPPER`
- `NY_MANUAL_IMPORT_DIR`
- `FL_MANUAL_IMPORT_DIR`
- `FL_BUSINESS_IMPORT_DIR`
- `ENABLE_LIVE_NY_ADAPTERS=false`
- `ENABLE_LIVE_FL_ADAPTERS=false`

No real credentials are required for the local demo.

## Importing Manual Source Files

Manual import is the preferred first mode for official/public sources where
automation is uncertain or restricted.

Drop downloaded files into:

```text
backend/data/imports/ny/
backend/data/imports/fl/
backend/data/imports/fl/business/
```

Adapters parse saved HTML, PDF, CSV, JSON, or text artifacts without attempting
to bypass CAPTCHA, login, payment, or access controls. Raw artifacts should be
saved before parsing so source provenance remains auditable.

## Running Mock Imports

With the backend running:

```bash
curl -X POST "http://localhost:8000/admin/import/mock?state=NY"
curl -X POST "http://localhost:8000/admin/import/mock?state=FL"
```

Then browse:

```bash
curl "http://localhost:8000/signals?state=NY&grade=A_PLUS"
curl "http://localhost:8000/signals?state=FL&grade=A_PLUS"
```

The demo seed command runs these mock imports and tops up demo data to at least:

- 25 New York sample MCA signals
- 25 Florida sample MCA signals
- 10 New York UCC signals
- 10 Florida UCC signals
- 5 buyer accounts
- 5 buyer rules
- 10 consented opt-in form leads
- 5 no-consent opt-in form leads for redaction testing
- 5 suppressed/excluded signals for export filter testing

## Running Classifier And Scorer

Mock imports and seed data automatically run MCA keyword classification, known
funder matching, lead scoring, exclusion checks, and grade assignment.

Useful API calls:

```bash
curl "http://localhost:8000/signals?min_score=90"
curl "http://localhost:8000/signals?has_document_text=true"
curl "http://localhost:8000/analytics/summary"
```

Useful local test targets:

```bash
cd backend
python -m pytest app/tests/test_mca_classifier.py app/tests/test_lead_scoring.py
python -m pytest app/tests/test_form_leads.py
```

## API Docs

FastAPI docs are available at:

- Swagger UI: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

Core endpoints:

- `GET /health`
- `GET /signals`
- `GET /signals/{id}`
- `POST /signals/{id}/review`
- `POST /signals/{id}/deliver`
- `GET /cases`
- `GET /ucc-filings`
- `GET /buyers`
- `POST /buyers`
- `POST /buyer-rules`
- `GET /analytics/summary`
- `POST /lead-form/mca-defense`
- `GET /admin/form-leads`
- `POST /admin/form-leads/{id}/route`
- `GET /exports/signals.csv`
- `GET /exports/signals.xlsx`
- `GET /exports/form-leads.csv`
- `GET /exports/form-leads.xlsx`

## Lead Exports

Exports support CSV and modern Excel `.xlsx`.

Public-record signals:

```bash
curl -L "http://localhost:8000/exports/signals.csv?state=NY&only_high_value=true" -o exports/ny_high_value_mca_signals.csv
curl -L "http://localhost:8000/exports/signals.xlsx?state=FL&only_high_value=true" -o exports/fl_high_value_mca_signals.xlsx
```

Opt-in form leads:

```bash
curl -L "http://localhost:8000/exports/form-leads.csv?only_high_value=true" -o exports/opt_in_mca_leads.csv
curl -L "http://localhost:8000/exports/form-leads.xlsx?only_high_value=true" -o exports/opt_in_mca_leads.xlsx
```

CLI examples:

```bash
cd backend
python -m app.scripts.export_leads --type signals --format csv --state NY --only-high-value --output ../exports/ny_high_value_mca_signals.csv
python -m app.scripts.export_leads --type signals --format xlsx --state FL --only-high-value --output ../exports/fl_high_value_mca_signals.xlsx
python -m app.scripts.export_leads --type signals --format xlsx --states NY FL --min-score 75 --output ../exports/ny_fl_mca_signals.xlsx
python -m app.scripts.export_leads --type form-leads --format csv --only-high-value --output ../exports/opt_in_mca_leads.csv
```

XLSX exports include `Signals` or `Form Leads`, `Summary`, and
`Export Metadata` sheets. Header rows are frozen, bolded, filtered, and
auto-sized. No-consent form leads redact contact fields as
`NO_CONSENT_REDACTED`.

## Demo Script

Run a full reset and demo seed:

```bash
make demo
```

The script:

1. Downgrades the database to base.
2. Applies all Alembic migrations.
3. Seeds mock/demo data.
4. Prints the dashboard URL.
5. Prints top A+ NY and FL signals.
6. Prints the analytics summary.

## Deployment Notes

- Keep live adapters disabled until source-specific terms review is complete.
- Use a real `SECRET_KEY` and `SENSITIVE_HASH_PEPPER` outside local demos.
- Mount durable storage for `/data/artifacts`.
- Run migrations before deploying new app code.
- Put the backend behind TLS and an authenticated admin boundary before handling
  real opt-in submissions.
- Configure production logging retention for audit and consent events.
- Use managed Postgres and Redis for production environments.

## Future Adapters

Planned source areas:

- NYSCEF manual import expansion for case documents.
- New York UCC licensed/manual bulk workflows.
- Florida E-Filing Portal manual import templates.
- Florida Secured Transaction Registry manual import templates.
- Florida Sunbiz data-download enrichment.
- County clerk manual import adapters for Miami-Dade, Broward, Palm Beach,
  Orange, Hillsborough, Pinellas, Duval, Polk, Lee, Collier, Seminole, and
  Osceola.
- Federal bankruptcy MCA creditor matching.
