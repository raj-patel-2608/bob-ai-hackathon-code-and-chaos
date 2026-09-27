"""End-to-end check of the MCP server exactly as IBM Bob uses it: starts server.py over stdio (the command in
.bob/mcp.json), lists the tools and calls several of them against the RUNNING core API.

Run (core API must be up on :8000):  .venv/Scripts/python smoke_test.py      (from src/mcp_server)
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent


def text_of(result) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[str(HERE / "server.py")],
                                   env={"CRIMEFIR_API_URL": "http://127.0.0.1:8000", "PYTHONIOENCODING": "utf-8"})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            print(f"connected to MCP server '{info.server_info.name}'")
            tools = (await session.list_tools()).tools
            print(f"{len(tools)} tools: {', '.join(t.name for t in tools)}")

            checks = [
                ("system_overview", {}),
                ("list_flagged_offenders", {"min_risk": 70}),
                ("search_firs", {"query": "9825"}),
                ("list_stations", {}),
            ]
            failed = 0
            for name, args in checks:
                res = await session.call_tool(name, args)
                body = text_of(res)
                ok = not res.is_error and body.strip() not in ("", "null")
                failed += not ok
                print(f"  {'OK  ' if ok else 'FAIL'} {name}({json.dumps(args)}) -> {body[:160].replace(chr(10), ' ')}")

            clusters = json.loads(text_of(await session.call_tool("list_flagged_offenders", {"min_risk": 70})))
            items = clusters.get("items", clusters) if isinstance(clusters, dict) else clusters
            if items:
                cid = items[0]["id"]
                res = await session.call_tool("get_offender_cluster", {"cluster_id": cid})
                data = json.loads(text_of(res))
                print(f"  OK   get_offender_cluster({cid}) -> {data.get('n_firs')} FIRs, risk {data.get('risk_level')}, "
                      f"first action: {(data.get('suggested_actions') or ['-'])[0][:80]}")
                fir_id = data["timeline"][0]["id"]
                rel = json.loads(text_of(await session.call_tool("find_related_firs", {"fir_id": fir_id})))
                print(f"  OK   find_related_firs({fir_id}) -> {len(rel.get('related', rel))} linked FIRs")
            stations = json.loads(text_of(await session.call_tool("list_stations", {})))
            if stations:
                res = await session.call_tool("station_trends", {"station": stations[0]["name"]})
                t = json.loads(text_of(res))
                print(f"  OK   station_trends({stations[0]['name']}) -> {t.get('firs')} FIRs in period, "
                      f"{len(t.get('flagged_clusters', []))} flagged groups")
            print("RESULT:", "all MCP tool calls succeeded" if not failed else f"{failed} call(s) failed")
            return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
