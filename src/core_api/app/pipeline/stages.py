"""Stage handlers. Each receives the RUNNING stage-runs it claimed and must
finish every one of them (succeeded / skipped / failed-with-retry)."""
from __future__ import annotations

import hashlib
import logging
import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.models import Embedding, Entity, Fir, FirAnalysis, FirStageRun
from ..domain.enums import DecidedBy, FirStatus, RunStatus, Stage
from ..domain.taxonomy import get_taxonomy
from ..extraction.accused import extract_accused, normalize_person
from ..extraction.amounts import total_loss
from ..extraction.fir_parser import parse_fir
from ..extraction.identifiers import extract_identifiers
from ..models_client.client import ModelUnavailable, get_model_client
from ..services.llm_usage import record_usage, tokens_used_this_month
from . import decisions
from .queue import mark_failed, mark_skipped, mark_succeeded

log = logging.getLogger("crimefir.pipeline")

AGE_GROUPS = ((17, "below_18"), (30, "18_30"), (45, "31_45"), (60, "46_60"), (200, "above_60"))


def _age_group(age: int | None) -> str | None:
    if age is None:
        return None
    return next(g for limit, g in AGE_GROUPS if age <= limit)


def _analysis(session: Session, fir_id: str) -> FirAnalysis:
    a = session.get(FirAnalysis, fir_id)
    if a is None:
        a = FirAnalysis(fir_id=fir_id, review_reasons=[], model_versions={})
        session.add(a)
    return a


def _add_review(a: FirAnalysis, reason: str) -> None:
    a.needs_review = True
    a.review_reasons = sorted(set((a.review_reasons or []) + [reason]))


def _set_model_version(a: FirAnalysis, key: str, value: str | None) -> None:
    versions = dict(a.model_versions or {})
    versions[key] = value
    a.model_versions = versions


# ----------------------------------------------------------------------------- extract (rules, local)

def run_extract(session: Session, runs: list[FirStageRun]) -> None:
    for run in runs:
        try:
            fir = session.get(Fir, run.fir_id)
            parsed = parse_fir(fir.raw_text)
            session.execute(delete(Entity).where(Entity.fir_id == fir.id))      # idempotent re-run
            for ident in extract_identifiers(parsed.raw_text, parsed.spans.get("complainant")):
                session.add(Entity(fir_id=fir.id, type=ident.type, raw=ident.raw, value=ident.value,
                                   role=ident.role, start=ident.start, end=ident.end, source="regex"))
            accused = []
            for m in extract_accused(parsed.fields.get("accused"), parsed.narrative):
                accused.append({"as_written": m.as_written, "name": m.name, "alias": m.alias, "source": m.source})
                if m.source == "claimed":
                    session.add(Entity(fir_id=fir.id, type="claimed_identity", raw=m.as_written, value=m.name,
                                       role="offender", source="regex"))
                    continue
                if m.name:
                    session.add(Entity(fir_id=fir.id, type="accused_name", raw=m.as_written, value=m.name,
                                       role="offender", source=m.source))
                if m.alias:
                    session.add(Entity(fir_id=fir.id, type="accused_alias", raw=m.as_written, value=m.alias,
                                       role="offender", source=m.source))
            a = _analysis(session, fir.id)
            a.accused = accused
            a.amount = total_loss(parsed.fields.get("property"), parsed.narrative)
            a.victim = {"age": parsed.complainant_age, "age_group": _age_group(parsed.complainant_age),
                        "occupation": parsed.complainant_occupation, "gender": None}
            fir.status = FirStatus.PROCESSING
            mark_succeeded(session, run, provider="rules")
        except Exception as exc:                                     # bug or bad data: do not retry forever
            log.exception("extract failed for %s", run.fir_id)
            mark_failed(session, run, error_code="extract_error", message=str(exc), transient=False)


# ----------------------------------------------------------------------------- decide (Laya, System 1)

def run_decide(session: Session, runs: list[FirStageRun]) -> None:
    s, tax = get_settings(), get_taxonomy()
    questions, label_to_id = decisions.laya_questions(tax)
    firs = {r.fir_id: session.get(Fir, r.fir_id) for r in runs}
    items = [{"id": fid, "text": decisions.narrative_for_models(f.narrative), "questions": questions}
             for fid, f in firs.items()]
    try:
        results, meta = get_model_client().decide(items, checkpoint=decisions.LAYA_CHECKPOINT)
        by_id = {r["id"]: r for r in results}
    except ModelUnavailable as exc:
        log.warning("decide: model service unavailable (%s); using rules fallback", exc)
        for run in runs:
            a = _analysis(session, run.fir_id)
            _apply_decision(a, decisions.rules_decide(firs[run.fir_id].narrative, tax), DecidedBy.RULES)
            _add_review(a, "AI decision model unavailable: classified by keyword rules")
            mark_succeeded(session, run, provider=DecidedBy.RULES, note="model service unavailable")
        return
    for run in runs:
        try:
            decision = decisions.interpret_laya(by_id[run.fir_id]["answers"], label_to_id, tax, s.mo_flag_threshold)
            a = _analysis(session, run.fir_id)
            _apply_decision(a, decision, DecidedBy.LAYA)
            _set_model_version(a, "decision", meta.model_id)
            if decision["confidence"] < s.decision_min_confidence:
                a.escalated = True
            mark_succeeded(session, run, provider=DecidedBy.LAYA, model_id=meta.model_id, device=meta.device,
                           note=f"confidence {decision['confidence']:.2f}")
        except Exception as exc:
            log.exception("decide failed for %s", run.fir_id)
            mark_failed(session, run, error_code="decide_error", message=str(exc), transient=False)


def _apply_decision(a: FirAnalysis, d: dict, by: DecidedBy) -> None:
    a.crime_minor, a.crime_major = d["crime_minor"], d["crime_major"]
    a.crime_confidence, a.crime_probabilities = d["confidence"], d["probabilities"]
    a.mo_flags = d["mo_flags"]
    a.decided_by = by
    if d.get("victim_female") is not None:
        victim = dict(a.victim or {})
        victim["gender"] = "female" if d["victim_female"] >= 0.5 else "male"
        a.victim = victim


# ----------------------------------------------------------------------------- enrich (Granite LLM, System 2)

def run_enrich(session: Session, runs: list[FirStageRun]) -> None:
    s, tax = get_settings(), get_taxonomy()
    for run in runs:
        a = _analysis(session, run.fir_id)
        if not a.escalated:
            mark_skipped(session, run, f"not needed: decision confidence {a.crime_confidence or 0:.2f} "
                                       f">= {s.decision_min_confidence:.2f}")
            continue
        if tokens_used_this_month(session) >= s.llm_monthly_token_budget:
            _add_review(a, "low decision confidence; monthly LLM token budget reached")
            mark_skipped(session, run, "LLM token budget reached")
            continue
        fir = session.get(Fir, run.fir_id)
        header_hint = "; ".join(x for x in (fir.complainant_text and f"complainant: {fir.complainant_text}",
                                             fir.accused_header and f"accused: {fir.accused_header}") if x)
        system, prompt, schema = decisions.llm_messages(tax, decisions.narrative_for_models(fir.narrative, 3000),
                                                        header_hint)
        try:
            result, meta = _generate_validated(session, system, prompt, schema, tax)
        except ModelUnavailable as exc:
            if exc.transient and mark_failed(session, run, error_code="llm_unavailable", message=str(exc),
                                             transient=True):
                continue                                             # will retry with backoff
            if run.status != RunStatus.FAILED:
                mark_skipped(session, run, f"LLM unavailable: {exc}")
            _add_review(a, "low decision confidence; LLM unavailable for a second opinion")
            continue
        except ValueError as exc:
            _add_review(a, "low decision confidence; LLM answer failed validation")
            mark_skipped(session, run, f"LLM output invalid after repair: {exc}")
            continue
        _apply_enrichment(session, fir, a, result, meta.model_id)
        mark_succeeded(session, run, provider=DecidedBy.LLM, model_id=meta.model_id, device=meta.device)


def _generate_validated(session: Session, system: str, prompt: str, schema: dict, tax):
    client = get_model_client()
    data, meta = client.generate(system=system, prompt=prompt, json_schema=schema)
    record_usage(session, data, meta.model_id, "enrich")
    try:
        return decisions.validate_llm(data.get("json") or data.get("text", ""), tax), meta
    except ValueError as first_error:                                # one repair attempt
        repair = f"{prompt}\n\nYour previous answer was invalid: {first_error}. Return only the corrected JSON."
        data, meta = client.generate(system=system, prompt=repair, json_schema=schema)
        record_usage(session, data, meta.model_id, "enrich-repair")
        return decisions.validate_llm(data.get("json") or data.get("text", ""), tax), meta


def _apply_enrichment(session: Session, fir: Fir, a: FirAnalysis, r: decisions.LlmEnrichment,
                      model_id: str | None) -> None:
    tax = get_taxonomy()
    a.crime_minor, a.crime_major = r.crime_minor, tax.major_of(r.crime_minor)
    a.mo_flags = {f: 1.0 for f in r.mo_flags}
    a.decided_by = DecidedBy.LLM
    a.summary, a.summary_by = r.summary, DecidedBy.LLM
    victim = dict(a.victim or {})
    if r.victim.gender != "unknown":
        victim["gender"] = r.victim.gender
    if r.victim.age_group != "unknown" and not victim.get("age_group"):
        victim["age_group"] = r.victim.age_group
    victim["occupation"] = victim.get("occupation") or r.victim.occupation
    a.victim = victim
    known = {(x.get("name"), x.get("alias")) for x in (a.accused or [])}
    accused = list(a.accused or [])
    for person in r.accused:
        name = normalize_person(person.name) if person.name else None
        alias = normalize_person(person.alias) if person.alias else None
        if (name, alias) in known or not (name or alias):
            continue
        source = "claimed" if person.claimed_identity else "llm"
        accused.append({"as_written": person.name or person.alias, "name": name, "alias": alias, "source": source})
        etype = "claimed_identity" if person.claimed_identity else "accused_name"
        if name:
            session.add(Entity(fir_id=fir.id, type=etype, raw=person.name, value=name, role="offender",
                               source="llm"))
        if alias and not person.claimed_identity:
            session.add(Entity(fir_id=fir.id, type="accused_alias", raw=person.alias, value=alias,
                               role="offender", source="llm"))
    a.accused = accused
    _set_model_version(a, "generator", model_id)


# ----------------------------------------------------------------------------- embed (Granite Embedding)

def run_embed(session: Session, runs: list[FirStageRun]) -> None:
    firs = {r.fir_id: session.get(Fir, r.fir_id) for r in runs}
    texts = [decisions.narrative_for_models(f.narrative) for f in firs.values()]
    try:
        vectors, meta = get_model_client().embed(texts)
    except ModelUnavailable as exc:
        for run in runs:
            if not mark_failed(session, run, error_code="embed_unavailable", message=str(exc),
                               transient=exc.transient):
                _finalize_fir(session, run.fir_id)
        return
    for run, text, vec in zip(runs, texts, vectors):
        arr = np.asarray(vec, dtype=np.float32)
        norm = float(np.linalg.norm(arr)) or 1.0
        emb = session.get(Embedding, run.fir_id) or Embedding(fir_id=run.fir_id)
        emb.model_id, emb.dim = meta.model_id or "unknown", len(arr)
        emb.vector = (arr / norm).astype("<f4").tobytes()
        emb.text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        session.merge(emb)
        mark_succeeded(session, run, provider="embedding", model_id=meta.model_id, device=meta.device)
        _finalize_fir(session, run.fir_id)


# ----------------------------------------------------------------------------- finalisation

def _template_summary(fir: Fir, a: FirAnalysis) -> str:
    tax = get_taxonomy()
    parts = [f"{tax.minor_label(a.crime_minor)} reported" if a.crime_minor else "Complaint reported"]
    if fir.station:
        parts.append(f"at {fir.station.name} PS ({fir.station.district})")
    if fir.registered_at:
        parts.append(f"on {fir.registered_at:%d %b %Y}")
    text = " ".join(parts) + "."
    if a.amount:
        text += f" Loss about Rs {a.amount:,}."
    if a.mo_flags:
        text += " Method: " + ", ".join(f.replace("_", " ") for f in list(a.mo_flags)[:4]) + "."
    return text


def _finalize_fir(session: Session, fir_id: str) -> None:
    """Called when the last stage of a FIR has ended: set the FIR's overall status."""
    fir = session.get(Fir, fir_id)
    runs = session.scalars(select(FirStageRun).where(FirStageRun.fir_id == fir_id)).all()
    a = session.get(FirAnalysis, fir_id)
    if any(r.stage == Stage.EXTRACT and r.status == RunStatus.FAILED for r in runs) or a is None:
        fir.status = FirStatus.FAILED
        return
    if not a.summary:
        a.summary, a.summary_by = _template_summary(fir, a), "template"
    fir.status = FirStatus.NEEDS_REVIEW if a.needs_review else FirStatus.ANALYZED


HANDLERS = {Stage.EXTRACT: run_extract, Stage.DECIDE: run_decide, Stage.ENRICH: run_enrich, Stage.EMBED: run_embed}
