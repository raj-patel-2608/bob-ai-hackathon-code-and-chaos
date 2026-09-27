"""Dashboard numbers, station-level trend facts and the station trend summary (PS10 output 4)."""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import (ClusterMember, Fir, FirAnalysis, Link, OffenderCluster, Station, StationReport,
                         utcnow)
from ..domain.enums import FirStatus, LinkKind
from ..domain.taxonomy import get_taxonomy
from ..models_client.client import ModelUnavailable, get_model_client
from .llm_usage import record_usage

log = logging.getLogger("crimefir.analytics")


def dashboard(session: Session) -> dict:
    tax = get_taxonomy()
    rows = session.execute(select(Fir.id, Fir.status, Fir.registered_at, Station.name, Station.district,
                                  FirAnalysis.crime_major, FirAnalysis.crime_minor, FirAnalysis.decided_by,
                                  FirAnalysis.amount)
                           .outerjoin(Station, Station.id == Fir.station_id)
                           .outerjoin(FirAnalysis, FirAnalysis.fir_id == Fir.id)).all()
    by_minor = Counter(r.crime_minor for r in rows if r.crime_minor)
    by_major = Counter(r.crime_major for r in rows if r.crime_major)
    clusters = session.scalars(select(OffenderCluster).order_by(OffenderCluster.risk_score.desc())).all()
    return {
        "total_firs": len(rows),
        "status": dict(Counter(r.status for r in rows)),
        "needs_review": sum(1 for r in rows if r.status == FirStatus.NEEDS_REVIEW),
        "decided_by": dict(Counter(r.decided_by for r in rows if r.decided_by)),
        "total_loss": sum(r.amount or 0 for r in rows),
        "crime_major": [{"id": k, "label": tax.major_label(k), "count": v} for k, v in by_major.most_common()],
        "crime_minor": [{"id": k, "label": tax.minor_label(k), "major": tax.major_of(k), "count": v}
                        for k, v in by_minor.most_common()],
        "stations": [{"station": k[0], "district": k[1], "count": v} for k, v in
                     Counter((r.name, r.district) for r in rows if r.name).most_common()],
        "monthly": sorted(Counter(r.registered_at.strftime("%Y-%m") for r in rows if r.registered_at).items()),
        "links": {k: v for k, v in session.execute(select(Link.kind, func.count()).group_by(Link.kind)).all()},
        "flagged_clusters": len(clusters),
        "high_risk_clusters": sum(1 for c in clusters if c.risk_level == "HIGH"),
        "top_clusters": [cluster_brief(c) for c in clusters[:5]],
    }


def cluster_brief(c: OffenderCluster) -> dict:
    return {"id": c.id, "risk_score": c.risk_score, "risk_level": c.risk_level, "n_firs": c.n_firs,
            "n_stations": c.n_stations, "n_districts": c.n_districts, "total_loss": c.total_loss,
            "first_seen": c.first_seen, "last_seen": c.last_seen, "key_identifiers": c.key_identifiers,
            "crime_types": c.crime_types, "risk_factors": c.risk_factors}


# ----------------------------------------------------------------------------- station facts

def station_facts(session: Session, station_id: int, period_from: datetime, period_to: datetime) -> dict:
    tax = get_taxonomy()
    station = session.get(Station, station_id)
    if station is None:
        raise LookupError(f"station {station_id} not found")
    span = period_to - period_from
    prev_from = period_from - span

    def load(start, end):
        return session.execute(select(Fir, FirAnalysis).outerjoin(FirAnalysis, FirAnalysis.fir_id == Fir.id)
                               .where(Fir.station_id == station_id, Fir.registered_at >= start,
                                      Fir.registered_at < end)).all()

    current, previous = load(period_from, period_to), load(prev_from, period_from)
    cur_types = Counter(a.crime_minor for _, a in current if a and a.crime_minor)
    prev_types = Counter(a.crime_minor for _, a in previous if a and a.crime_minor)
    rising = sorted(((t, cur_types[t], prev_types.get(t, 0)) for t in cur_types),
                    key=lambda x: (x[2] - x[1], -x[1]))
    mo = Counter(flag for _, a in current if a for flag in (a.mo_flags or {}))
    fir_ids = [f.id for f, _ in current]

    cluster_rows = session.execute(select(OffenderCluster, func.count(ClusterMember.fir_id))
                                   .join(ClusterMember, ClusterMember.cluster_id == OffenderCluster.id)
                                   .where(ClusterMember.fir_id.in_(fir_ids))
                                   .group_by(OffenderCluster.id)
                                   .order_by(OffenderCluster.risk_score.desc())).all() if fir_ids else []
    cross = session.execute(select(Link).where(Link.kind == LinkKind.EVIDENCE,
                                               (Link.fir_a.in_(fir_ids)) | (Link.fir_b.in_(fir_ids)))).scalars().all() \
        if fir_ids else []
    other_ids = {l.fir_b if l.fir_a in fir_ids else l.fir_a for l in cross} - set(fir_ids)
    other_stations = Counter()
    if other_ids:
        for name, district in session.execute(select(Station.name, Station.district)
                                              .join(Fir, Fir.station_id == Station.id)
                                              .where(Fir.id.in_(other_ids), Fir.station_id != station_id)):
            other_stations[f"{name} ({district})"] += 1

    n_cur, n_prev = len(current), len(previous)
    return {
        "station": station.name, "district": station.district,
        "period": {"from": period_from.date().isoformat(), "to": (period_to - timedelta(days=1)).date().isoformat()},
        "firs": n_cur, "previous_period_firs": n_prev,
        "change_pct": round((n_cur - n_prev) * 100 / n_prev) if n_prev else None,
        "total_loss": sum((a.amount or 0) for _, a in current if a),
        "senior_citizen_victims": sum(1 for _, a in current if a and (a.victim or {}).get("age_group") == "above_60"),
        "crime_types": [{"type": tax.minor_label(t), "count": c, "previous": prev_types.get(t, 0)}
                        for t, c in cur_types.most_common()],
        "rising": [{"type": tax.minor_label(t), "count": c, "previous": p} for t, c, p in rising if c > p][:3],
        "top_methods": [{"method": tax.mo_flags[m], "count": c} for m, c in mo.most_common(5)],
        "flagged_clusters": [{"id": c.id, "risk_level": c.risk_level, "risk_score": c.risk_score,
                              "firs_here": n, "firs_total": c.n_firs, "stations": c.n_stations,
                              "districts": c.n_districts,
                              "key_identifier": (c.key_identifiers or [{}])[0]} for c, n in cluster_rows],
        "linked_firs_at_other_stations": [{"station": k, "firs": v} for k, v in other_stations.most_common(5)],
        "pending_review": sum(1 for f, _ in current if f.status == FirStatus.NEEDS_REVIEW),
    }


# ----------------------------------------------------------------------------- narrative

def template_narrative(f: dict) -> str:
    lines = [f"Station crime brief: {f['station']} ({f['district']}), {f['period']['from']} to {f['period']['to']}."]
    change = f" ({'+' if (f['change_pct'] or 0) >= 0 else ''}{f['change_pct']}% vs previous period)" \
        if f["change_pct"] is not None else ""
    lines.append(f"{f['firs']} FIRs registered{change}; total reported loss Rs {f['total_loss']:,}.")
    if f["crime_types"]:
        top = ", ".join(f"{c['type']} ({c['count']})" for c in f["crime_types"][:3])
        lines.append(f"Main crime types: {top}.")
    if f["rising"]:
        lines.append("Rising: " + ", ".join(f"{r['type']} {r['previous']} -> {r['count']}" for r in f["rising"]) + ".")
    if f["top_methods"]:
        lines.append("Most common methods: " + "; ".join(m["method"] for m in f["top_methods"][:3]) + ".")
    if f["senior_citizen_victims"]:
        lines.append(f"{f['senior_citizen_victims']} victims were senior citizens.")
    for c in f["flagged_clusters"][:3]:
        lines.append(f"Flagged repeat-offender cluster {c['id']} ({c['risk_level']} risk): {c['firs_here']} FIR(s) here, "
                     f"{c['firs_total']} in total across {c['stations']} stations.")
    if f["linked_firs_at_other_stations"]:
        lines.append("Evidence links to other stations: " + ", ".join(
            f"{x['station']} ({x['firs']})" for x in f["linked_firs_at_other_stations"]) + ".")
    if f["pending_review"]:
        lines.append(f"{f['pending_review']} FIR(s) await officer review of the automatic classification.")
    lines.append("All links are investigation leads and require human verification.")
    return " ".join(lines)


def _numbers_are_grounded(text: str, facts: dict) -> bool:
    allowed = set(re.findall(r"\d+", json.dumps(facts).replace(",", "")))
    allowed |= {str(n) for n in range(0, 11)}
    used = re.findall(r"\d+", text.replace(",", ""))
    return all(n in allowed for n in used)


def generate_report(session: Session, station_id: int, period_from: datetime, period_to: datetime) -> StationReport:
    facts = station_facts(session, station_id, period_from, period_to)
    narrative, by, validated = template_narrative(facts), "template", True
    system = ("You write short, factual crime-trend briefs for a Station House Officer. Use only the facts given. "
              "Do not invent numbers, names or events. Mention that links are leads needing verification.")
    prompt = ("Write a brief (max 170 words, plain text, no headings) for the Station House Officer from these "
              f"facts, highlighting rising crime types, repeat-offender clusters and suggested focus areas:\n"
              f"{json.dumps(facts, default=str)}")
    try:
        data, meta = get_model_client().generate(system=system, prompt=prompt, max_tokens=350)
        text = (data.get("text") or "").strip()
        record_usage(session, data, meta.model_id, "station_report")
        if text and _numbers_are_grounded(text, facts):
            narrative, by, validated = text, f"llm:{meta.model_id}", True
        else:
            log.warning("LLM station brief rejected (ungrounded numbers); using template")
    except ModelUnavailable as exc:
        log.info("station brief uses template: %s", exc)
    report = StationReport(station_id=station_id, period_from=period_from, period_to=period_to, facts=facts,
                           narrative=narrative, generated_by=by, validated=validated, created_at=utcnow())
    session.add(report)
    session.flush()
    return report
