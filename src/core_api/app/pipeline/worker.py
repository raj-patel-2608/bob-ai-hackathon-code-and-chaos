"""Background worker: drains the stage queue in micro-batches and finalises batches.

One worker thread runs inside the API process (enough for a single machine;
in production the same loop would run as separate worker processes against
PostgreSQL). It records a heartbeat so /api/health/ready can tell whether it
is alive.
"""
from __future__ import annotations

import logging
import os
import socket
import threading
import time
from datetime import datetime

from sqlalchemy import func, select

from ..config import get_settings
from ..db.engine import session_scope
from ..db.models import AuditLog, Fir, FirStageRun, IngestBatch, utcnow
from ..domain.enums import STAGE_ORDER, BatchStatus, FirStatus, RunStatus, Stage
from ..services import intelligence
from .queue import claim, recover_expired, reset_all_running
from .stages import HANDLERS

log = logging.getLogger("crimefir.worker")

# how many FIRs a stage takes per micro-batch; the LLM stage goes one at a time
STAGE_BATCH = {Stage.EXTRACT: 50, Stage.DECIDE: 16, Stage.ENRICH: 1, Stage.EMBED: 32}


class Worker:
    def __init__(self) -> None:
        self.id = f"{socket.gethostname()}:{os.getpid()}"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_heartbeat: datetime | None = None
        self.last_error: str | None = None

    # -------------------------------------------------------------- lifecycle
    def start(self) -> None:
        with session_scope() as session:
            requeued = reset_all_running(session)
        if requeued:
            log.warning("requeued %d stage runs left RUNNING by a previous process", requeued)
        self._thread = threading.Thread(target=self._loop, name="crimefir-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    @property
    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # -------------------------------------------------------------- loop
    def _loop(self) -> None:
        s = get_settings()
        last_recovery = 0.0
        while not self._stop.is_set():
            self.last_heartbeat = utcnow()
            try:
                if time.monotonic() - last_recovery > 30:
                    with session_scope() as session:
                        recover_expired(session)
                    last_recovery = time.monotonic()
                did_work = self.run_once()
                self.last_error = None
            except Exception as exc:                        # keep the worker alive whatever happens
                log.exception("worker iteration failed")
                self.last_error = f"{exc.__class__.__name__}: {exc}"
                did_work = False
            if not did_work:
                self._stop.wait(s.worker_poll_s)

    def run_once(self) -> bool:
        """Process at most one micro-batch per stage, then finalise finished batches. Returns True if work was done."""
        did_work = False
        for stage in STAGE_ORDER:
            with session_scope() as session:
                runs = claim(session, stage, STAGE_BATCH[stage], self.id)
                if runs:
                    HANDLERS[stage](session, runs)
                    did_work = True
        did_work |= self.finalize_batches()
        return did_work

    def finalize_batches(self) -> bool:
        with session_scope() as session:
            open_batches = session.scalars(select(IngestBatch).where(
                IngestBatch.status.in_((BatchStatus.PROCESSING, BatchStatus.LINKING)))).all()
            ready = []
            for batch in open_batches:
                unfinished = session.scalar(
                    select(func.count()).select_from(FirStageRun).join(Fir, Fir.id == FirStageRun.fir_id)
                    .where(Fir.batch_id == batch.id,
                           FirStageRun.status.in_((RunStatus.WAITING, RunStatus.PENDING, RunStatus.RUNNING))))
                if unfinished == 0:
                    batch.status = BatchStatus.LINKING
                    ready.append(batch.id)
        if not ready:
            return False
        with session_scope() as session:
            stats = intelligence.rebuild(session)               # one rebuild covers all finished batches
            for batch_id in ready:
                batch = session.get(IngestBatch, batch_id)
                failed = session.scalar(select(func.count()).select_from(Fir)
                                        .where(Fir.batch_id == batch_id, Fir.status == FirStatus.FAILED))
                batch.status = BatchStatus.COMPLETED_WITH_ERRORS if failed else BatchStatus.COMPLETED
                batch.link_status = RunStatus.SUCCEEDED
                batch.finished_at = utcnow()
                session.add(AuditLog(action="batch.completed", target=batch_id,
                                     detail={"failed_firs": failed, **{k: v for k, v in stats.items()
                                                                       if k != "ignored_hub_identifiers"}}))
        return True


_worker: Worker | None = None


def get_worker() -> Worker | None:
    return _worker


def start_worker() -> Worker:
    global _worker
    _worker = Worker()
    _worker.start()
    return _worker


def stop_worker() -> None:
    if _worker:
        _worker.stop()
