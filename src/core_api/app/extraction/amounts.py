"""Money amounts in Indian formats: Rs. 1,48,000 / Rs 148000 / ₹1.48 lakh / INR 61000 / Rs.3,05,500/-"""
from __future__ import annotations

import re

AMOUNT_RE = re.compile(r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(lakh|lac|crore|cr)?", re.I)


def parse_amounts(text: str) -> list[int]:
    values = []
    for m in AMOUNT_RE.finditer(text or ""):
        number = m.group(1).replace(",", "")
        if not number or number == ".":
            continue
        try:
            value = float(number)
        except ValueError:
            continue
        unit = (m.group(2) or "").lower()
        if unit in ("lakh", "lac"):
            value *= 100_000
        elif unit in ("crore", "cr"):
            value *= 10_000_000
        values.append(int(round(value)))
    return values


def total_loss(property_text: str | None, narrative: str) -> int | None:
    """Prefer the header's property value; otherwise the largest amount in the narrative."""
    header = parse_amounts(property_text or "")
    if header:
        return max(header)
    found = parse_amounts(narrative)
    return max(found) if found else None
