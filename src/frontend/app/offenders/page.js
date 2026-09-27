"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { RiskBadge } from "../../components/Badges";
import ErrorBox from "../../components/ErrorBox";
import PageHeader from "../../components/PageHeader";
import InfoTip from "../../components/InfoTip";
import { api, fmtDate, fmtMoneyShort, IDENTITY_LABELS } from "../../lib/api";
import { GLOSSARY } from "../../lib/glossary";

export default function OffendersPage() {
  const [data, setData] = useState(null);
  const [stations, setStations] = useState([]);
  const [station, setStation] = useState("");
  const [minRisk, setMinRisk] = useState(0);
  const [error, setError] = useState(null);

  useEffect(() => { api.stations().then(setStations).catch(() => {}); }, []);
  useEffect(() => {
    api.offenders({ station_id: station, min_risk: minRisk }).then(setData).catch((e) => setError(e.message));
  }, [station, minRisk]);

  const input = "input";
  return (
    <div>
      <PageHeader title="Repeat offenders"
        description="Each group is a set of FIRs that share the same hard evidence (phone number, bank account, UPI ID, vehicle, online handle or named accused), so they probably involve the same person or gang, often across police stations and districts. Highest risk first. These are investigation leads: verify before acting."
        action={
          <div className="flex gap-2">
            <select value={station} onChange={(e) => setStation(e.target.value)} className={input}>
              <option value="">All stations</option>
              {stations.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.district})</option>)}
            </select>
            <select value={minRisk} onChange={(e) => setMinRisk(e.target.value)} className={input}>
              <option value={0}>All risk levels</option>
              <option value={45}>Medium and high</option>
              <option value={70}>High only</option>
            </select>
          </div>
        } />
      <div className="px-8 py-5 space-y-4">
        <div className="flex items-center gap-2 text-xs text-paper-500">What do HIGH / MEDIUM mean? <InfoTip text={GLOSSARY.highRisk} /></div>
        <ErrorBox error={error} />
        {!data ? <div className="text-sm text-paper-500">Loading…</div> : data.items.length === 0 ? (
          <div className="case-panel p-6 text-sm text-paper-500">No groups match these filters.</div>
        ) : data.items.map((c) => (
          <Link key={c.id} href={`/offenders/${c.id}`}
            className={`case-panel block p-5 hover:bg-ink-800/50 ${c.risk_level === "HIGH" ? "stripe-red" : c.risk_level === "MEDIUM" ? "stripe-amber" : "stripe-blue"}`}>
            <div className="flex items-start justify-between gap-6">
              <div>
                <div className="flex items-center gap-3">
                  <span className="text-lg font-semibold text-paper-100">Group {c.id}</span>
                  <RiskBadge risk={c.risk_level} score={c.risk_score} />
                </div>
                <div className="text-xs text-paper-500 mt-1">
                  {c.n_firs} FIRs at {c.n_stations} police stations in {c.n_districts} district(s) · {fmtMoneyShort(c.total_loss)} lost · first case {fmtDate(c.first_seen)}, latest {fmtDate(c.last_seen)}
                </div>
                <div className="text-xs text-paper-300 mt-2">{c.stations.join(" · ")}</div>
              </div>
              <div className="text-xs text-right space-y-1">
                {c.key_identifiers.slice(0, 3).map((k) => (
                  <div key={k.value}><span className="text-paper-500">{IDENTITY_LABELS[k.type] || k.type}</span>{" "}
                    <span className="data-id text-paper-100">{k.value}</span> <span className="text-paper-500">({k.fir_count} FIRs)</span></div>
                ))}
              </div>
            </div>
            <div className="text-[11px] text-paper-500 mt-3 mb-1">Why this risk level:</div>
            <div className="flex flex-wrap gap-2">
              {c.risk_factors.map((f) => <span key={f} className="pill bg-ink-800 text-paper-300 font-normal">{f}</span>)}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
