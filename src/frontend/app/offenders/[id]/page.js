"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { LinkBadge, RiskBadge } from "../../../components/Badges";
import ErrorBox from "../../../components/ErrorBox";
import InvestigationGraph from "../../../components/InvestigationGraph";
import PageHeader from "../../../components/PageHeader";
import { api, fmtDate, fmtMoney, fmtMoneyShort, IDENTITY_LABELS } from "../../../lib/api";

export default function ClusterPage() {
  const { id } = useParams();
  const [c, setC] = useState(null);
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.offender(id).then(setC).catch((e) => setError(e.message));
    api.graph({ cluster_id: id, include_pattern: false }).then(setGraph).catch(() => {});
  }, [id]);

  if (error) return <div className="p-8"><ErrorBox error={error} /></div>;
  if (!c) return <div className="px-8 py-5 text-sm text-paper-500">Loading cluster…</div>;

  return (
    <div>
      <PageHeader eyebrow="Repeat-offender group" title={`Group ${c.id}`}
        description={`${c.n_firs} FIRs at ${c.n_stations} police stations in ${c.n_districts} district(s), from ${fmtDate(c.first_seen)} to ${fmtDate(c.last_seen)}, total reported loss ${fmtMoneyShort(c.total_loss)}. They are connected by the shared evidence listed on the right.`}
        action={<RiskBadge risk={c.risk_level} score={c.risk_score} />} />
      <div className="px-8 py-5 grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <div className="case-panel p-3">{graph ? <InvestigationGraph graph={graph} height={480} initialMode="timeline" /> : <div className="px-8 py-5 text-sm text-paper-500">Loading graph…</div>}</div>
          <div className="case-panel p-5">
            <div className="section-title mb-3">The FIRs in order of date</div>
            <div className="divide-y divide-ink-700">
              {c.timeline.map((f) => (
                <Link key={f.id} href={`/firs/${encodeURIComponent(f.id)}`} className="py-2.5 flex justify-between gap-4 hover:bg-ink-800/50 px-1">
                  <div>
                    <span className="data-id text-sm text-paper-100">{f.id}</span>
                    <div className="text-xs text-paper-500">{fmtDate(f.registered_at)} · {f.station} ({f.district}) · {fmtMoney(f.amount)}</div>
                  </div>
                  <span className="text-xs text-paper-300">{f.crime_minor_label}</span>
                </Link>
              ))}
            </div>
          </div>
          <div className="case-panel p-5">
            <div className="section-title mb-3">Why these FIRs are linked</div>
            <div className="space-y-3">
              {c.links.map((l) => (
                <div key={`${l.fir_a}-${l.fir_b}-${l.kind}`} className="rounded-lg border border-ink-700 p-3 text-xs">
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
            <div className="section-title mb-3">Shared evidence (what links them)</div>
            {c.key_identifiers.map((k) => (
              <div key={k.value} className="text-xs mb-2">
                <div className="text-paper-500">{IDENTITY_LABELS[k.type] || k.type} · appears in {k.fir_count} FIRs</div>
                <Link href={`/firs?q=${encodeURIComponent(k.value)}`} className="data-id text-paper-100 hover:text-accent">{k.value}</Link>
              </div>
            ))}
            {c.claimed_identities?.length ? (
              <div className="text-xs mt-3 border-t border-ink-700 pt-3">
                <div className="text-paper-500 mb-1">Names the caller claimed to be (a signature, not proof of identity)</div>
                {c.claimed_identities.map((x) => <div key={x.value} className="text-paper-300">· {x.value} ({x.firs} FIRs)</div>)}
              </div>
            ) : null}
          </div>
          <div className="case-panel p-5">
            <div className="section-title mb-3">Why this risk level</div>
            {c.risk_factors.map((f) => <div key={f} className="text-xs text-paper-300 mb-1">· {f}</div>)}
          </div>
          <div className="case-panel stripe-green p-5">
            <div className="section-title mb-3">Suggested next actions</div>
            {c.suggested_actions.map((a) => <div key={a} className="text-xs text-paper-300 mb-1.5">· {a}</div>)}
            <div className="text-[11px] text-paper-500 mt-3">Investigation lead only. Requires human verification.</div>
          </div>
        </div>
      </div>
    </div>
  );
}
