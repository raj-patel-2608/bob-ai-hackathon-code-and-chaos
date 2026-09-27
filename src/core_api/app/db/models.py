"""ORM models.

Input (immutable):   IngestBatch, Fir (raw_text never changes)
Processing:          FirStageRun (state machine per FIR x stage), FirAnalysis, Entity, Embedding
Output:              Link, OffenderCluster, ClusterMember, StationReport, EvalRun
Operations:          LlmUsage, AuditLog
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ..domain.enums import BatchStatus, FirStatus, RunStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    type_annotation_map = {dict: JSON, list: JSON}


class Station(Base):
    __tablename__ = "stations"
    __table_args__ = (UniqueConstraint("name", "district"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    district: Mapped[str] = mapped_column(String(120))


class IngestBatch(Base):
    __tablename__ = "ingest_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(20))             # upload | api | seed
    content_sha256: Mapped[str] = mapped_column(String(64))
    stored_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default=BatchStatus.RECEIVED)
    total: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    link_status: Mapped[str] = mapped_column(String(20), default=RunStatus.PENDING)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class Fir(Base):
    __tablename__ = "firs"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)       # e.g. AHM-NAV-2026-0412
    batch_id: Mapped[str] = mapped_column(ForeignKey("ingest_batches.id"), index=True)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id"), index=True)
    fir_no: Mapped[str | None] = mapped_column(String(40))
    registered_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime)
    place: Mapped[str | None] = mapped_column(String(300))
    acts_sections: Mapped[str | None] = mapped_column(String(300))
    complainant_text: Mapped[str | None] = mapped_column(String(500))
    accused_header: Mapped[str | None] = mapped_column(String(300))
    property_text: Mapped[str | None] = mapped_column(String(300))
    raw_text: Mapped[str] = mapped_column(Text)
    narrative: Mapped[str] = mapped_column(Text)
    text_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20), default=FirStatus.QUEUED, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    batch: Mapped[IngestBatch] = relationship()
    station: Mapped[Station | None] = relationship()
    analysis: Mapped[FirAnalysis | None] = relationship(back_populates="fir", uselist=False,
                                                        cascade="all, delete-orphan")
    entities: Mapped[list[Entity]] = relationship(back_populates="fir", cascade="all, delete-orphan")
    stage_runs: Mapped[list[FirStageRun]] = relationship(back_populates="fir", cascade="all, delete-orphan")


class FirStageRun(Base):
    """One row per FIR per pipeline stage: the processing state machine."""
    __tablename__ = "fir_stage_runs"
    __table_args__ = (UniqueConstraint("fir_id", "stage"),
                      Index("ix_stage_runs_claim", "status", "stage", "next_attempt_at"))
    id: Mapped[int] = mapped_column(primary_key=True)
    fir_id: Mapped[str] = mapped_column(ForeignKey("firs.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=4)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    lease_owner: Mapped[str | None] = mapped_column(String(80))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    provider: Mapped[str | None] = mapped_column(String(40))            # laya | llm | rules | granite-embedding
    model_id: Mapped[str | None] = mapped_column(String(200))
    device: Mapped[str | None] = mapped_column(String(20))
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(300))               # e.g. why a stage was skipped
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    fir: Mapped[Fir] = relationship(back_populates="stage_runs")


class FirAnalysis(Base):
    """The auto-drafted I.I.F.-II crime classification plus extracted intelligence."""
    __tablename__ = "fir_analysis"
    fir_id: Mapped[str] = mapped_column(ForeignKey("firs.id", ondelete="CASCADE"), primary_key=True)
    crime_major: Mapped[str | None] = mapped_column(String(40), index=True)
    crime_minor: Mapped[str | None] = mapped_column(String(60), index=True)
    crime_confidence: Mapped[float | None] = mapped_column(Float)
    crime_probabilities: Mapped[dict | None] = mapped_column(JSON)
    decided_by: Mapped[str | None] = mapped_column(String(20))
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    mo_flags: Mapped[dict | None] = mapped_column(JSON)                 # flag -> probability
    victim: Mapped[dict | None] = mapped_column(JSON)                   # age, age_group, gender, occupation
    accused: Mapped[list | None] = mapped_column(JSON)                  # [{name, alias, as_written, source}]
    amount: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_by: Mapped[str | None] = mapped_column(String(20))
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    review_reasons: Mapped[list | None] = mapped_column(JSON)
    model_versions: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    fir: Mapped[Fir] = relationship(back_populates="analysis")


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (Index("ix_entities_type_value", "type", "value"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    fir_id: Mapped[str] = mapped_column(ForeignKey("firs.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(30))          # phone | bank_account | upi_id | imei | vehicle |
    raw: Mapped[str] = mapped_column(String(300))          # online_handle | accused_name | accused_alias
    value: Mapped[str] = mapped_column(String(200))        # canonical form used for matching
    role: Mapped[str] = mapped_column(String(20))          # offender | property | complainant
    start: Mapped[int | None] = mapped_column(Integer)
    end: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20))        # regex | header | llm

    fir: Mapped[Fir] = relationship(back_populates="entities")


class Embedding(Base):
    __tablename__ = "embeddings"
    fir_id: Mapped[str] = mapped_column(ForeignKey("firs.id", ondelete="CASCADE"), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(200))
    dim: Mapped[int] = mapped_column(Integer)
    vector: Mapped[bytes] = mapped_column(LargeBinary)     # float32 little-endian
    text_hash: Mapped[str] = mapped_column(String(64))


class Link(Base):
    __tablename__ = "links"
    __table_args__ = (UniqueConstraint("fir_a", "fir_b", "kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    fir_a: Mapped[str] = mapped_column(ForeignKey("firs.id", ondelete="CASCADE"), index=True)
    fir_b: Mapped[str] = mapped_column(ForeignKey("firs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    score: Mapped[float] = mapped_column(Float)
    evidence: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class OffenderCluster(Base):
    __tablename__ = "offender_clusters"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)       # e.g. K-003
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(10))
    n_firs: Mapped[int] = mapped_column(Integer)
    n_stations: Mapped[int] = mapped_column(Integer)
    n_districts: Mapped[int] = mapped_column(Integer)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime)
    total_loss: Mapped[int] = mapped_column(Integer, default=0)
    key_identifiers: Mapped[list] = mapped_column(JSON)
    crime_types: Mapped[dict] = mapped_column(JSON)
    risk_factors: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    members: Mapped[list[ClusterMember]] = relationship(cascade="all, delete-orphan")


class ClusterMember(Base):
    __tablename__ = "cluster_members"
    cluster_id: Mapped[str] = mapped_column(ForeignKey("offender_clusters.id", ondelete="CASCADE"),
                                            primary_key=True)
    fir_id: Mapped[str] = mapped_column(ForeignKey("firs.id", ondelete="CASCADE"), primary_key=True, index=True)


class StationReport(Base):
    __tablename__ = "station_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)
    period_from: Mapped[datetime] = mapped_column(DateTime)
    period_to: Mapped[datetime] = mapped_column(DateTime)
    facts: Mapped[dict] = mapped_column(JSON)
    narrative: Mapped[str] = mapped_column(Text)
    generated_by: Mapped[str] = mapped_column(String(40))              # llm | template
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LlmUsage(Base):
    __tablename__ = "llm_usage"
    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7), index=True)          # YYYY-MM
    purpose: Mapped[str] = mapped_column(String(40))
    model_id: Mapped[str | None] = mapped_column(String(200))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    split: Mapped[str] = mapped_column(String(20))
    metrics: Mapped[dict] = mapped_column(JSON)
    settings: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    action: Mapped[str] = mapped_column(String(60))
    target: Mapped[str | None] = mapped_column(String(120))
    detail: Mapped[dict | None] = mapped_column(JSON)
