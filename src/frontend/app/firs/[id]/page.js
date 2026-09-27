"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { DecidedBy, EntityChip, LinkBadge, StatusBadge } from "../../../components/Badges";
import ErrorBox from "../../../components/ErrorBox";
import PageHeader from "../../../components/PageHeader";
import { api, fmtDate, fmtMoney, IDENTITY_LABELS, pct } from "../../../lib/api";
import InfoTip from "../../../components/InfoTip";
import { GLOSSARY } from "../../../lib/glossary";

const HIGHLIGHT = {
  phone: "bg-emerald-500/25", bank_account: "bg-amber-500/25", upi_id: "bg-amber-500/25", imei: "bg-violet-500/25",
  vehicle: "bg-orange-500/25", online_handle: "bg-cyan-500/25",
};

function HighlightedNarrative({ narrative, offset, entities }) {
  // entity spans are offsets in the raw FIR text; the narrative starts at `offset`
  const parts = useMemo(() => {
    const spans = entities
      .filter((e) => e.start !== null && e.end !== null && e.role !== "complainant" && HIGHLIGHT[e.type])
      .map((e) => ({ ...e, s: e.start - offset, t: e.end - offset }))
      .filter((e) => e.s >= 0 && e.t <= narrative.length)
      .sort((a, b) => a.s - b.s);
    const out = [];
    let pos = 0;
    spans.forEach((e, i) => {
      if (e.s < pos) return;
      out.push(<span key={`t${i}`}>{narrative.slice(pos, e.s)}</span>);
      out.push(
        <mark key={`m${i}`} title={`${IDENTITY_LABELS[e.type]} → ${e.value}`} className={`${HIGHLIGHT[e.type]} text-paper-100 px-0.5`}>
          {narrative.slice(e.s, e.t)}
        </mark>
      );
      pos = e.t;
    });
    out.push(<span key="end">{narrative.slice(pos)}</span>);
    return out;
  }, [narrative, offset, entities]);
  return <p className="text-sm text-paper-300 leading-relaxed whitespace-pre-wrap">{parts}</p>;
}

function ReviewBox({ fir, onDone }) {
  const [minor, setMinor] = useState(fir.crime_minor || "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const options = [...new Set([fir.crime_minor, ...(fir.iif2_draft?.alternatives || []).map((a) => a.id)])];
  const submit = async (decision) => {
    setBusy(true);
    try {
      await api.review(fir.id, { decision, crime_minor: decision === "correct" ? minor : undefined, note });
      onDone();
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="case-panel stripe-amber p-5 space-y-3">
      <div className="section-title">Officer check needed</div>
      <div className="text-xs text-paper-500">{(fir.iif2_draft?.review_reasons || []).join(" · ") || "Confirm or correct the automatic classification."}</div>
      <input value={minor} onChange={(e) => setMinor(e.target.value)} placeholder="crime minor id, e.g. cyber.digital_arrest"
        className="input w-full text-xs data-id" list="minor-options" />
      <datalist id="minor-options">{options.filter(Boolean).map((o) => <option key={o} value={o} />)}</datalist>
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="note (optional)"
        className="input w-full text-xs" />
      <div className="flex gap-2">
        <button disabled={busy} onClick={() => submit("confirm")} className="btn btn-primary btn-sm">Confirm</button>
        <button disabled={busy || !minor} onClick={() => submit("correct")} className="btn btn-secondary btn-sm">Correct to this type</button>
      </div>
    </div>
  );
}

export default function FirDetailPage() {
  const { id } = useParams();
  const firId = decodeURIComponent(id);
  const [fir, setFir] = useState(null);
  const [related, setRelated] = useState([]);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    Promise.all([api.fir(firId), api.related(firId)])
      .then(([f, r]) => { setFir(f); setRelated(r.related); })
      .catch((e) => setError(e.message));
  }, [firId]);
  useEffect(load, [load]);

  if (error) return <div className="p-8"><ErrorBox error={error} /></div>;
  if (!fir) return <div className="px-8 py-5 text-sm text-paper-500">Loading case file…</div>;
  const d = fir.iif2_draft || {};
  const evidence = fir.entities.filter((e) => e.role !== "complainant" && !["accused_name", "accused_alias", "claimed_identity"].includes(e.type));

  return (
    <div>
      <PageHeader eyebrow={`${fir.station || "Unknown station"} · ${fir.district || ""}`} title={fir.id}
        description={d.summary}
        action={
          <div className="flex flex-col items-end gap-2">
            <StatusBadge status={fir.status} />
            {fir.cluster_id ? (
              <Link href={`/offenders/${fir.cluster_id}`} className="btn btn-danger-outline btn-sm">
                Part of repeat-offender group {fir.cluster_id}
              </Link>
            ) : null}
            <Link href={`/graph?fir=${encodeURIComponent(fir.id)}`} className="btn btn-secondary btn-sm">Show links on graph</Link>
          </div>
        } />
      <div className="px-8 py-5 grid grid-cols-1 xl:grid-cols-5 gap-6">
        <div className="xl:col-span-3 space-y-6">
          <div className="case-panel stripe-blue p-5">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-paper-500 mb-3">
              Crime classification (drafted by AI) <InfoTip text={GLOSSARY.classification} />
            </div>
            <div className="grid grid-cols-2 gap-4 mb-2">
              <div>
                <div className="flex items-center gap-1.5 text-[11px] text-paper-500">Crime category <InfoTip text={GLOSSARY.crimeCategory} /></div>
                <div className="text-paper-100">{d.major_head || "—"}</div>
              </div>
              <div>
                <div className="flex items-center gap-1.5 text-[11px] text-paper-500">Crime type <InfoTip text={GLOSSARY.crimeType} /></div>
                <div className="text-paper-100 font-medium">{d.minor_head || "Unclassified"}</div>
              </div>
            </div>
            <div className="mt-2"><DecidedBy by={d.decided_by} confidence={d.confidence} />
              {d.escalated_to_llm && d.decided_by !== "llm" ? <span className="text-[11px] text-signal-amber ml-2">below 40% confidence: waiting for Granite LLM second opinion</span> : null}</div>
            {d.alternatives?.length ? (
              <div className="text-[11px] text-paper-500 mt-2">
                Other possibilities Laya considered: {d.alternatives.map((a) => `${a.minor_head} ${pct(a.probability)}`).join(" · ")}
              </div>
            ) : null}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4 text-xs">
              <div>
                <div className="flex items-center gap-1.5 text-paper-500 mb-1">How it was done (method) <InfoTip text={GLOSSARY.method} /></div>
                {d.methods?.length ? d.methods.map((m) => (
                  <div key={m.flag} className="text-paper-300">· {m.label} <span className="text-paper-500">{d.decided_by === "llm" ? "(Granite)" : pct(m.probability)}</span></div>
                )) : <div className="text-paper-500">none detected</div>}
              </div>
              <div>
                <div className="text-paper-500 mb-1">Victim profile</div>
                <div className="text-paper-300">Age: {d.victim?.age ?? "—"} ({d.victim?.age_group?.replace("_", "–") || "—"})</div>
                <div className="text-paper-300">Gender: {d.victim?.gender || "—"}</div>
                <div className="text-paper-300">Occupation: {d.victim?.occupation || "—"}</div>
                <div className="text-paper-300">Loss: {fmtMoney(d.loss)}</div>
              </div>
              <div>
                <div className="text-paper-500 mb-1">Accused</div>
                {d.accused?.length ? d.accused.map((a, i) => (
                  <div key={i} className="text-paper-300">
                    · {a.as_written}{" "}
                    <span className="text-paper-500">{a.source === "claimed" ? "(identity claimed by offender)" : `(${a.source})`}</span>
                  </div>
                )) : <div className="text-paper-500">unknown</div>}
              </div>
            </div>
          </div>

          <div className="case-panel p-5">
            <div className="flex justify-between items-baseline mb-3">
              <div className="section-title">FIR text (what the complainant said)</div>
              <div className="text-[11px] text-paper-500">highlighted = evidence found automatically</div>
            </div>
            <HighlightedNarrative narrative={fir.narrative} offset={fir.narrative_offset} entities={fir.entities} />
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-paper-500 mt-4 border-t border-ink-700 pt-3">
              <div>FIR no: <span className="text-paper-300">{fir.header.fir_no || "—"}</span></div>
              <div>Registered: <span className="text-paper-300">{fmtDate(fir.registered_at)}</span></div>
              <div>Sections: <span className="text-paper-300">{fir.header.acts_sections || "—"}</span></div>
              <div>Place: <span className="text-paper-300">{fir.header.place || "—"}</span></div>
              <div className="col-span-2">Complainant: <span className="text-paper-300">{fir.header.complainant || "—"}</span></div>
            </div>
          </div>

          <div className="case-panel p-5">
            <div className="section-title mb-3">Evidence found in this FIR</div>
            <div className="flex flex-wrap gap-2">
              {evidence.length ? evidence.map((e, i) => <EntityChip key={i} type={e.type} value={e.value} role={e.role} />)
                : <span className="text-sm text-paper-500">No hard identifiers in this FIR.</span>}
            </div>
          </div>

          <div className="case-panel p-5">
            <div className="section-title mb-3">How this FIR was processed</div>
            <div className="grid grid-cols-4 gap-2 text-[11px]">
              {fir.pipeline.map((p) => (
                <div key={p.stage} className="rounded-lg border border-ink-700 p-2">
                  <div className="text-paper-300">{p.stage}</div>
                  <div className={p.status === "SUCCEEDED" ? "text-signal-green" : p.status === "FAILED" ? "text-signal-red" : "text-paper-500"}>{p.status.toLowerCase()}</div>
                  <div className="text-paper-500 truncate" title={p.model_id || ""}>{p.provider || ""}{p.device ? ` · ${p.device}` : ""}</div>
                  {p.note ? <div className="text-paper-500 truncate" title={p.note}>{p.note}</div> : null}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="xl:col-span-2 space-y-6">
          {fir.needs_review ? <ReviewBox fir={fir} onDone={load} /> : null}
          <div className="case-panel p-5">
            <div className="section-title mb-1">Connected FIRs</div>
            <div className="text-xs text-paper-500 mb-4">"Evidence" = same phone, account, UPI ID, vehicle or accused. "Pattern only" = similar story, no shared evidence (weak).</div>
            {related.length === 0 ? <div className="text-sm text-paper-500">No linked FIRs.</div> : (
              <div className="space-y-3">
                {related.map((r) => (
                  <div key={`${r.id}-${r.link_kind}`} className="rounded-lg border border-ink-700 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <Link href={`/firs/${encodeURIComponent(r.id)}`} className="data-id text-sm text-paper-100 hover:text-accent">{r.id}</Link>
                      <LinkBadge kind={r.link_kind} score={r.score} />
                    </div>
                    <div className="text-xs text-paper-500 mt-1">{r.crime_minor_label} · {r.station} ({r.district}) · {fmtDate(r.registered_at)}</div>
                    <ul className="mt-2 space-y-1 text-xs text-paper-300">
                      {r.reasons.map((x, i) => <li key={i}>· {x}</li>)}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
