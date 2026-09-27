"""CrimeFIR MCP server: exposes the CrimeFIR intelligence API as tools for IBM Bob.

IBM Bob (IDE or Bob Shell) starts this server over stdio using .bob/mcp.json. An investigator can
then ask Bob questions in plain English ("which repeat-offender clusters touched Navrangpura PS in
August?") and Bob calls these tools, which call the core API. The server holds no data itself.

Run manually (for testing):  .venv/Scripts/python server.py
Env: CRIMEFIR_API_URL (default http://127.0.0.1:8000)
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

API_URL = os.environ.get("CRIMEFIR_API_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = float(os.environ.get("CRIMEFIR_API_TIMEOUT", "60"))

mcp = MCPServer(
    name="crimefir",
    title="CrimeFIR FIR Intelligence",
    instructions=(
        "Tools for police FIR intelligence: search FIRs, read the auto-drafted crime classification (NCRB I.I.F.-II), "
        "find FIRs linked by shared evidence, list flagged repeat-offender clusters and produce station-level crime "
        "trend briefs. Always cite FIR ids and cluster ids. Links and clusters are investigation leads that require "
        "human verification; never state that a person is guilty. Complainant personal data is masked."),
)


class ApiError(Exception):
    pass


async def _request(method: str, path: str, **kwargs) -> Any:
    try:
        async with httpx.AsyncClient(base_url=API_URL, timeout=TIMEOUT) as client:
            resp = await client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        raise ApiError(f"CrimeFIR API not reachable at {API_URL} ({exc.__class__.__name__}). "
                       "Start it with: src/core_api -> uvicorn app.main:app --port 8000") from exc
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise ApiError(f"CrimeFIR API {resp.status_code}: {detail}")
    return resp.json()


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str, indent=1)


async def _station_id(station: str) -> tuple[int, str]:
    stations = await _request("GET", "/api/stations")
    if station.isdigit():
        match = [s for s in stations if s["id"] == int(station)]
    else:
        key = station.lower().replace("police station", "").replace(" ps", "").strip()
        match = [s for s in stations if key in s["name"].lower()]
    if not match:
        raise ApiError(f"station '{station}' not found; known stations: "
                       + ", ".join(f"{s['name']} ({s['district']})" for s in stations))
    if len(match) > 1:
        raise ApiError("ambiguous station: " + ", ".join(f"{s['id']}={s['name']} ({s['district']})" for s in match))
    return match[0]["id"], f"{match[0]['name']} ({match[0]['district']})"


# ----------------------------------------------------------------------------- tools

@mcp.tool()
async def system_overview() -> str:
    """Overall picture: number of FIRs, crime types, stations, flagged clusters, review queue and model mode."""
    dashboard = await _request("GET", "/api/dashboard")
    ready = await _request("GET", "/api/health/ready")
    dashboard["top_clusters"] = [{k: c[k] for k in ("id", "risk_level", "n_firs", "n_stations", "n_districts")}
                                 for c in dashboard.get("top_clusters", [])]
    return _json({"mode": ready.get("mode"), **dashboard})


@mcp.tool()
async def ingest_firs(text: str) -> str:
    """Submit one or more FIR texts (separate FIRs with a line containing ---). Processing runs in the
    background; use batch_status with the returned batch_id to follow progress."""
    return _json(await _request("POST", "/api/batches/text", json={"text": text}))


@mcp.tool()
async def batch_status(batch_id: str) -> str:
    """Progress and per-stage status of an ingestion batch."""
    return _json(await _request("GET", f"/api/batches/{batch_id}"))


@mcp.tool()
async def search_firs(query: str = "", crime_type: str = "", station: str = "", needs_review: bool | None = None,
                      limit: int = 20) -> str:
    """Search FIRs by free text, FIR id or any identifier in any format (phone, account, UPI ID, vehicle).
    Optional filters: crime_type (taxonomy id such as cyber.digital_arrest), station name, needs_review."""
    params: dict[str, Any] = {"limit": min(max(limit, 1), 100)}
    if query:
        params["q"] = query
    if crime_type:
        params["crime_minor" if "." in crime_type else "crime_major"] = crime_type
    if station:
        params["station_id"], _ = await _station_id(station)
    if needs_review is not None:
        params["needs_review"] = needs_review
    return _json(await _request("GET", "/api/firs", params=params))


@mcp.tool()
async def get_fir(fir_id: str) -> str:
    """One FIR: header, narrative, auto-drafted crime classification (major/minor head, MO, victim, accused),
    extracted evidence, cluster membership and pipeline status."""
    fir = await _request("GET", f"/api/firs/{fir_id}")
    fir.pop("narrative_offset", None)
    return _json(fir)


@mcp.tool()
async def find_related_firs(fir_id: str) -> str:
    """FIRs linked to this FIR, with the reasons: EVIDENCE links (shared phone/account/UPI/vehicle/accused) and
    PATTERN links (same crime type, similar story, no shared evidence)."""
    return _json(await _request("GET", f"/api/firs/{fir_id}/related"))


@mcp.tool()
async def explain_link(fir_a: str, fir_b: str) -> str:
    """Why two FIRs are linked, quoting the shared evidence as written in each FIR."""
    return _json(await _request("GET", f"/api/links/{fir_a}/{fir_b}"))


@mcp.tool()
async def list_flagged_offenders(min_risk: int = 0, station: str = "") -> str:
    """The flagged repeat-offender list: clusters of FIRs connected by shared evidence, ranked by a transparent
    risk score (FIRs, stations, districts, loss, recency, senior-citizen victims). Optionally only clusters that
    touch one station."""
    params: dict[str, Any] = {"min_risk": min_risk}
    if station:
        params["station_id"], _ = await _station_id(station)
    return _json(await _request("GET", "/api/offenders", params=params))


@mcp.tool()
async def get_offender_cluster(cluster_id: str) -> str:
    """Details of one repeat-offender cluster: timeline of FIRs, key identifiers, claimed fake identities,
    links with reasons, risk factors and suggested investigative actions."""
    return _json(await _request("GET", f"/api/offenders/{cluster_id}"))


@mcp.tool()
async def list_stations() -> str:
    """Police stations present in the data."""
    return _json(await _request("GET", "/api/stations"))


@mcp.tool()
async def station_trends(station: str, date_from: str = "", date_to: str = "") -> str:
    """Station-level crime facts for a period (ISO dates; default = last 30 days of data) vs the previous period:
    crime mix, rising types, common methods, losses, flagged clusters, links to other stations."""
    sid, _ = await _station_id(station)
    params = {k: v for k, v in (("date_from", date_from), ("date_to", date_to)) if v}
    return _json(await _request("GET", f"/api/stations/{sid}/trends", params=params))


@mcp.tool()
async def station_brief(station: str, date_from: str = "", date_to: str = "") -> str:
    """Generate and store the station-level crime trend summary (Granite LLM on watsonx, every number checked
    against the facts; template fallback) for the Station House Officer."""
    sid, _ = await _station_id(station)
    body = {k: v for k, v in (("date_from", date_from), ("date_to", date_to)) if v}
    report = await _request("POST", f"/api/stations/{sid}/reports", json=body)
    return _json({k: report[k] for k in ("id", "narrative", "generated_by", "validated", "period_from", "period_to")})


if __name__ == "__main__":
    mcp.run("stdio")
