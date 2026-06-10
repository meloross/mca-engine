.PHONY: install up down migrate seed test lint demo export-csv export-xlsx export-form-leads-csv export-form-leads-xlsx

install:
	cd backend && python -m pip install -e ".[dev]"

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python -m app.jobs.seed_demo

test:
	cd backend && python -m pytest

lint:
	cd backend && python -m ruff check .
	cd backend && python -m mypy app

demo:
	docker compose exec backend python -m app.jobs.demo

export-csv:
	cd backend && python -m app.scripts.export_leads --type signals --format csv --states NY FL --only-high-value --output ../exports/ny_fl_high_value_mca_signals.csv

export-xlsx:
	cd backend && python -m app.scripts.export_leads --type signals --format xlsx --states NY FL --only-high-value --output ../exports/ny_fl_high_value_mca_signals.xlsx

export-form-leads-csv:
	cd backend && python -m app.scripts.export_leads --type form-leads --format csv --only-high-value --output ../exports/opt_in_mca_leads.csv

export-form-leads-xlsx:
	cd backend && python -m app.scripts.export_leads --type form-leads --format xlsx --only-high-value --output ../exports/opt_in_mca_leads.xlsx
