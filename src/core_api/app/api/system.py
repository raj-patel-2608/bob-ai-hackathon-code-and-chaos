"""Health checks, system status and demo reset."""
from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.engine import get_session
from ..db.models import (AuditLog, ClusterMember, Embedding, Entity, Fir, FirAnalysis, FirStageRun, IngestBatch,
                         Link, LlmUsage, OffenderCluster, Station, StationReport, utcnow)
from ..models_client.client import get_model_client
from ..pipeline.worker import get_worker
from ..services.llm_usage import tokens_used_this_month

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health/live")
def live() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(response: Response, session: Session = Depends(get_session)) -> dict:
    """Ready = database reachable + worker alive with a fresh heartbeat. Model service state is reported
    but not required (the system degrades to rules-only mode without it)."""
    checks = {}
    try:
        session.execute(text("SELECT 1"))
        checks["database"] = {"ok": True}
    except Exception as exc:                                  # pragma: no cover - defensive
        checks["database"] = {"ok": False, "error": str(exc)}
    worker = get_worker()
    s = get_settings()
    if not s.worker_enabled:
        checks["worker"] = {"ok": True, "note": "disabled by configuration"}
    else:
        age = (utcnow() - worker.last_heartbeat).total_seconds() if worker and worker.last_heartbeat else None
        checks["worker"] = {"ok": bool(worker and worker.alive and age is not None and age < 60),
                            "heartbeat_age_s": round(age, 1) if age is not None else None,
                            "last_error": worker.last_error if worker else None}
    models = get_model_client().health()
    checks["model_service"] = {"ok": models.get("reachable", False), **models}
    ok = checks["database"]["ok"] and checks["worker"]["ok"]
    response.status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
    mode = "full" if models.get("reachable") else "rules-only (model service unreachable)"
    return {"status": "ready" if ok else "not_ready", "mode": mode, "checks": checks}


@router.get("/system/status")
def system_status(session: Session = Depends(get_session)) -> dict:
    s = get_settings()
    stage_rows = session.execute(select(FirStageRun.stage, FirStageRun.status, func.count())
                                 .group_by(FirStageRun.stage, FirStageRun.status)).all()
    stages: dict[str, dict] = {}
    for stage, st, n in stage_rows:
        stages.setdefault(stage, {})[st] = n
    return {
        "firs": session.scalar(select(func.count()).select_from(Fir)),
        "fir_status": dict(session.execute(select(Fir.status, func.count()).group_by(Fir.status)).all()),
        "stages": stages,
        "llm_tokens_this_month": tokens_used_this_month(session),
        "llm_monthly_budget": s.llm_monthly_token_budget,
        "settings": {"decision_min_confidence": s.decision_min_confidence, "mo_flag_threshold": s.mo_flag_threshold,
                     "soft_link_min_similarity": s.soft_link_min_similarity,
                     "model_service_url": s.model_service_url},
    }


@router.post("/system/reset")
def reset(session: Session = Depends(get_session)) -> dict:
    """Wipe all data (demo convenience). Disabled when CRIMEFIR_ENV=production."""
    s = get_settings()
    if s.env == "production":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "reset is disabled in production")
    for model in (ClusterMember, OffenderCluster, Link, Embedding, Entity, FirStageRun, FirAnalysis,
                  StationReport, Fir, IngestBatch, Station, LlmUsage):
        session.execute(delete(model))
    session.add(AuditLog(action="system.reset"))
    if s.upload_dir.exists():
        shutil.rmtree(s.upload_dir, ignore_errors=True)
    return {"status": "reset"}
