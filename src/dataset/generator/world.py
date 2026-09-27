"""Fictional "world" for the synthetic FIR dataset: police stations, places,
people and identifier factories.

Every person, phone number, bank account, UPI ID, IMEI and vehicle number
produced here is randomly generated and fictional. Police station and area
names are real place names used only as geography.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Station:
    code: str          # short code used in the FIR key, e.g. "NAV"
    name: str          # police station name as written on an FIR
    district: str      # district / commissionerate
    district_code: str
    rto: str           # vehicle registration prefix for the district
    areas: tuple[str, ...]


STATIONS: tuple[Station, ...] = (
    Station("NAV", "Navrangpura", "Ahmedabad City", "AHD", "GJ01",
            ("Stadium Road, Navrangpura", "C.G. Road", "Swastik Cross Road", "Navrangpura Gam", "Commerce Six Roads")),
    Station("SAT", "Satellite", "Ahmedabad City", "AHD", "GJ01",
            ("Jodhpur Cross Road", "Shyamal Cross Road", "Prahladnagar", "Ramdev Nagar", "Satellite Road")),
    Station("VAS", "Vastrapur", "Ahmedabad City", "AHD", "GJ01",
            ("Vastrapur Lake", "IIM Road", "Himalaya Mall area", "Judges Bungalow Road", "Vastrapur Gam")),
    Station("MAN", "Maninagar", "Ahmedabad City", "AHD", "GJ01",
            ("Kankaria Lake", "Jawahar Chowk", "Maninagar Railway Station", "L.G. Hospital Road", "Bhairavnath Road")),
    Station("CYB", "Cyber Crime Police Station", "Ahmedabad City", "AHD", "GJ01",
            ("Bodakdev", "Thaltej", "Gota", "Chandkheda", "Naranpura")),
    Station("ADJ", "Adajan", "Surat City", "SRT", "GJ05",
            ("Honey Park Road", "Pal Gam", "L.P. Savani Road", "Adajan Patia", "Rander Road")),
    Station("ATH", "Athwa", "Surat City", "SRT", "GJ05",
            ("Ghod Dod Road", "Parle Point", "Athwalines", "City Light Road", "Ummarwada")),
    Station("SAY", "Sayajigunj", "Vadodara City", "VAD", "GJ06",
            ("Sayajigunj", "Fatehgunj", "Railway Station Road, Vadodara", "Alkapuri", "Productivity Road")),
    Station("GOT", "Gotri", "Vadodara City", "VAD", "GJ06",
            ("Gotri Road", "Sevasi", "Vasna-Bhayli Road", "Race Course Circle", "Tandalja")),
)
STATION_BY_CODE = {s.code: s for s in STATIONS}

MALE_FIRST = ("Hasmukhbhai", "Rameshbhai", "Jignesh", "Nilesh", "Ketan", "Paresh", "Mahesh", "Rakesh", "Bhavesh",
              "Chirag", "Dhruv", "Harsh", "Kunal", "Mehul", "Nirav", "Pratik", "Sanjay", "Tushar", "Vipul", "Yash",
              "Arvind", "Dinesh", "Gaurang", "Hemant", "Kamlesh", "Manoj", "Pankaj", "Rohit", "Sunil", "Umesh",
              "Imran", "Salman", "Joseph", "Gurpreet", "Anil", "Vikram", "Deepak", "Suresh", "Kiran", "Ashok")
FEMALE_FIRST = ("Meenaben", "Kokilaben", "Hetal", "Nidhi", "Priyanka", "Komal", "Pooja", "Riddhi", "Shital", "Urvashi",
                "Bhavna", "Darshana", "Falguni", "Jyoti", "Kinjal", "Mansi", "Neha", "Rina", "Sonal", "Varsha",
                "Ayesha", "Farzana", "Mary", "Harpreet", "Anjali", "Deepa", "Geeta", "Lata", "Sarita", "Usha")
SURNAMES = ("Shah", "Patel", "Mehta", "Desai", "Joshi", "Trivedi", "Pandya", "Parmar", "Solanki", "Chauhan",
            "Rathod", "Vaghela", "Makwana", "Prajapati", "Modi", "Bhatt", "Vyas", "Dave", "Thakkar", "Soni",
            "Sheikh", "Pathan", "Christian", "Singh", "Sharma", "Gupta", "Nair", "Iyer", "Kulkarni", "Jadeja")
OCCUPATIONS_BY_AGE = {
    "18_30": ("student", "software engineer", "sales executive", "nursing student", "delivery partner", "accountant"),
    "31_45": ("businessman", "teacher", "bank employee", "shop owner", "private job", "doctor", "housewife"),
    "46_60": ("businessman", "government employee", "housewife", "textile trader", "chartered accountant"),
    "above_60": ("retired bank clerk", "retired teacher", "retired government employee", "pensioner", "housewife"),
}
BANKS = ("SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "Bank of Baroda", "Kotak Mahindra Bank", "IDFC First Bank",
         "Punjab National Bank", "Canara Bank", "Union Bank")
UPI_PSPS = ("okaxis", "ybl", "paytm", "oksbi", "ibl", "axl", "okhdfcbank")


def age_group(age: int) -> str:
    if age < 18:
        return "below_18"
    if age <= 30:
        return "18_30"
    if age <= 45:
        return "31_45"
    if age <= 60:
        return "46_60"
    return "above_60"


@dataclass
class IdFactory:
    """Creates unique fictional identifiers and remembers them to avoid clashes."""
    rng: random.Random
    used: set[str] = field(default_factory=set)

    def _unique(self, make) -> str:
        for _ in range(1000):
            value = make()
            if value not in self.used:
                self.used.add(value)
                return value
        raise RuntimeError("could not create a unique identifier")

    def phone(self) -> str:
        """Canonical form: +91 followed by 10 digits starting 6-9."""
        return self._unique(lambda: "+91" + str(self.rng.choice("6789"))
                            + "".join(self.rng.choice("0123456789") for _ in range(9)))

    def bank_account(self) -> str:
        length = self.rng.choice((11, 12, 14, 15, 16))
        return self._unique(lambda: str(self.rng.randint(1, 9))
                            + "".join(self.rng.choice("0123456789") for _ in range(length - 1)))

    def upi(self, stem: str | None = None) -> str:
        stems = ("rewardpoint", "kyc.update", "refund.help", "cashback", "taskpay", "earnmore", "armycanteen",
                 "loanfix", "helpdesk", "payout", "gatepass", "customsclear", "legalfee", "trustpay")
        base = stem or self.rng.choice(stems)
        return self._unique(lambda: f"{base}{self.rng.randint(10, 9999)}@{self.rng.choice(UPI_PSPS)}")

    def imei(self) -> str:
        return self._unique(self._luhn_imei)

    def _luhn_imei(self) -> str:
        body = "35" + "".join(self.rng.choice("0123456789") for _ in range(12))
        total = 0
        for i, ch in enumerate(body):
            d = int(ch)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return body + str((10 - total % 10) % 10)

    def vehicle(self, rto: str) -> str:
        letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
        return self._unique(lambda: f"{rto}{self.rng.choice(letters)}{self.rng.choice(letters)}"
                            f"{self.rng.randint(1000, 9999)}")

    def person(self, gender: str | None = None) -> tuple[str, str]:
        """Unique fictional name, so no two FIRs accidentally share a person."""
        gender = gender or self.rng.choice(("male", "female"))
        pool = MALE_FIRST if gender == "male" else FEMALE_FIRST
        name = self._unique(lambda: f"{self.rng.choice(pool)} {self.rng.choice('ABCDGHJKMNPRSV')}. "
                                    f"{self.rng.choice(SURNAMES)}")
        return name, gender


# ---------------------------------------------------------------------------
# Surface formats: the same identifier is written differently in each FIR,
# exactly like real complainants and writers do.
# ---------------------------------------------------------------------------

def fmt_phone(canonical: str, rng: random.Random) -> str:
    d = canonical[-10:]
    return rng.choice((
        f"{d[:5]} {d[5:]}",
        f"+91-{d}",
        f"+91 {d[:5]} {d[5:]}",
        f"0{d}",
        d,
        f"+91{d}",
        f"{d[:3]}-{d[3:6]}-{d[6:]}",
    ))


def fmt_account(canonical: str, rng: random.Random) -> str:
    if rng.random() < 0.3:
        return " ".join(canonical[i:i + 4] for i in range(0, len(canonical), 4))
    return canonical


def fmt_upi(canonical: str, rng: random.Random) -> str:
    return canonical.upper() if rng.random() < 0.15 else canonical


def fmt_imei(canonical: str, rng: random.Random) -> str:
    if rng.random() < 0.3:
        return f"{canonical[:2]}-{canonical[2:8]}-{canonical[8:14]}-{canonical[14]}"
    return canonical


def fmt_vehicle(canonical: str, rng: random.Random) -> str:
    rto, series, num = canonical[:4], canonical[4:-4], canonical[-4:]
    return rng.choice((
        canonical,
        f"{rto[:2]}-{rto[2:]}-{series}-{num}",
        f"{rto[:2]} {rto[2:]} {series} {num}",
        f"{rto[:2]}{rto[2:]} {series} {num}",
        canonical.lower(),
    ))


def fmt_amount(amount: int, rng: random.Random) -> str:
    def indian(n: int) -> str:
        s = str(n)
        if len(s) <= 3:
            return s
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        return ",".join(groups) + "," + tail

    options = [f"Rs. {indian(amount)}", f"Rs {amount}", f"Rs.{indian(amount)}/-", f"INR {amount}", f"₹{indian(amount)}"]
    if amount >= 100000 and amount % 10000 == 0:
        options.append(f"Rs. {amount / 100000:g} lakh")
    return rng.choice(options)
