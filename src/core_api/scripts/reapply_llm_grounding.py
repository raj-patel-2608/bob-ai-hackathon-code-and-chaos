"""One-off repair: apply the name-grounding rules to LLM results already stored (no new LLM calls).

    python scripts/reapply_llm_grounding.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402

from app.db.engine import init_engine, session_scope  # noqa: E402
from app.db.models import Entity, Fir, FirAnalysis  # noqa: E402
from app.pipeline.decisions import LlmAccused  # noqa: E402
from app.pipeline.stages import _grounded_person  # noqa: E402
from app.services import intelligence  # noqa: E402

init_engine()
changed = 0
with session_scope() as s:
    for a in s.scalars(select(FirAnalysis).where(FirAnalysis.decided_by == "llm")):
        fir = s.get(Fir, a.fir_id)
        kept = [x for x in (a.accused or []) if x.get("source") not in ("llm", "claimed")]
        s.execute(delete(Entity).where(Entity.fir_id == fir.id, Entity.source == "llm"))
        for x in (a.accused or []):
            if x.get("source") not in ("llm", "claimed"):
                continue
            person = LlmAccused(name=x.get("as_written") if x.get("name") else None, alias=x.get("alias"),
                                claimed_identity=x.get("source") == "claimed")
            name, alias, name_claimed = _grounded_person(fir.raw_text, person)
            if person.claimed_identity:
                alias = None
            if not (name or alias):
                changed += 1
                continue
            kept.append({**x, "name": name, "alias": alias, "source": "claimed" if name_claimed and not alias else "llm"})
            if name:
                s.add(Entity(fir_id=fir.id, type="claimed_identity" if name_claimed else "accused_name",
                             raw=person.name, value=name, role="offender", source="llm"))
            if alias:
                s.add(Entity(fir_id=fir.id, type="accused_alias", raw=alias, value=alias, role="offender",
                             source="llm"))
        a.accused = kept
    stats = intelligence.rebuild(s)
print(f"dropped {changed} ungrounded/generic LLM names; rebuilt: {stats}")
