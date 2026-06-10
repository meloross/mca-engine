from __future__ import annotations

import csv
from datetime import date, datetime
from html.parser import HTMLParser
from io import StringIO
from typing import Any


class DataRowParser(HTMLParser):
    def __init__(self, *, record_name: str) -> None:
        super().__init__()
        self.record_name = record_name
        self.rows: list[dict[str, str]] = []
        self._current_row: dict[str, str] | None = None
        self._current_field: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "tr" and attr_map.get("data-record") == self.record_name:
            self._current_row = {}
        if self._current_row is not None and tag in {"td", "th"} and attr_map.get("data-field"):
            self._current_field = attr_map["data-field"]
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._current_field is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_field and self._current_row is not None:
            self._current_row[self._current_field] = " ".join(self._buffer).strip()
            self._current_field = None
            self._buffer = []
        if tag == "tr" and self._current_row is not None:
            self.rows.append(self._current_row)
            self._current_row = None


def parse_html_rows(html: str, *, record_name: str) -> list[dict[str, str]]:
    parser = DataRowParser(record_name=record_name)
    parser.feed(html)
    return parser.rows


def parse_csv_rows(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(text))
    return [{key: value for key, value in row.items() if key and value} for row in reader]


def split_names(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


def parse_date(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value.strip()[:10])
    return None


def parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        return datetime.fromisoformat(value.strip())
    return None


def compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value not in (None, "", [], {})}


def truthy_text(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}
