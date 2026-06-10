from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import settings
from app.events import publish_event
from app.exports import ExportFilters, export_signals_bytes
from app.harvest.funder_queries import load_funder_queries
from app.harvest.run_state import HarvestRunState
from app.harvest.source_policy import (
    check_source_policy,
    ensure_default_source_policies,
    list_source_policies,
)
from app.harvest.source_runner import SourceRunResult, run_source
from app.integrations.google_sheets import GoogleSheetsSyncService
from app.models import AuditLog, SourcePolicy, SourcePolicyStatus


@dataclass(frozen=True)
class LiveHarvestResult:
    status: str
    run_id: str
    summary: dict[str, object]
    export_paths: tuple[str, ...] = ()
    messages: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "run_id": self.run_id,
            "summary": self.summary,
            "export_paths": list(self.export_paths),
            "messages": list(self.messages),
        }


class LiveHarvester:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run(
        self,
        *,
        states: tuple[str, ...] = ("NY", "FL"),
        target: int = 100,
        dry_run: bool = False,
        enrich: bool = True,
        sync_google_sheets: bool = False,
        export: bool = True,
    ) -> LiveHarvestResult:
        normalized_states = tuple(dict.fromkeys(state.upper() for state in states or ("NY", "FL")))
        run_state = HarvestRunState(
            run_id=f"LIVE-{datetime.now(UTC):%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
            states=normalized_states,
            target=target,
            dry_run=dry_run,
        )
        self._audit("live_harvest_started", run_state.run_id, run_state.as_dict())
        publish_event("harvest_started", run_state.as_dict())
        if not settings.enable_live_adapters:
            message = "ENABLE_LIVE_ADAPTERS=false; live harvest skipped."
            run_state.add_log("ALL", "skipped", message)
            run_state.finish()
            result = self._finish(run_state, "skipped", messages=(message,))
            self.session.commit()
            return result

        ensure_default_source_policies(self.session)
        funder_queries = load_funder_queries(self.session)
        policies = self._candidate_policies(normalized_states)
        for policy in policies:
            run_state.sources_checked += 1
            check_source_policy(self.session, policy.source_code, actor="live_harvester")
            if not self._state_feature_enabled(policy):
                self._skip_policy(run_state, policy, "State-level live adapter flag is disabled.")
                continue
            if policy.status == SourcePolicyStatus.BLOCKED_BY_TERMS:
                self._skip_policy(run_state, policy, policy.status_reason or "Blocked by terms.")
                continue
            if not policy.live_enabled or policy.status != SourcePolicyStatus.ACTIVE:
                self._skip_policy(
                    run_state,
                    policy,
                    policy.status_reason or "Source policy is not enabled for live acquisition.",
                )
                continue
            publish_event(
                "source_started",
                {"run_id": run_state.run_id, "source_code": policy.source_code},
            )
            source_result = run_source(
                self.session,
                policy,
                funder_queries=funder_queries,
                target=max(1, target - run_state.leads_created),
                dry_run=dry_run,
            )
            self._apply_source_result(run_state, source_result)
            publish_event(
                "source_finished",
                {"run_id": run_state.run_id, **_source_result_payload(source_result)},
            )
            self.session.commit()
            if run_state.leads_created >= target:
                break

        export_paths: tuple[str, ...] = ()
        if export and not dry_run:
            export_paths = self._write_exports(run_state)
        if sync_google_sheets and not dry_run:
            self._sync_google_sheets(run_state)
        if enrich:
            run_state.add_log(
                "ENRICHMENT",
                "scheduled",
                "Enrichment remains policy-gated and can be run by the worker queue.",
            )
        run_state.finish()
        status = "ok" if run_state.errors_count == 0 else "partial"
        result = self._finish(run_state, status, export_paths=export_paths)
        self.session.commit()
        return result

    def _candidate_policies(self, states: tuple[str, ...]) -> list[SourcePolicy]:
        return [
            policy
            for policy in list_source_policies(self.session)
            if policy.state is None or policy.state in states
        ]

    def _skip_policy(self, run_state: HarvestRunState, policy: SourcePolicy, message: str) -> None:
        run_state.sources_skipped += 1
        run_state.add_log(policy.source_code, "skipped", message)
        event_type = (
            "source_blocked"
            if policy.status == SourcePolicyStatus.BLOCKED_BY_TERMS
            else "source_skipped"
        )
        publish_event(
            event_type,
            {"run_id": run_state.run_id, "source_code": policy.source_code, "message": message},
        )

    def _apply_source_result(
        self,
        run_state: HarvestRunState,
        source_result: SourceRunResult,
    ) -> None:
        if source_result.status in {"ok", "partial"}:
            run_state.sources_run += 1
        else:
            run_state.sources_skipped += 1
        run_state.records_seen += source_result.records_seen
        run_state.records_created += source_result.records_created
        run_state.records_updated += source_result.records_updated
        run_state.leads_created += source_result.leads_created
        run_state.leads_updated += source_result.leads_updated
        run_state.business_entities_seen += source_result.business_entities_seen
        run_state.business_entities_updated += source_result.business_entities_updated
        run_state.errors_count += source_result.errors_count
        run_state.add_log(
            source_result.source_code,
            source_result.status,
            source_result.message,
            records_seen=source_result.records_seen,
            leads_created=source_result.leads_created,
            errors=list(source_result.errors),
            metadata=source_result.metadata,
        )

    def _write_exports(self, run_state: HarvestRunState) -> tuple[str, ...]:
        output_dir = Path("exports") / "live_harvest"
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filters = ExportFilters.from_state(states=run_state.states, only_high_value=True)
        written: list[str] = []
        for export_format in ("csv", "xlsx"):
            export_result = export_signals_bytes(
                self.session,
                filters=filters,
                export_format=export_format,
            )
            path = output_dir / f"live_mca_leads_{stamp}.{export_format}"
            path.write_bytes(export_result.content)
            written.append(str(path))
        summary_path = output_dir / f"live_mca_leads_{stamp}.summary.json"
        summary_path.write_text(
            json.dumps(run_state.as_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        written.append(str(summary_path))
        run_state.add_log("EXPORT", "ok", "Wrote live harvest exports.", paths=written)
        return tuple(written)

    def _sync_google_sheets(self, run_state: HarvestRunState) -> None:
        if not settings.google_sheets_enabled:
            run_state.add_log("GOOGLE_SHEETS", "skipped", "GOOGLE_SHEETS_ENABLED=false")
            return
        results = GoogleSheetsSyncService(self.session).sync_all_to_master_sheet()
        run_state.add_log(
            "GOOGLE_SHEETS",
            "ok",
            "Synced live harvest data to Google Sheets.",
            results={key: value.appended for key, value in results.items()},
        )

    def _finish(
        self,
        run_state: HarvestRunState,
        status: str,
        *,
        export_paths: tuple[str, ...] = (),
        messages: tuple[str, ...] = (),
    ) -> LiveHarvestResult:
        payload = run_state.as_dict()
        payload["export_paths"] = list(export_paths)
        self._audit("live_harvest_finished", run_state.run_id, payload)
        publish_event("harvest_finished", payload)
        return LiveHarvestResult(
            status=status,
            run_id=run_state.run_id,
            summary=payload,
            export_paths=export_paths,
            messages=messages,
        )

    def _audit(self, action: str, entity_id: str, metadata: dict[str, object]) -> None:
        self.session.add(
            AuditLog(
                actor="live_harvester",
                action=action,
                entity_type="live_harvest",
                entity_id=entity_id,
                event_metadata=metadata,
            )
        )

    def _state_feature_enabled(self, policy: SourcePolicy) -> bool:
        if policy.state == "NY":
            return settings.enable_live_ny_adapters
        if policy.state == "FL":
            return settings.enable_live_fl_adapters
        return True


def _source_result_payload(result: SourceRunResult) -> dict[str, object]:
    return {
        "source_code": result.source_code,
        "status": result.status,
        "message": result.message,
        "records_seen": result.records_seen,
        "records_created": result.records_created,
        "records_updated": result.records_updated,
        "leads_created": result.leads_created,
        "leads_updated": result.leads_updated,
        "business_entities_seen": result.business_entities_seen,
        "business_entities_updated": result.business_entities_updated,
        "errors": list(result.errors),
        "metadata": result.metadata,
    }
