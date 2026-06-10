from __future__ import annotations

from app.adapters.florida.fl_ucc_live import FloridaUccLiveAdapter
from app.adapters.ucc import contains_access_barrier, dedupe_ucc_records, parse_ucc_search_html


def test_ucc_parser_detects_access_barriers() -> None:
    assert contains_access_barrier("<html>Please complete CAPTCHA</html>")
    assert not contains_access_barrier("<table><tr><td>public data</td></tr></table>")


def test_ucc_parser_reads_data_record_rows_and_dedupes() -> None:
    html = """
    <table>
      <tr data-record="ucc">
        <td data-field="filing_number">FL-100</td>
        <td data-field="filing_type">Initial</td>
        <td data-field="filing_date">2026-06-01</td>
        <td data-field="debtor_name">Biscayne Bistro LLC</td>
        <td data-field="secured_party_name">Cloudfund LLC</td>
        <td data-field="collateral_text">Merchant cash advance receivables</td>
      </tr>
      <tr data-record="ucc">
        <td data-field="filing_number">FL-100</td>
        <td data-field="filing_type">Initial</td>
        <td data-field="filing_date">2026-06-01</td>
        <td data-field="debtor_name">Biscayne Bistro LLC</td>
        <td data-field="secured_party_name">Cloudfund LLC</td>
      </tr>
    </table>
    """

    records = dedupe_ucc_records(
        parse_ucc_search_html(
            html,
            state="FL",
            secured_party_name="Cloudfund",
            source_url="https://floridaucc.com/search",
        )
    )

    assert len(records) == 1
    assert records[0].filing_number == "FL-100"
    assert records[0].debtor_name == "Biscayne Bistro LLC"
    assert records[0].secured_party_name == "Cloudfund LLC"


def test_ucc_live_adapter_blocks_captcha_without_bypass() -> None:
    result = FloridaUccLiveAdapter().run_html(
        "<html>reCAPTCHA challenge</html>",
        secured_party_name="Cloudfund",
    )

    assert result.status == "blocked"
    assert result.records == ()
