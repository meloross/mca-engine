.PHONY: install up down logs logs-worker logs-scheduler migrate seed test lint demo run-worker run-scheduler worker scheduler enqueue-demo-leads enqueue-enrichment sync-google-sheets live-demo live-harvest live-harvest-dry-run live-harvest-ny live-harvest-fl export-csv export-xlsx export-form-leads-csv export-form-leads-xlsx

install:
	cd backend && python -m pip install -e ".[dev]"

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f backend

logs-worker:
	docker compose logs -f worker

logs-scheduler:
	docker compose logs -f scheduler

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python -m app.jobs.seed_demo

test:
	cd backend && python -m pytest

lint:
	cd backend && python -m ruff check .
	cd backend && python -m mypy app

run-worker:
	cd backend && python -m app.scripts.worker

run-scheduler:
	cd backend && python -m app.scripts.scheduler

worker: run-worker

scheduler: run-scheduler

enqueue-demo-leads:
	cd backend && python -m app.scripts.enqueue_jobs --job demo_leads --count 10

enqueue-enrichment:
	cd backend && python -m app.scripts.enqueue_jobs --job enrichment

sync-google-sheets:
	cd backend && python -m app.scripts.sync_google_sheets --all

live-demo:
	cd backend && python -m app.scripts.enqueue_jobs --job demo_leads --count 10 --interval-seconds 5

live-harvest:
	cd backend && python -m app.scripts.run_live_mca_harvest --target 100

live-harvest-dry-run:
	cd backend && python -m app.scripts.run_live_mca_harvest --target 100 --dry-run --no-export

live-harvest-ny:
	cd backend && python -m app.scripts.run_live_mca_harvest --state NY --target 100

live-harvest-fl:
	cd backend && python -m app.scripts.run_live_mca_harvest --state FL --target 100

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
