from __future__ import annotations

from html import escape

FL_CIVIL_FILINGS: tuple[dict[str, object], ...] = (
    {
        "county": "Miami-Dade",
        "court_name": "Miami-Dade Circuit Court",
        "case_number": "2026-CA-010001",
        "filing_date": "2026-06-07",
        "caption": "Cloudfund LLC v. Biscayne Bistro LLC",
        "plaintiff_names": ["Cloudfund LLC"],
        "defendant_names": ["Biscayne Bistro LLC"],
        "document_title": "Complaint",
        "document_text": "Merchant cash advance dispute, future receivables, and ACH debit.",
        "source_url": "https://myflcourtaccess.com/authority/filings/2026-CA-010001",
        "source_timestamp": "2026-06-07T14:00:00+00:00",
    },
    {
        "county": "Broward",
        "court_name": "Broward Circuit Court",
        "case_number": "CACE-26-010002",
        "filing_date": "2026-06-06",
        "caption": "Yellowstone Capital LLC v. Las Olas Market Inc.",
        "plaintiff_names": ["Yellowstone Capital LLC"],
        "defendant_names": ["Las Olas Market Inc."],
        "document_title": "Verified Complaint",
        "document_text": "Revenue purchase agreement, remittance, and personal guaranty.",
        "source_url": "https://myflcourtaccess.com/authority/filings/CACE-26-010002",
        "source_timestamp": "2026-06-06T13:00:00+00:00",
    },
    {
        "county": "Palm Beach",
        "court_name": "Palm Beach Circuit Court",
        "case_number": "50-2026-CA-010003",
        "filing_date": "2026-06-05",
        "caption": "WCM Funding LLC v. Atlantic Smoothies LLC",
        "plaintiff_names": ["WCM Funding LLC"],
        "defendant_names": ["Atlantic Smoothies LLC"],
        "document_title": "Complaint",
        "document_text": "Receivables purchase agreement and confession of judgment.",
        "source_url": "https://myflcourtaccess.com/authority/filings/50-2026-CA-010003",
        "source_timestamp": "2026-06-05T12:00:00+00:00",
    },
    {
        "county": "Orange",
        "court_name": "Orange Circuit Court",
        "case_number": "2026-CA-010004-O",
        "filing_date": "2026-06-04",
        "caption": "Green Capital Funding LLC v. Orlando Auto Spa LLC",
        "plaintiff_names": ["Green Capital Funding LLC"],
        "defendant_names": ["Orlando Auto Spa LLC"],
        "document_title": "Complaint",
        "document_text": "Daily ACH, purchased amount, and default judgment.",
        "source_url": "https://myflcourtaccess.com/authority/filings/2026-CA-010004-O",
        "source_timestamp": "2026-06-04T11:00:00+00:00",
    },
    {
        "county": "Hillsborough",
        "court_name": "Hillsborough Circuit Court",
        "case_number": "26-CA-010005",
        "filing_date": "2026-06-03",
        "caption": "Fundry LLC v. Tampa Tacos LLC",
        "plaintiff_names": ["Fundry LLC"],
        "defendant_names": ["Tampa Tacos LLC"],
        "document_title": "Complaint",
        "document_text": "MCA agreement, weekly ACH, and breach of merchant agreement.",
        "source_url": "https://myflcourtaccess.com/authority/filings/26-CA-010005",
        "source_timestamp": "2026-06-03T15:00:00+00:00",
    },
    {
        "county": "Pinellas",
        "court_name": "Pinellas Circuit Court",
        "case_number": "26-CA-010006",
        "filing_date": "2026-06-02",
        "caption": "Thryve Capital Funding LLC v. Gulf Coast Deli LLC",
        "plaintiff_names": ["Thryve Capital Funding LLC"],
        "defendant_names": ["Gulf Coast Deli LLC"],
        "document_title": "Complaint",
        "document_text": "Future receivables, lockbox, and bank restraint.",
        "source_url": "https://myflcourtaccess.com/authority/filings/26-CA-010006",
        "source_timestamp": "2026-06-02T15:00:00+00:00",
    },
    {
        "county": "Duval",
        "court_name": "Duval Circuit Court",
        "case_number": "16-2026-CA-010007",
        "filing_date": "2026-06-01",
        "caption": "Capital Advance Services Inc. v. River City Fitness LLC",
        "plaintiff_names": ["Capital Advance Services Inc."],
        "defendant_names": ["River City Fitness LLC"],
        "document_title": "Complaint",
        "document_text": "Purchase and sale of future receivables and ACH debit.",
        "source_url": "https://myflcourtaccess.com/authority/filings/16-2026-CA-010007",
        "source_timestamp": "2026-06-01T15:00:00+00:00",
    },
    {
        "county": "Polk",
        "court_name": "Polk Circuit Court",
        "case_number": "2026-CA-010008",
        "filing_date": "2026-05-31",
        "caption": "Merchant Funding Services LLC v. Lakeland Market LLC",
        "plaintiff_names": ["Merchant Funding Services LLC"],
        "defendant_names": ["Lakeland Market LLC"],
        "document_title": "Complaint",
        "document_text": "Accounts receivable purchase transaction and UCC lien.",
        "source_url": "https://myflcourtaccess.com/authority/filings/2026-CA-010008",
        "source_timestamp": "2026-05-31T15:00:00+00:00",
    },
    {
        "county": "Lee",
        "court_name": "Lee Circuit Court",
        "case_number": "26-CA-010009",
        "filing_date": "2026-05-30",
        "caption": "High Speed Capital LLC v. Fort Myers Cafe LLC",
        "plaintiff_names": ["High Speed Capital LLC"],
        "defendant_names": ["Fort Myers Cafe LLC"],
        "document_title": "Complaint",
        "document_text": "Merchant cash advance, payment processor, and civil usury.",
        "source_url": "https://myflcourtaccess.com/authority/filings/26-CA-010009",
        "source_timestamp": "2026-05-30T15:00:00+00:00",
    },
    {
        "county": "Collier",
        "court_name": "Collier Circuit Court",
        "case_number": "11-2026-CA-010010",
        "filing_date": "2026-05-29",
        "caption": "Fundzio LLC v. Naples Retail Group LLC",
        "plaintiff_names": ["Fundzio LLC"],
        "defendant_names": ["Naples Retail Group LLC"],
        "document_title": "Complaint",
        "document_text": "Purchased amount, purchase price, and deceptive practices.",
        "source_url": "https://myflcourtaccess.com/authority/filings/11-2026-CA-010010",
        "source_timestamp": "2026-05-29T15:00:00+00:00",
    },
    {
        "county": "Seminole",
        "court_name": "Seminole Circuit Court",
        "case_number": "2026-CA-010011",
        "filing_date": "2026-05-28",
        "caption": "Business Advance Team LLC v. Sanford Pizza LLC",
        "plaintiff_names": ["Business Advance Team LLC"],
        "defendant_names": ["Sanford Pizza LLC"],
        "document_title": "Complaint",
        "document_text": "Remittance, specified percentage, and fraudulent inducement.",
        "source_url": "https://myflcourtaccess.com/authority/filings/2026-CA-010011",
        "source_timestamp": "2026-05-28T15:00:00+00:00",
    },
    {
        "county": "Osceola",
        "court_name": "Osceola Circuit Court",
        "case_number": "2026-CA-010012",
        "filing_date": "2026-05-27",
        "caption": "ABC Merchant Solutions LLC v. Kissimmee Bakery LLC",
        "plaintiff_names": ["ABC Merchant Solutions LLC"],
        "defendant_names": ["Kissimmee Bakery LLC"],
        "document_title": "Complaint",
        "document_text": "Receivables purchase agreement, ACH debit, and COJ.",
        "source_url": "https://myflcourtaccess.com/authority/filings/2026-CA-010012",
        "source_timestamp": "2026-05-27T15:00:00+00:00",
    },
    {
        "county": "Miami-Dade",
        "court_name": "Miami-Dade Circuit Court",
        "case_number": "2026-CA-RESTRICTED",
        "filing_date": "2026-06-07",
        "caption": "Restricted Filing v. Confidential Party",
        "plaintiff_names": ["Restricted Filing LLC"],
        "defendant_names": ["Confidential Party LLC"],
        "document_title": "Restricted Complaint",
        "document_text": "Merchant cash advance text should not be parsed into a lead.",
        "source_url": "https://myflcourtaccess.com/authority/filings/restricted",
        "source_timestamp": "2026-06-07T15:00:00+00:00",
        "is_confidential": "true",
    },
)

FL_UCC_FILINGS: tuple[dict[str, object], ...] = (
    {
        "filing_number": "FL202606010001",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-01",
        "debtor_name": "Biscayne Bistro LLC",
        "debtor_address": "100 Biscayne Blvd, Miami, FL",
        "secured_party_name": "Cloudfund LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": (
            "All future receivables, ACH debit proceeds, and payment processor rights."
        ),
        "source_url": "https://floridaucc.com/search/FL202606010001",
        "source_timestamp": "2026-06-01T10:00:00+00:00",
    },
    {
        "filing_number": "FL202606010002",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-01",
        "debtor_name": "Las Olas Market Inc.",
        "debtor_address": "200 Las Olas Blvd, Fort Lauderdale, FL",
        "secured_party_name": "Yellowstone Capital LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Receivables purchase agreement, lockbox, and remittance collateral.",
        "source_url": "https://floridaucc.com/search/FL202606010002",
        "source_timestamp": "2026-06-01T10:15:00+00:00",
    },
    {
        "filing_number": "FL202606020003",
        "filing_type": "UCC-3 Amendment",
        "filing_date": "2026-06-02",
        "debtor_name": "Atlantic Smoothies LLC",
        "debtor_address": "300 Ocean Ave, Palm Beach, FL",
        "secured_party_name": "WCM Funding LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Amendment to future receivables UCC lien.",
        "source_url": "https://floridaucc.com/search/FL202606020003",
        "source_timestamp": "2026-06-02T10:00:00+00:00",
    },
    {
        "filing_number": "FL202606030004",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-03",
        "debtor_name": "Orlando Auto Spa LLC",
        "debtor_address": "400 Orange Ave, Orlando, FL",
        "secured_party_name": "Green Capital Funding LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Merchant cash advance collateral and blocked account proceeds.",
        "source_url": "https://floridaucc.com/search/FL202606030004",
        "source_timestamp": "2026-06-03T10:00:00+00:00",
    },
    {
        "filing_number": "FL202606040005",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-04",
        "debtor_name": "Tampa Tacos LLC",
        "debtor_address": "500 Kennedy Blvd, Tampa, FL",
        "secured_party_name": "Fundry LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Revenue purchase agreement and payment processor rights.",
        "source_url": "https://floridaucc.com/search/FL202606040005",
        "source_timestamp": "2026-06-04T10:00:00+00:00",
    },
    {
        "filing_number": "FL202606050006",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-05",
        "debtor_name": "Gulf Coast Deli LLC",
        "debtor_address": "600 Central Ave, St. Petersburg, FL",
        "secured_party_name": "Thryve Capital Funding LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Purchased amount, future receivables, and ACH remittance.",
        "source_url": "https://floridaucc.com/search/FL202606050006",
        "source_timestamp": "2026-06-05T10:00:00+00:00",
    },
    {
        "filing_number": "FL202606060007",
        "filing_type": "UCC-3 Assignment",
        "filing_date": "2026-06-06",
        "debtor_name": "River City Fitness LLC",
        "debtor_address": "700 Bay St, Jacksonville, FL",
        "secured_party_name": "Capital Advance Services Inc.",
        "secured_party_address": "New York, NY",
        "collateral_text": "Assignment of accounts receivable purchase transaction.",
        "source_url": "https://floridaucc.com/search/FL202606060007",
        "source_timestamp": "2026-06-06T10:00:00+00:00",
    },
    {
        "filing_number": "FL202606070008",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-07",
        "debtor_name": "Lakeland Market LLC",
        "debtor_address": "800 Lake Ave, Lakeland, FL",
        "secured_party_name": "Merchant Funding Services LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Future receivables and weekly ACH proceeds.",
        "source_url": "https://floridaucc.com/search/FL202606070008",
        "source_timestamp": "2026-06-07T10:00:00+00:00",
    },
    {
        "filing_number": "FL202606080009",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-08",
        "debtor_name": "Fort Myers Cafe LLC",
        "debtor_address": "900 First St, Fort Myers, FL",
        "secured_party_name": "High Speed Capital LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Merchant cash advance, lockbox, and payment processor.",
        "source_url": "https://floridaucc.com/search/FL202606080009",
        "source_timestamp": "2026-06-08T10:00:00+00:00",
    },
    {
        "filing_number": "FL202606090010",
        "filing_type": "UCC-1",
        "filing_date": "2026-06-09",
        "debtor_name": "Kissimmee Bakery LLC",
        "debtor_address": "1000 Main St, Kissimmee, FL",
        "secured_party_name": "ABC Merchant Solutions LLC",
        "secured_party_address": "New York, NY",
        "collateral_text": "Receivables purchase agreement and specified percentage remittance.",
        "source_url": "https://floridaucc.com/search/FL202606090010",
        "source_timestamp": "2026-06-09T10:00:00+00:00",
    },
)


def _entity_type(name: str) -> str:
    if name.endswith("LLC"):
        return "Florida Limited Liability Company"
    return "Florida Profit Corporation"


FL_BUSINESS_ENTITIES: tuple[dict[str, object], ...] = tuple(
    {
        "entity_name": name,
        "entity_type": _entity_type(name),
        "status": "ACTIVE",
        "principal_address": address,
        "registered_agent_name": f"{name.split()[0]} Registered Agent",
        "registered_agent_address": address,
        "source_url": f"https://dos.fl.gov/sunbiz/search/{index:04d}",
        "source_timestamp": "2026-06-09T08:00:00+00:00",
    }
    for index, (name, address) in enumerate(
        (
            ("Biscayne Bistro LLC", "100 Biscayne Blvd, Miami, FL"),
            ("Las Olas Market Inc.", "200 Las Olas Blvd, Fort Lauderdale, FL"),
            ("Atlantic Smoothies LLC", "300 Ocean Ave, Palm Beach, FL"),
            ("Orlando Auto Spa LLC", "400 Orange Ave, Orlando, FL"),
            ("Tampa Tacos LLC", "500 Kennedy Blvd, Tampa, FL"),
            ("Gulf Coast Deli LLC", "600 Central Ave, St. Petersburg, FL"),
            ("River City Fitness LLC", "700 Bay St, Jacksonville, FL"),
            ("Lakeland Market LLC", "800 Lake Ave, Lakeland, FL"),
            ("Fort Myers Cafe LLC", "900 First St, Fort Myers, FL"),
            ("Naples Retail Group LLC", "10 Gulf Shore Blvd, Naples, FL"),
            ("Sanford Pizza LLC", "11 First St, Sanford, FL"),
            ("Kissimmee Bakery LLC", "1000 Main St, Kissimmee, FL"),
        ),
        start=1,
    )
)


def render_civil_html(records: tuple[dict[str, object], ...] = FL_CIVIL_FILINGS) -> str:
    return _render_table("civil_filing", records)


def render_ucc_html(records: tuple[dict[str, object], ...] = FL_UCC_FILINGS) -> str:
    return _render_table("ucc", records)


def render_business_entities_csv(
    records: tuple[dict[str, object], ...] = FL_BUSINESS_ENTITIES,
) -> str:
    fields = (
        "entity_name",
        "entity_type",
        "status",
        "principal_address",
        "registered_agent_name",
        "registered_agent_address",
        "source_url",
        "source_timestamp",
    )
    rows = [",".join(fields)]
    for record in records:
        rows.append(",".join(_csv_value(record[field]) for field in fields))
    return "\n".join(rows)


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


def _csv_value(value: object) -> str:
    text = str(value).replace('"', '""')
    return f'"{text}"'
