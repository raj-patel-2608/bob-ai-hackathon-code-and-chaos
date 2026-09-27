"""Splits an uploaded batch into FIRs and parses the I.I.F.-I header of each.

Real FIRs are semi-structured: a header (station, dates, sections, place,
complainant, accused, property) followed by the free-text "First Information
contents". Every header field is optional; the narrative alone is enough for
the pipeline to work.
"""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime

BATCH_SEPARATOR = re.compile(r"\r?\n[ \t]*(?:-{3,}|={3,})[ \t]*\r?\n")
NARRATIVE_LABEL = re.compile(r"^\s*(?:12\.\s*)?First Information contents\s*:?\s*$", re.I | re.M)

HEADER_FIELDS = {
    "fir_no": re.compile(r"^\s*FIR\s*No\.?\s*[:\-]\s*(?P<v>.+)$", re.I | re.M),
    "district": re.compile(r"District\s*[:\-]\s*(?P<v>.+?)(?:\s{2,}|\s+Police Station|$)", re.I | re.M),
    "police_station": re.compile(r"(?:Police Station|P\.S\.)\s*[:\-]\s*(?P<v>.+?)\s*$", re.I | re.M),
    "registered_at": re.compile(r"^\s*Date(?:\s*&\s*Time)?\s*of\s*FIR\s*[:\-]\s*(?P<v>.+)$", re.I | re.M),
    "acts_sections": re.compile(r"^\s*Acts?\s*(?:&|and)\s*Sections?\s*[:\-]\s*(?P<v>.+)$", re.I | re.M),
    "occurrence": re.compile(r"^\s*Occurrence of offence\s*[:\-]\s*(?P<v>.+)$", re.I | re.M),
    "place": re.compile(r"^\s*Place of occurrence\s*[:\-]\s*(?P<v>.+)$", re.I | re.M),
    "complainant": re.compile(r"^\s*Complainant(?:\s*/\s*Informant)?\s*[:\-]\s*(?P<v>.+)$", re.I | re.M),
    "accused": re.compile(r"^\s*Accused\s*[:\-]\s*(?P<v>.+)$", re.I | re.M),
    "property": re.compile(r"^\s*Propert(?:y|ies)(?:\s*involved|\s*stolen)?\s*[:\-]\s*(?P<v>.+)$", re.I | re.M),
}
DATE_RE = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})(?:\s+(\d{1,2}):(\d{2}))?")
AGE_RE = re.compile(r"\bage(?:d)?\s*(?:about\s*)?(\d{1,3})", re.I)


@dataclass
class ParsedFIR:
    raw_text: str
    narrative: str
    fields: dict[str, str] = field(default_factory=dict)
    spans: dict[str, tuple[int, int]] = field(default_factory=dict)
    registered_at: datetime | None = None
    occurred_at: datetime | None = None
    complainant_age: int | None = None
    complainant_occupation: str | None = None

    @property
    def fir_no(self) -> str | None:
        return self.fields.get("fir_no")


def split_batch(content: str, filename: str = "") -> list[str]:
    """Split an uploaded file into raw FIR texts (.txt with --- separators, .jsonl, .json or .csv)."""
    name = filename.lower()
    content = content.lstrip("﻿")
    if name.endswith(".jsonl"):
        return [_text_of(json.loads(line)) for line in content.splitlines() if line.strip()]
    if name.endswith(".json"):
        data = json.loads(content)
        items = data.get("firs", data) if isinstance(data, dict) else data
        return [_text_of(item) for item in items]
    if name.endswith(".csv"):
        rows = csv.DictReader(io.StringIO(content))
        return [_text_of(row) for row in rows if _text_of(row).strip()]
    parts = BATCH_SEPARATOR.split("\n" + content.strip() + "\n")
    return [p.strip() for p in parts if p.strip()]


def _text_of(item) -> str:
    if isinstance(item, str):
        return item.strip()
    for key in ("raw_text", "text", "fir_text", "content"):
        if item.get(key):
            return str(item[key]).strip()
    raise ValueError("record has no raw_text/text field")


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    m = DATE_RE.search(value)
    if not m:
        return None
    day, month, year, hour, minute = m.groups()
    try:
        return datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0))
    except ValueError:
        return None


def parse_fir(raw_text: str) -> ParsedFIR:
    text = raw_text.replace("\r\n", "\n")
    label = NARRATIVE_LABEL.search(text)
    if label:
        header, narrative = text[:label.start()], text[label.end():].strip()
    else:
        # no explicit label: treat lines that look like "Field: value" at the top as the header
        header, narrative = "", text.strip()
    parsed = ParsedFIR(raw_text=text, narrative=narrative)
    for name, pattern in HEADER_FIELDS.items():
        m = pattern.search(header)
        if m:
            parsed.fields[name] = m.group("v").strip()
            parsed.spans[name] = (m.start("v"), m.end("v"))
    parsed.registered_at = _parse_date(parsed.fields.get("registered_at"))
    parsed.occurred_at = _parse_date(parsed.fields.get("occurrence"))
    comp = parsed.fields.get("complainant", "")
    if comp:
        age = AGE_RE.search(comp)
        parsed.complainant_age = int(age.group(1)) if age else None
        parts = [p.strip() for p in comp.split(",")]
        if len(parts) >= 3 and AGE_RE.search(parts[1]):
            parsed.complainant_occupation = parts[2]
    return parsed
