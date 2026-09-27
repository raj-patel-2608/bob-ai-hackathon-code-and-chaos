"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { RiskBadge } from "../../components/Badges";
import ErrorBox from "../../components/ErrorBox";
import PageHeader from "../../components/PageHeader";
import { api, fmtDate, fmtMoney, IDENTITY_LABELS } from "../../lib/api";

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

  const input = "bg-ink-950 border border-ink-600 px-3 py-2 text-sm text-paper-100";
  return (
    <div>
      <PageHeader eyebrow="Flagged repeat-offender list" title="Repeat-offender clusters"
        description="FIRs connected by shared evidence (phone, bank account, UPI ID, vehicle, online handle, accused name/alias) form a cluster, found with NetworkX. The risk score is a transparent points formula. Every cluster is a lead that needs human verification."
        action={
          <div className="flex gap-2">
            <select value={station} onChange={(e) => setStation(e.target.value)} className={input}>
              <option value="">All stations</option>
              {stations.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.district})</option>)}
            </select>
            <select value={minRisk} onChange={(e) => setMinRisk(e.target.value)} className={input}>
              <option value={0}>Any risk</option>
              <option value={35}>Medium +</option>
              <option value={60}>High only</option>
            </select>
          </div>
        } />
      <div className="p-8 space-y-4">
        <ErrorBox error={error} />
        {!data ? <div className="text-sm text-paper-500">Loading…</div> : data.items.length === 0 ? (
          <div className="case-panel p-6 text-sm text-paper-500">No clusters match.</div>
        ) : data.items.map((c) => (
          <Link key={c.id} href={`/offenders/${c.id}`}
            className={`case-panel block p-5 hover:bg-ink-800/60 ${c.risk_level === "HIGH" ? "stripe-red" : c.risk_level === "MEDIUM" ? "stripe-amber" : "stripe-blue"}`}>
            <div className="flex items-start justify-between gap-6">
              <div>
                <div className="flex items-center gap-3">
                  <span className="font-serif text-xl text-paper-100">{c.id}</span>
                  <RiskBadge risk={c.risk_level} score={c.risk_score} />
                </div>
                <div className="text-xs text-paper-500 mt-1">
                  {c.n_firs} FIRs · {c.n_stations} police stations · {c.n_districts} district(s) · {fmtMoney(c.total_loss)} · {fmtDate(c.first_seen)} – {fmtDate(c.last_seen)}
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
            <div className="flex flex-wrap gap-2 mt-3">
              {c.risk_factors.map((f) => <span key={f} className="text-[11px] border border-ink-600 px-2 py-0.5 text-paper-300">{f}</span>)}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
