"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import BarList from "../../components/BarList";
import { RiskBadge } from "../../components/Badges";
import ErrorBox from "../../components/ErrorBox";
import PageHeader from "../../components/PageHeader";
import StatCard from "../../components/StatCard";
import InfoTip from "../../components/InfoTip";
import { api, fmtDate, fmtMoneyShort } from "../../lib/api";
import { GLOSSARY } from "../../lib/glossary";

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

  const input = "input";
  return (
    <div>
      <PageHeader title="Station briefs"
        description="Pick a police station and a period (default: the last 30 days of data). You see what happened there compared with the period before, and can generate a short written brief for the Station House Officer."
        action={
          <div className="flex gap-2 items-center">
            <select value={station} onChange={(e) => setStation(e.target.value)} className={input}>
              {stations.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.district})</option>)}
            </select>
            <input type="date" value={range.date_from} onChange={(e) => setRange({ ...range, date_from: e.target.value })} className={input} />
            <input type="date" value={range.date_to} onChange={(e) => setRange({ ...range, date_to: e.target.value })} className={input} />
          </div>
        } />
      <div className="px-8 py-5 space-y-6">
        <ErrorBox error={error} />
        {facts ? (
          <>
            <div className="text-xs text-paper-500">Showing {facts.station} ({facts.district}) from {fmtDate(facts.period.from)} to {fmtDate(facts.period.to)}, compared with the same number of days just before.</div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <StatCard label="FIRs this period" value={facts.firs} sub={facts.change_pct === null ? "no FIRs in the period before" : `${facts.change_pct >= 0 ? "+" : ""}${facts.change_pct}% vs period before (${facts.previous_period_firs})`} stripe="blue" />
              <StatCard label="Money lost" value={fmtMoneyShort(facts.total_loss)} stripe="green" />
              <StatCard label="Victims aged 60+" value={facts.senior_citizen_victims} stripe="amber" />
              <StatCard label="Repeat-offender groups active here" value={facts.flagged_clusters.length} stripe="red" info={GLOSSARY.group} />
              <StatCard label="Need officer check" value={facts.pending_review} stripe="amber" info={GLOSSARY.review} />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="case-panel p-5">
                <div className="section-title mb-1">Number of FIRs by crime type</div>
                <div className="text-[11px] text-paper-500 mb-4">this period (number in brackets = period before)</div>
                <BarList data={Object.fromEntries(facts.crime_types.map((c) => [`${c.type} (${c.previous})`, c.count]))} />
                {facts.rising.length ? (
                  <div className="mt-4 text-xs text-signal-amber">Increasing: {facts.rising.map((r) => `${r.type} ${r.previous}→${r.count}`).join(" · ")}</div>
                ) : null}
              </div>
              <div className="case-panel p-5">
                <div className="section-title mb-4">How crimes were committed (most common)</div>
                {facts.top_methods.map((m) => <div key={m.method} className="text-xs text-paper-300 mb-1.5">· {m.method} <span className="text-paper-500">({m.count})</span></div>)}
                <div className="section-title mt-5 mb-2">Same evidence also seen at other stations</div>
                {facts.linked_firs_at_other_stations.length ? facts.linked_firs_at_other_stations.map((x) => (
                  <div key={x.station} className="text-xs text-paper-300">· {x.station}: {x.firs} FIR(s)</div>
                )) : <div className="text-xs text-paper-500">none</div>}
              </div>
              <div className="case-panel p-5">
                <div className="section-title mb-4">Repeat-offender groups with FIRs here</div>
                {facts.flagged_clusters.length ? facts.flagged_clusters.map((c) => (
                  <Link key={c.id} href={`/offenders/${c.id}`} className="block text-xs mb-2 hover:text-accent">
                    <span className="data-id text-paper-100">{c.id}</span> <RiskBadge risk={c.risk_level} />{" "}
                    <span className="text-paper-500">{c.firs_here} FIR(s) here, {c.firs_total} in total across {c.stations} stations</span>
                  </Link>
                )) : <div className="text-xs text-paper-500">none</div>}
              </div>
            </div>
          </>
        ) : null}

        <div className="case-panel p-5">
          <div className="flex justify-between items-center mb-4">
            <div><div className="flex items-center gap-2 section-title">Written brief for the Station House Officer <InfoTip text={GLOSSARY.brief} /></div><div className="text-[11px] text-paper-500 mt-1">Input: the numbers above. Output: a short text written by IBM Granite (watsonx.ai), accepted only if every number in it matches the data.</div></div>
            <button onClick={generate} disabled={busy || !station} className="btn btn-primary">
              {busy ? "Writing…" : "Generate brief"}
            </button>
          </div>
          {reports.length === 0 ? <div className="text-sm text-paper-500">No briefs yet.</div> : reports.map((r) => (
            <div key={r.id} className="rounded-lg border border-ink-700 p-4 mb-3">
              <div className="text-[11px] text-paper-500 mb-2">
                {fmtDate(r.period_from)} – {fmtDate(r.period_to)} · {r.generated_by.startsWith("llm") ? "written by IBM Granite (watsonx.ai)" : "template (AI text not available or rejected)"} · {r.validated ? "all numbers checked against the data" : "not checked"} · created {fmtDate(r.created_at)}
              </div>
              <p className="text-sm text-paper-300 leading-relaxed whitespace-pre-wrap">{r.narrative}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
