from __future__ import annotations

from html import escape

MOCK_NYSCEF_NEW_CASES: tuple[dict[str, object], ...] = (
    {
        "court_name": "Supreme Court, Kings County",
        "county": "Kings",
        "case_number": "501001/2026",
        "caption": "Yellowstone Capital LLC v. Bella Pizza LLC and Maria Gomez",
        "filing_date": "2026-06-07",
        "case_type": "Commercial",
        "plaintiff_names": ["Yellowstone Capital LLC"],
        "defendant_names": ["Bella Pizza LLC", "Maria Gomez"],
        "source_url": "https://iapps.courts.state.ny.us/nyscef/CaseSearch?case=501001/2026",
        "document_text": (
            "Complaint alleges breach of merchant agreement, revenue purchase agreement, "
            "daily ACH debit, purchased amount, and confession of judgment."
        ),
    },
    {
        "court_name": "Supreme Court, New York County",
        "county": "New York",
        "case_number": "652110/2026",
        "caption": "ABC Merchant Solutions LLC v. Midtown Deli Group Inc.",
        "filing_date": "2026-06-06",
        "case_type": "Commercial",
        "plaintiff_names": ["ABC Merchant Solutions LLC"],
        "defendant_names": ["Midtown Deli Group Inc."],
        "source_url": "https://iapps.courts.state.ny.us/nyscef/CaseSearch?case=652110/2026",
        "document_text": (
            "Merchant cash advance dispute involving future receivables, remittance, "
            "and personal guaranty."
        ),
    },
    {
        "court_name": "Supreme Court, Queens County",
        "county": "Queens",
        "case_number": "703210/2026",
        "caption": "Capital Advance Services Inc. v. Queens Auto Repair LLC",
        "filing_date": "2026-06-05",
        "case_type": "Commercial",
        "plaintiff_names": ["Capital Advance Services Inc."],
        "defendant_names": ["Queens Auto Repair LLC"],
        "source_url": "https://iapps.courts.state.ny.us/nyscef/CaseSearch?case=703210/2026",
        "document_text": (
            "Action on receivables purchase agreement, specified percentage, "
            "ACH debit, and default judgment."
        ),
    },
    {
        "court_name": "Supreme Court, Bronx County",
        "county": "Bronx",
        "case_number": "810410/2026E",
        "caption": "Business Advance Team LLC v. Bronx Market Corp.",
        "filing_date": "2026-06-04",
        "case_type": "Commercial",
        "plaintiff_names": ["Business Advance Team LLC"],
        "defendant_names": ["Bronx Market Corp."],
        "source_url": "https://iapps.courts.state.ny.us/nyscef/CaseSearch?case=810410/2026E",
        "document_text": (
            "Breach of merchant agreement concerning purchase and sale of future "
            "receivables and bank restraint."
        ),
    },
    {
        "court_name": "Supreme Court, Nassau County",
        "county": "Nassau",
        "case_number": "604500/2026",
        "caption": "Cloudfund LLC v. Harbor Bagel Cafe LLC",
        "filing_date": "2026-06-03",
        "case_type": "Commercial",
        "plaintiff_names": ["Cloudfund LLC"],
        "defendant_names": ["Harbor Bagel Cafe LLC"],
        "source_url": "https://iapps.courts.state.ny.us/nyscef/CaseSearch?case=604500/2026",
        "document_text": "Merchant cash advance complaint, reconciliation clause, and ACH debit.",
    },
    {
        "court_name": "Supreme Court, Suffolk County",
        "county": "Suffolk",
        "case_number": "612345/2026",
        "caption": "WCM Funding LLC v. East End Bistro LLC",
        "filing_date": "2026-06-02",
        "case_type": "Commercial",
        "plaintiff_names": ["WCM Funding LLC"],
        "defendant_names": ["East End Bistro LLC"],
        "source_url": "https://iapps.courts.state.ny.us/nyscef/CaseSearch?case=612345/2026",
        "document_text": (
            "Future receivables agreement, lockbox, payment processor, and fraudulent "
            "inducement allegations."
        ),
    },
    {
        "court_name": "Supreme Court, Westchester County",
        "county": "Westchester",
        "case_number": "550020/2026",
        "caption": "Green Capital Funding LLC v. Yonkers Grill Inc.",
        "filing_date": "2026-06-01",
        "case_type": "Commercial",
        "plaintiff_names": ["Green Capital Funding LLC"],
        "defendant_names": ["Yonkers Grill Inc."],
        "source_url": "https://iapps.courts.state.ny.us/nyscef/CaseSearch?case=550020/2026",
        "document_text": (
            "Revenue purchase agreement, purchased amount, personal guaranty, "
            "and civil usury defense referenced."
        ),
    },
    {
        "court_name": "Supreme Court, Albany County",
        "county": "Albany",
        "case_number": "905001/2026",
        "caption": "Thryve Capital Funding LLC v. Capital City Laundry LLC",
        "filing_date": "2026-05-31",
        "case_type": "Commercial",
        "plaintiff_names": ["Thryve Capital Funding LLC"],
        "defendant_names": ["Capital City Laundry LLC"],
        "source_url": "https://iapps.courts.state.ny.us/nyscef/CaseSearch?case=905001/2026",
        "document_text": "MCA remittance dispute and UCC lien enforcement.",
    },
    {
        "court_name": "Supreme Court, Erie County",
        "county": "Erie",
        "case_number": "806777/2026",
        "caption": "Fundzio LLC v. Buffalo Hardware LLC",
        "filing_date": "2026-05-30",
        "case_type": "Commercial",
        "plaintiff_names": ["Fundzio LLC"],
        "defendant_names": ["Buffalo Hardware LLC"],
        "source_url": "https://iapps.courts.state.ny.us/nyscef/CaseSearch?case=806777/2026",
        "document_text": "Accounts receivable purchase transaction and blocked account dispute.",
    },
    {
        "court_name": "Supreme Court, Monroe County",
        "county": "Monroe",
        "case_number": "E2026001234",
        "caption": "High Speed Capital LLC v. Rochester Smoothie Bar LLC",
        "filing_date": "2026-05-29",
        "case_type": "Commercial",
        "plaintiff_names": ["High Speed Capital LLC"],
        "defendant_names": ["Rochester Smoothie Bar LLC"],
        "source_url": "https://iapps.courts.state.ny.us/nyscef/CaseSearch?case=E2026001234",
        "document_text": "Merchant cash advance, weekly ACH, and deceptive practices allegations.",
    },
    {
        "court_name": "Supreme Court, Kings County",
        "county": "Kings",
        "case_number": "501120/2026",
        "caption": "Merchant Funding Services LLC v. Brooklyn Grocery Corp.",
        "filing_date": "2026-05-28",
        "case_type": "Commercial",
        "plaintiff_names": ["Merchant Funding Services LLC"],
        "defendant_names": ["Brooklyn Grocery Corp."],
        "source_url": "https://iapps.courts.state.ny.us/nyscef/CaseSearch?case=501120/2026",
        "document_text": "Receivables purchase agreement and breach of merchant agreement.",
    },
    {
        "court_name": "Supreme Court, New York County",
        "county": "New York",
        "case_number": "652220/2026",
        "caption": "Midnight Advance Capital LLC v. Soho Apparel LLC",
        "filing_date": "2026-05-27",
        "case_type": "Commercial",
        "plaintiff_names": ["Midnight Advance Capital LLC"],
        "defendant_names": ["Soho Apparel LLC"],
        "source_url": "https://iapps.courts.state.ny.us/nyscef/CaseSearch?case=652220/2026",
        "document_text": "Purchased amount, purchase price, COJ, and bank restraint.",
    },
)

MOCK_CASE_DOCUMENTS: tuple[dict[str, object], ...] = (
    {
        "case_number": "501001/2026",
        "court_name": "Supreme Court, Kings County",
        "document_title": "Verified Complaint",
        "document_type": "Complaint",
        "filed_at": "2026-06-07T10:15:00+00:00",
        "document_url": "https://iapps.courts.state.ny.us/nyscef/document/501001-complaint",
        "text_content": (
            "This complaint concerns a merchant cash advance and revenue purchase "
            "agreement with daily ACH debit remittances."
        ),
    },
    {
        "case_number": "652110/2026",
        "court_name": "Supreme Court, New York County",
        "document_title": "Summons and Complaint",
        "document_type": "Complaint",
        "filed_at": "2026-06-06T14:30:00+00:00",
        "document_url": "https://iapps.courts.state.ny.us/nyscef/document/652110-complaint",
        "text_content": "Future receivables purchase agreement and personal guaranty.",
    },
)

MOCK_NY_UCC_FILINGS: tuple[dict[str, object], ...] = (
    {
        "filing_number": "202606010001",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-01",
        "debtor_name": "Bella Pizza LLC",
        "debtor_address": "100 Flatbush Ave, Brooklyn, NY",
        "secured_party_name": "Yellowstone Capital LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "All future receivables, remittances, payment processor proceeds.",
        "source_url": "https://dos.ny.gov/uniform-commercial-code?filing=202606010001",
    },
    {
        "filing_number": "202606010002",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-01",
        "debtor_name": "Midtown Deli Group Inc.",
        "debtor_address": "40 W 34th St, New York, NY",
        "secured_party_name": "ABC Merchant Solutions LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Receivables purchase agreement, ACH debit, lockbox rights.",
        "source_url": "https://dos.ny.gov/uniform-commercial-code?filing=202606010002",
    },
    {
        "filing_number": "202606020010",
        "filing_type": "UCC-3 Amendment",
        "filing_date": "2026-06-02",
        "debtor_name": "Queens Auto Repair LLC",
        "debtor_address": "88 Northern Blvd, Queens, NY",
        "secured_party_name": "Capital Advance Services Inc.",
        "secured_party_address": "Brooklyn, NY",
        "collateral_text": "Amendment covering accounts receivable purchase transaction.",
        "source_url": "https://dos.ny.gov/uniform-commercial-code?filing=202606020010",
    },
    {
        "filing_number": "202606020011",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-02",
        "debtor_name": "Bronx Market Corp.",
        "debtor_address": "200 Fordham Rd, Bronx, NY",
        "secured_party_name": "Business Advance Team LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Future receivables and blocked account proceeds.",
        "source_url": "https://dos.ny.gov/uniform-commercial-code?filing=202606020011",
    },
    {
        "filing_number": "202606030020",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-03",
        "debtor_name": "Harbor Bagel Cafe LLC",
        "debtor_address": "12 Main St, Port Washington, NY",
        "secured_party_name": "Cloudfund LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Merchant cash advance collateral and payment processor rights.",
        "source_url": "https://dos.ny.gov/uniform-commercial-code?filing=202606030020",
    },
    {
        "filing_number": "202606030021",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-03",
        "debtor_name": "East End Bistro LLC",
        "debtor_address": "9 Ocean Rd, Southampton, NY",
        "secured_party_name": "WCM Funding LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "All receivables, remittance rights, and lockbox deposits.",
        "source_url": "https://dos.ny.gov/uniform-commercial-code?filing=202606030021",
    },
    {
        "filing_number": "202606040100",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-04",
        "debtor_name": "Yonkers Grill Inc.",
        "debtor_address": "45 Riverdale Ave, Yonkers, NY",
        "secured_party_name": "Green Capital Funding LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Purchased amount and future receivables collateral.",
        "source_url": "https://dos.ny.gov/uniform-commercial-code?filing=202606040100",
    },
    {
        "filing_number": "202606050222",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-05",
        "debtor_name": "Capital City Laundry LLC",
        "debtor_address": "1 State St, Albany, NY",
        "secured_party_name": "Thryve Capital Funding LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Revenue purchase agreement collateral and ACH debit proceeds.",
        "source_url": "https://dos.ny.gov/uniform-commercial-code?filing=202606050222",
    },
    {
        "filing_number": "202606050223",
        "filing_type": "UCC-3 Assignment",
        "filing_date": "2026-06-05",
        "debtor_name": "Buffalo Hardware LLC",
        "debtor_address": "77 Elmwood Ave, Buffalo, NY",
        "secured_party_name": "Fundzio LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Assignment of receivables purchase agreement UCC lien.",
        "source_url": "https://dos.ny.gov/uniform-commercial-code?filing=202606050223",
    },
    {
        "filing_number": "202606060333",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-06",
        "debtor_name": "Rochester Smoothie Bar LLC",
        "debtor_address": "15 Park Ave, Rochester, NY",
        "secured_party_name": "High Speed Capital LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Merchant cash advance, weekly ACH, and future receivables.",
        "source_url": "https://dos.ny.gov/uniform-commercial-code?filing=202606060333",
    },
)


def render_new_cases_html(records: tuple[dict[str, object], ...] = MOCK_NYSCEF_NEW_CASES) -> str:
    return _render_table("case", records)


def render_ucc_html(records: tuple[dict[str, object], ...] = MOCK_NY_UCC_FILINGS) -> str:
    return _render_table("ucc", records)


def render_case_document_text(record: dict[str, object] | None = None) -> str:
    selected = record or MOCK_CASE_DOCUMENTS[0]
    text = selected["text_content"]
    return "\n".join(
        (
            f"Document Title: {selected['document_title']}",
            f"Document Type: {selected['document_type']}",
            f"Filed At: {selected['filed_at']}",
            f"Document URL: {selected['document_url']}",
            "",
            "Text:",
            str(text),
        )
    )


def _render_table(record_name: str, records: tuple[dict[str, object], ...]) -> str:
    rows = []
    for record in records:
        cells = []
        for key, value in record.items():
            if isinstance(value, list):
                value = "; ".join(str(item) for item in value)
            cells.append(f'<td data-field="{escape(key)}">{escape(str(value))}</td>')
        rows.append(f'<tr data-record="{record_name}">{"".join(cells)}</tr>')
    return f"<html><body><table>{''.join(rows)}</table></body></html>"
