"""Batch upload and processing status."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db.engine import get_session
from ..db.models import AuditLog, Fir, FirStageRun, IngestBatch, utcnow
from ..domain.enums import BatchStatus, RunStatus
from ..services import intelligence
from ..pipeline.queue import retry_failed
from ..services.ingestion import IngestError, delete_firs, ingest_content

ACTIVE = (BatchStatus.RECEIVED, BatchStatus.PROCESSING, BatchStatus.LINKING, BatchStatus.CANCELLING)

router = APIRouter(prefix="/api/batches", tags=["batches"])


class TextBatch(BaseModel):
    text: str = Field(min_length=20, description="One or more FIRs separated by a line of ---")
    filename: str = "pasted.txt"


def _accepted(result) -> dict:
    return {"batch_id": result.batch.id, "status": result.batch.status, "total": result.batch.total,
            "created": len(result.created), "duplicates": len(result.duplicates),
            "status_url": f"/api/batches/{result.batch.id}"}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_batch(file: UploadFile = File(...), session: Session = Depends(get_session)) -> dict:
    """Upload a .txt (FIRs separated by ---), .jsonl, .json or .csv file. Returns immediately; processing
    runs in the background. Poll the status_url for progress."""
    content = await file.read()
    try:
        result = ingest_content(session, content, file.filename or "upload.txt")
        session.commit()                    # visible to the status poll that follows this response
        return _accepted(result)
    except IngestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/text", status_code=status.HTTP_202_ACCEPTED)
def upload_text(body: TextBatch, session: Session = Depends(get_session)) -> dict:
    name = body.filename if body.filename.lower().endswith((".txt", ".csv", ".json", ".jsonl")) else "pasted.txt"
    try:
        result = ingest_content(session, body.text.encode("utf-8"), name, source="api")
        session.commit()
        return _accepted(result)
    except IngestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("")
def list_batches(limit: int = 20, session: Session = Depends(get_session)) -> list[dict]:
    batches = session.scalars(select(IngestBatch).order_by(IngestBatch.created_at.desc()).limit(limit)).all()
    return [_batch_summary(session, b) for b in batches]


@router.get("/{batch_id}")
def get_batch(batch_id: str, session: Session = Depends(get_session)) -> dict:
    batch = session.get(IngestBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "batch not found")
    summary = _batch_summary(session, batch)
    failures = session.execute(select(FirStageRun.fir_id, FirStageRun.stage, FirStageRun.error_code,
                                      FirStageRun.error_message, FirStageRun.attempts)
                               .join(Fir, Fir.id == FirStageRun.fir_id)
                               .where(Fir.batch_id == batch_id, FirStageRun.error_code.is_not(None))
                               .limit(50)).all()
    summary["recent_errors"] = [dict(r._mapping) for r in failures]
    return summary


@router.post("/{batch_id}/retry-failed")
def retry_batch(batch_id: str, session: Session = Depends(get_session)) -> dict:
    batch = session.get(IngestBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "batch not found")
    fir_ids = list(session.scalars(select(Fir.id).where(Fir.batch_id == batch_id)))
    requeued = retry_failed(session, fir_ids)
    if requeued:
        batch.status = "PROCESSING"
    return {"requeued_stage_runs": requeued}


@router.delete("/{batch_id}")
def delete_batch(batch_id: str, session: Session = Depends(get_session)) -> dict:
    """Delete a batch and everything derived from its FIRs (analysis, evidence, embeddings, links), then
    rebuild the repeat-offender groups from the remaining data. Refused while the batch is still processing."""
    batch = session.get(IngestBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "batch not found")
    if batch.status in ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "batch is still processing; stop it first or wait until it finishes")
    fir_ids = list(session.scalars(select(Fir.id).where(Fir.batch_id == batch_id)))
    delete_firs(session, fir_ids)
    session.delete(batch)
    session.flush()
    if batch.stored_path:
        shutil.rmtree(Path(batch.stored_path).parent, ignore_errors=True)
    stats = intelligence.rebuild(session)
    session.add(AuditLog(action="batch.deleted", target=batch_id,
                         detail={"filename": batch.filename, "firs_deleted": len(fir_ids)}))
    return {"deleted_batch": batch_id, "firs_deleted": len(fir_ids), "clusters_now": stats["clusters"]}


@router.post("/{batch_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
def cancel_batch(batch_id: str, session: Session = Depends(get_session)) -> dict:
    """Stop processing a batch. FIRs that are already fully analysed are kept; the rest are removed by the
    worker as soon as the step it is running now has finished (usually a few seconds)."""
    batch = session.get(IngestBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "batch not found")
    if batch.status not in (BatchStatus.RECEIVED, BatchStatus.PROCESSING):
        raise HTTPException(status.HTTP_409_CONFLICT, f"batch is {batch.status.lower()}; nothing to stop")
    fir_ids = select(Fir.id).where(Fir.batch_id == batch_id)
    skipped = session.execute(update(FirStageRun)
                              .where(FirStageRun.fir_id.in_(fir_ids),
                                     FirStageRun.status.in_((RunStatus.WAITING, RunStatus.PENDING)))
                              .values(status=RunStatus.SKIPPED, note="cancelled by user", finished_at=utcnow())
                              ).rowcount or 0
    batch.status = BatchStatus.CANCELLING
    session.add(AuditLog(action="batch.cancel_requested", target=batch_id, detail={"skipped_stage_runs": skipped}))
    return {"batch_id": batch_id, "status": batch.status, "skipped_stage_runs": skipped}


def _batch_summary(session: Session, batch: IngestBatch) -> dict:
    stage_rows = session.execute(select(FirStageRun.stage, FirStageRun.status, func.count())
                                 .join(Fir, Fir.id == FirStageRun.fir_id).where(Fir.batch_id == batch.id)
                                 .group_by(FirStageRun.stage, FirStageRun.status)).all()
    stages: dict[str, dict[str, int]] = {}
    for stage, st, n in stage_rows:
        stages.setdefault(stage, {})[st] = n
    fir_rows = session.execute(select(Fir.status, func.count()).where(Fir.batch_id == batch.id)
                               .group_by(Fir.status)).all()
    done = sum(n for st, n in fir_rows if st in ("ANALYZED", "NEEDS_REVIEW", "FAILED"))
    elapsed = ((batch.finished_at or utcnow()) - batch.created_at).total_seconds() if batch.created_at else None
    return {"id": batch.id, "filename": batch.filename, "source": batch.source, "status": batch.status,
            "total": batch.total, "created": batch.created_count, "duplicates": batch.duplicate_count,
            "firs_done": done, "progress": round(done / batch.created_count, 3) if batch.created_count else 1.0,
            "fir_status": {st: n for st, n in fir_rows}, "stages": stages, "created_at": batch.created_at,
            "finished_at": batch.finished_at, "elapsed_s": round(elapsed, 1) if elapsed is not None else None,
            "size_bytes": _size(batch.stored_path)}


def _size(path: str | None) -> int | None:
    try:
        return Path(path).stat().st_size if path else None
    except OSError:
        return None
