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

  useEffect(() => { api.dashboard().then(setData).catch(setError); }, []);

  if (error) return <div className="px-8 py-7"><ErrorBox error={error} /></div>;
  if (!data) return <div className="px-8 py-7 text-paper-500 text-sm">Loading…</div>;

  if (data.total_firs === 0) {
    return (
      <div>
        <PageHeader title="Dashboard" />
        <div className="px-8 py-5">
          <div className="case-panel p-10 max-w-2xl flex flex-col items-start">
            <div className="text-lg font-semibold text-paper-100 mb-1">No FIRs yet</div>
            <p className="text-sm text-paper-500 mb-5">
              Add FIRs to see crime types, repeat-offender groups and station trends. Try{" "}
              <span className="data-id">src/dataset/firs_main.txt</span> for a 400-FIR sample.
            </p>
            <Link href="/upload" className="btn btn-primary">Add FIRs</Link>
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
      <PageHeader title="Dashboard" description="Repeat-offender groups to act on, and cases waiting for an officer." />
      <div className="px-8 py-5 space-y-5">
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard label="FIRs analysed" value={data.total_firs.toLocaleString("en-IN")} stripe="blue" href="/firs"
            sub={`${data.linked_firs || 0} in groups · ${standalone} standalone`} />
          <StatCard label="Repeat-offender groups" value={data.flagged_clusters} stripe="red" href="/offenders"
            sub={`${high} high risk`} info={GLOSSARY.group} />
          <StatCard label="Needs officer check" value={data.needs_review} stripe="amber" href="/firs?needs_review=true"
            sub={data.needs_review ? "AI was unsure of the crime type" : "Nothing pending"} info={GLOSSARY.review} />
          <StatCard label="Reported loss" value={fmtMoneyShort(data.total_loss)} stripe="green" sub="Across all FIRs" />
        </div>

        <div className="case-panel overflow-hidden">
          <div className="panel-head">
            <div className="flex items-center gap-2 section-title">Highest-risk groups <InfoTip text={GLOSSARY.highRisk} /></div>
            <Link href="/offenders" className="link text-xs">View all {data.flagged_clusters}</Link>
          </div>
          <div className="divide-y divide-ink-700">
            {data.top_clusters.map((c) => (
              <Link key={c.id} href={`/offenders/${c.id}`} className="px-5 py-3.5 flex items-center justify-between gap-4 hover:bg-ink-800/50">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="data-id font-medium text-paper-100">Group {c.id}</span>
                    <RiskBadge risk={c.risk_level} />
                  </div>
                  <div className="text-xs text-paper-500 mt-1">
                    {c.n_firs} FIRs · {c.n_stations} stations · {c.n_districts} district{c.n_districts > 1 ? "s" : ""} ·{" "}
                    {fmtMoneyShort(c.total_loss)} lost · latest {fmtDate(c.last_seen)}
                  </div>
                </div>
                <div className="text-xs text-right hidden md:block">
                  {(c.key_identifiers || []).slice(0, 2).map((k) => (
                    <div key={k.value} className="text-paper-300"><span className="text-paper-500">{IDENTITY_LABELS[k.type]}</span> <span className="data-id">{k.value}</span></div>
                  ))}
                </div>
              </Link>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="case-panel">
            <div className="panel-head"><div className="flex items-center gap-2 section-title">FIRs by crime category <InfoTip text={GLOSSARY.crimeCategory} /></div></div>
            <div className="p-5"><BarList data={categories} colorClass="bg-accent" /></div>
          </div>
          <div className="case-panel">
            <div className="panel-head">
              <div className="section-title">Busiest police stations</div>
              <Link href="/stations" className="link text-xs">Station briefs</Link>
            </div>
            <div className="p-5"><BarList data={stations} colorClass="bg-khaki" /></div>
          </div>
        </div>
      </div>
    </div>
  );
}
