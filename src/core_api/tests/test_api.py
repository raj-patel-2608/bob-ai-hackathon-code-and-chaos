import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from conftest import drain
from test_pipeline import KYC, fir


@pytest.fixture()
def client(worker):
    with TestClient(create_app()) as c:
        yield c


def _upload(client, texts):
    body = "\n---\n".join(texts).encode()
    return client.post("/api/batches", files={"file": ("batch.txt", body, "text/plain")})


def test_upload_process_and_query(client, worker):
    resp = _upload(client, [fir("0101", "Navrangpura", "Ahmedabad City", 10, KYC.format(phone="98251 77304")),
                            fir("0102", "Adajan", "Surat City", 12, KYC.format(phone="+91-9825177304"))])
    assert resp.status_code == 202
    batch = resp.json()
    assert batch["created"] == 2
    drain(worker)

    status = client.get(batch["status_url"]).json()
    assert status["status"] == "COMPLETED" and status["progress"] == 1.0

    firs = client.get("/api/firs").json()
    assert firs["total"] == 2
    fir_id = firs["items"][0]["id"]

    detail = client.get(f"/api/firs/{fir_id}").json()
    assert detail["iif2_draft"]["minor_head"] == "OTP/KYC & bank-impersonation fraud"
    assert "XXXXXX" in detail["header"]["complainant"]                       # complainant phone masked
    assert all(e["value"] == "masked" for e in detail["entities"] if e["role"] == "complainant")

    related = client.get(f"/api/firs/{fir_id}/related").json()["related"]
    assert related and related[0]["link_kind"] == "EVIDENCE"
    assert any("+919825177304" in r for r in related[0]["reasons"])

    offenders = client.get("/api/offenders").json()
    assert offenders["total"] == 1 and offenders["items"][0]["n_districts"] == 2

    cluster = client.get(f"/api/offenders/{offenders['items'][0]['id']}").json()
    assert any("CDR" in a for a in cluster["suggested_actions"])

    search = client.get("/api/firs", params={"q": "9825177304"}).json()
    assert search["total"] == 2

    graph = client.get("/api/graph").json()
    assert any(n["type"] == "identity" for n in graph["nodes"])


def test_station_report_falls_back_to_template(client, worker, fake_models):
    fake_models.generator_available = False
    _upload(client, [fir("0101", "Navrangpura", "Ahmedabad City", 10, KYC.format(phone="98251 77304"))])
    drain(worker)
    station_id = client.get("/api/stations").json()[0]["id"]
    report = client.post(f"/api/stations/{station_id}/reports", json={}).json()
    assert report["generated_by"] == "template" and "Navrangpura" in report["narrative"]
    trends = client.get(f"/api/stations/{station_id}/trends").json()
    assert trends["firs"] == 1


def test_llm_report_with_invented_numbers_is_rejected(client, worker, fake_models):
    fake_models.generate_payload = {"text": "There were 999 frauds this month."}
    _upload(client, [fir("0101", "Navrangpura", "Ahmedabad City", 10, KYC.format(phone="98251 77304"))])
    drain(worker)
    station_id = client.get("/api/stations").json()[0]["id"]
    report = client.post(f"/api/stations/{station_id}/reports", json={}).json()
    assert report["generated_by"] == "template"


def test_review_and_bad_uploads(client, worker):
    assert client.post("/api/batches", files={"file": ("x.exe", b"abc", "application/octet-stream")}).status_code == 400
    assert client.post("/api/batches/text", json={"text": "   " * 10}).status_code in (400, 422)
    _upload(client, [fir("0101", "Navrangpura", "Ahmedabad City", 10, KYC.format(phone="98251 77304"))])
    drain(worker)
    fir_id = client.get("/api/firs").json()["items"][0]["id"]
    r = client.post(f"/api/firs/{fir_id}/review", json={"decision": "correct", "crime_minor": "cyber.fake_customer_care"})
    assert r.json()["crime_minor"] == "cyber.fake_customer_care" and r.json()["decided_by"] == "officer"


def test_health(client):
    ready = client.get("/api/health/ready").json()
    assert ready["checks"]["database"]["ok"] is True
    assert client.get("/api/health/live").json() == {"status": "ok"}


def test_reprocess_llm_after_credentials_added(client, worker, fake_models):
    fake_models.generator_available = False
    _upload(client, [fir("0901", "Gotri", "Vadodara City", 9, "LOWCONF caller said parcel seized, sent money.")])
    drain(worker)
    item = client.get("/api/firs").json()["items"][0]
    assert item["status"] == "NEEDS_REVIEW"

    fake_models.generator_available = True
    fake_models.generate_payload = {"json": {
        "crime_minor": "cyber.digital_arrest", "mo_flags": ["threat_of_arrest_or_case"], "accused": [],
        "victim": {"gender": "unknown", "age_group": "unknown"}, "summary": "Fake officers claimed a parcel was seized."}}
    assert client.post("/api/system/reprocess-llm").json()["requeued"] == 1
    drain(worker)
    item = client.get("/api/firs").json()["items"][0]
    assert item["status"] == "ANALYZED" and item["decided_by"] == "llm"
    assert item["crime_minor"] == "cyber.digital_arrest"
