"""Status values used throughout the pipeline (stored as strings in the database)."""
from enum import StrEnum


class BatchStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    LINKING = "LINKING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"
    CANCELLING = "CANCELLING"          # user pressed Stop; unfinished FIRs are removed by the worker
    CANCELLED = "CANCELLED"


class FirStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    ANALYZED = "ANALYZED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


class Stage(StrEnum):
    EXTRACT = "extract"      # header parsing, identifiers, amounts, accused (rules, always local)
    DECIDE = "decide"        # crime type, MO flags, victim hints (Laya)
    ENRICH = "enrich"        # LLM for low-confidence FIRs: re-decide + accused + victim + summary
    EMBED = "embed"          # narrative embedding (Granite Embedding)


STAGE_ORDER = [Stage.EXTRACT, Stage.DECIDE, Stage.ENRICH, Stage.EMBED]


class RunStatus(StrEnum):
    WAITING = "WAITING"      # previous stage of this FIR not finished yet
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


TERMINAL_RUN_STATUSES = {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.SKIPPED}


class LinkKind(StrEnum):
    EVIDENCE = "EVIDENCE"                # shared hard identifier or resolved accused name
    PATTERN = "PATTERN"                  # same crime type + similar narrative, no shared evidence


class DecidedBy(StrEnum):
    LAYA = "laya"
    LLM = "llm"
    RULES = "rules"
