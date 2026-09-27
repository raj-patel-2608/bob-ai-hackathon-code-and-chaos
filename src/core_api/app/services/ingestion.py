"""Batch ingestion: validate, store the original file, split into FIRs, de-duplicate, enqueue.

This runs inside the upload request and is fast (no AI). Processing happens
later in the background worker, so the API returns immediately with a batch id.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.models import AuditLog, Fir, IngestBatch, Station
from ..domain.enums import BatchStatus, FirStatus
from ..extraction.fir_parser import parse_fir, split_batch
from ..pipeline.queue import create_stage_runs

ALLOWED_SUFFIXES = (".txt", ".csv", ".json", ".jsonl")
_STOP_WORDS = {"police", "station", "ps", "p.s.", "city", "the"}


class IngestError(ValueError):
    """Bad input; reported to the user as HTTP 400/413."""


@dataclass
class IngestResult:
    batch: IngestBatch
    created: list[str]
    duplicates: list[str]


def _abbrev(value: str | None, default: str) -> str:
    if not value:
        return default
    words = [w for w in re.split(r"[\s,]+", value) if w and w.lower() not in _STOP_WORDS]
    return (words[0][:3] if words else value[:3]).upper()


def _fir_key(session: Session, district: str | None, station: str | None, fir_no: str | None,
             year: int | None, text_hash: str) -> str:
    if fir_no:
        number = re.split(r"[/\s]", fir_no)[0]
        key = f"{_abbrev(district, 'UNK')}-{_abbrev(station, 'UNK')}-{year or 'NA'}-{number}"
    else:
        key = f"FIR-{text_hash[:10].upper()}"
    candidate, n = key, 1
    while session.get(Fir, candidate) is not None:
        n += 1
        candidate = f"{key}-{n}"
    return candidate


def _station(session: Session, name: str | None, district: str | None) -> Station | None:
    if not name:
        return None
    district = district or "Unknown district"
    station = session.scalar(select(Station).where(Station.name == name, Station.district == district))
    if station is None:
        station = Station(name=name, district=district)
        session.add(station)
        session.flush()
    return station


def ingest_content(session: Session, content: bytes, filename: str, source: str = "upload") -> IngestResult:
    s = get_settings()
    if not filename.lower().endswith(ALLOWED_SUFFIXES):
        raise IngestError(f"unsupported file type; use one of {', '.join(ALLOWED_SUFFIXES)}")
    if len(content) > s.max_upload_mb * 1024 * 1024:
        raise IngestError(f"file larger than {s.max_upload_mb} MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestError("file must be UTF-8 text") from exc
    try:
        raw_firs = [t for t in split_batch(text, filename) if t.strip()]
    except (ValueError, KeyError) as exc:
        raise IngestError(f"could not read records: {exc}") from exc
    if not raw_firs:
        raise IngestError("no FIR text found in the file")
    if len(raw_firs) > s.max_firs_per_batch:
        raise IngestError(f"batch has {len(raw_firs)} FIRs; the limit is {s.max_firs_per_batch} per upload")

    content_hash = hashlib.sha256(content).hexdigest()
    batch = IngestBatch(id=str(uuid.uuid4()), filename=filename, source=source, content_sha256=content_hash,
                        total=len(raw_firs), status=BatchStatus.RECEIVED)
    session.add(batch)
    upload_dir = s.upload_dir / batch.id
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored = upload_dir / re.sub(r"[^\w.\-]", "_", filename)
    stored.write_bytes(content)                               # original kept unchanged
    batch.stored_path = str(stored)

    created, duplicates = [], []
    for raw in raw_firs:
        text_hash = hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()
        existing = session.scalar(select(Fir.id).where(Fir.text_sha256 == text_hash))
        if existing:
            duplicates.append(existing)
            continue
        parsed = parse_fir(raw)
        f = parsed.fields
        year = parsed.registered_at.year if parsed.registered_at else None
        station = _station(session, f.get("police_station"), f.get("district"))
        fir = Fir(id=_fir_key(session, f.get("district"), f.get("police_station"), parsed.fir_no, year, text_hash),
                  batch_id=batch.id, station_id=station.id if station else None, fir_no=parsed.fir_no,
                  registered_at=parsed.registered_at, occurred_at=parsed.occurred_at, place=f.get("place"),
                  acts_sections=f.get("acts_sections"), complainant_text=f.get("complainant"),
                  accused_header=f.get("accused"), property_text=f.get("property"),
                  raw_text=parsed.raw_text, narrative=parsed.narrative, text_sha256=text_hash,
                  status=FirStatus.QUEUED)
        session.add(fir)
        session.flush()
        create_stage_runs(session, fir.id)
        created.append(fir.id)

    batch.created_count, batch.duplicate_count = len(created), len(duplicates)
    batch.status = BatchStatus.PROCESSING if created else BatchStatus.COMPLETED
    session.add(AuditLog(action="batch.ingested", target=batch.id,
                         detail={"filename": filename, "created": len(created), "duplicates": len(duplicates)}))
    return IngestResult(batch, created, duplicates)
