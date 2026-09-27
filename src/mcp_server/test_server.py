"""Unit tests for the MCP server (no running API needed): tool registration and station resolution."""
import asyncio

import pytest

import server

STATIONS = [{"id": 1, "name": "Maninagar", "district": "Ahmedabad City"},
            {"id": 3, "name": "Navrangpura", "district": "Ahmedabad City"},
            {"id": 7, "name": "Sayajigunj", "district": "Vadodara City"}]


@pytest.fixture()
def fake_api(monkeypatch):
    calls = []

    async def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path == "/api/stations":
            return STATIONS
        if path.endswith("/trends"):
            return {"station": "Navrangpura", "firs": 9}
        return {"ok": True}
    monkeypatch.setattr(server, "_request", fake_request)
    return calls


def test_all_tools_registered():
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert {"search_firs", "get_fir", "find_related_firs", "list_flagged_offenders", "get_offender_cluster",
            "station_trends", "station_brief", "ingest_firs"} <= names


def test_station_name_resolution(fake_api):
    assert asyncio.run(server._station_id("navrangpura PS")) == (3, "Navrangpura (Ahmedabad City)")
    assert asyncio.run(server._station_id("7"))[0] == 7
    with pytest.raises(server.ApiError, match="not found"):
        asyncio.run(server._station_id("Andheri"))


def test_station_trends_calls_api_with_resolved_id(fake_api):
    asyncio.run(server.mcp.call_tool("station_trends", {"station": "Navrangpura", "date_from": "2026-08-01"}))
    method, path, kwargs = fake_api[-1]
    assert path == "/api/stations/3/trends" and kwargs["params"] == {"date_from": "2026-08-01"}
