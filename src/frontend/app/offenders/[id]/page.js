"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CrimeTag, LinkBadge, RiskBadge } from "../../../components/Badges";
import ErrorBox from "../../../components/ErrorBox";
import ForceGraph from "../../../components/ForceGraph";
import PageHeader from "../../../components/PageHeader";
import { api, fmtDate, fmtMoney, IDENTITY_LABELS, toForceGraph } from "../../../lib/api";

export default function ClusterPage() {
  const { id } = useParams();
  const [c, setC] = useState(null);
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.offender(id).then(setC).catch((e) => setError(e.message));
    api.graph({ cluster_id: id, include_pattern: false }).then((g) => setGraph(toForceGraph(g))).catch(() => {});
  }, [id]);

  if (error) return <div className="p-8"><ErrorBox error={error} /></div>;
  if (!c) return <div className="p-8 text-sm text-paper-500">Loading cluster…</div>;

  return (
    <div>
      <PageHeader eyebrow="Flagged repeat-offender cluster" title={c.id}
        description={`${c.n_firs} FIRs across ${c.n_stations} police stations in ${c.n_districts} district(s), ${fmtDate(c.first_seen)} – ${fmtDate(c.last_seen)}, total reported loss ${fmtMoney(c.total_loss)}.`}
        action={<RiskBadge risk={c.risk_level} score={c.risk_score} />} />
      <div className="p-8 grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <div className="case-panel p-2">{graph ? <ForceGraph graph={graph} /> : <div className="p-8 text-sm text-paper-500">Loading graph…</div>}</div>
          <div className="case-panel p-5">
            <div className="text-sm text-paper-100 font-medium mb-3">Timeline of linked FIRs</div>
            <div className="divide-y divide-ink-700">
              {c.timeline.map((f) => (
                <Link key={f.id} href={`/firs/${encodeURIComponent(f.id)}`} className="py-2.5 flex justify-between gap-4 hover:bg-ink-800/50 px-1">
                  <div>
                    <span className="data-id text-sm text-paper-100">{f.id}</span>
                    <div className="text-xs text-paper-500">{fmtDate(f.registered_at)} · {f.station} ({f.district}) · {fmtMoney(f.amount)}</div>
                  </div>
                  <CrimeTag>{f.crime_minor_label}</CrimeTag>
                </Link>
              ))}
            </div>
          </div>
          <div className="case-panel p-5">
            <div className="text-sm text-paper-100 font-medium mb-3">Why these FIRs are linked</div>
            <div className="space-y-3">
              {c.links.map((l) => (
                <div key={`${l.fir_a}-${l.fir_b}-${l.kind}`} className="border border-ink-700 p-3 text-xs">
                  <div className="flex justify-between gap-2 mb-1">
                    <span className="data-id text-paper-100">{l.fir_a} ↔ {l.fir_b}</span>
                    <LinkBadge kind={l.kind} score={l.score} />
                  </div>
                  {l.reasons.map((r, i) => <div key={i} className="text-paper-300">· {r}</div>)}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="space-y-6">
          <div className="case-panel stripe-red p-5">
            <div className="text-sm text-paper-100 font-medium mb-3">Key identifiers</div>
            {c.key_identifiers.map((k) => (
              <div key={k.value} className="text-xs mb-2">
                <div className="text-paper-500">{IDENTITY_LABELS[k.type] || k.type} · in {k.fir_count} FIRs · centrality {k.centrality}</div>
                <Link href={`/firs?q=${encodeURIComponent(k.value)}`} className="data-id text-paper-100 hover:text-signal-amber">{k.value}</Link>
              </div>
            ))}
            {c.claimed_identities?.length ? (
              <div className="text-xs mt-3 border-t border-ink-700 pt-3">
                <div className="text-paper-500 mb-1">Identities the offender claimed (signature only)</div>
                {c.claimed_identities.map((x) => <div key={x.value} className="text-paper-300">· {x.value} ({x.firs} FIRs)</div>)}
              </div>
            ) : null}
          </div>
          <div className="case-panel p-5">
            <div className="text-sm text-paper-100 font-medium mb-3">Risk factors</div>
            {c.risk_factors.map((f) => <div key={f} className="text-xs text-paper-300 mb-1">· {f}</div>)}
          </div>
          <div className="case-panel stripe-green p-5">
            <div className="text-sm text-paper-100 font-medium mb-3">Suggested next actions</div>
            {c.suggested_actions.map((a) => <div key={a} className="text-xs text-paper-300 mb-1.5">· {a}</div>)}
            <div className="text-[11px] text-paper-500 mt-3">Investigation lead only. Requires human verification.</div>
          </div>
        </div>
      </div>
    </div>
  );
}
