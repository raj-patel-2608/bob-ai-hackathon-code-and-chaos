from app.extraction.accused import extract_accused
from app.extraction.amounts import parse_amounts, total_loss
from app.extraction.fir_parser import parse_fir, split_batch
from app.extraction.identifiers import extract_identifiers, normalize_phone


def values(text, kind, **kw):
    return [i.value for i in extract_identifiers(text, **kw) if i.type == kind]


def test_phone_formats_normalise_to_one_value():
    for written in ("98765 43210", "+91-9876543210", "+91 98765 43210", "09876543210", "9876543210",
                    "+919876543210", "987-654-3210"):
        assert values(f"call came from {written} yesterday", "phone") == ["+919876543210"], written


def test_phone_not_found_inside_longer_numbers():
    assert values("account 899272073588981 was used", "phone") == []
    assert normalize_phone("12345") is None


def test_accounts_upi_imei_vehicle_handles():
    text = ("Money went to a/c no. 5010 0458 7122 33 and UPI ID Refund.Help147@okhdfcbank. "
            "His phone IMEI 35-678910-452341-1 was stolen. Bike number was GJ-01-AB-4471. "
            "Joined Telegram @hr_priya_tasks and site bullrunpro-trade.com. Mail me at x.y@gmail.com.")
    assert values(text, "bank_account") == ["50100458712233"]
    assert values(text, "upi_id") == ["refund.help147@okhdfcbank"]
    assert values(text, "vehicle") == ["GJ01AB4471"]
    assert set(values(text, "online_handle")) == {"@hr_priya_tasks", "bullrunpro-trade.com"}
    assert "x.y@gmail" not in values(text, "upi_id")


def test_amounts_are_not_accounts():
    assert values("Rs 148000000 was lost", "bank_account") == []


def test_roles_complainant_and_property():
    fir = ("Complainant / Informant: A. Shah, age 60, retired, Mob. 98251 11111\n"
           "First Information contents:\nMaine apni Honda Shine (GJ05 AB 1234) park ki thi. "
           "Caller from 99887 76655 asked OTP. The motorcycle number was GJ01CD5678.")
    parsed = parse_fir(fir)
    ids = {i.value: i.role for i in extract_identifiers(parsed.raw_text, parsed.spans.get("complainant"))}
    assert ids["+919825111111"] == "complainant"
    assert ids["+919988776655"] == "offender"
    assert ids["GJ05AB1234"] == "property"
    assert ids["GJ01CD5678"] == "offender"


def test_parse_header_and_split():
    batch = "FIR No.: 0412/2026\nDistrict: Ahmedabad City    Police Station: Navrangpura\n" \
            "Date & Time of FIR: 14/08/2026 16:40\nFirst Information contents:\nstory one\n---\n" \
            "Just a narrative without header, long enough."
    parts = split_batch(batch, "x.txt")
    assert len(parts) == 2
    p = parse_fir(parts[0])
    assert p.fields["police_station"] == "Navrangpura"
    assert p.fields["district"] == "Ahmedabad City"
    assert p.registered_at.year == 2026 and p.registered_at.hour == 16
    assert parse_fir(parts[1]).narrative.startswith("Just a narrative")


def test_amounts():
    assert parse_amounts("Rs. 1,48,000 and ₹2.5 lakh and INR 61000 and Rs.3,05,500/-") == [148000, 250000, 61000,
                                                                                            305500]
    assert total_loss("Rs 90,000 (online transfer)", "lost Rs 5000") == 90000


def test_accused_aliases_and_unknowns():
    got = extract_accused("Salim Sheikh alias Pappu", "Later identified as Pappu. He said he is Inspector "
                                                      "Vikram Rathore of CBI.")
    kinds = {(m.name, m.alias, m.source) for m in got}
    assert ("salim sheikh", "pappu", "header") in kinds
    assert ("vikram rathore", None, "claimed") in kinds          # fake persona: not an identity
    assert extract_accused("Unknown caller", "") == []
    assert extract_accused("Two unknown persons", "") == []


def test_llm_names_must_be_grounded_and_identifying():
    from app.pipeline.decisions import LlmAccused as P
    from app.pipeline.stages import _grounded_person
    text = "A girl who said her name is Kajal made a video call. One of them was Salim alias Pappu. Accused Ramesh K. Patel."
    assert _grounded_person(text, P(name="Kajal")) == ("kajal", None, True)            # first name only: weak
    assert _grounded_person(text, P(name="Unknown caller"))[0] is None                 # generic
    assert _grounded_person(text, P(name="Vikram Singh"))[0] is None                   # not in the FIR
    assert _grounded_person(text, P(name="Ramesh K. Patel")) == ("ramesh k patel", None, False)
    assert _grounded_person(text, P(name="Salim", alias="Pappu"))[1] == "pappu"         # stated alias kept
    assert _grounded_person(text, P(alias="Bhuro"))[1] is None                         # alias not stated
