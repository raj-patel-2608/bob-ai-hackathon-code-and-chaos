"""Cross-FIR intelligence: links, repeat-offender clusters and risk scores.

EVIDENCE links  two FIRs share a hard identifier (phone, bank account, UPI ID, IMEI,
                vehicle, online handle) or a resolved accused name/alias.
PATTERN links   same crime type + similar narrative (Granite Embedding cosine) within a
                time window, with no shared evidence. Shown as leads, never used to flag
                an offender.
Clusters        connected components (NetworkX) of the FIR <-> identity graph built from
                evidence only. A cluster is a "flagged repeat-offender signature".

The whole layer is recomputed after each batch (fast at this scale) so it is always
consistent with the data.
"""
from __future__ import annotations

import itertools
import logging
from collections import defaultdict

import networkx as nx
import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.models import ClusterMember, Embedding, Entity, Fir, FirAnalysis, Link, OffenderCluster
from ..domain.enums import LinkKind

log = logging.getLogger("crimefir.intelligence")

# how strongly one shared identifier of each type suggests the same offender
EVIDENCE_WEIGHT = {"bank_account": 0.95, "upi_id": 0.95, "phone": 0.90, "imei": 0.90, "online_handle": 0.85,
                   "vehicle": 0.80, "accused_name": 0.70, "accused_alias": 0.50}
IDENTITY_TYPES = tuple(EVIDENCE_WEIGHT)
NAME_TYPES = {"accused_name", "accused_alias"}
HUB_LIMIT = 40          # an identifier in more FIRs than this is probably generic (helpline, own bank) -> ignored


def _noisy_or(weights: list[float]) -> float:
    p = 1.0
    for w in weights:
        p *= 1.0 - w
    return round(1.0 - p, 4)


def rebuild(session: Session) -> dict:
    s = get_settings()
    session.execute(delete(ClusterMember))
    session.execute(delete(OffenderCluster))
    session.execute(delete(Link))

    rows = session.execute(select(Entity.fir_id, Entity.type, Entity.value, Entity.raw)
                           .where(Entity.role.in_(("offender", "property")),
                                  Entity.type.in_(IDENTITY_TYPES + ("claimed_identity",)))).all()
    identity_firs: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    claimed: dict[str, set[str]] = defaultdict(set)
    for fir_id, etype, value, raw in rows:
        if etype == "claimed_identity":
            claimed[fir_id].add(value)
        else:
            identity_firs[(etype, value)].setdefault(fir_id, raw)

    hubs = {k for k, v in identity_firs.items() if len(v) > HUB_LIMIT}
    shared = {k: v for k, v in identity_firs.items() if len(v) >= 2 and k not in hubs}

    # ------------------------------------------------------------------ evidence links
    pair_evidence: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for (etype, value), firs in shared.items():
        for a, b in itertools.combinations(sorted(firs), 2):
            pair_evidence[(a, b)].append({"type": etype, "value": value, "as_written": [firs[a], firs[b]]})
    for (a, b), evidence in pair_evidence.items():
        support = sorted(claimed.get(a, set()) & claimed.get(b, set()))
        session.add(Link(fir_a=a, fir_b=b, kind=LinkKind.EVIDENCE,
                         score=_noisy_or([EVIDENCE_WEIGHT[e["type"]] for e in evidence]),
                         evidence={"shared": evidence, "claimed_identity_also_shared": support,
                                   "name_only": all(e["type"] in NAME_TYPES for e in evidence)}))

    # ------------------------------------------------------------------ pattern links
    pattern_count = _pattern_links(session, set(pair_evidence), s)

    # ------------------------------------------------------------------ clusters (NetworkX)
    graph = nx.Graph()
    for (etype, value), firs in shared.items():
        node = f"{etype}:{value}"
        graph.add_node(node, kind="identity", etype=etype, value=value)
        for fir_id in firs:
            graph.add_node(fir_id, kind="fir")
            graph.add_edge(fir_id, node)
    clusters = _clusters(session, graph)
    session.flush()
    stats = {"evidence_links": len(pair_evidence), "pattern_links": pattern_count, "clusters": clusters,
             "ignored_hub_identifiers": [f"{t}:{v}" for t, v in sorted(hubs)]}
    log.info("intelligence rebuilt: %s", stats)
    return stats


def _pattern_links(session: Session, evidence_pairs: set[tuple[str, str]], s) -> int:
    rows = session.execute(select(Fir.id, Fir.registered_at, FirAnalysis.crime_minor, FirAnalysis.mo_flags,
                                  Embedding.vector)
                           .join(FirAnalysis, FirAnalysis.fir_id == Fir.id)
                           .join(Embedding, Embedding.fir_id == Fir.id)).all()
    by_type: dict[str, list] = defaultdict(list)
    for row in rows:
        if row.crime_minor:
            by_type[row.crime_minor].append(row)
    created = 0
    for minor, group in by_type.items():
        if len(group) < 2:
            continue
        mat = np.stack([np.frombuffer(r.vector, dtype="<f4") for r in group])
        sims = mat @ mat.T
        np.fill_diagonal(sims, -1.0)
        chosen: set[tuple[str, str]] = set()
        for i, row in enumerate(group):
            for j in np.argsort(-sims[i])[: s.soft_links_per_fir]:
                sim = float(sims[i, j])
                other = group[j]
                if sim < s.soft_link_min_similarity:
                    break
                days = (abs((row.registered_at - other.registered_at).days)
                        if row.registered_at and other.registered_at else None)
                if days is not None and days > s.soft_link_max_days:
                    continue
                pair = tuple(sorted((row.id, other.id)))
                if pair in evidence_pairs or pair in chosen:
                    continue
                chosen.add(pair)
                shared_mo = sorted(set(row.mo_flags or {}) & set(other.mo_flags or {}))
                session.add(Link(fir_a=pair[0], fir_b=pair[1], kind=LinkKind.PATTERN, score=round(sim, 4),
                                 evidence={"same_crime_type": minor, "narrative_similarity": round(sim, 4),
                                           "shared_mo": shared_mo, "days_apart": days}))
        created += len(chosen)
    return created


def _clusters(session: Session, graph: nx.Graph) -> int:
    firs = {f.id: f for f in session.scalars(select(Fir).where(Fir.id.in_([n for n, d in graph.nodes(data=True)
                                                                             if d["kind"] == "fir"])))}
    analyses = {a.fir_id: a for a in session.scalars(select(FirAnalysis).where(FirAnalysis.fir_id.in_(list(firs))))}
    latest = max((f.registered_at for f in firs.values() if f.registered_at), default=None)
    components = []
    for comp in nx.connected_components(graph):
        fir_ids = sorted(n for n in comp if graph.nodes[n]["kind"] == "fir")
        if len(fir_ids) >= 2:
            components.append((comp, fir_ids))

    scored = []
    for comp, fir_ids in components:
        sub = graph.subgraph(comp)
        centrality = nx.degree_centrality(sub)
        identities = sorted((n for n in comp if graph.nodes[n]["kind"] == "identity"),
                            key=lambda n: (-sub.degree(n), n))
        members = [firs[i] for i in fir_ids]
        stations = {m.station.name for m in members if m.station}
        districts = {m.station.district for m in members if m.station}
        dates = [m.registered_at for m in members if m.registered_at]
        loss = sum((analyses[m.id].amount or 0) for m in members if m.id in analyses)
        seniors = sum(1 for m in members if m.id in analyses
                      and (analyses[m.id].victim or {}).get("age_group") == "above_60")
        crime_types: dict[str, int] = defaultdict(int)
        for m in members:
            if m.id in analyses and analyses[m.id].crime_minor:
                crime_types[analyses[m.id].crime_minor] += 1
        name_only = all(graph.nodes[n]["etype"] in NAME_TYPES for n in identities)

        score, factors = 0, []
        pts = min(15 * (len(members) - 1), 45); score += pts
        factors.append(f"{len(members)} FIRs linked by shared evidence (+{pts})")
        if len(stations) > 1:
            pts = min(10 * (len(stations) - 1), 20); score += pts
            factors.append(f"spans {len(stations)} police stations (+{pts})")
        if len(districts) > 1:
            score += 15
            factors.append(f"crosses {len(districts)} districts (+15)")
        if loss >= 1_000_000:
            score += 15; factors.append(f"total loss Rs {loss:,} (+15)")
        elif loss >= 100_000:
            score += 8; factors.append(f"total loss Rs {loss:,} (+8)")
        if latest and dates and (latest - max(dates)).days <= 30:
            score += 10; factors.append("active in the last 30 days (+10)")
        if seniors:
            pts = min(5 * seniors, 10); score += pts
            factors.append(f"{seniors} senior-citizen victim(s) (+{pts})")
        if name_only:
            score = int(score * 0.6)
            factors.append("linked only by accused name/alias: verify identity (x0.6)")
        score = min(score, 100)
        key_identifiers = [{"type": graph.nodes[n]["etype"], "value": graph.nodes[n]["value"],
                            "fir_count": sub.degree(n), "centrality": round(centrality[n], 3)}
                           for n in identities[:6]]
        scored.append((score, fir_ids, dict(stations=len(stations), districts=len(districts), dates=dates,
                                            loss=loss, key=key_identifiers, types=dict(crime_types),
                                            factors=factors)))

    scored.sort(key=lambda x: (-x[0], x[1][0]))
    for idx, (score, fir_ids, info) in enumerate(scored, start=1):
        level = "HIGH" if score >= 60 else "MEDIUM" if score >= 35 else "LOW"
        cluster = OffenderCluster(id=f"K-{idx:03d}", risk_score=score, risk_level=level, n_firs=len(fir_ids),
                                  n_stations=info["stations"], n_districts=info["districts"],
                                  first_seen=min(info["dates"]) if info["dates"] else None,
                                  last_seen=max(info["dates"]) if info["dates"] else None, total_loss=info["loss"],
                                  key_identifiers=info["key"], crime_types=info["types"],
                                  risk_factors=info["factors"])
        session.add(cluster)
        session.flush()
        for fir_id in fir_ids:
            session.add(ClusterMember(cluster_id=cluster.id, fir_id=fir_id))
    return len(scored)
