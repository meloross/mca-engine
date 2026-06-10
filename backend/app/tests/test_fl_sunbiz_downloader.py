from __future__ import annotations

from pathlib import Path

from app.adapters.florida.fl_sunbiz_downloader import (
    FloridaSunbizDownloader,
    SunbizFile,
    match_sunbiz_records_to_leads,
    parse_sunbiz_business_text,
)


def test_sunbiz_download_page_lists_official_files() -> None:
    downloader = FloridaSunbizDownloader()
    files = downloader.list_available_files(
        """
        <a href="/sunbiz/downloads/corp_daily.zip">Corporate Daily File</a>
        <a href="/not-relevant.pdf">PDF</a>
        """
    )

    assert files == [
        SunbizFile(
            url="https://dos.fl.gov/sunbiz/downloads/corp_daily.zip",
            filename="corp_daily.zip",
        )
    ]


def test_sunbiz_parser_matches_lead_business_names() -> None:
    records = parse_sunbiz_business_text(
        "\n".join(
            (
                "entity_name,entity_type,status,principal_address,registered_agent_name,source_url",
                "Biscayne Bistro LLC,LLC,Active,1 Ocean Dr Miami FL,Jordan Rivera,https://sunbiz.test/biz",
            )
        ),
        source_url="https://dos.fl.gov/sunbiz/other-services/data-downloads/",
    )

    matches = match_sunbiz_records_to_leads(records, ["Biscayne Bistro, LLC"])

    assert len(records) == 1
    assert matches["Biscayne Bistro, LLC"].registered_agent_name == "Jordan Rivera"


def test_sunbiz_downloader_skips_duplicate_downloads(tmp_path: Path) -> None:
    downloader = FloridaSunbizDownloader(
        download_dir=tmp_path,
        file_fetcher=lambda url: b"entity_name,status\nBiscayne Bistro LLC,Active\n",
    )

    first = downloader.download_files(
        [
            SunbizFile(
                url="https://dos.fl.gov/sunbiz/downloads/corp_daily.csv",
                filename="corp_daily.csv",
            )
        ]
    )
    second = downloader.download_files(
        [
            SunbizFile(
                url="https://dos.fl.gov/sunbiz/downloads/corp_daily.csv",
                filename="corp_daily.csv",
            )
        ]
    )

    assert first.downloaded == 1
    assert second.skipped == 1
    assert (tmp_path / "corp_daily.csv").exists()
