# Using MCA Legal Signal Engine In Visual Studio Code

This guide is for opening, running, debugging, testing, and exporting MCA legal
leads from VS Code.

## 1. Install Tools

Install:

- Visual Studio Code
- Docker Desktop
- Python 3.12
- Git, if you want source control features

Install the OpenAI Codex IDE extension from the official VS Code Marketplace or
from current OpenAI setup instructions. This repo does not pin an extension ID
because extension identifiers can change.

When VS Code opens the project, it will recommend Python, Pylance, Ruff, Docker,
Dev Containers, YAML, and GitHub Actions extensions.

## 2. Open The Workspace

From VS Code:

1. Select **File > Open Workspace from File**.
2. Open `mca-legal-signal-engine.code-workspace`.
3. Confirm you can see these folders:
   - `project-root`
   - `backend`
   - `docs`
   - `exports`

You can also open the project root folder directly.

## 3. Configure Local Environment

Copy the sample env file:

```bash
cp .env.example .env
```

On PowerShell:

```powershell
Copy-Item .env.example .env
```

Live adapters are disabled by default:

```text
ENABLE_LIVE_ADAPTERS=false
```

No real credentials are required for local demos.

## 4. Start The App

Open the VS Code Command Palette and run:

```text
Tasks: Run Task
```

Run these tasks in order:

1. `Docker Compose Up`
2. `Alembic Migrate`
3. `Seed Demo Data`

Then open:

- Dashboard: <http://localhost:8000/dashboard>
- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

## 5. Debug The Backend

Use the **Run and Debug** panel.

Available debug configs:

- `Debug FastAPI Backend`
- `Debug Current Python File`
- `Debug Pytest Current Test File`

The project does not currently include a Celery or RQ worker, so no worker debug
configuration is required yet.

## 6. Run Tests And Linters

From **Tasks: Run Task**:

- `Run Tests`
- `Run Ruff`
- `Run Mypy`

You can also run a single test file with the `Debug Pytest Current Test File`
configuration.

## 7. Import Mock Leads

With the backend running:

- Run `Import Mock NY Leads`
- Run `Import Mock FL Leads`

These tasks call the mock import API. They do not access live court, UCC, or
business registry systems.

## 8. Export Leads

Use these VS Code tasks:

- `Export Leads CSV`
- `Export Leads XLSX`

Files are saved under:

```text
exports/
```

You can also call the API directly:

```text
http://localhost:8000/exports/signals.csv?state=NY&only_high_value=true
http://localhost:8000/exports/signals.xlsx?state=FL&only_high_value=true
http://localhost:8000/exports/form-leads.csv?only_high_value=true
http://localhost:8000/exports/form-leads.xlsx?only_high_value=true
```

Or run the CLI:

```bash
cd backend
python -m app.scripts.export_leads --type signals --format csv --state NY --only-high-value --output ../exports/ny_high_value_mca_signals.csv
python -m app.scripts.export_leads --type form-leads --format xlsx --only-high-value --output ../exports/opt_in_mca_leads.xlsx
```

## 9. Dev Container

If you use Dev Containers:

1. Install the VS Code Dev Containers extension.
2. Run **Dev Containers: Reopen in Container**.
3. Wait for `postCreateCommand` to install backend dependencies.

The dev container uses the backend service from `docker-compose.yml` and includes
Python 3.12, PostgreSQL client tools, and Redis tools.

## 10. Compliance Reminder

Exports are for attorney intelligence and consented opt-in lead review. They are
not cold-call or cold-text lists. Users are responsible for attorney advertising,
solicitation, privacy, TCPA, CAN-SPAM, and other applicable rules.
