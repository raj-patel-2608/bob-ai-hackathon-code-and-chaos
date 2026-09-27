from datetime import timedelta

from sqlalchemy import select

from app.db.engine import session_scope
from app.db.models import Fir, FirStageRun, IngestBatch, utcnow
from app.domain.enums import RunStatus, Stage
from app.pipeline.queue import (claim, create_stage_runs, mark_failed, mark_succeeded, recover_expired,
                                reset_all_running)


def _setup_fir(session, fir_id="F-1"):
    session.add(IngestBatch(id="b1", filename="x.txt", source="api", content_sha256="0"))
    session.add(Fir(id=fir_id, batch_id="b1", raw_text="t", narrative="t", text_sha256=fir_id))
    session.flush()
    create_stage_runs(session, fir_id)


def _run(session, fir_id, stage):
    return session.scalar(select(FirStageRun).where(FirStageRun.fir_id == fir_id, FirStageRun.stage == stage))


def test_only_first_stage_is_claimable_and_success_releases_next(db):
    with session_scope() as s:
        _setup_fir(s)
    with session_scope() as s:
        assert claim(s, Stage.DECIDE, 10, "w") == []
        runs = claim(s, Stage.EXTRACT, 10, "w")
        assert len(runs) == 1 and runs[0].status == RunStatus.RUNNING and runs[0].lease_owner == "w"
        assert claim(s, Stage.EXTRACT, 10, "w2") == []                    # cannot be claimed twice
        mark_succeeded(s, runs[0], provider="rules")
    with session_scope() as s:
        assert _run(s, "F-1", Stage.DECIDE).status == RunStatus.PENDING
        assert _run(s, "F-1", Stage.ENRICH).status == RunStatus.WAITING


def test_transient_failure_retries_then_fails(db):
    with session_scope() as s:
        _setup_fir(s)
    for attempt in range(1, 5):
        with session_scope() as s:
            runs = claim(s, Stage.EXTRACT, 1, "w")
            assert runs, f"attempt {attempt} should be claimable"
            retried = mark_failed(s, runs[0], error_code="x", message="boom", transient=True)
            assert retried == (attempt < 4)
    with session_scope() as s:
        run = _run(s, "F-1", Stage.EXTRACT)
        assert run.status == RunStatus.FAILED and run.attempts == 4
        assert _run(s, "F-1", Stage.DECIDE).status == RunStatus.PENDING   # later stages still get a chance


def test_permanent_failure_does_not_retry(db):
    with session_scope() as s:
        _setup_fir(s)
        runs = claim(s, Stage.EXTRACT, 1, "w")
        assert mark_failed(s, runs[0], error_code="bad", message="bad input", transient=False) is False
        assert runs[0].status == RunStatus.FAILED


def test_expired_lease_is_recovered(db):
    with session_scope() as s:
        _setup_fir(s)
        run = claim(s, Stage.EXTRACT, 1, "crashed-worker")[0]
        run.lease_expires_at = utcnow() - timedelta(seconds=1)
    with session_scope() as s:
        assert recover_expired(s) == 1
        assert _run(s, "F-1", Stage.EXTRACT).status == RunStatus.PENDING


def test_restart_requeues_running(db):
    with session_scope() as s:
        _setup_fir(s)
        claim(s, Stage.EXTRACT, 1, "w")
    with session_scope() as s:
        assert reset_all_running(s) == 1
