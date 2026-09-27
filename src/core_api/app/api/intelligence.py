"""Flagged repeat offenders, investigation graph, station trends and reports, dashboard, evaluation."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db.engine import get_session
from ..db.models import (ClusterMember, Entity, EvalRun, Fir, FirAnalysis, Link, OffenderCluster, Station,
                         StationReport)
from ..services import analytics, evaluation
from .firs import explain_link, fir_row

router = APIRouter(prefix="/api", tags=["intelligence"])


@router.get("/dashboard")
def dashboard(session: Session = Depends(get_session)) -> dict:
    return analytics.dashboard(session)


# ----------------------------------------------------------------------------- repeat offenders

@router.get("/offenders")
def flagged_offenders(min_risk: int = 0, station_id: int | None = None,
                      session: Session = Depends(get_session)) -> dict:
    """The flagged repeat-offender list: clusters of FIRs connected by shared evidence, ranked by risk."""
    stmt = select(OffenderCluster).where(OffenderCluster.risk_score >= min_risk)
    if station_id:
        stmt = stmt.where(OffenderCluster.id.in_(
            select(ClusterMember.cluster_id).join(Fir, Fir.id == ClusterMember.fir_id)
            .where(Fir.station_id == station_id)))
    clusters = session.scalars(stmt.order_by(OffenderCluster.risk_score.desc())).all()
    items = []
    for c in clusters:
        brief = analytics.cluster_brief(c)
        brief["stations"] = sorted({f"{s.name} ({s.district})" for s in session.scalars(
            select(Station).join(Fir, Fir.station_id == Station.id).join(ClusterMember, ClusterMember.fir_id == Fir.id)
            .where(ClusterMember.cluster_id == c.id))})
        items.append(brief)
    return {"total": len(items), "items": items,
            "note": "Clusters are investigation leads built from shared evidence. They require human verification."}


@router.get("/offenders/{cluster_id}")
def offender_cluster(cluster_id: str, session: Session = Depends(get_session)) -> dict:
    c = session.get(OffenderCluster, cluster_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "cluster not found")
    fir_ids = [m.fir_id for m in c.members]
    rows = session.execute(select(Fir, FirAnalysis).outerjoin(FirAnalysis, FirAnalysis.fir_id == Fir.id)
                           .where(Fir.id.in_(fir_ids)).order_by(Fir.registered_at)).all()
    links = session.scalars(select(Link).where(Link.fir_a.in_(fir_ids), Link.fir_b.in_(fir_ids))).all()
    claimed = session.execute(select(Entity.value, func.count(func.distinct(Entity.fir_id)))
                              .where(Entity.fir_id.in_(fir_ids), Entity.type == "claimed_identity")
                              .group_by(Entity.value)).all()
    return {**analytics.cluster_brief(c),
            "timeline": [fir_row(f, a) for f, a in rows],
            "claimed_identities": [{"value": v.title(), "firs": n} for v, n in claimed],
            "links": [{"fir_a": l.fir_a, "fir_b": l.fir_b, "kind": l.kind, "score": l.score,
                       "reasons": explain_link(l)} for l in links],
            "suggested_actions": _suggested_actions(c)}


def _suggested_actions(c: OffenderCluster) -> list[str]:
    actions = []
    for ident in c.key_identifiers[:3]:
        t, v = ident["type"], ident["value"]
        if t in ("bank_account", "upi_id"):
            actions.append(f"Request freeze and KYC/transaction trail for {t.replace('_', ' ')} {v} (bank / NPCI)")
        elif t == "phone":
            actions.append(f"Request CDR, subscriber details and IMEI history for {v} (telecom provider)")
        elif t == "vehicle":
            actions.append(f"Circulate vehicle {v} to patrol units; check ANPR/CCTV and RTO records")
        elif t == "online_handle":
            actions.append(f"Request account and IP logs for {v} from the platform")
        elif t in ("accused_name", "accused_alias"):
            actions.append(f"Check criminal records (CCTNS) for '{v.title()}' and known associates")
    if c.n_stations > 1:
        actions.append(f"Share this cluster with the {c.n_stations} involved stations for a joint investigation")
    return actions


@router.get("/graph")
def graph(cluster_id: str | None = None, fir_id: str | None = None, include_pattern: bool = True,
          session: Session = Depends(get_session)) -> dict:
    """Nodes (FIRs + shared identifiers) and edges for the investigation graph."""
    if cluster_id:
        fir_ids = set(session.scalars(select(ClusterMember.fir_id).where(ClusterMember.cluster_id == cluster_id)))
    elif fir_id:
        linked = session.scalars(select(Link).where(or_(Link.fir_a == fir_id, Link.fir_b == fir_id))).all()
        fir_ids = {fir_id} | {l.fir_a for l in linked} | {l.fir_b for l in linked}
    else:
        fir_ids = set(session.scalars(select(ClusterMember.fir_id)))
        if include_pattern:
            fir_ids |= {x for l in session.scalars(select(Link)) for x in (l.fir_a, l.fir_b)}
    if not fir_ids:
        return {"nodes": [], "edges": []}
    rows = session.execute(select(Fir, FirAnalysis).outerjoin(FirAnalysis, FirAnalysis.fir_id == Fir.id)
                           .where(Fir.id.in_(fir_ids))).all()
    membership = dict(session.execute(select(ClusterMember.fir_id, ClusterMember.cluster_id)
                                      .where(ClusterMember.fir_id.in_(fir_ids))).all())
    nodes = [{"id": f.id, "type": "fir", **fir_row(f, a), "cluster_id": membership.get(f.id)} for f, a in rows]
    edges = []
    links = session.scalars(select(Link).where(Link.fir_a.in_(fir_ids), Link.fir_b.in_(fir_ids))).all()
    identity_nodes = {}
    for l in links:
        if l.kind == "PATTERN":
            if include_pattern:
                edges.append({"source": l.fir_a, "target": l.fir_b, "kind": "PATTERN", "score": l.score})
            continue
        for e in l.evidence.get("shared", []):
            node_id = f"{e['type']}:{e['value']}"
            identity_nodes[node_id] = {"id": node_id, "type": "identity", "identity_type": e["type"],
                                       "label": e["value"]}
            for fir in (l.fir_a, l.fir_b):
                edge = {"source": fir, "target": node_id, "kind": "EVIDENCE", "identity_type": e["type"]}
                if edge not in edges:
                    edges.append(edge)
    return {"nodes": nodes + list(identity_nodes.values()), "edges": edges}


# ----------------------------------------------------------------------------- stations

def _period(date_from: str | None, date_to: str | None, session: Session) -> tuple[datetime, datetime]:
    latest = session.scalar(select(func.max(Fir.registered_at))) or datetime.now()
    end = datetime.fromisoformat(date_to) + timedelta(days=1) if date_to else \
        datetime(latest.year, latest.month, latest.day) + timedelta(days=1)
    start = datetime.fromisoformat(date_from) if date_from else end - timedelta(days=30)
    if start >= end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "date_from must be before date_to")
    return start, end


@router.get("/stations/{station_id}/trends")
def station_trends(station_id: int, date_from: str | None = None, date_to: str | None = None,
                   session: Session = Depends(get_session)) -> dict:
    """Station-level facts for a period (default: last 30 days of data) compared with the previous period."""
    start, end = _period(date_from, date_to, session)
    try:
        return analytics.station_facts(session, station_id, start, end)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


class ReportRequest(BaseModel):
    date_from: str | None = None
    date_to: str | None = None


@router.post("/stations/{station_id}/reports", status_code=status.HTTP_201_CREATED)
def create_station_report(station_id: int, body: ReportRequest, session: Session = Depends(get_session)) -> dict:
    """Station-level crime trend summary: facts + narrative (Granite LLM, number-checked; template fallback)."""
    start, end = _period(body.date_from, body.date_to, session)
    try:
        report = analytics.generate_report(session, station_id, start, end)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _report_out(report)


@router.get("/stations/{station_id}/reports")
def list_station_reports(station_id: int, session: Session = Depends(get_session)) -> list[dict]:
    reports = session.scalars(select(StationReport).where(StationReport.station_id == station_id)
                              .order_by(StationReport.created_at.desc()).limit(20)).all()
    return [_report_out(r) for r in reports]


def _report_out(r: StationReport) -> dict:
    return {"id": r.id, "station_id": r.station_id, "period_from": r.period_from, "period_to": r.period_to,
            "narrative": r.narrative, "generated_by": r.generated_by, "validated": r.validated, "facts": r.facts,
            "created_at": r.created_at}


# ----------------------------------------------------------------------------- evaluation

@router.post("/evaluation/run")
def run_evaluation(split: str = Query("test", pattern="^(dev|test|all)$"),
                   session: Session = Depends(get_session)) -> dict:
    return evaluation.evaluate(session, split)


@router.get("/evaluation/latest")
def latest_evaluation(session: Session = Depends(get_session)) -> dict:
    run = session.scalar(select(EvalRun).order_by(EvalRun.created_at.desc()))
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no evaluation run yet")
    return {"created_at": run.created_at, "split": run.split, "settings": run.settings, "metrics": run.metrics}
