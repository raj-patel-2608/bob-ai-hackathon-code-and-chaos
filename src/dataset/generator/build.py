"""Generates the CrimeFIR synthetic FIR dataset and its answer key.

Run from the repository root:
    python src/dataset/generator/build.py

Outputs (src/dataset/):
    firs_main.txt / .jsonl / .csv     ~400 FIRs, text only (the pipeline input)
    ground_truth.json                 answer key, never read by the pipeline
    demo_live_batch.txt (+ ground truth) small batch for the live demo
    DATASET_CARD.md                   statistics of the generated data

The dataset is deterministic for a given SEED.
"""
from __future__ import annotations

import csv
import json
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from render import add_typos, fill_slots, render_conditionals, render_header, uses_key  # noqa: E402
from templates import Template, templates_for  # noqa: E402
from world import (BANKS, OCCUPATIONS_BY_AGE, STATION_BY_CODE, STATIONS, IdFactory, Station, age_group,  # noqa: E402
                   fmt_account, fmt_amount, fmt_imei, fmt_phone, fmt_upi, fmt_vehicle)

SEED = 20260927
OUT_DIR = HERE.parent
TAXONOMY = json.loads((HERE.parent.parent / "shared" / "taxonomy.json").read_text(encoding="utf-8"))
PERIOD_START = datetime(2026, 4, 1)
PERIOD_END = datetime(2026, 9, 20)
DEV_FRACTION = 0.30

SECTIONS = {
    "cyber.kyc_bank_impersonation": "BNS 318(4), 319(2); IT Act 66C, 66D",
    "cyber.fake_customer_care": "BNS 318(4), 319(2); IT Act 66D",
    "cyber.digital_arrest": "BNS 204, 308(2), 318(4), 319(2); IT Act 66D",
    "cyber.investment_trading": "BNS 316(2), 318(4); IT Act 66D",
    "cyber.job_task": "BNS 318(4); IT Act 66D",
    "cyber.loan_app": "BNS 308(2), 351(2), 356(2); IT Act 67",
    "cyber.sextortion": "BNS 308(2), 351(2); IT Act 66E, 67",
    "cyber.marketplace": "BNS 318(4), 319(2); IT Act 66D",
    "cyber.matrimonial": "BNS 318(4), 319(2); IT Act 66D",
    "property.vehicle_theft": "BNS 303(2)",
    "property.burglary": "BNS 305(a), 331(4)",
    "property.snatching": "BNS 304(2)",
    "property.robbery": "BNS 309(4)",
    "property.theft_other": "BNS 303(2)",
    "body.assault": "BNS 115(2), 351(2), 352",
    "body.intimidation": "BNS 351(2), 352",
    "economic.cheating_offline": "BNS 318(4)",
}

AMOUNT_RANGES = {
    "cyber.kyc_bank_impersonation": (18_000, 3_50_000), "cyber.fake_customer_care": (9_000, 1_60_000),
    "cyber.digital_arrest": (2_00_000, 48_00_000), "cyber.investment_trading": (1_50_000, 32_00_000),
    "cyber.job_task": (25_000, 6_50_000), "cyber.loan_app": (4_000, 60_000),
    "cyber.sextortion": (15_000, 2_40_000), "cyber.marketplace": (12_000, 1_10_000),
    "cyber.matrimonial": (60_000, 9_00_000), "property.vehicle_theft": (35_000, 1_40_000),
    "property.burglary": (60_000, 8_50_000), "property.snatching": (18_000, 1_60_000),
    "property.robbery": (8_000, 90_000), "property.theft_other": (3_000, 70_000),
    "body.assault": (0, 0), "body.intimidation": (0, 0), "economic.cheating_offline": (80_000, 12_00_000),
}

# relative monthly intensity Apr..Sep, gives station summaries real trends to find
MONTH_WEIGHTS = {
    "cyber.digital_arrest": (0.5, 0.7, 1.0, 1.4, 2.0, 2.4),
    "cyber.job_task": (0.6, 0.8, 1.0, 1.2, 1.5, 1.7),
    "property.snatching": (0.8, 0.8, 0.9, 1.0, 1.8, 2.1),
    "property.burglary": (1.0, 1.9, 1.7, 0.8, 0.7, 0.8),
}

BACKGROUND_COUNTS = {
    "cyber.kyc_bank_impersonation": 18, "cyber.fake_customer_care": 12, "cyber.digital_arrest": 10,
    "cyber.investment_trading": 10, "cyber.job_task": 12, "cyber.loan_app": 8, "cyber.sextortion": 6,
    "cyber.marketplace": 8, "cyber.matrimonial": 5, "property.vehicle_theft": 38, "property.burglary": 26,
    "property.snatching": 24, "property.robbery": 12, "property.theft_other": 40, "body.assault": 35,
    "body.intimidation": 18, "economic.cheating_offline": 12,
}

# ---------------------------------------------------------------------------
# Planted repeat-offender clusters. Each member lists which of the cluster's
# identifiers appear in that FIR ({} = linked only by pattern, not evidence).
# ---------------------------------------------------------------------------
CLUSTERS = [
    dict(id="C01", name="Card-reward / KYC call centre (Jamtara-style)", minor="cyber.kyc_bank_impersonation",
         window=("2026-04-08", "2026-08-30"), victim_age=(58, 78),
         pool={"P1": "phone", "P2": "phone", "A1": "bank_account"},
         personas={"persona": ("Vikas Sharma", "Rohit Verma")},
         members=[("NAV", {"phone": "P1"}), ("SAT", {"phone": "P1", "account": "A1"}), ("ADJ", {"account": "A1"}),
                  ("SAY", {"phone": "P2", "account": "A1"}), ("GOT", {"phone": "P2"}), ("VAS", {"phone": "P1"}),
                  ("ATH", {"account": "A1"}), ("MAN", {})]),
    dict(id="C02", name="Fake customer-care helpline ring", minor="cyber.fake_customer_care",
         window=("2026-05-02", "2026-08-25"), victim_age=(24, 55),
         pool={"P3": "phone", "U1": "upi_id"},
         members=[("MAN", {"phone": "P3", "upi": "U1"}), ("ATH", {"phone": "P3"}), ("GOT", {"upi": "U1"}),
                  ("NAV", {"phone": "P3"}), ("CYB", {"upi": "U1"})]),
    dict(id="C03", name="Digital-arrest (fake CBI / customs parcel) ring", minor="cyber.digital_arrest",
         window=("2026-07-01", "2026-09-18"), victim_age=(50, 76),
         pool={"P4": "phone", "A2": "bank_account", "A3": "bank_account"},
         personas={"cop_persona": ("Inspector Vikram Rathore",), "agency": ("CBI, Mumbai",)},
         members=[("CYB", {"phone": "P4", "account": "A2"}), ("VAS", {"account": "A2"}),
                  ("ADJ", {"account": "A2", "account2": "A3"}), ("SAY", {"account": "A3"}),
                  ("NAV", {"phone": "P4"}), ("SAT", {"account": "A3"})]),
    dict(id="C04", name="Telegram part-time task scam", minor="cyber.job_task",
         window=("2026-06-05", "2026-09-15"), victim_age=(19, 29),
         pool={"H1": "online_handle", "U2": "upi_id", "A4": "bank_account"},
         personas={"persona": ("Priya (HR)",)},
         members=[("SAT", {"handle": "H1", "upi": "U2"}), ("ATH", {"upi": "U2"}), ("GOT", {"upi": "U2", "account": "A4"}),
                  ("NAV", {"account": "A4"}), ("ADJ", {"handle": "H1"}), ("VAS", {"account": "A4"})]),
    dict(id="C05", name="Fake stock-trading app group", minor="cyber.investment_trading",
         window=("2026-04-12", "2026-07-20"), victim_age=(32, 62),
         pool={"H2": "online_handle", "A5": "bank_account"},
         personas={"advisor": ("Rahul Mehta",), "app": ("BullRun Pro",), "group": ("BullRun VIP Club 27",)},
         members=[("CYB", {"handle": "H2", "account": "A5"}), ("SAY", {"account": "A5"}), ("ATH", {"handle": "H2"}),
                  ("SAT", {"account": "A5"}), ("GOT", {"handle": "H2"})]),
    dict(id="C06", name="InstaRupee loan-app recovery harassment", minor="cyber.loan_app",
         window=("2026-04-20", "2026-08-10"), victim_age=(21, 38),
         pool={"P5": "phone", "U5": "upi_id"},
         personas={"loan_app": ("InstaRupee",)},
         members=[("MAN", {"phone": "P5"}), ("NAV", {"phone": "P5", "upi": "U5"}), ("ADJ", {"upi": "U5"}),
                  ("SAY", {"phone": "P5"}), ("VAS", {"upi": "U5"})]),
    dict(id="C07", name="Sextortion video-call gang (Mewat-style, fake Crime Branch)", minor="cyber.sextortion",
         window=("2026-05-10", "2026-09-05"), victim_age=(26, 64), gender="male",
         pool={"P6": "phone", "P7": "phone", "U3": "upi_id"},
         personas={"cop_persona": ("ASI Rakesh Yadav",), "girl_name": ("Neha", "Riya")},
         members=[("CYB", {"phone": "P6", "phone2": "P7", "upi": "U3"}), ("ATH", {"phone2": "P7"}),
                  ("GOT", {"phone": "P6", "upi": "U3"}), ("SAT", {"upi": "U3"}), ("ADJ", {"phone2": "P7"})]),
    dict(id="C08", name="Fake army-officer OLX sellers (Bharatpur-style)", minor="cyber.marketplace",
         window=("2026-04-15", "2026-08-05"), victim_age=(22, 48),
         pool={"P8": "phone", "U4": "upi_id"},
         personas={"army_persona": ("Subedar Rajesh Kumar",)},
         members=[("NAV", {"phone": "P8", "upi": "U4"}), ("MAN", {"upi": "U4"}), ("ADJ", {"phone": "P8"}),
                  ("GOT", {"upi": "U4"}), ("VAS", {"phone": "P8"})]),
    dict(id="C09", name="Fake NRI doctor matrimonial profile", minor="cyber.matrimonial",
         window=("2026-05-01", "2026-09-10"), victim_age=(26, 38), gender="female",
         pool={"P9": "phone", "A6": "bank_account"},
         personas={"groom_persona": ("Dr. Arjun Malhotra",), "matrimony_site": ("a matrimonial website",)},
         members=[("SAT", {"phone": "P9", "account": "A6"}), ("SAY", {"account": "A6"}), ("ATH", {"phone": "P9"}),
                  ("NAV", {"account": "A6"})]),
    dict(id="C10", name="Bike-borne chain-snatching gang using a stolen motorcycle", minor="property.snatching",
         window=("2026-08-01", "2026-09-19"), victim_age=(35, 70), gender="female",
         pool={"V1": "vehicle", "N1": "accused_name"},
         accused={"N1": ("Salim Sheikh", "Pappu")},
         members=[("MAN", {"victim_vehicle": "V1"}, "property.vehicle_theft"), ("MAN", {"vehicle": "V1"}),
                  ("VAS", {"vehicle": "V1", "accused": "N1"}), ("SAT", {"accused": "N1"}), ("NAV", {"vehicle": "V1"}),
                  ("MAN", {"accused": "N1"}, "property.robbery"), ("VAS", {})]),
    dict(id="C11", name="Two-wheeler lifting ring with a tempo", minor="property.vehicle_theft",
         window=("2026-04-18", "2026-07-30"), victim_age=(20, 55),
         pool={"N2": "accused_name", "V2": "vehicle"},
         accused={"N2": ("Kalpesh Thakor", "Kalu")},
         members=[("ADJ", {"accused": "N2"}), ("ATH", {"vehicle": "V2"}), ("ADJ", {"accused": "N2", "vehicle": "V2"}),
                  ("GOT", {"vehicle": "V2"}), ("SAY", {"accused": "N2"})]),
    dict(id="C12", name="Locked-house burglary gang (Vadodara-Ahmedabad)", minor="property.burglary",
         window=("2026-05-02", "2026-06-28"), victim_age=(35, 72),
         pool={"N3": "accused_name", "V3": "vehicle"},
         accused={"N3": ("Bhura Singh", "Bhuro")},
         members=[("SAY", {"accused": "N3"}), ("GOT", {"vehicle": "V3"}), ("NAV", {"accused": "N3", "vehicle": "V3"}),
                  ("SAT", {"vehicle": "V3"}), ("ADJ", {"accused": "N3"})]),
]

DECOYS_PER_CLUSTER = {"C01": 5, "C02": 3, "C03": 5, "C04": 4, "C05": 3, "C06": 3, "C07": 3, "C08": 3, "C09": 2,
                      "C10": 4, "C11": 3, "C12": 2}

LIVE_DEMO = [  # new FIRs that attach to existing clusters during the live demo
    ("C01", "NAV", {"phone": "P2"}), ("C03", "SAT", {"account": "A3"}), ("C10", "SAT", {"vehicle": "V1"}),
]

# slot value pools for generic narrative details
POOLS = {
    "persona": ("Amit Verma", "Rahul", "Sanjay Kumar", "Deepak Singh", "Ankit", "Rajiv Malhotra", "Manish"),
    "remote_app": ("AnyDesk", "QuickSupport", "TeamViewer QS", "RustDesk"),
    "ecom": ("Flipkart", "Amazon", "Meesho", "Myntra"),
    "product": ("a mobile phone", "a pair of shoes", "a mixer grinder", "a watch", "a saree"),
    "courier": ("FedEx", "DHL", "Blue Dart", "DTDC"),
    "country": ("Taiwan", "Cambodia", "Iran", "Thailand", "the UK", "Canada"),
    "contraband": ("MDMA drugs and fake passports", "5 passports and 3 credit cards", "150 grams of drugs"),
    "cop_persona": ("Inspector Ajay Pal", "DCP Sanjay Rana", "Sub-Inspector Mohit Sharma", "IPS officer Neeraj"),
    "agency": ("Mumbai Cyber Police", "Narcotics Control Bureau", "CBI Delhi", "Enforcement Directorate"),
    "group": ("Stock Guru Club", "Profit Kings 88", "IPO Masters India", "Smart Traders VIP"),
    "advisor": ("Prof. Anil Kapoor", "Vinod Sir", "Madam Kavya", "Rakesh Jain"),
    "app": ("TradeMax Global", "CoinBase Elite", "Axis Wealth Pro", "IPO Hub"),
    "loan_app": ("CashPocket", "RupeeBazaar", "QuickLoan Plus", "EasyCredit"),
    "girl_name": ("Anjali", "Simran", "Kajal", "Pooja"),
    "vehicle_item": ("Royal Enfield Bullet", "Activa scooter", "Maruti Swift car", "Pulsar bike"),
    "army_persona": ("Captain Amit Singh", "Havildar Suresh Yadav", "Major Rohit Chauhan", "Naik Pradeep Kumar"),
    "cantonment": ("Jaipur Cantonment", "Ambala Cantt", "Jodhpur Military Station", "Gandhinagar Air Force Station"),
    "groom_persona": ("Karan Oberoi", "Aditya Rao", "Nikhil Bhatia", "Sameer Kapoor"),
    "matrimony_site": ("a matrimonial website", "a matrimony app", "Shaadi portal"),
    "bike_model": ("Honda Activa", "Hero Splendor", "Bajaj Pulsar", "TVS Jupiter", "Honda Shine", "Suzuki Access"),
    "parking_place": ("the vegetable market", "my office", "a hospital", "the railway station", "a temple",
                      "a shopping complex"),
    "town": ("Rajkot", "Udaipur", "Mumbai", "his native village", "Pune", "Junagadh"),
    "accused_desc_unknown": ("two young boys with covered faces", "a man in a red t-shirt",
                             "two persons on a scooter", "three unknown persons"),
}


@dataclass
class Case:
    fir_key: str = ""
    station: Station | None = None
    fir_no: int = 0
    registered: datetime | None = None
    occurred: datetime | None = None
    minor: str = ""
    template: Template | None = None
    present: dict[str, str] = field(default_factory=dict)   # conditional key -> canonical value
    accused_person: tuple[str, str] | None = None            # (canonical name, alias) for named accused
    accused_name_text: str = ""
    complainant_name: str = ""
    gender: str = ""
    age: int = 0
    occupation: str = ""
    home_area: str = ""
    complainant_phone: str | None = None
    complainant_phone_text: str = ""
    victim_vehicle: str | None = None
    amount: int = 0
    sections: str = ""
    place: str = ""
    accused_header: str = ""
    property_text: str = ""
    delay_reason: str = ""
    cluster_id: str | None = None
    decoy_of: str | None = None
    evidence_linkable: bool = False
    persona_overrides: dict[str, str] = field(default_factory=dict)
    text: str = ""
    split: str = "test"


def rand_date(rng: random.Random, start: datetime, end: datetime, weights=None) -> datetime:
    if weights:
        months = [(datetime(2026, m, 1), datetime(2026, m + 1, 1) - timedelta(days=1)) for m in range(4, 10)]
        m_start, m_end = rng.choices(months, weights=weights)[0]
        start, end = max(start, m_start), min(end, m_end)
    span = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randint(0, max(span, 1)))


def pick_station(rng: random.Random, minor: str) -> Station:
    if minor.startswith("cyber.") and rng.random() < 0.45:
        return STATION_BY_CODE["CYB"]
    choices = [s for s in STATIONS if s.code != "CYB"]
    return rng.choice(choices)


def name_variant(canonical: str, alias: str, rng: random.Random) -> str:
    first, last = canonical.split(" ", 1)
    return rng.choice((f"{canonical} alias {alias}", f"{first} alias {alias}", alias, canonical,
                       f"{first}bhai alias {alias}", f"{alias} ({canonical})"))


def build_case(rng: random.Random, ids: IdFactory, minor: str, station: Station, when: datetime, *,
               present: dict[str, str] | None = None, accused_person=None, age_range=(18, 75),
               gender: str | None = None, persona_overrides=None, require_all: bool = True) -> Case:
    """Plan one FIR. With require_all, the template must express every given identifier;
    otherwise any template is chosen and identifiers it cannot express are dropped."""
    c = Case(minor=minor, station=station, present=dict(present or {}), accused_person=accused_person,
             persona_overrides=dict(persona_overrides or {}))
    c.registered = when.replace(hour=rng.randint(9, 22), minute=rng.randint(0, 59))
    if minor.startswith("cyber."):
        c.occurred = c.registered - timedelta(days=rng.choice((0, 0, 1, 1, 2, 3, 5, 9, 16)), hours=rng.randint(1, 8))
    else:
        c.occurred = c.registered - timedelta(days=rng.choice((0, 0, 0, 1, 1, 2)), hours=rng.randint(1, 10))
    if (c.registered - c.occurred).days >= 5:
        c.delay_reason = rng.choice(("Complainant first approached the bank and then the helpline 1930.",
                                     "Complainant was afraid and informed family later."))
    # choose a template that can express every identifier this case must contain
    needed = set(c.present) | ({"accused"} if accused_person else set())
    options = [t for t in templates_for(minor) if gender is None or t.gender in (None, gender)]
    if require_all:
        options = [t for t in options if all(uses_key(t.text, k) for k in needed)]
    if not options:
        raise RuntimeError(f"no template for {minor} with {needed} and gender {gender}")
    c.template = rng.choice(options)

    c.age = rng.randint(*age_range)
    c.complainant_name, c.gender = ids.person(c.template.gender or gender)
    jobs = [j for j in OCCUPATIONS_BY_AGE.get(age_group(c.age), ("private job",))
            if not (c.gender == "male" and j == "housewife")]
    c.occupation = rng.choice(jobs)
    c.home_area = rng.choice(station.areas)
    if rng.random() < 0.55:
        c.complainant_phone = ids.phone()
        c.complainant_phone_text = fmt_phone(c.complainant_phone, rng)
    lo, hi = AMOUNT_RANGES[minor]
    c.amount = rng.randrange(lo, hi, 500) if hi else 0
    c.sections = SECTIONS[minor]
    c.place = rng.choice(station.areas)

    if minor == "property.vehicle_theft":
        c.victim_vehicle = c.present.pop("victim_vehicle", None) or ids.vehicle(station.rto)
    c.present = {k: v for k, v in c.present.items() if uses_key(c.template.text, k)}
    return c


def finish_case(c: Case, rng: random.Random, ids: IdFactory) -> None:
    """Fill the narrative, header fields and final text of a case."""
    t = c.template
    ctx = {k: rng.choice(v) for k, v in POOLS.items()}
    ctx.update(c.persona_overrides)
    ctx.update(time=f"{rng.randint(7, 11)}.{rng.choice(('00', '15', '30', '45'))} "
                    f"{rng.choice(('am', 'pm'))}", time2=f"{rng.randint(1, 10)}.{rng.choice(('00', '30'))} pm",
               bank=rng.choice(BANKS), n_txn=rng.randint(2, 6), small_amt=rng.choice((1500, 2000, 3500, 4999, 7500)),
               hours=rng.randint(3, 30),
               a_occupation=("an " if c.occupation[0] in "aeiou" else "a ") + c.occupation, profit=f"{rng.randint(4, 60)},{rng.randint(100, 999)}00",
               price=rng.choice((28000, 45000, 62000, 18500, 90000)), grams=rng.choice((10, 12, 15, 20, 25, 40)),
               cash=rng.choice((3500, 8000, 12000, 25000, 45000)), age=c.age, occupation=c.occupation,
               place=c.place, place2=rng.choice(c.station.areas), date_occ=c.occurred.strftime("%d/%m/%Y"),
               amount=fmt_amount(c.amount or rng.randint(20, 90) * 1000, rng))
    if c.victim_vehicle:
        ctx["victim_vehicle"] = fmt_vehicle(c.victim_vehicle, rng)
    fmt = {"phone": fmt_phone, "phone2": fmt_phone, "account": fmt_account, "account2": fmt_account,
           "upi": fmt_upi, "vehicle": fmt_vehicle, "imei": fmt_imei, "handle": lambda v, r: v}
    for key, value in c.present.items():
        ctx[key] = fmt[key](value, rng)

    present_keys = set(c.present)
    if c.accused_person:
        c.accused_name_text = name_variant(*c.accused_person, rng)
        present_keys.add("accused")
        ctx["accused_name"] = c.accused_name_text
        ctx["accused_desc"] = rng.choice((f"{c.accused_name_text}, a known offender of the area",
                                          f"a man later identified as {c.accused_name_text}",
                                          c.accused_name_text))
    else:
        # background case: a named accused when the text needs a name, sometimes an unknown description
        name_always_shown = "{accused_name}" in render_conditionals(t.text, set())
        if name_always_shown or ("{accused_name}" in t.text and rng.random() < 0.35):
            name, _ = ids.person("male")
            c.accused_person = (name, "")
            c.accused_name_text = ctx["accused_name"] = name
            present_keys.add("accused")
        elif "{accused_desc}" in t.text and rng.random() < 0.3:
            ctx["accused_desc"] = ctx["accused_desc_unknown"]
            present_keys.add("accused")
    ctx.setdefault("accused_name", "")
    ctx.setdefault("accused_desc", ctx["accused_desc_unknown"])

    narrative = t.text
    if rng.random() < 0.25:
        narrative = add_typos(narrative, rng, rng.randint(1, 3))
    narrative = fill_slots(render_conditionals(narrative, present_keys), ctx)
    narrative = re.sub(r"\s+([.,])", r"\1", " ".join(narrative.split()))
    if rng.random() < 0.05:
        narrative = narrative.lower()

    if c.accused_person and c.accused_person[1]:
        c.accused_header = c.accused_name_text
    elif c.accused_person:
        c.accused_header = c.accused_person[0]
    elif c.minor.startswith("cyber."):
        c.accused_header = rng.choice(("Unknown person (details in contents)", "Unknown caller", "Unknown",
                                       "Unknown - mobile/account holder to be traced"))
    else:
        c.accused_header = rng.choice(("Unknown", "Two unknown persons", "Unknown persons"))
    if c.amount:
        c.property_text = rng.choice((f"{fmt_amount(c.amount, rng)} (online transfer)" if c.minor.startswith("cyber.")
                                      else f"Valuables worth {fmt_amount(c.amount, rng)}", fmt_amount(c.amount, rng)))
    drop = {"sections": rng.random() < 0.08, "place": rng.random() < 0.10, "accused": rng.random() < 0.15,
            "property": rng.random() < 0.20}
    c.text = render_header(c, rng, drop) + "\n" + narrative


def truth_record(c: Case) -> dict:
    ident = []
    type_of = {"phone": "phone", "phone2": "phone", "account": "bank_account", "account2": "bank_account",
               "upi": "upi_id", "handle": "online_handle", "vehicle": "vehicle", "imei": "imei"}
    rendered_keys = {k for k in c.present if uses_key(c.template.text, k)}
    for key in sorted(rendered_keys):
        role = "property" if key == "imei" else "offender"
        ident.append({"type": type_of[key], "value": c.present[key], "role": role})
    if c.victim_vehicle:
        ident.append({"type": "vehicle", "value": c.victim_vehicle, "role": "property"})
    if c.complainant_phone:
        ident.append({"type": "phone", "value": c.complainant_phone, "role": "complainant"})
    return {
        "fir_key": c.fir_key, "split": c.split, "station_code": c.station.code, "station": c.station.name,
        "district": c.station.district, "registered_on": c.registered.strftime("%Y-%m-%d"),
        "crime_major": TAXONOMY["crime_minor"][c.minor]["major"], "crime_minor": c.minor,
        "mo_flags": sorted(c.template.mo),
        "victim": {"age_group": age_group(c.age), "gender": c.gender, "occupation": c.occupation},
        "amount": c.amount, "identifiers": ident,
        "accused": ({"canonical": c.accused_person[0], "alias": c.accused_person[1] or None,
                     "as_written": c.accused_name_text} if c.accused_person else None),
        "cluster_id": c.cluster_id, "decoy_of": c.decoy_of, "evidence_linkable": c.evidence_linkable,
    }


def generate():
    rng = random.Random(SEED)
    ids = IdFactory(rng)
    cases: list[Case] = []
    pools: dict[str, dict[str, str]] = {}

    def resolve_pool(cluster) -> dict[str, str]:
        values = {}
        for key, kind in cluster["pool"].items():
            if kind == "phone":
                values[key] = ids.phone()
            elif kind == "bank_account":
                values[key] = ids.bank_account()
            elif kind == "upi_id":
                values[key] = ids.upi()
            elif kind == "online_handle":
                values[key] = {"H1": "@hr_priya_tasks", "H2": "bullrunpro-trade.com"}[key]
            elif kind == "vehicle":
                values[key] = ids.vehicle({"V1": "GJ01", "V2": "GJ05", "V3": "GJ06"}[key])
            elif kind == "accused_name":
                values[key] = key
        return values

    # 1. planted clusters
    for cl in CLUSTERS:
        pool = pools[cl["id"]] = resolve_pool(cl)
        start, end = (datetime.fromisoformat(d) for d in cl["window"])
        for member in cl["members"]:
            st_code, refs = member[0], member[1]
            minor = member[2] if len(member) > 2 else cl["minor"]
            present = {k: pool[v] for k, v in refs.items() if k != "accused"}
            accused = cl["accused"][refs["accused"]] if "accused" in refs else None
            overrides = {k: rng.choice(v) for k, v in cl.get("personas", {}).items()}
            c = build_case(rng, ids, minor, STATION_BY_CODE[st_code], rand_date(rng, start, end),
                           present=present, accused_person=accused, age_range=cl["victim_age"],
                           gender=cl.get("gender") if minor == cl["minor"] else None, persona_overrides=overrides)
            c.cluster_id = cl["id"]
            c.evidence_linkable = bool(refs)
            cases.append(c)

    # 2. decoys: same crime pattern and period as a cluster, but no shared evidence
    for cl in CLUSTERS:
        start, end = (datetime.fromisoformat(d) for d in cl["window"])
        for _ in range(DECOYS_PER_CLUSTER[cl["id"]]):
            present = {}
            for key, kind in cl["pool"].items():
                if kind == "phone" and "phone" not in present:
                    present["phone"] = ids.phone()
                elif kind == "bank_account" and "account" not in present:
                    present["account"] = ids.bank_account()
                elif kind == "upi_id":
                    present["upi"] = ids.upi()
                elif kind == "vehicle":
                    present["vehicle"] = ids.vehicle("GJ01")
                elif kind == "online_handle":
                    present["handle"] = ids._unique(lambda: rng.choice(
                        (f"@parttime_job_{rng.randint(10, 999)}", f"{rng.choice(('smartinvest', 'profitx', 'tradewin'))}"
                         f"{rng.randint(10, 99)}.com")))
            c = build_case(rng, ids, cl["minor"], rng.choice([s for s in STATIONS if s.code != "CYB"]),
                           rand_date(rng, start, end), present=present, age_range=cl["victim_age"],
                           gender=cl.get("gender"), require_all=False)
            c.decoy_of = cl["id"]
            cases.append(c)

    # 3. background cases
    for minor, count in BACKGROUND_COUNTS.items():
        for _ in range(count):
            present = {}
            if minor.startswith("cyber."):
                if rng.random() < 0.7:
                    present["phone"] = ids.phone()
                if rng.random() < 0.5:
                    present["account"] = ids.bank_account()
                if rng.random() < 0.4:
                    present["upi"] = ids.upi()
            elif minor in ("property.snatching", "property.robbery", "property.theft_other", "property.burglary"):
                if rng.random() < 0.35:
                    present["imei"] = ids.imei()
                if minor != "property.theft_other" and rng.random() < 0.2:
                    present["vehicle"] = ids.vehicle("GJ01")
            c = build_case(rng, ids, minor, pick_station(rng, minor),
                           rand_date(rng, PERIOD_START, PERIOD_END, MONTH_WEIGHTS.get(minor)),
                           present=present, require_all=False)
            cases.append(c)

    # 4. live-demo batch (kept separate from the main file)
    live: list[Case] = []
    for cid, st_code, refs in LIVE_DEMO:
        cl = next(x for x in CLUSTERS if x["id"] == cid)
        present = {k: pools[cid][v] for k, v in refs.items()}
        minor = cl["minor"]
        c = build_case(rng, ids, minor, STATION_BY_CODE[st_code],
                       datetime(2026, 9, rng.randint(22, 26)), present=present, age_range=cl["victim_age"],
                       gender=cl.get("gender"),
                       persona_overrides={k: rng.choice(v) for k, v in cl.get("personas", {}).items()})
        c.cluster_id, c.evidence_linkable = cid, True
        live.append(c)
    for minor in ("property.theft_other", "body.assault", "cyber.fake_customer_care"):
        live.append(build_case(rng, ids, minor, pick_station(rng, minor), datetime(2026, 9, rng.randint(22, 26)),
                               present={"phone": ids.phone()} if minor.startswith("cyber.") else {}))

    # FIR numbers per station in registration order, then render
    all_cases = sorted(cases, key=lambda x: x.registered) + sorted(live, key=lambda x: x.registered)
    counters: Counter = Counter()
    for c in all_cases:
        counters[c.station.code] += 1
        c.fir_no = 100 + counters[c.station.code] * 3 + rng.randint(0, 2)
        c.fir_key = f"{c.station.district_code}-{c.station.code}-{c.registered.year}-{c.fir_no:04d}"
    for c in all_cases:
        finish_case(c, rng, ids)
    dev_rng = random.Random(SEED + 1)
    for c in cases:
        c.split = "dev" if dev_rng.random() < DEV_FRACTION else "test"
    for c in live:
        c.split = "live_demo"
    rng.shuffle(cases)
    return cases, live


def write_outputs(cases: list[Case], live: list[Case]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    def write_txt(path: Path, items: list[Case]):
        path.write_text("\n\n---\n\n".join(c.text for c in items) + "\n", encoding="utf-8")

    write_txt(OUT_DIR / "firs_main.txt", cases)
    write_txt(OUT_DIR / "demo_live_batch.txt", live)
    with open(OUT_DIR / "firs_main.jsonl", "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps({"raw_text": c.text}, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "firs_main.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["raw_text"])
        for c in cases:
            w.writerow([c.text])
    meta = {"generator": "src/dataset/generator/build.py", "seed": SEED, "taxonomy_version": TAXONOMY["version"],
            "note": "Answer key. Never give this file to the pipeline."}
    (OUT_DIR / "ground_truth.json").write_text(
        json.dumps({**meta, "clusters": [{"id": c["id"], "name": c["name"]} for c in CLUSTERS],
                    "firs": [truth_record(c) for c in cases]}, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "demo_live_ground_truth.json").write_text(
        json.dumps({**meta, "firs": [truth_record(c) for c in live]}, indent=1, ensure_ascii=False), encoding="utf-8")
    write_card(cases, live)


def write_card(cases: list[Case], live: list[Case]) -> None:
    by_minor = Counter(c.minor for c in cases)
    by_station = Counter(f"{c.station.name} ({c.station.district})" for c in cases)
    by_month = Counter(c.registered.strftime("%Y-%m") for c in cases)
    kinds = Counter("cluster" if c.cluster_id else "decoy" if c.decoy_of else "background" for c in cases)
    splits = Counter(c.split for c in cases)
    lines = ["# Dataset card (generated)", "",
             f"Generated by `generator/build.py` with seed `{SEED}`. Do not edit by hand; re-run the generator.", "",
             f"- FIRs in main set: **{len(cases)}** ({kinds['cluster']} in planted clusters, {kinds['decoy']} decoys, "
             f"{kinds['background']} background)",
             f"- Splits: dev {splits['dev']}, test {splits['test']}",
             f"- Live-demo batch: {len(live)} FIRs ({sum(1 for c in live if c.cluster_id)} attach to existing clusters)",
             f"- Period: {min(c.registered for c in cases):%d %b %Y} to {max(c.registered for c in cases):%d %b %Y}",
             "", "## Planted repeat-offender clusters", "", "| Cluster | Pattern | FIRs | Stations | Linkable by evidence |",
             "|---|---|---|---|---|"]
    for cl in CLUSTERS:
        members = [c for c in cases if c.cluster_id == cl["id"]]
        stations = sorted({c.station.name for c in members})
        lines.append(f"| {cl['id']} | {cl['name']} | {len(members)} | {', '.join(stations)} | "
                     f"{sum(c.evidence_linkable for c in members)} of {len(members)} |")
    lines += ["", "## Crime types", "", "| Minor head | FIRs |", "|---|---|"]
    lines += [f"| {TAXONOMY['crime_minor'][m]['label']} (`{m}`) | {n} |" for m, n in sorted(by_minor.items())]
    lines += ["", "## Stations", "", "| Station | FIRs |", "|---|---|"]
    lines += [f"| {s} | {n} |" for s, n in sorted(by_station.items())]
    lines += ["", "## Registrations per month", "", "| Month | FIRs |", "|---|---|"]
    lines += [f"| {m} | {n} |" for m, n in sorted(by_month.items())]
    (OUT_DIR / "DATASET_CARD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main_cases, live_cases = generate()
    write_outputs(main_cases, live_cases)
    print(f"wrote {len(main_cases)} FIRs + {len(live_cases)} live-demo FIRs to {OUT_DIR}")
