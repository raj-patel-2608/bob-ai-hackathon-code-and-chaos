"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { CrimeTag, DecidedBy, StatusBadge } from "../../components/Badges";
import ErrorBox from "../../components/ErrorBox";
import PageHeader from "../../components/PageHeader";
import { api, fmtDate, fmtMoney } from "../../lib/api";

function FirList() {
  const params = useSearchParams();
  const [filters, setFilters] = useState({
    q: params.get("q") || "",
    station_id: params.get("station_id") || "",
    crime_major: "",
    needs_review: params.get("needs_review") || "",
  });
  const [stations, setStations] = useState([]);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);
  const pageSize = 50;

  useEffect(() => { api.stations().then(setStations).catch(() => {}); }, []);
  useEffect(() => {
    const t = setTimeout(() => {
      api.firs({ ...filters, limit: pageSize, offset: page * pageSize })
        .then(setData).catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [filters, page]);

  const set = (k) => (e) => { setPage(0); setFilters({ ...filters, [k]: e.target.value }); };
  const input = "bg-ink-950 border border-ink-600 px-3 py-2 text-sm text-paper-100 focus:outline-none focus:border-signal-amber";

  return (
    <div>
      <PageHeader eyebrow="Case files" title="FIRs"
        description="Search by free text, FIR id, or any identifier in any format: a phone number written as 98765 43210 or +91-9876543210, a partial number, an account, UPI ID or vehicle." />
      <div className="p-8">
        <div className="flex flex-col md:flex-row gap-3 mb-5">
          <input value={filters.q} onChange={set("q")} placeholder="Search text, FIR id, phone, account, UPI, vehicle…" className={`flex-1 ${input}`} />
          <select value={filters.station_id} onChange={set("station_id")} className={input}>
            <option value="">All stations</option>
            {stations.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.district})</option>)}
          </select>
          <select value={filters.crime_major} onChange={set("crime_major")} className={input}>
            <option value="">All crime types</option>
            <option value="cyber">Cyber Crime</option>
            <option value="property">Crimes against Property</option>
            <option value="body">Crimes against the Body</option>
            <option value="economic">Economic Offences</option>
          </select>
          <select value={filters.needs_review} onChange={set("needs_review")} className={input}>
            <option value="">Any review state</option>
            <option value="true">Needs officer review</option>
            <option value="false">Reviewed / confident</option>
          </select>
        </div>
        <ErrorBox error={error} />
        {!data ? <div className="text-sm text-paper-500">Loading…</div> : (
          <>
            <div className="text-xs text-paper-500 mb-2">{data.total} FIRs</div>
            <div className="case-panel divide-y divide-ink-700">
              {data.items.map((f) => (
                <Link key={f.id} href={`/firs/${encodeURIComponent(f.id)}`}
                  className="flex items-center justify-between gap-4 px-5 py-3 hover:bg-ink-800/60">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="data-id text-sm text-paper-100">{f.id}</span>
                      <CrimeTag>{f.crime_minor_label || "Unclassified"}</CrimeTag>
                      <StatusBadge status={f.status} />
                    </div>
                    <div className="text-xs text-paper-500 mt-1 truncate">
                      {f.station} · {f.district} · {fmtDate(f.registered_at)} · {fmtMoney(f.amount)} ·{" "}
                      <DecidedBy by={f.decided_by} confidence={f.confidence} />
                    </div>
                  </div>
                  <span className="text-paper-500 text-lg">›</span>
                </Link>
              ))}
            </div>
            <div className="flex justify-between mt-4 text-xs">
              <button disabled={page === 0} onClick={() => setPage(page - 1)} className="text-signal-amber disabled:opacity-30">‹ Previous</button>
              <span className="text-paper-500">Page {page + 1} of {Math.max(1, Math.ceil(data.total / pageSize))}</span>
              <button disabled={(page + 1) * pageSize >= data.total} onClick={() => setPage(page + 1)} className="text-signal-amber disabled:opacity-30">Next ›</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function FirListPage() {
  return <Suspense fallback={<div className="p-8 text-sm text-paper-500">Loading…</div>}><FirList /></Suspense>;
}
