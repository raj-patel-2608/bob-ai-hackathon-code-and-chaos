"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import BarList from "../components/BarList";
import { RiskBadge } from "../components/Badges";
import ErrorBox from "../components/ErrorBox";
import InfoTip from "../components/InfoTip";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import { api, fmtDate, fmtMoneyShort, IDENTITY_LABELS } from "../lib/api";
import { GLOSSARY } from "../lib/glossary";

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { api.dashboard().then(setData).catch((e) => setError(e.message)); }, []);

  if (error) return <div className="p-8"><ErrorBox error={error} /></div>;
  if (!data) return <div className="p-8 text-paper-500 text-sm">Loading…</div>;

  if (data.total_firs === 0) {
    return (
      <div>
        <PageHeader title="Dashboard" description="No FIRs yet." />
        <div className="p-8">
          <div className="case-panel stripe-amber p-8 max-w-xl">
            <div className="font-serif text-xl text-paper-100 mb-2">Start by adding FIRs</div>
            <p className="text-sm text-paper-500 mb-5">
              Upload a file of FIRs (for example <span className="data-id">src/dataset/firs_main.txt</span>) or paste FIR
              text. CrimeFIR reads each FIR, classifies the crime and finds cases that are connected by the same evidence.
            </p>
            <Link href="/upload" className="bg-signal-amber text-ink-950 text-sm font-medium px-4 py-2">Add FIRs</Link>
          </div>
        </div>
      </div>
    );
  }

  const high = data.clusters_by_risk?.HIGH || 0;
  const standalone = data.total_firs - (data.linked_firs || 0);
  const categories = Object.fromEntries(data.crime_major.map((c) => [c.label, c.count]));
  const stations = Object.fromEntries(data.stations.slice(0, 6).map((s) => [`${s.station} (${s.district})`, s.count]));

  return (
    <div>
      <PageHeader title="Dashboard"
        description="What needs attention across all FIRs: groups of cases that point to the same offender, and cases the AI was unsure about." />
      <div className="p-8 space-y-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="FIRs analysed" value={data.total_firs} stripe="blue" href="/firs"
            sub={`${data.linked_firs || 0} linked to a group · ${standalone} standalone`} />
          <StatCard label="Repeat-offender groups" value={data.flagged_clusters} stripe="red" href="/offenders"
            sub={`${high} high risk`} info={GLOSSARY.group} />
          <StatCard label="Need officer check" value={data.needs_review} stripe="amber" href="/firs?needs_review=true"
            sub={data.needs_review ? "AI was not sure of the crime type" : "nothing pending"} info={GLOSSARY.review} />
          <StatCard label="Money reported lost" value={fmtMoneyShort(data.total_loss)} stripe="green"
            sub="total across all FIRs" />
        </div>

        <div className="case-panel p-5">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2 text-sm text-paper-100 font-medium">
              Act on these first: highest-risk repeat-offender groups <InfoTip text={GLOSSARY.highRisk} />
            </div>
            <Link href="/offenders" className="text-xs text-signal-amber hover:underline">See all {data.flagged_clusters} ›</Link>
          </div>
          <div className="text-xs text-paper-500 mb-3">Each group is a set of FIRs, often from different police stations, that share the same phone, bank account, UPI ID or vehicle.</div>
          <div className="divide-y divide-ink-700">
            {data.top_clusters.map((c) => (
              <Link key={c.id} href={`/offenders/${c.id}`} className="py-3 flex items-start justify-between gap-4 hover:bg-ink-800/50 px-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="data-id text-paper-100">Group {c.id}</span>
                    <RiskBadge risk={c.risk_level} />
                  </div>
                  <div className="text-xs text-paper-300 mt-1">
                    {c.n_firs} FIRs at {c.n_stations} police stations in {c.n_districts} district{c.n_districts > 1 ? "s" : ""} ·
                    {" "}{fmtMoneyShort(c.total_loss)} lost · latest case {fmtDate(c.last_seen)}
                  </div>
                </div>
                <div className="text-xs text-right">
                  <div className="text-paper-500">shared evidence</div>
                  {(c.key_identifiers || []).slice(0, 2).map((k) => (
                    <div key={k.value} className="text-paper-300"><span className="text-paper-500">{IDENTITY_LABELS[k.type]}:</span> <span className="data-id">{k.value}</span></div>
                  ))}
                </div>
              </Link>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="case-panel p-5">
            <div className="flex items-center gap-2 text-sm text-paper-100 font-medium mb-4">FIRs by crime category <InfoTip text={GLOSSARY.crimeCategory} /></div>
            <BarList data={categories} colorClass="bg-signal-blue" />
          </div>
          <div className="case-panel p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm text-paper-100 font-medium">Busiest police stations</div>
              <Link href="/stations" className="text-xs text-signal-amber hover:underline">Station briefs ›</Link>
            </div>
            <BarList data={stations} colorClass="bg-signal-amber" />
          </div>
        </div>
      </div>
    </div>
  );
}
