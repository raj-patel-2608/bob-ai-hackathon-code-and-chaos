"""Deterministic extraction of hard identifiers from FIR text.

Hard identifiers (phones, bank accounts, UPI IDs, IMEIs, vehicle numbers,
online handles) are the evidence that links FIRs together, so they are
extracted with explainable rules rather than an AI model. Every match keeps
its character span so the UI can highlight it and the explanation can quote it.

Canonical forms (used for matching across FIRs):
    phone          +91XXXXXXXXXX
    bank_account   digits only
    upi_id         lower case
    imei           15 digits
    vehicle        upper case, no separators (GJ01AB1234)
    online_handle  lower case (@handle or domain)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Indian vehicle registration state / UT codes, used to reject look-alike tokens
STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CH", "CG", "DD", "DL", "DN", "GA", "GJ", "HP", "HR", "JH", "JK", "KA", "KL",
    "LA", "LD", "MH", "ML", "MN", "MP", "MZ", "NL", "OD", "OR", "PB", "PY", "RJ", "SK", "TN", "TR", "TS", "UK",
    "UP", "WB",
}

_SEP = r"[ \-]?"
PHONE_PATTERNS = (
    # +91 98765 43210 / +91-9876543210 / 09876543210 / 98765 43210 / 9876543210
    re.compile(rf"(?<![\w+])(?:\+91{_SEP}|0091{_SEP}|0)?[6-9]\d{{4}}{_SEP}\d{{5}}(?!\d)"),
    # 987-654-3210
    re.compile(r"(?<![\w+])(?:\+91[ \-]?)?[6-9]\d{2}[ \-]\d{3}[ \-]\d{4}(?!\d)"),
)
IMEI_PATTERN = re.compile(r"(?<!\d)(\d{2}[ \-]?\d{6}[ \-]?\d{6}[ \-]?\d)(?!\d)")
ACCOUNT_PATTERN = re.compile(r"(?<![\d\w])(\d{4}(?:[ \-]\d{2,4}){2,4}|\d{9,18})(?![\d\w])")
UPI_PATTERN = re.compile(r"(?<![\w.\-])([A-Za-z0-9][A-Za-z0-9.\-_]{1,63}@[A-Za-z]{2,20})(?!\w|\.[A-Za-z])")
VEHICLE_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{2})[ \-]?(\d{1,2})[ \-]?([A-Za-z]{1,3})[ \-]?(\d{4})(?![A-Za-z0-9])")
HANDLE_PATTERN = re.compile(r"(?<![\w@.])(@[A-Za-z][A-Za-z0-9_]{3,31})(?![\w@])")
DOMAIN_PATTERN = re.compile(r"(?<![\w@.\-])([a-z0-9][a-z0-9\-]{1,62}\.(?:com|in|net|org|app|io|xyz|co|live|top|vip))"
                            r"(?!\w|\.[A-Za-z])", re.I)

ACCOUNT_CONTEXT = re.compile(r"(a/c|acc(?:ount)?|khata|beneficiary|credited|transferred|rtgs|neft|imps)", re.I)
IMEI_CONTEXT = re.compile(r"imei", re.I)
# a vehicle is the victim's property when a possessive or "registration no." precedes it in the same sentence
PROPERTY_VEHICLE_CONTEXT = re.compile(
    r"\b(my|his|her|our|apni|apna|meri|mera|hamari|parked|registration|bearing|stolen|missing)\b"
    r"(?:[^.!?\n]|(?<=\bno)\.){0,60}$", re.I)
LEGIT_DOMAINS = {"cybercrime.gov.in", "sancharsaathi.gov.in"}


@dataclass(frozen=True)
class Identifier:
    type: str          # phone | bank_account | upi_id | imei | vehicle | online_handle
    raw: str           # exactly as written in the text
    value: str         # canonical form
    start: int
    end: int
    role: str          # offender | property | complainant


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def normalize_phone(raw: str) -> str | None:
    d = _digits(raw)
    if len(d) == 13 and d.startswith("091"):
        d = d[3:]
    elif len(d) == 12 and d.startswith("91"):
        d = d[2:]
    elif len(d) == 11 and d.startswith("0"):
        d = d[1:]
    if len(d) == 10 and d[0] in "6789":
        return "+91" + d
    return None


def luhn_ok(number: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def normalize_vehicle(state: str, rto: str, series: str, number: str) -> str | None:
    state = state.upper()
    if state not in STATE_CODES:
        return None
    return f"{state}{int(rto):02d}{series.upper()}{number}"


def _overlaps(span: tuple[int, int], taken: list[tuple[int, int]]) -> bool:
    return any(span[0] < e and s < span[1] for s, e in taken)


def extract_identifiers(text: str, complainant_span: tuple[int, int] | None = None) -> list[Identifier]:
    """Find every hard identifier in `text`.

    `complainant_span` is the character range of the complainant's own details
    (the "Complainant / Informant" header line); identifiers inside it get the
    role "complainant" and must never be used as offender evidence.
    """
    found: list[Identifier] = []
    taken: list[tuple[int, int]] = []

    def role_for(start: int, default: str) -> str:
        if complainant_span and complainant_span[0] <= start < complainant_span[1]:
            return "complainant"
        return default

    def add(kind: str, m_start: int, m_end: int, value: str, default_role: str):
        taken.append((m_start, m_end))
        found.append(Identifier(kind, text[m_start:m_end], value, m_start, m_end, role_for(m_start, default_role)))

    # UPI IDs and handles first, so their digits are not read as phones or accounts
    for m in UPI_PATTERN.finditer(text):
        add("upi_id", m.start(1), m.end(1), m.group(1).lower(), "offender")
    for m in HANDLE_PATTERN.finditer(text):
        if not _overlaps(m.span(1), taken):
            add("online_handle", m.start(1), m.end(1), m.group(1).lower(), "offender")
    for m in DOMAIN_PATTERN.finditer(text):
        dom = m.group(1).lower()
        if dom not in LEGIT_DOMAINS and not _overlaps(m.span(1), taken):
            add("online_handle", m.start(1), m.end(1), dom, "offender")

    # IMEIs: 15 digits with the Luhn check digit, or explicitly labelled
    for m in IMEI_PATTERN.finditer(text):
        d = _digits(m.group(1))
        labelled = IMEI_CONTEXT.search(text[max(0, m.start() - 20):m.start()])
        if len(d) == 15 and (labelled or luhn_ok(d)) and not _overlaps(m.span(1), taken):
            add("imei", m.start(1), m.end(1), d, "property")

    for pattern in PHONE_PATTERNS:
        for m in pattern.finditer(text):
            value = normalize_phone(m.group(0))
            if value and not _overlaps(m.span(), taken):
                add("phone", m.start(), m.end(), value, "offender")

    for m in ACCOUNT_PATTERN.finditer(text):
        if _overlaps(m.span(1), taken):
            continue
        d = _digits(m.group(1))
        if not 9 <= len(d) <= 18:
            continue
        before = text[max(0, m.start() - 45):m.start()]
        if re.search(r"(rs\.?|inr|₹)\s*$", before, re.I):
            continue                                     # an amount, not an account
        if ACCOUNT_CONTEXT.search(before) or len(d) >= 11:
            add("bank_account", m.start(1), m.end(1), d, "offender")

    for m in VEHICLE_PATTERN.finditer(text):
        value = normalize_vehicle(*m.groups())
        if value and not _overlaps(m.span(), taken):
            before = text[max(0, m.start() - 60):m.start()]
            role = "property" if PROPERTY_VEHICLE_CONTEXT.search(before) else "offender"
            add("vehicle", m.start(), m.end(), value, role)

    found.sort(key=lambda i: i.start)
    return found
