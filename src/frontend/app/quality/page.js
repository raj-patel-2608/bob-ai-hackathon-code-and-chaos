"use client";

import { useEffect, useState } from "react";
import ErrorBox from "../../components/ErrorBox";
import PageHeader from "../../components/PageHeader";
import StatCard from "../../components/StatCard";
import { api, fmtDate, pct } from "../../lib/api";

export default function QualityPage() {
  const [evaluation, setEvaluation] = useState(null);
  const [ready, setReady] = useState(null);
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = () => {
    api.evaluation().then(setEvaluation).catch(() => setEvaluation(null));
    api.ready().then(setReady).catch((e) => setError(e.message));
    api.systemStatus().then(setStatus).catch(() => {});
  };
  useEffect(load, []);

  const run = async (split) => {
    setBusy(true);
    try { await api.runEvaluation(split); load(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  const m = evaluation?.metrics;
  const caps = ready?.checks?.model_service?.capabilities || {};
  return (
    <div>
      <PageHeader eyebrow="Measured, not claimed" title="Model quality"
        description="Accuracy measured against the dataset answer key on the held-out test split (never used for tuning). The answer key is read only by the evaluation, never by the pipeline."
        action={
          <div className="flex gap-2">
            <button disabled={busy} onClick={() => run("test")} className="bg-signal-amber text-ink-950 text-sm font-medium px-4 py-2 disabled:opacity-40">Evaluate test split</button>
            <button disabled={busy} onClick={() => run("dev")} className="border border-ink-600 text-paper-100 text-sm px-4 py-2 disabled:opacity-40">Dev split</button>
          </div>
        } />
      <div className="p-8 space-y-6">
        <ErrorBox error={error} />
        {m && !m.error ? (
          <>
            <div className="text-xs text-paper-500">
              Split: <span className="text-paper-300">{m.split}</span> · {m.firs_evaluated} FIRs · run {fmtDate(evaluation.created_at)} ·
              Laya threshold {evaluation.settings?.decision_min_confidence}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Crime major head" value={pct(m.crime_major_accuracy)} stripe="blue" />
              <StatCard label="Crime minor head" value={pct(m.crime_minor_accuracy)} sub={`macro-F1 ${m.crime_minor_macro_f1}`} stripe="blue" />
              <StatCard label="Evidence extraction" value={`${pct(m.identifiers.precision)} / ${pct(m.identifiers.recall)}`} sub={`precision / recall · roles ${pct(m.identifiers.role_accuracy)}`} stripe="green" />
              <StatCard label="Accused found" value={pct(m.accused.recall)} sub={`${m.accused.false_positive_firs} false`} stripe="green" />
              <StatCard label="Cluster precision" value={pct(m.clusters.pairwise.precision)} sub={`recall ${pct(m.clusters.pairwise.recall)}`} stripe="red" />
              <StatCard label="Planted gangs recovered" value={`${m.clusters.recovered_exactly}/${m.clusters.planted_clusters}`} sub={`${m.clusters.decoys_wrongly_clustered} decoys wrongly clustered`} stripe="red" />
              <StatCard label="MO flags F1" value={m.mo_flags.f1} sub={`P ${m.mo_flags.precision} · R ${m.mo_flags.recall}`} stripe="amber" />
              <StatCard label="Sent to LLM" value={m.escalated_to_llm} sub="Laya confidence below threshold" stripe="amber" />
            </div>
            <div className="case-panel p-5 text-xs text-paper-300">
              <div className="text-sm text-paper-100 font-medium mb-2">Accuracy by decider</div>
              {Object.entries(m.accuracy_by_decider).map(([k, v]) => <div key={k}>· {k}: {pct(v.accuracy)} on {v.firs} FIRs</div>)}
              <div className="text-paper-500 mt-3">{m.note}</div>
            </div>
          </>
        ) : <div className="case-panel p-6 text-sm text-paper-500">No evaluation yet: load src/dataset/firs_main.txt, then click "Evaluate test split".</div>}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="case-panel p-5 text-xs">
            <div className="text-sm text-paper-100 font-medium mb-3">Models (model service)</div>
            {Object.entries(caps).map(([k, c]) => (
              <div key={k} className="mb-2">
                <span className="text-paper-100">{k}</span>{" "}
                {c.available ? (
                  <span className="text-paper-300">· {c.model_id} · <span className={c.device === "cuda" ? "text-signal-green" : "text-signal-amber"}>{c.device}</span>{c.degraded ? " (fell back to CPU)" : ""}</span>
                ) : <span className="text-signal-amber">· unavailable: {c.reason}</span>}
              </div>
            ))}
            {ready?.checks?.model_service?.gpu ? (
              <div className="text-paper-500 mt-2">GPU {ready.checks.model_service.gpu.device}: {ready.checks.model_service.gpu.allocated_mb} MB used, {ready.checks.model_service.gpu.free_mb} MB free</div>
            ) : null}
            <div className="text-paper-500 mt-2">Mode: {ready?.mode}</div>
          </div>
          <div className="case-panel p-5 text-xs">
            <div className="text-sm text-paper-100 font-medium mb-3">Pipeline & budget</div>
            {status ? (
              <>
                {Object.entries(status.stages).map(([s, v]) => (
                  <div key={s} className="text-paper-300">· {s}: {Object.entries(v).map(([k, n]) => `${k.toLowerCase()} ${n}`).join(", ")}</div>
                ))}
                <div className="text-paper-300 mt-2">LLM tokens this month: {status.llm_tokens_this_month.toLocaleString()} / {status.llm_monthly_budget.toLocaleString()}</div>
                <div className="text-paper-500 mt-2">Laya acceptance threshold {status.settings.decision_min_confidence} · pattern-link similarity {status.settings.soft_link_min_similarity}</div>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
