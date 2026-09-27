"""Crime-type / MO decisions: Laya questions, LLM prompt + validation, rules fallback.

Three tiers:
  1. Laya (System 1)  typed questions, calibrated probabilities, ~0.3 s per FIR
  2. Granite LLM      only when Laya's confidence < settings.decision_min_confidence
  3. Rules            only when the model service is unavailable (marked for review)
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..domain.taxonomy import Taxonomy

LAYA_CHECKPOINT = "typed-decisions"      # chosen in the Phase-0 spike (dev split)

MO_QUESTIONS = {
    "impersonated_bank_official": "Did the caller or offender claim to be from a bank, card department or KYC team?",
    "impersonated_customer_care": "Did the offender pretend to be customer care or a helpline of a company?",
    "impersonated_police_or_agency": "Did the offender claim to be police, CBI, customs, courier or a government "
                                     "officer?",
    "impersonated_army_officer": "Did the offender claim to be an army or defence officer?",
    "asked_otp_or_card_details": "Was the victim asked to share an OTP, PIN, CVV or card number?",
    "remote_access_app": "Was the victim made to install AnyDesk, QuickSupport, TeamViewer or a screen-sharing app?",
    "phishing_link_or_fake_app": "Was the victim sent a link, QR code, APK, fake app or fake website?",
    "video_call_used": "Was there a video call?",
    "threat_of_arrest_or_case": "Was the victim threatened with arrest, a police case or legal action?",
    "morphed_or_obscene_content": "Were morphed, obscene or intimate photos or videos used?",
    "promise_of_high_returns": "Was the victim promised high profits or returns?",
    "paid_tasks_or_job_offer": "Was the victim offered a job or paid online tasks?",
    "advance_or_fee_payment": "Did the victim pay an advance, fee, charge or deposit first?",
    "fake_marketplace_listing": "Was a fake item listed for sale online, for example on OLX?",
    "fake_relationship_or_marriage": "Did the offender build a romantic or marriage relationship?",
    "loan_app_recovery_harassment": "Did loan app recovery agents harass the victim or the victim's contacts?",
    "money_to_mule_account": "Was money transferred to a bank account or UPI ID given by the offender?",
    "motorcycle_used": "Did the offenders come or flee on a motorcycle, bike or scooter?",
    "weapon_shown": "Was a knife, gun, pipe or other weapon used or shown?",
    "forced_entry": "Was a lock, door, window or grill broken to get inside?",
    "premises_unoccupied": "Was the house or shop locked or empty at the time?",
    "vehicle_taken_from_parking": "Was a vehicle stolen from where it was parked?",
    "physical_violence": "Was the victim beaten, hit or physically hurt?",
    "verbal_threat_in_person": "Was the victim threatened face to face or over a personal dispute?",
}


def narrative_for_models(narrative: str, max_chars: int = 1800) -> str:
    """Laya's English checkpoint reads ~512 tokens; keep the story, trim the tail if very long."""
    return narrative if len(narrative) <= max_chars else narrative[:max_chars]


def laya_questions(tax: Taxonomy) -> tuple[dict, dict[str, str]]:
    """Returns (questions, readable-label -> minor-id map)."""
    criteria, label_to_id = {}, {}
    for minor_id, spec in tax.minor.items():
        criteria[spec["label"]] = spec["hint"]
        label_to_id[spec["label"]] = minor_id
    questions: dict = {
        "crime_minor": {"type": "choice", "instructions": "What exact type of crime is reported in this police "
                                                          "complaint?", "criteria": criteria},
        "victim_female": {"type": "noul", "instructions": "Is the complainant or victim a woman?"},
        "accused_identified": {"type": "noul", "instructions": "Is any accused person identified by name?"},
    }
    for flag, text in MO_QUESTIONS.items():
        questions[f"mo:{flag}"] = {"type": "noul", "instructions": text}
    return questions, label_to_id


def interpret_laya(answers: dict, label_to_id: dict[str, str], tax: Taxonomy, mo_threshold: float) -> dict:
    minor_ans = answers["crime_minor"]
    minor = label_to_id[minor_ans["choice"]]
    probs = {label_to_id[k]: round(float(v), 4) for k, v in (minor_ans.get("probabilities") or {}).items()
             if k in label_to_id}
    mo = {k.split(":", 1)[1]: round(float(v["noul"]), 3) for k, v in answers.items() if k.startswith("mo:")}
    return {
        "crime_minor": minor,
        "crime_major": tax.major_of(minor),
        "confidence": float(minor_ans.get("answer_confidence", minor_ans.get("confidence", 0.0))),
        "probabilities": probs,
        "mo_flags": {k: p for k, p in mo.items() if p >= mo_threshold},
        "mo_probabilities": mo,
        "victim_female": float(answers["victim_female"]["noul"]),
    }


# ----------------------------------------------------------------------------- LLM (System 2)

class LlmAccused(BaseModel):
    name: str | None = None
    alias: str | None = None
    description: str | None = None
    claimed_identity: bool = False


class LlmVictim(BaseModel):
    gender: Literal["male", "female", "other", "unknown"] = "unknown"
    age_group: Literal["below_18", "18_30", "31_45", "46_60", "above_60", "unknown"] = "unknown"
    occupation: str | None = None


class LlmEnrichment(BaseModel):
    crime_minor: str
    mo_flags: list[str] = Field(default_factory=list)
    accused: list[LlmAccused] = Field(default_factory=list)
    victim: LlmVictim = Field(default_factory=LlmVictim)
    summary: str = Field(min_length=10, max_length=600)

    @field_validator("summary")
    @classmethod
    def no_chatter(cls, v: str) -> str:
        if re.match(r"^\s*(here is|sure|certainly|as an ai)", v, re.I):
            raise ValueError("summary contains assistant chatter")
        return v.strip()


def llm_messages(tax: Taxonomy, narrative: str, header_hint: str) -> tuple[str, str, dict]:
    minors = "\n".join(f"- {k}: {v['label']} ({v['hint']})" for k, v in tax.minor.items())
    flags = "\n".join(f"- {k}: {v}" for k, v in tax.mo_flags.items())
    system = ("You are a police crime-records analyst. You read one First Information Report and fill a "
              "structured crime-details record. Use only facts written in the FIR. Never guess names. "
              "Respond with a single JSON object and nothing else.")
    prompt = (f"Allowed crime_minor values:\n{minors}\n\nAllowed mo_flags values (choose all that apply):\n{flags}\n\n"
              "JSON fields: crime_minor (one allowed value), mo_flags (list of allowed values), accused (list of "
              "{name, alias, description, claimed_identity}; claimed_identity=true when the name is only what a "
              "fraudster claimed to be), victim {gender, age_group, occupation}, summary (2 factual sentences, "
              "no speculation).\n\n"
              f"FIR header facts: {header_hint or 'not available'}\n\nFIR narrative:\n\"\"\"{narrative}\"\"\"")
    return system, prompt, LlmEnrichment.model_json_schema()


def validate_llm(payload: dict | str, tax: Taxonomy) -> LlmEnrichment:
    """Parse + validate the LLM output; raises ValueError with a reason usable for one repair attempt."""
    import json
    if isinstance(payload, str):
        match = re.search(r"\{.*\}", payload, re.S)
        if not match:
            raise ValueError("no JSON object in the response")
        payload = json.loads(match.group(0))
    try:
        result = LlmEnrichment.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"schema errors: {exc.errors()[:3]}") from exc
    if result.crime_minor not in tax.minor:
        raise ValueError(f"crime_minor '{result.crime_minor}' is not an allowed value")
    unknown = [f for f in result.mo_flags if f not in tax.mo_flags]
    if unknown:
        raise ValueError(f"unknown mo_flags {unknown}")
    return result


# ----------------------------------------------------------------------------- rules fallback (degraded mode)

RULE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cyber.digital_arrest": ("digital arrest", "cbi", "customs", "arrest warrant", "money laundering", "narcotics"),
    "cyber.sextortion": ("obscene", "video call", "nude", "intimate"),
    "cyber.loan_app": ("loan app", "recovery agent", "morphed"),
    "cyber.job_task": ("part-time", "part time", "task", "telegram", "work from home", "review"),
    "cyber.investment_trading": ("trading", "ipo", "stock", "crypto", "invest"),
    "cyber.marketplace": ("olx", "army", "gate pass", "for sale"),
    "cyber.matrimonial": ("matrimon", "shaadi", "marriage", "profile"),
    "cyber.fake_customer_care": ("customer care", "helpline", "refund", "courier", "electricity"),
    "cyber.kyc_bank_impersonation": ("otp", "kyc", "credit card", "debit card", "cvv", "reward points"),
    "property.snatching": ("snatch",),
    "property.robbery": ("knife point", "knife", "robbed", "at gun"),
    "property.burglary": ("lock broken", "lock was broken", "grill", "burglary", "house was locked", "door is open"),
    "property.vehicle_theft": ("parked", "registration no", "vehicle was missing", "gaadi nahi"),
    "body.assault": ("beat", "hit him", "injury", "assault", "stick", "pipe"),
    "body.intimidation": ("threaten", "dhamki", "consequences"),
    "economic.cheating_offline": ("token money", "visa", "placement", "plot", "papers given"),
    "property.theft_other": ("pocket", "wallet", "missing", "stolen", "shortage"),
}


def rules_decide(narrative: str, tax: Taxonomy) -> dict:
    text = narrative.lower()
    scores = {minor: sum(text.count(k) for k in kws) for minor, kws in RULE_KEYWORDS.items()}
    minor = max(scores, key=scores.get) if any(scores.values()) else "property.theft_other"
    return {"crime_minor": minor, "crime_major": tax.major_of(minor), "confidence": 0.3 if scores[minor] else 0.0,
            "probabilities": {}, "mo_flags": {}, "mo_probabilities": {}, "victim_female": None}
