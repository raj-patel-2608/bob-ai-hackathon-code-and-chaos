"""FIR case files: list, detail (auto-drafted I.I.F.-II), related FIRs, explanations, officer review."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db.engine import get_session
from ..db.models import AuditLog, ClusterMember, Entity, Fir, FirAnalysis, FirStageRun, Link, Station
from ..domain.enums import FirStatus, LinkKind
from ..domain.taxonomy import get_taxonomy
from ..extraction.identifiers import normalize_phone

router = APIRouter(prefix="/api", tags=["firs"])

PHONE_IN_TEXT = re.compile(r"(Mob\.?\s*)([+\d][\d \-]{8,16}\d)")


def mask_complainant(text: str | None) -> str | None:
    """Complainant phone numbers are personal data: masked in API responses."""
    if not text:
        return text
    return PHONE_IN_TEXT.sub(lambda m: m.group(1) + "XXXXXX" + re.sub(r"\D", "", m.group(2))[-4:], text)


def fir_row(fir: Fir, a: FirAnalysis | None) -> dict:
    tax = get_taxonomy()
    return {
        "id": fir.id, "fir_no": fir.fir_no, "status": fir.status,
        "station": fir.station.name if fir.station else None,
        "district": fir.station.district if fir.station else None,
        "registered_at": fir.registered_at,
        "crime_major": a.crime_major if a else None,
        "crime_major_label": tax.major_label(a.crime_major) if a and a.crime_major else None,
        "crime_minor": a.crime_minor if a else None,
        "crime_minor_label": tax.minor_label(a.crime_minor) if a and a.crime_minor else None,
        "confidence": a.crime_confidence if a else None, "decided_by": a.decided_by if a else None,
        "amount": a.amount if a else None, "needs_review": bool(a and a.needs_review),
        "summary": a.summary if a else None,
    }


def _get_fir(session: Session, fir_id: str) -> Fir:
    fir = session.get(Fir, fir_id)
    if fir is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"FIR {fir_id} not found")
    return fir


@router.get("/firs")
def list_firs(station_id: int | None = None, crime_major: str | None = None, crime_minor: str | None = None,
              fir_status: str | None = Query(None, alias="status"), needs_review: bool | None = None,
              q: str | None = None, limit: int = Query(50, le=500), offset: int = 0,
              session: Session = Depends(get_session)) -> dict:
    stmt = select(Fir, FirAnalysis).outerjoin(FirAnalysis, FirAnalysis.fir_id == Fir.id)
    if station_id:
        stmt = stmt.where(Fir.station_id == station_id)
    if crime_major:
        stmt = stmt.where(FirAnalysis.crime_major == crime_major)
    if crime_minor:
        stmt = stmt.where(FirAnalysis.crime_minor == crime_minor)
    if fir_status:
        stmt = stmt.where(Fir.status == fir_status)
    if needs_review is not None:
        stmt = stmt.where(FirAnalysis.needs_review == needs_review)
    if q:
        stmt = stmt.where(or_(*_search_conditions(q)))
    total = len(session.execute(stmt).all())
    rows = session.execute(stmt.order_by(Fir.registered_at.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [fir_row(f, a) for f, a in rows]}


def _search_conditions(q: str):
    """Free text, FIR id, or any identifier in any format (phone numbers are normalised first)."""
    q = q.strip()
    conditions = [Fir.id.ilike(f"%{q}%"), Fir.narrative.ilike(f"%{q}%")]
    candidates = {q.lower(), re.sub(r"[\s\-]", "", q).upper(), re.sub(r"\D", "", q)}
    phone = normalize_phone(q)
    if phone:
        candidates.add(phone)
    candidates.discard("")
    conditions.append(Fir.id.in_(select(Entity.fir_id).where(Entity.value.in_(candidates))))
    digits = re.sub(r"\D", "", q)
    if len(digits) >= 5:                                   # partial number an investigator remembers
        conditions.append(Fir.id.in_(select(Entity.fir_id).where(Entity.role != "complainant",
                                                                 Entity.value.contains(digits))))
    return conditions


@router.get("/firs/{fir_id}")
def get_fir(fir_id: str, session: Session = Depends(get_session)) -> dict:
    tax = get_taxonomy()
    fir = _get_fir(session, fir_id)
    a = fir.analysis
    entities = session.scalars(select(Entity).where(Entity.fir_id == fir_id).order_by(Entity.start)).all()
    runs = session.scalars(select(FirStageRun).where(FirStageRun.fir_id == fir_id)).all()
    cluster = session.scalar(select(ClusterMember.cluster_id).where(ClusterMember.fir_id == fir_id))
    header_offset = fir.raw_text.find(fir.narrative) if fir.narrative else -1
    body = fir_row(fir, a)
    body.update({
        "header": {"district": fir.station.district if fir.station else None, "fir_no": fir.fir_no,
                   "acts_sections": fir.acts_sections, "occurred_at": fir.occurred_at, "place": fir.place,
                   "complainant": mask_complainant(fir.complainant_text), "accused": fir.accused_header,
                   "property": fir.property_text},
        "narrative": fir.narrative,
        "narrative_offset": header_offset,
        "iif2_draft": None if a is None else {
            "major_head": tax.major_label(a.crime_major) if a.crime_major else None,
            "minor_head": tax.minor_label(a.crime_minor) if a.crime_minor else None,
            "confidence": a.crime_confidence, "decided_by": a.decided_by, "escalated_to_llm": a.escalated,
            "alternatives": sorted(({"minor_head": tax.minor_label(k), "probability": v}
                                    for k, v in (a.crime_probabilities or {}).items()),
                                   key=lambda x: -x["probability"])[:3],
            "methods": [{"flag": f, "label": tax.mo_flags.get(f, f), "probability": p}
                        for f, p in sorted((a.mo_flags or {}).items(), key=lambda x: -x[1])],
            "victim": a.victim, "accused": a.accused, "loss": a.amount,
            "summary": a.summary, "summary_by": a.summary_by,
            "needs_review": a.needs_review, "review_reasons": a.review_reasons, "model_versions": a.model_versions,
        },
        "entities": [{"type": e.type, "raw": e.raw if e.role != "complainant" else "masked", "value":
                      e.value if e.role != "complainant" else "masked", "role": e.role, "source": e.source,
                      "start": e.start, "end": e.end} for e in entities],
        "cluster_id": cluster,
        "pipeline": [{"stage": r.stage, "status": r.status, "provider": r.provider, "model_id": r.model_id,
                      "device": r.device, "attempts": r.attempts, "note": r.note, "error": r.error_message,
                      "duration_ms": r.duration_ms} for r in sorted(runs, key=lambda r: r.id)],
    })
    return body


@router.get("/firs/{fir_id}/related")
def related(fir_id: str, session: Session = Depends(get_session)) -> dict:
    _get_fir(session, fir_id)
    links = session.scalars(select(Link).where(or_(Link.fir_a == fir_id, Link.fir_b == fir_id))
                            .order_by(Link.kind, Link.score.desc())).all()
    others = {l.fir_b if l.fir_a == fir_id else l.fir_a for l in links}
    rows = {f.id: (f, a) for f, a in session.execute(
        select(Fir, FirAnalysis).outerjoin(FirAnalysis, FirAnalysis.fir_id == Fir.id).where(Fir.id.in_(others)))}
    return {"fir_id": fir_id, "related": [
        {**fir_row(*rows[o]), "link_kind": l.kind, "score": l.score, "reasons": explain_link(l)}
        for l in links for o in [l.fir_b if l.fir_a == fir_id else l.fir_a] if o in rows]}


LABELS = {"phone": "phone number", "bank_account": "bank account", "upi_id": "UPI ID", "imei": "IMEI",
          "vehicle": "vehicle number", "online_handle": "online handle / website", "accused_name": "accused name",
          "accused_alias": "accused alias"}


def explain_link(link: Link) -> list[str]:
    ev = link.evidence or {}
    if link.kind == LinkKind.EVIDENCE:
        reasons = [f"Same {LABELS.get(e['type'], e['type'])} {e['value']} (written as \"{e['as_written'][0]}\" and "
                   f"\"{e['as_written'][1]}\")" for e in ev.get("shared", [])]
        for c in ev.get("claimed_identity_also_shared", []):
            reasons.append(f"Offender claimed the same identity in both: \"{c.title()}\" (supporting only)")
        if ev.get("name_only"):
            reasons.append("Linked by name only: verify the person is the same")
    else:
        tax = get_taxonomy()
        reasons = [f"Same crime type: {tax.minor_label(ev['same_crime_type'])}",
                   f"Narratives are {ev['narrative_similarity']:.0%} similar (Granite Embedding)"]
        if ev.get("shared_mo"):
            reasons.append("Same methods: " + ", ".join(m.replace("_", " ") for m in ev["shared_mo"]))
        if ev.get("days_apart") is not None:
            reasons.append(f"{ev['days_apart']} days apart")
        reasons.append("No shared evidence: pattern similarity only")
    reasons.append("Investigation lead only. Requires human verification.")
    return reasons


@router.get("/links/{fir_a}/{fir_b}")
def link_explanation(fir_a: str, fir_b: str, session: Session = Depends(get_session)) -> dict:
    a, b = sorted((fir_a, fir_b))
    links = session.scalars(select(Link).where(Link.fir_a == a, Link.fir_b == b)).all()
    if not links:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "these FIRs are not linked")
    return {"fir_a": a, "fir_b": b, "links": [{"kind": l.kind, "score": l.score, "reasons": explain_link(l),
                                               "evidence": l.evidence} for l in links]}


class Review(BaseModel):
    decision: str                      # confirm | correct
    crime_minor: str | None = None
    note: str | None = None
    officer: str = "officer"


@router.post("/firs/{fir_id}/review")
def review_fir(fir_id: str, body: Review, session: Session = Depends(get_session)) -> dict:
    """Human verification: an officer confirms or corrects the automatic classification."""
    fir = _get_fir(session, fir_id)
    a = fir.analysis
    if a is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "FIR has not been analysed yet")
    tax = get_taxonomy()
    before = a.crime_minor
    if body.decision == "correct":
        if body.crime_minor not in tax.minor:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "crime_minor must be a taxonomy value")
        a.crime_minor, a.crime_major, a.decided_by = body.crime_minor, tax.major_of(body.crime_minor), "officer"
    elif body.decision != "confirm":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "decision must be confirm or correct")
    a.needs_review, a.review_reasons = False, []
    fir.status = FirStatus.ANALYZED
    session.add(AuditLog(action=f"fir.review.{body.decision}", target=fir_id,
                         detail={"officer": body.officer, "before": before, "after": a.crime_minor,
                                 "note": body.note}))
    return fir_row(fir, a)


@router.get("/stations")
def stations(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.execute(select(Station).order_by(Station.district, Station.name)).scalars().all()
    return [{"id": s.id, "name": s.name, "district": s.district} for s in rows]
