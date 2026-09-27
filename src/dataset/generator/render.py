"""Renders a planned case into FIR text in the NCRB I.I.F.-I layout."""
from __future__ import annotations

import random
import re
from datetime import datetime

_COND = re.compile(r"<<(\w+)\|([^|]*?)\|([^>]*?)>>")
_TOKEN = re.compile(r"[A-Za-z]{6,}")

DIRECTIONS = ("east", "west", "north", "south", "north-east", "south-west")


def render_conditionals(text: str, present: set[str]) -> str:
    """Resolve <<key|with|without>> segments for the identifiers a case has."""
    return _COND.sub(lambda m: m.group(2) if m.group(1) in present else m.group(3), text)


def uses_key(text: str, key: str) -> bool:
    return f"<<{key}|" in text or "{" + key + "}" in text


def add_typos(text: str, rng: random.Random, count: int) -> str:
    """Introduce small spelling mistakes in plain words only (never in slots or markers)."""
    words = [m for m in _TOKEN.finditer(text)]
    rng.shuffle(words)
    chars = list(text)
    done = 0
    for m in words:
        if done >= count:
            break
        start, end = m.span()
        # skip words that sit inside a {slot} or a <<key|...>> marker name
        before = text[max(0, start - 2):start]
        if "{" in before or "<<" in before or text[end:end + 1] in "}|":
            continue
        i = rng.randint(start + 1, end - 2)
        if rng.random() < 0.5:
            chars[i], chars[i + 1] = chars[i + 1], chars[i]      # swap
        else:
            chars[i] = ""                                          # drop
        done += 1
    return "".join(chars)


def fill_slots(text: str, ctx: dict) -> str:
    def repl(m):
        key = m.group(1)
        if key not in ctx:
            raise KeyError(f"template slot {{{key}}} has no value")
        return str(ctx[key])
    return re.sub(r"\{(\w+)\}", repl, text)


def fmt_date(d: datetime) -> str:
    return d.strftime("%d/%m/%Y")


def render_header(case, rng: random.Random, drop: dict[str, bool]) -> str:
    st = case.station
    lines = [
        f"FIR No.: {case.fir_no:04d}/{case.registered.year}",
        f"District: {st.district}    Police Station: {st.name}",
        f"Date & Time of FIR: {fmt_date(case.registered)} {case.registered.strftime('%H:%M')}",
    ]
    if not drop.get("sections"):
        lines.append(f"Acts & Sections: {case.sections}")
    occ = f"{fmt_date(case.occurred)} at about {case.occurred.strftime('%H:%M')}"
    lines.append(f"Occurrence of offence: {occ}")
    if not drop.get("place"):
        lines.append(f"Place of occurrence: {case.place}, about {rng.choice((0.5, 1, 1.5, 2, 3, 4))} km "
                     f"{rng.choice(DIRECTIONS)} of P.S.")
    comp = f"{case.complainant_name}, age {case.age}, {case.occupation}, r/o {case.home_area}"
    if case.complainant_phone_text:
        comp += f", Mob. {case.complainant_phone_text}"
    lines.append(f"Complainant / Informant: {comp}")
    if not drop.get("accused"):
        lines.append(f"Accused: {case.accused_header}")
    if not drop.get("property") and case.property_text:
        lines.append(f"Properties involved: {case.property_text}")
    if case.delay_reason:
        lines.append(f"Reason for delay in reporting: {case.delay_reason}")
    lines.append("First Information contents:")
    return "\n".join(lines)
