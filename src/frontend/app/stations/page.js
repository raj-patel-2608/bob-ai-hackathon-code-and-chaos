"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import BarList from "../../components/BarList";
import { RiskBadge } from "../../components/Badges";
import ErrorBox from "../../components/ErrorBox";
import PageHeader from "../../components/PageHeader";
import StatCard from "../../components/StatCard";
import { api, fmtDate, fmtMoney } from "../../lib/api";

export default function StationsPage() {
  const [stations, setStations] = useState([]);
  const [station, setStation] = useState("");
  const [range, setRange] = useState({ date_from: "", date_to: "" });
  const [facts, setFacts] = useState(null);
  const [reports, setReports] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.stations().then((s) => { setStations(s); if (s[0]) setStation(String(s[0].id)); }).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!station) return;
    setError(null);
    api.trends(station, range).then(setFacts).catch((e) => setError(e.message));
    api.reports(station).then(setReports).catch(() => {});
  }, [station, range]);

  const generate = async () => {
    setBusy(true);
    try {
      await api.createReport(station, range);
      setReports(await api.reports(station));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const input = "bg-ink-950 border border-ink-600 px-3 py-2 text-sm text-paper-100";
  return (
    <div>
      <PageHeader eyebrow="Station-level crime trend summary" title="Station briefs"
        description="Facts are computed from the data. The written brief comes from IBM Granite (watsonx.ai) and is accepted only if every number in it matches the facts; otherwise a template brief is used."
        action={
          <div className="flex gap-2 items-center">
            <select value={station} onChange={(e) => setStation(e.target.value)} className={input}>
              {stations.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.district})</option>)}
            </select>
            <input type="date" value={range.date_from} onChange={(e) => setRange({ ...range, date_from: e.target.value })} className={input} />
            <input type="date" value={range.date_to} onChange={(e) => setRange({ ...range, date_to: e.target.value })} className={input} />
          </div>
        } />
      <div className="p-8 space-y-6">
        <ErrorBox error={error} />
        {facts ? (
          <>
            <div className="text-xs text-paper-500">Period {facts.period.from} to {facts.period.to} (compared with the previous period of the same length)</div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <StatCard label="FIRs" value={facts.firs} sub={facts.change_pct === null ? "no previous data" : `${facts.change_pct >= 0 ? "+" : ""}${facts.change_pct}% vs previous`} stripe="blue" />
              <StatCard label="Reported loss" value={fmtMoney(facts.total_loss)} stripe="green" />
              <StatCard label="Senior-citizen victims" value={facts.senior_citizen_victims} stripe="amber" />
              <StatCard label="Flagged clusters here" value={facts.flagged_clusters.length} stripe="red" />
              <StatCard label="Pending review" value={facts.pending_review} stripe="amber" />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="case-panel p-5">
                <div className="text-sm text-paper-100 font-medium mb-4">Crime types this period</div>
                <BarList data={Object.fromEntries(facts.crime_types.map((c) => [c.type, c.count]))} />
                {facts.rising.length ? (
                  <div className="mt-4 text-xs text-signal-amber">Rising: {facts.rising.map((r) => `${r.type} ${r.previous}→${r.count}`).join(" · ")}</div>
                ) : null}
              </div>
              <div className="case-panel p-5">
                <div className="text-sm text-paper-100 font-medium mb-4">Most common methods</div>
                {facts.top_methods.map((m) => <div key={m.method} className="text-xs text-paper-300 mb-1.5">· {m.method} <span className="text-paper-500">({m.count})</span></div>)}
                <div className="text-sm text-paper-100 font-medium mt-5 mb-2">Evidence links to other stations</div>
                {facts.linked_firs_at_other_stations.length ? facts.linked_firs_at_other_stations.map((x) => (
                  <div key={x.station} className="text-xs text-paper-300">· {x.station}: {x.firs} FIR(s)</div>
                )) : <div className="text-xs text-paper-500">none</div>}
              </div>
              <div className="case-panel p-5">
                <div className="text-sm text-paper-100 font-medium mb-4">Flagged clusters active here</div>
                {facts.flagged_clusters.length ? facts.flagged_clusters.map((c) => (
                  <Link key={c.id} href={`/offenders/${c.id}`} className="block text-xs mb-2 hover:text-signal-amber">
                    <span className="data-id text-paper-100">{c.id}</span> <RiskBadge risk={c.risk_level} />{" "}
                    <span className="text-paper-500">{c.firs_here} here / {c.firs_total} total, {c.stations} stations</span>
                  </Link>
                )) : <div className="text-xs text-paper-500">none</div>}
              </div>
            </div>
          </>
        ) : null}

        <div className="case-panel p-5">
          <div className="flex justify-between items-center mb-4">
            <div className="text-sm text-paper-100 font-medium">Crime trend briefs for the Station House Officer</div>
            <button onClick={generate} disabled={busy || !station} className="bg-signal-amber text-ink-950 text-sm font-medium px-4 py-2 disabled:opacity-40">
              {busy ? "Writing…" : "Generate brief"}
            </button>
          </div>
          {reports.length === 0 ? <div className="text-sm text-paper-500">No briefs yet.</div> : reports.map((r) => (
            <div key={r.id} className="border border-ink-700 p-4 mb-3">
              <div className="text-[11px] text-paper-500 mb-2">
                {fmtDate(r.period_from)} – {fmtDate(r.period_to)} · written by {r.generated_by} · {r.validated ? "numbers verified" : "unverified"} · {fmtDate(r.created_at)}
              </div>
              <p className="text-sm text-paper-300 leading-relaxed whitespace-pre-wrap">{r.narrative}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
