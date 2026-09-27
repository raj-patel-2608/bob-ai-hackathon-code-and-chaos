"""LLM token accounting against the monthly budget (watsonx Lite quota)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import LlmUsage


def current_month() -> str:
    return datetime.now().strftime("%Y-%m")


def tokens_used_this_month(session: Session) -> int:
    used = session.scalar(select(func.coalesce(func.sum(LlmUsage.input_tokens + LlmUsage.output_tokens), 0))
                          .where(LlmUsage.month == current_month()))
    return int(used or 0)


def record_usage(session: Session, response: dict, model_id: str | None, purpose: str) -> None:
    usage = response.get("usage") or {}
    session.add(LlmUsage(month=current_month(), purpose=purpose, model_id=model_id,
                         input_tokens=int(usage.get("input_tokens", 0)),
                         output_tokens=int(usage.get("output_tokens", 0))))
