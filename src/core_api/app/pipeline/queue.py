"""Database-backed work queue for per-FIR pipeline stages.

State machine per (FIR, stage):
    WAITING -> PENDING -> RUNNING -> SUCCEEDED | SKIPPED | FAILED
                  ^          |
                  +----------+  transient error, attempts < max_attempts (exponential backoff)

- claim(): atomically moves PENDING rows whose next_attempt_at has passed to RUNNING with a lease
- a RUNNING row whose lease expired (worker crashed) is put back to PENDING by recover_expired()
- when a stage ends, the next stage of the same FIR moves WAITING -> PENDING
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.models import FirStageRun, utcnow
from ..domain.enums import STAGE_ORDER, RunStatus, Stage


def create_stage_runs(session: Session, fir_id: str) -> None:
    s = get_settings()
    for i, stage in enumerate(STAGE_ORDER):
        session.add(FirStageRun(fir_id=fir_id, stage=stage, max_attempts=s.max_attempts,
                                status=RunStatus.PENDING if i == 0 else RunStatus.WAITING))


def claim(session: Session, stage: Stage, limit: int, worker_id: str) -> list[FirStageRun]:
    session.flush()          # pending inserts get their timestamps before we read the clock
    now = utcnow()
    candidates = session.scalars(
        select(FirStageRun.id)
        .where(FirStageRun.stage == stage, FirStageRun.status == RunStatus.PENDING,
               FirStageRun.next_attempt_at <= now)
        .order_by(FirStageRun.next_attempt_at, FirStageRun.id)
        .limit(limit)).all()
    claimed = []
    lease_until = now + timedelta(seconds=get_settings().lease_s)
    for run_id in candidates:
        result = session.execute(
            update(FirStageRun)
            .where(FirStageRun.id == run_id, FirStageRun.status == RunStatus.PENDING)
            .values(status=RunStatus.RUNNING, lease_owner=worker_id, lease_expires_at=lease_until,
                    started_at=now, error_code=None, error_message=None))
        if result.rowcount == 1:
            claimed.append(run_id)
    session.flush()
    if not claimed:
        return []
    return list(session.scalars(select(FirStageRun).where(FirStageRun.id.in_(claimed))
                                .execution_options(populate_existing=True)))


def _finish(run: FirStageRun, status: RunStatus) -> None:
    run.status = status
    run.finished_at = utcnow()
    run.lease_owner = None
    run.lease_expires_at = None
    if run.started_at:
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)


def _release_next(session: Session, run: FirStageRun) -> None:
    idx = STAGE_ORDER.index(Stage(run.stage))
    if idx + 1 < len(STAGE_ORDER):
        session.execute(update(FirStageRun)
                        .where(FirStageRun.fir_id == run.fir_id, FirStageRun.stage == STAGE_ORDER[idx + 1],
                               FirStageRun.status == RunStatus.WAITING)
                        .values(status=RunStatus.PENDING, next_attempt_at=utcnow()))


def mark_succeeded(session: Session, run: FirStageRun, *, provider: str | None = None,
                   model_id: str | None = None, device: str | None = None, note: str | None = None) -> None:
    run.provider, run.model_id, run.device, run.note = provider, model_id, device, note
    _finish(run, RunStatus.SUCCEEDED)
    _release_next(session, run)


def mark_skipped(session: Session, run: FirStageRun, note: str) -> None:
    run.note = note
    _finish(run, RunStatus.SKIPPED)
    _release_next(session, run)


def mark_failed(session: Session, run: FirStageRun, *, error_code: str, message: str, transient: bool) -> bool:
    """Record a failure. Returns True if the run will be retried."""
    s = get_settings()
    run.attempts += 1
    run.error_code, run.error_message = error_code, message[:2000]
    if transient and run.attempts < run.max_attempts:
        run.status = RunStatus.PENDING
        run.next_attempt_at = utcnow() + timedelta(seconds=s.backoff_base_s * (2 ** (run.attempts - 1)))
        run.lease_owner = run.lease_expires_at = None
        return True
    _finish(run, RunStatus.FAILED)
    _release_next(session, run)          # later stages still run where they can (graceful degradation)
    return False


def recover_expired(session: Session) -> int:
    """Put RUNNING rows with an expired lease back to PENDING (e.g. after a crash)."""
    now = utcnow()
    result = session.execute(update(FirStageRun)
                             .where(FirStageRun.status == RunStatus.RUNNING, FirStageRun.lease_expires_at < now)
                             .values(status=RunStatus.PENDING, lease_owner=None, lease_expires_at=None,
                                     next_attempt_at=now))
    return result.rowcount or 0


def reset_all_running(session: Session) -> int:
    """At process start nothing can legitimately be RUNNING: requeue it."""
    result = session.execute(update(FirStageRun).where(FirStageRun.status == RunStatus.RUNNING)
                             .values(status=RunStatus.PENDING, lease_owner=None, lease_expires_at=None,
                                     next_attempt_at=utcnow()))
    return result.rowcount or 0


def retry_failed(session: Session, fir_ids: list[str] | None = None) -> int:
    stmt = update(FirStageRun).where(FirStageRun.status == RunStatus.FAILED)
    if fir_ids:
        stmt = stmt.where(FirStageRun.fir_id.in_(fir_ids))
    result = session.execute(stmt.values(status=RunStatus.PENDING, attempts=0, next_attempt_at=utcnow(),
                                         error_code=None, error_message=None))
    return result.rowcount or 0
