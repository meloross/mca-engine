from __future__ import annotations

from html import escape
from typing import Annotated, Any
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.signals import _filtered_signal_statement
from app.db import get_session
from app.models import BuyerAccount, LeadSignal
from app.services.presentation import serialize_buyer, serialize_signal

router = APIRouter(tags=["dashboard"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/", response_class=HTMLResponse)
def dashboard_root() -> HTMLResponse:
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/dashboard">')


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_signals(
    session: SessionDependency,
    state: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    county: str | None = None,
    grade: str | None = None,
    min_score: int | None = None,
    signal_type: str | None = None,
    funder_name: str | None = None,
    business_name: str | None = None,
    status: str | None = None,
) -> HTMLResponse:
    statement = (
        _filtered_signal_statement(
            state=state,
            county=county,
            grade=grade,
            min_score=min_score,
            signal_type=signal_type,
            funder_name=funder_name,
            business_name=business_name,
            date_from=None,
            date_to=None,
            status=status,
            has_document_text=None,
        )
        .order_by(LeadSignal.signal_date.desc(), LeadSignal.score.desc())
        .limit(100)
    )
    signals = [serialize_signal(session, signal) for signal in session.scalars(statement).all()]
    return HTMLResponse(_layout("Signals", _signals_page(signals, locals())))


@router.get("/dashboard/signals/{signal_id}", response_class=HTMLResponse)
def dashboard_signal_detail(signal_id: UUID, session: SessionDependency) -> HTMLResponse:
    signal = session.get(LeadSignal, signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found.")
    payload = serialize_signal(session, signal, include_detail=True)
    buyers = [serialize_buyer(buyer) for buyer in session.scalars(select(BuyerAccount)).all()]
    return HTMLResponse(
        _layout(str(payload["business_name"]), _signal_detail_page(payload, buyers))
    )


@router.get("/dashboard/buyers", response_class=HTMLResponse)
def dashboard_buyers(session: SessionDependency) -> HTMLResponse:
    buyers = [serialize_buyer(buyer) for buyer in session.scalars(select(BuyerAccount)).all()]
    return HTMLResponse(_layout("Buyers", _buyers_page(buyers)))


def _signals_page(signals: list[dict[str, Any]], params: dict[str, Any]) -> str:
    rows = "".join(
        _signal_row(signal)
        for signal in signals
    )
    return f"""
    <section class="toolbar">
      <form method="get" action="/dashboard" class="filters">
        {_input("state", params.get("state"), "State")}
        {_input("county", params.get("county"), "County")}
        {_select("grade", params.get("grade"), ["", "A_PLUS", "A", "B", "C", "D", "EXCLUDE"])}
        {_input("min_score", params.get("min_score"), "Min score", "number")}
        {_input("funder_name", params.get("funder_name"), "Funder")}
        {_input("business_name", params.get("business_name"), "Business")}
        {
        _select(
            "status",
            params.get("status"),
            ["", "new", "reviewed", "delivered", "suppressed", "excluded"],
        )
    }
        <button type="submit">Filter</button>
        <a class="button" href="/dashboard?grade=A_PLUS">A+</a>
        <a class="button" href="/dashboard?grade=A">A</a>
      </form>
      {_export_links(params)}
      <nav class="exports">
        <button type="button" onclick="syncSheet('/admin/sync/google-sheets/all')">
          Sync All to Google Sheet
        </button>
        <button type="button" onclick="syncSheet('/admin/sync/google-sheets/leads')">
          Sync Current Filter to Google Sheet
        </button>
      </nav>
    </section>
    <table>
      <thead>
        <tr>
          <th>Lead Ref</th><th>Batch</th><th>Business</th><th>State</th><th>County</th>
          <th>Grade</th><th>Score</th><th>Funder</th><th>Type</th><th>Status</th><th>Date</th>
          <th>Source Name</th><th>Source URL</th><th>Captured</th><th>Sheet Status</th>
          <th>Exported</th><th>Last Synced</th>
        </tr>
      </thead>
      <tbody>{rows or '<tr><td colspan="17">No signals</td></tr>'}</tbody>
    </table>
    <script>
      async function syncSheet(path) {{
        const response = await fetch(path, {{method: 'POST'}});
        alert(JSON.stringify(await response.json(), null, 2));
        location.reload();
      }}
      async function copyText(value) {{
        await navigator.clipboard.writeText(value);
      }}
    </script>
    """


def _signal_row(signal: dict[str, Any]) -> str:
    lead_reference_id = _h(signal["lead_reference_id"])
    batch_number = _h(signal["batch_number"])
    return f"""
        <tr>
          <td>
            <code>{lead_reference_id}</code>
            <button class="mini" onclick="copyText('{lead_reference_id}')">Copy</button>
          </td>
          <td>
            <code>{batch_number}</code>
            <button class="mini" onclick="copyText('{batch_number}')">Copy</button>
          </td>
          <td><a href="/dashboard/signals/{_h(signal["id"])}">{_h(signal["business_name"])}</a></td>
          <td>{_h(signal["state"])}</td>
          <td>{_h(signal["county"])}</td>
          <td>{_h(signal["grade"])}</td>
          <td>{_h(signal["score"])}</td>
          <td>{_h(signal["funder_name"])}</td>
          <td>{_h(signal["signal_type"])}</td>
          <td>{_h(signal["status"])}</td>
          <td>{_h(signal["signal_date"])}</td>
          <td>{_h(signal["source_name"])}</td>
          <td><a href="{_h(signal["source_url"])}" rel="noreferrer">Source</a></td>
          <td>{_h(signal["source_captured_at"])}</td>
          <td>{_h(signal["master_sheet_sync_status"])}</td>
          <td>{_h(signal["exported_to_master_sheet"])}</td>
          <td>{_h(signal["master_sheet_synced_at"])}</td>
        </tr>
        """


def _export_links(params: dict[str, Any]) -> str:
    query = _filter_query(params)
    suffix = f"?{query}" if query else ""
    return f"""
    <nav class="exports">
      <a class="button" href="/exports/signals.csv{suffix}">Export Current Filter as CSV</a>
      <a class="button" href="/exports/signals.xlsx{suffix}">Export Current Filter as XLSX</a>
      <a class="button" href="/exports/signals.csv?state=NY&only_high_value=true">
        Export A/A+ NY Leads
      </a>
      <a class="button" href="/exports/signals.csv?state=FL&only_high_value=true">
        Export A/A+ FL Leads
      </a>
      <a class="button" href="/exports/form-leads.csv?only_high_value=true">
        Export Opt-In Leads CSV
      </a>
      <a class="button" href="/exports/form-leads.xlsx?only_high_value=true">
        Export Opt-In Leads XLSX
      </a>
    </nav>
    """


def _filter_query(params: dict[str, Any]) -> str:
    allowed = {
        "state",
        "county",
        "grade",
        "min_score",
        "signal_type",
        "funder_name",
        "business_name",
        "status",
    }
    return urlencode(
        {
            key: value
            for key, value in params.items()
            if key in allowed and value not in (None, "")
        }
    )


def _signal_detail_page(signal: dict[str, Any], buyers: list[dict[str, Any]]) -> str:
    case_panel = _panel("Case", _key_values(signal["case"])) if signal.get("case") else ""
    ucc_panel = _panel("UCC", _key_values(signal["ucc_filing"])) if signal.get("ucc_filing") else ""
    lead_reference_id = _h(signal["lead_reference_id"])
    batch_number = _h(signal["batch_number"])
    buyer_options = "".join(
        f'<option value="{_h(buyer["id"])}">{_h(buyer["firm_name"])}</option>' for buyer in buyers
    )
    return f"""
    <section class="detail-head">
      <div>
        <a href="/dashboard">Signals</a>
        <h1>{_h(signal["business_name"])}</h1>
        <p>{_h(signal["title"])}</p>
      </div>
      <div class="score">
        <strong>{_h(signal["grade"])}</strong>
        <span>{_h(signal["score"])}</span>
      </div>
    </section>
    <section class="grid">
      {
        _panel(
            "Signal",
            _key_values(signal, skip={"case", "ucc_filing", "deliveries", "audit_log"}),
        )
    }
      {_panel("MCA Keyword Hits", _list(signal.get("keyword_hits", [])))}
      {_panel("Score Explanation", _list(signal.get("score_reasons", [])))}
      {_panel("Compliance Flags", _list(signal.get("compliance_flags", [])))}
      {case_panel}
      {ucc_panel}
    </section>
    <section class="actions">
      <button onclick="copyText('{lead_reference_id}')">Copy Lead Reference ID</button>
      <button onclick="copyText('{batch_number}')">Copy Batch Number</button>
      <button onclick="reviewSignal('reviewed')">Reviewed</button>
      <button onclick="reviewSignal('suppressed')">Suppress</button>
      <button onclick="reviewSignal('excluded')">Exclude</button>
      <select id="buyer">{buyer_options}</select>
      <select id="delivery">
        <option value="dashboard">Dashboard</option>
        <option value="email">Email</option>
        <option value="webhook">Webhook</option>
        <option value="csv">CSV</option>
      </select>
      <button onclick="deliverSignal()">Deliver</button>
      <a class="button" href="{_h(signal["source_url"])}" rel="noreferrer">Source</a>
    </section>
    <script>
      async function reviewSignal(status) {{
        const notes = prompt('Notes') || '';
        const exclusion_reason = status === 'reviewed' ? null : notes || status;
        await fetch('/signals/{_h(signal["id"])}/review', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{status, notes, exclusion_reason}})
        }});
        location.reload();
      }}
      async function deliverSignal() {{
        const buyer_account_id = document.getElementById('buyer').value;
        const delivery_method = document.getElementById('delivery').value;
        await fetch('/signals/{_h(signal["id"])}/deliver', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{buyer_account_id, delivery_method}})
        }});
        location.reload();
      }}
      async function copyText(value) {{
        await navigator.clipboard.writeText(value);
      }}
    </script>
    """


def _buyers_page(buyers: list[dict[str, Any]]) -> str:
    rows = "".join(
        f"""
        <tr>
          <td>{_h(buyer["firm_name"])}</td>
          <td>{_h(buyer["contact_name"])}</td>
          <td>{_h(buyer["email"])}</td>
          <td>{_h(", ".join(buyer["states"]))}</td>
          <td>{_h(", ".join(buyer["practice_tags"]))}</td>
          <td>{_h(buyer["active"])}</td>
        </tr>
        """
        for buyer in buyers
    )
    return f"""
    <a href="/dashboard">Signals</a>
    <table>
      <thead><tr><th>Firm</th><th>Contact</th><th>Email</th><th>States</th><th>Tags</th><th>Active</th></tr></thead>
      <tbody>{rows or '<tr><td colspan="6">No buyers</td></tr>'}</tbody>
    </table>
    """


def _layout(title: str, body: str) -> str:
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{_h(title)} | MCA Legal Signal Engine</title>
        <style>{_css()}</style>
      </head>
      <body>
        <header>
          <strong>MCA Legal Signal Engine</strong>
          <a href="/dashboard">Signals</a>
          <a href="/dashboard/buyers">Buyers</a>
          <a href="/analytics/summary">Analytics</a>
        </header>
        <main>{body}</main>
      </body>
    </html>
    """


def _input(name: str, value: object, placeholder: str, input_type: str = "text") -> str:
    return (
        f'<input type="{_h(input_type)}" name="{_h(name)}" value="{_h(value or "")}" '
        f'placeholder="{_h(placeholder)}">'
    )


def _select(name: str, value: object, options: list[str]) -> str:
    rendered = ""
    for option in options:
        selected = " selected" if str(value or "") == option else ""
        label = option or name.replace("_", " ").title()
        rendered += f'<option value="{_h(option)}"{selected}>{_h(label)}</option>'
    return f'<select name="{_h(name)}">{rendered}</select>'


def _panel(title: str, content: str) -> str:
    return f'<section class="panel"><h2>{_h(title)}</h2>{content}</section>'


def _key_values(value: object, *, skip: set[str] | None = None) -> str:
    skip = skip or set()
    if not isinstance(value, dict):
        return "<p>None</p>"
    items = ""
    for key, item in value.items():
        if key in skip or item in (None, "", [], {}):
            continue
        if isinstance(item, list):
            item = ", ".join(str(entry) for entry in item)
        items += f"<dt>{_h(key)}</dt><dd>{_h(item)}</dd>"
    return f"<dl>{items}</dl>" if items else "<p>None</p>"


def _list(values: object) -> str:
    if not isinstance(values, list) or not values:
        return "<p>None</p>"
    return "<ul>" + "".join(f"<li>{_h(value)}</li>" for value in values) + "</ul>"


def _h(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)


def _css() -> str:
    return "\n".join(
        (
            "body { margin: 0; font: 14px/1.45 system-ui, sans-serif;",
            "  background: #f7f8fa; color: #1b1f24; }",
            "header { background: #17202a; color: white; padding: 14px 24px;",
            "  display: flex; gap: 20px; align-items: center; }",
            "header a { color: white; text-decoration: none; }",
            "main { padding: 24px; }",
            "table { width: 100%; border-collapse: collapse; background: white; }",
            "th, td { padding: 10px; border-bottom: 1px solid #e4e7ec;",
            "  text-align: left; vertical-align: top; }",
            "th { font-size: 12px; text-transform: uppercase; color: #667085; }",
            "input, select, button, .button { padding: 8px 10px;",
            "  border: 1px solid #cfd6df; border-radius: 6px; background: white; }",
            "button, .button { cursor: pointer; text-decoration: none; color: #17202a; }",
            ".mini { padding: 3px 6px; margin-left: 4px; font-size: 11px; }",
            "code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }",
            ".filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }",
            ".exports { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 16px; }",
            ".detail-head { display: flex; justify-content: space-between;",
            "  gap: 16px; align-items: start; }",
            ".score { background: white; padding: 16px; min-width: 120px;",
            "  text-align: center; }",
            ".score strong { display: block; font-size: 28px; }",
            ".score span { font-size: 22px; }",
            ".grid { display: grid; grid-template-columns: repeat(auto-fit,",
            "  minmax(280px, 1fr)); gap: 14px; }",
            ".panel { background: white; padding: 14px; border: 1px solid #e4e7ec; }",
            ".panel h2 { margin-top: 0; font-size: 15px; }",
            ".actions { margin: 18px 0; display: flex; flex-wrap: wrap; gap: 8px; }",
            "dl { display: grid; grid-template-columns: 120px 1fr; gap: 6px 10px; }",
            "dt { color: #667085; }",
            "dd { margin: 0; overflow-wrap: anywhere; }",
        )
    )
