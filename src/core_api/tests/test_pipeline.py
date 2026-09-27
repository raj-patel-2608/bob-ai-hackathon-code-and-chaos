from pathlib import Path

from sqlalchemy import select

from app.db.engine import session_scope
from app.db.models import ClusterMember, Fir, FirAnalysis, IngestBatch, Link, LlmUsage, OffenderCluster
from app.domain.enums import BatchStatus, FirStatus
from app.services.evaluation import evaluate
from app.services.ingestion import ingest_content
from conftest import drain

HEADER = ("FIR No.: {no}/2026\nDistrict: {district}    Police Station: {ps}\nDate & Time of FIR: {d}/08/2026 11:00\n"
          "Complainant / Informant: Person {no}, age 67, retired, Mob. 9{no}00000000\nAccused: Unknown caller\n"
          "First Information contents:\n")
KYC = "A caller said he is from SBI KYC department and asked the OTP. Rs 50,000 was debited. Caller number {phone}."


def fir(no, ps, district, day, body):
    return HEADER.format(no=no, ps=ps, district=district, d=day) + body


def ingest(texts, name="batch.txt"):
    with session_scope() as s:
        return ingest_content(s, "\n---\n".join(texts).encode(), name).batch.id


def test_linked_firs_across_stations_form_one_cluster(worker):
    batch_id = ingest([
        fir("0101", "Navrangpura", "Ahmedabad City", 10, KYC.format(phone="98251 77304")),
        fir("0102", "Adajan", "Surat City", 12, KYC.format(phone="+91-9825177304")),
        fir("0103", "Gotri", "Vadodara City", 15, KYC.format(phone="09825177304")),
        fir("0104", "Satellite", "Ahmedabad City", 16, "Two men on a bike snatched my gold chain near the lake."),
    ])
    drain(worker)
    with session_scope() as s:
        assert s.get(IngestBatch, batch_id).status == BatchStatus.COMPLETED
        assert {f.status for f in s.scalars(select(Fir))} == {FirStatus.ANALYZED}
        clusters = s.scalars(select(OffenderCluster)).all()
        assert len(clusters) == 1
        c = clusters[0]
        assert c.n_firs == 3 and c.n_stations == 3 and c.n_districts == 3
        assert c.key_identifiers[0]["value"] == "+919825177304"
        members = set(s.scalars(select(ClusterMember.fir_id)))
        assert len(members) == 3
        # complainant phones differ per FIR and must never link anything
        assert all(e["type"] == "phone" for l in s.scalars(select(Link)) if l.kind == "EVIDENCE"
                   for e in l.evidence["shared"])
        a = s.get(FirAnalysis, sorted(members)[0])
        assert a.crime_minor == "cyber.kyc_bank_impersonation" and a.decided_by == "laya"
        assert "asked_otp_or_card_details" in a.mo_flags
        assert a.amount == 50000 and a.victim["age_group"] == "above_60"


def test_low_confidence_goes_to_llm(worker, fake_models):
    fake_models.generate_payload = {"json": {
        "crime_minor": "cyber.digital_arrest", "mo_flags": ["impersonated_police_or_agency", "video_call_used"],
        "accused": [{"name": "Vikram Rathore", "claimed_identity": True}],
        "victim": {"gender": "male", "age_group": "above_60", "occupation": "retired"},
        "summary": "Victim was kept on a video call by a fake officer and transferred money."}}
    ingest([fir("0201", "Vastrapur", "Ahmedabad City", 3, "LOWCONF strange call about a parcel from Inspector Vikram Rathore, money sent.")])
    drain(worker)
    with session_scope() as s:
        a = s.scalars(select(FirAnalysis)).one()
        assert a.escalated and a.decided_by == "llm" and a.crime_minor == "cyber.digital_arrest"
        assert a.summary_by == "llm" and a.accused[-1]["source"] == "claimed"
        assert s.scalar(select(LlmUsage.input_tokens)) == 500


def test_llm_not_configured_marks_for_review(worker, fake_models):
    fake_models.generator_available = False
    ingest([fir("0301", "Maninagar", "Ahmedabad City", 4, "LOWCONF unclear complaint text here.")])
    drain(worker)
    with session_scope() as s:
        f = s.scalars(select(Fir)).one()
        assert f.status == FirStatus.NEEDS_REVIEW
        assert any("LLM unavailable" in r for r in f.analysis.review_reasons)


def test_model_service_down_falls_back_to_rules(worker, fake_models):
    fake_models.available = False
    batch_id = ingest([fir("0401", "Athwa", "Surat City", 5, KYC.format(phone="98111 22233"))])
    for _ in range(50):          # embed retries with backoff (0 s in tests), then gives up
        worker.run_once()
    with session_scope() as s:
        a = s.scalars(select(FirAnalysis)).one()
        assert a.decided_by == "rules" and a.needs_review
        assert s.get(IngestBatch, batch_id).status == BatchStatus.COMPLETED


def test_duplicate_upload_is_detected(worker):
    text = fir("0501", "Gotri", "Vadodara City", 6, KYC.format(phone="98111 22233"))
    ingest([text])
    with session_scope() as s:
        result = ingest_content(s, text.encode(), "again.txt")
        assert result.created == [] and len(result.duplicates) == 1


def test_full_dataset_recovers_planted_clusters(worker):
    """Regression test for the linking logic on the whole 400-FIR dataset (fake models)."""
    dataset = Path(__file__).resolve().parents[2] / "dataset" / "firs_main.txt"
    with session_scope() as s:
        ingest_content(s, dataset.read_bytes(), "firs_main.txt")
    drain(worker, max_rounds=2000)
    with session_scope() as s:
        m = evaluate(s, "all")
    assert m["identifiers"]["recall"] == 1.0 and m["identifiers"]["precision"] == 1.0
    # Known limitation: in cluster C10 two FIRs name the accused only as "Salim alias Pappu" / "Pappu" and no FIR
    # ties "Pappu" to the full name "Salim Sheikh", so evidence alone cannot prove they are one person.
    assert m["clusters"]["planted_clusters"] == 12
    assert m["clusters"]["recovered_exactly"] >= 11
    assert m["clusters"]["decoys_wrongly_clustered"] == 0
    assert m["clusters"]["pairwise"]["precision"] == 1.0


def test_standalone_dataset_creates_no_links_or_clusters(worker):
    dataset = Path(__file__).resolve().parents[2] / "dataset" / "firs_unrelated.txt"
    with session_scope() as s:
        assert len(ingest_content(s, dataset.read_bytes(), "firs_unrelated.txt").created) == 60
    drain(worker, max_rounds=500)
    with session_scope() as s:
        assert s.scalars(select(OffenderCluster)).all() == []
        assert s.scalars(select(Link).where(Link.kind == "EVIDENCE")).all() == []
