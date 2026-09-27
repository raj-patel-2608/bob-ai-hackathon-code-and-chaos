"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { StatusBadge } from "../../components/Badges";
import ErrorBox from "../../components/ErrorBox";
import InfoTip from "../../components/InfoTip";
import PageHeader from "../../components/PageHeader";
import { api, fmtDate, fmtMoney, pct } from "../../lib/api";
import { GLOSSARY } from "../../lib/glossary";

const COLUMNS = [
  { key: "id", label: "FIR", sortable: true },
  { key: "registered_at", label: "Registered", sortable: true },
  { key: "station", label: "Police station", sortable: true },
  { key: null, label: "Crime type", info: GLOSSARY.crimeType },
  { key: "amount", label: "Loss", sortable: true },
  { key: "confidence", label: "Decided by", sortable: true, info: GLOSSARY.decidedBy },
  { key: null, label: "Group", info: GLOSSARY.group },
];

function FirList() {
  const params = useSearchParams();
  const router = useRouter();
  const [filters, setFilters] = useState({
    q: params.get("q") || "", station_id: params.get("station_id") || "", crime_major: "",
    needs_review: params.get("needs_review") || "", linked: params.get("linked") || "",
  });
  const [sort, setSort] = useState({ key: "registered_at", order: "desc" });
  const [pageSize, setPageSize] = useState(25);
  const [page, setPage] = useState(0);
  const [stations, setStations] = useState([]);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { api.stations().then(setStations).catch(() => {}); }, []);
  useEffect(() => {
    const t = setTimeout(() => {
      api.firs({ ...filters, sort: sort.key, order: sort.order, limit: pageSize, offset: page * pageSize })
        .then((d) => { setData(d); setError(null); }).catch((e) => setError(e.message));
    }, 200);
    return () => clearTimeout(t);
  }, [filters, sort, pageSize, page]);

  const set = (k) => (e) => { setPage(0); setFilters({ ...filters, [k]: e.target.value }); };
  const toggleSort = (key) => {
    setPage(0);
    setSort((s) => (s.key === key ? { key, order: s.order === "asc" ? "desc" : "asc" } : { key, order: key === "id" || key === "station" ? "asc" : "desc" }));
  };
  const input = "input";
  const from = data && data.total ? page * pageSize + 1 : 0;
  const to = data ? Math.min((page + 1) * pageSize, data.total) : 0;
  const pages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  return (
    <div>
      <PageHeader title="Case files"
        description="Every FIR with its automatically drafted crime type. Search works with any identifier in any format, e.g. a phone written as 98765 43210 or +91-9876543210, or just part of a number." />
      <div className="p-8">
        <div className="flex flex-col xl:flex-row gap-3 mb-4">
          <input value={filters.q} onChange={set("q")} placeholder="Search text, FIR no., phone, account, UPI ID, vehicle…" className={`flex-1 ${input}`} />
          <select value={filters.station_id} onChange={set("station_id")} className={input}>
            <option value="">All police stations</option>
            {stations.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.district})</option>)}
          </select>
          <select value={filters.crime_major} onChange={set("crime_major")} className={input}>
            <option value="">All crime categories</option>
            <option value="cyber">Cyber crime</option>
            <option value="property">Property crime</option>
            <option value="body">Crime against the body</option>
            <option value="economic">Economic offence</option>
          </select>
          <select value={filters.linked} onChange={set("linked")} className={input}>
            <option value="">Grouped and standalone</option>
            <option value="true">In a repeat-offender group</option>
            <option value="false">Standalone (no shared evidence)</option>
          </select>
          <select value={filters.needs_review} onChange={set("needs_review")} className={input}>
            <option value="">Any review state</option>
            <option value="true">Needs officer check</option>
            <option value="false">No check needed</option>
          </select>
        </div>
        <ErrorBox error={error} />
        {!data ? <div className="text-sm text-paper-500">Loading…</div> : (
          <div className="case-panel overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="label border-b border-ink-700 bg-ink-800">
                  {COLUMNS.map((c) => (
                    <th key={c.label} className="text-left font-normal px-4 py-3 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1.5">
                        {c.sortable ? (
                          <button onClick={() => toggleSort(c.key)} className={`inline-flex items-center gap-1 uppercase tracking-[0.06em] hover:text-paper-100 ${sort.key === c.key ? "text-accent" : ""}`}>
                            {c.label}
                            <span className="text-[10px]">{sort.key === c.key ? (sort.order === "asc" ? "▲" : "▼") : "↕"}</span>
                          </button>
                        ) : c.label}
                        {c.info ? <InfoTip text={c.info} /> : null}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-700">
                {data.items.map((f) => (
                  <tr key={f.id} onClick={() => router.push(`/firs/${encodeURIComponent(f.id)}`)} className="hover:bg-ink-800/50 cursor-pointer">
                    <td className="px-4 py-3"><div className="data-id text-paper-100">{f.id}</div><StatusBadge status={f.status} /></td>
                    <td className="px-4 py-3 text-paper-300 whitespace-nowrap">{fmtDate(f.registered_at)}</td>
                    <td className="px-4 py-3 text-paper-300">{f.station}<div className="text-[11px] text-paper-500">{f.district}</div></td>
                    <td className="px-4 py-3 text-paper-300">{f.crime_minor_label || "—"}<div className="text-[11px] text-paper-500">{f.crime_major_label}</div></td>
                    <td className="px-4 py-3 text-paper-300 whitespace-nowrap">{fmtMoney(f.amount)}</td>
                    <td className="px-4 py-3 text-[12px] text-paper-300 whitespace-nowrap">
                      {f.decided_by === "llm" ? "IBM Granite" : f.decided_by === "laya" ? `Laya · ${pct(f.confidence)}` : f.decided_by || "—"}
                    </td>
                    <td className="px-4 py-3">
                      {f.cluster_id ? (
                        <Link href={`/offenders/${f.cluster_id}`} onClick={(e) => e.stopPropagation()} className="data-id text-xs text-signal-red hover:underline">{f.cluster_id}</Link>
                      ) : <span className="text-[11px] text-paper-500">standalone</span>}
                    </td>
                  </tr>
                ))}
                {data.items.length === 0 ? <tr><td colSpan={7} className="px-4 py-6 text-paper-500">No FIRs match these filters.</td></tr> : null}
              </tbody>
            </table>
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-t border-ink-700 text-xs text-paper-500">
              <div>Showing <span className="text-paper-100">{from}–{to}</span> of <span className="text-paper-100">{data.total}</span> FIRs</div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">Rows per page
                  <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(0); }} className="input py-1 px-2 text-xs">
                    {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </label>
                <button disabled={page === 0} onClick={() => setPage(page - 1)} className="btn btn-secondary btn-sm">‹ Prev</button>
                <span>Page {page + 1} of {pages}</span>
                <button disabled={page + 1 >= pages} onClick={() => setPage(page + 1)} className="btn btn-secondary btn-sm">Next ›</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function FirListPage() {
  return <Suspense fallback={<div className="px-8 py-5 text-sm text-paper-500">Loading…</div>}><FirList /></Suspense>;
}
