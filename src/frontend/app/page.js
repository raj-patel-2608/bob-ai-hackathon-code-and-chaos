"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import BarList from "../components/BarList";
import { RiskBadge } from "../components/Badges";
import ErrorBox from "../components/ErrorBox";
import PageHeader from "../components/PageHeader";
import Sparkline from "../components/Sparkline";
import StatCard from "../components/StatCard";
import { api, fmtDate, fmtMoney, IDENTITY_LABELS } from "../lib/api";

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="p-8"><ErrorBox error={error} /></div>;
  if (!data) return <div className="p-8 text-paper-500 text-sm">Loading dashboard…</div>;

  if (data.total_firs === 0) {
    return (
      <div>
        <PageHeader eyebrow="Overview" title="Investigation dashboard" description="No FIRs ingested yet." />
        <div className="p-8">
          <div className="case-panel stripe-amber p-8 max-w-xl">
            <div className="font-serif text-xl text-paper-100 mb-2">Nothing to show yet</div>
            <p className="text-sm text-paper-500 mb-5">
              Upload a batch of FIRs (for example <span className="data-id">src/dataset/firs_main.txt</span>) to see
              crime classification, evidence links and flagged repeat-offender clusters.
            </p>
            <Link href="/upload" className="bg-signal-amber text-ink-950 text-sm font-medium px-4 py-2">
              Ingest FIRs
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const byMajor = Object.fromEntries(data.crime_major.map((c) => [c.label, c.count]));
  const byMinor = Object.fromEntries(data.crime_minor.slice(0, 10).map((c) => [c.label, c.count]));
  const byStation = Object.fromEntries(data.stations.map((s) => [`${s.station} (${s.district})`, s.count]));
  const monthly = Object.fromEntries(data.monthly);

  return (
    <div>
      <PageHeader
        eyebrow="Overview"
        title="Investigation dashboard"
        description="Crime intelligence across every ingested FIR: classification, evidence links between stations and districts, and flagged repeat-offender clusters."
      />
      <div className="p-8 space-y-8">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard label="FIRs analysed" value={data.total_firs} stripe="blue" />
          <StatCard label="Flagged clusters" value={data.flagged_clusters} sub={`${data.high_risk_clusters} high risk`} stripe="red" />
          <StatCard label="Evidence links" value={data.links?.EVIDENCE || 0} sub={`${data.links?.PATTERN || 0} pattern-only`} stripe="amber" />
          <StatCard label="Awaiting review" value={data.needs_review} sub="low-confidence classifications" stripe="amber" />
          <StatCard label="Reported loss" value={fmtMoney(data.total_loss)} stripe="green" />
        </div>

        <div className="case-panel p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm text-paper-100 font-medium">Top flagged repeat-offender clusters</div>
            <Link href="/offenders" className="text-xs text-signal-amber hover:underline">All clusters ›</Link>
          </div>
          <div className="divide-y divide-ink-700">
            {data.top_clusters.map((c) => (
              <Link key={c.id} href={`/offenders/${c.id}`} className="py-3 flex items-start justify-between gap-4 hover:bg-ink-800/50 px-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="data-id text-paper-100">{c.id}</span>
                    <RiskBadge risk={c.risk_level} score={c.risk_score} />
                  </div>
                  <div className="text-xs text-paper-500 mt-1">
                    {c.n_firs} FIRs · {c.n_stations} stations · {c.n_districts} districts · {fmtMoney(c.total_loss)} ·{" "}
                    {fmtDate(c.first_seen)} – {fmtDate(c.last_seen)}
                  </div>
                </div>
                <div className="text-xs text-paper-300 text-right max-w-sm">
                  {(c.key_identifiers || []).slice(0, 2).map((k) => (
                    <div key={k.value}>
                      <span className="text-paper-500">{IDENTITY_LABELS[k.type] || k.type}:</span>{" "}
                      <span className="data-id">{k.value}</span>
                    </div>
                  ))}
                </div>
              </Link>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="case-panel p-5">
            <div className="text-sm text-paper-100 font-medium mb-4">Crime type (major head)</div>
            <BarList data={byMajor} colorClass="bg-signal-blue" />
            <div className="text-sm text-paper-100 font-medium mt-6 mb-4">Top minor heads</div>
            <BarList data={byMinor} colorClass="bg-signal-blue" />
          </div>
          <div className="case-panel p-5">
            <div className="text-sm text-paper-100 font-medium mb-4">FIRs by police station</div>
            <BarList data={byStation} colorClass="bg-signal-amber" />
            <div className="text-sm text-paper-100 font-medium mt-6 mb-2">Decided by</div>
            <div className="text-xs text-paper-500">
              {Object.entries(data.decided_by).map(([k, v]) => `${k}: ${v}`).join(" · ")}
            </div>
          </div>
        </div>

        <div className="case-panel p-5">
          <div className="text-sm text-paper-100 font-medium mb-4">FIRs registered per month</div>
          <Sparkline data={monthly} />
        </div>
      </div>
    </div>
  );
}
