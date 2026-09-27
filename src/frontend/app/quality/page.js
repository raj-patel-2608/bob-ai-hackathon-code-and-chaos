"use client";

import { useEffect, useState } from "react";
import ErrorBox from "../../components/ErrorBox";
import InfoTip from "../../components/InfoTip";
import PageHeader from "../../components/PageHeader";
import { api, fmtDate, pct } from "../../lib/api";
import { GLOSSARY } from "../../lib/glossary";

const DECIDERS = {
  laya: ["Laya (local AI)", "decided on its own because it was at least 40% sure", "bg-signal-blue"],
  llm: ["IBM Granite on watsonx.ai", "second opinion because Laya was less than 40% sure", "bg-signal-amber"],
  officer: ["Officer", "corrected or confirmed by a person", "bg-signal-green"],
  rules: ["Keyword rules", "AI service was offline (fallback)", "bg-signal-red"],
};
const PURPOSE = {
  enrich: "Second opinion on unsure FIRs",
  "enrich-repair": "Second opinion: asked again after an invalid answer",
  station_report: "Writing station briefs",
};

function Metric({ label, value, help, good = true }) {
  return (
    <div className={`case-panel ${good ? "stripe-green" : "stripe-amber"} p-4`}>
      <div className="text-[11px] uppercase tracking-wide text-paper-500">{label}</div>
      <div className="font-mono text-[26px] font-medium text-paper-100 mt-1">{value}</div>
      <div className="text-xs text-paper-500 mt-1 leading-relaxed">{help}</div>
    </div>
  );
}

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
  const run = async () => {
    setBusy(true);
    try { await api.runEvaluation("test"); load(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  const m = evaluation?.metrics;
  const caps = ready?.checks?.model_service?.capabilities || {};
  const decided = status?.decided_by || {};
  const totalDecided = Object.values(decided).reduce((a, b) => a + b, 0);
  const llmCalls = (status?.llm_usage || []).reduce((a, u) => a + u.calls, 0);

  return (
    <div>
      <PageHeader title="AI accuracy"
        description="Which AI did the work, how accurate it is, and which models are running. Accuracy is measured against a hidden answer sheet that comes with the test data." />
      <div className="px-8 py-5 space-y-8">
        <ErrorBox error={error} />

        <section className="space-y-3">
          <div className="flex items-center gap-2 section-title">1. Who decided the crime type <InfoTip text={GLOSSARY.decidedBy} /></div>
          <div className="case-panel p-5 space-y-3">
            {totalDecided === 0 ? <div className="text-sm text-paper-500">No FIRs analysed yet.</div> : Object.entries(decided).map(([k, n]) => (
              <div key={k}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-paper-100">{DECIDERS[k]?.[0] || k} <span className="text-paper-500">· {DECIDERS[k]?.[1]}</span></span>
                  <span className="data-id text-paper-300">{n} FIRs ({Math.round((n / totalDecided) * 100)}%)</span>
                </div>
                <div className="h-2 rounded-full bg-ink-800 overflow-hidden"><div className={`h-2 ${DECIDERS[k]?.[2] || "bg-paper-500"}`} style={{ width: `${(n / totalDecided) * 100}%` }} /></div>
              </div>
            ))}
          </div>
          <div className="case-panel p-5">
            <div className="section-title mb-1">IBM watsonx.ai usage (Granite LLM)</div>
            <div className="text-xs text-paper-500 mb-3">watsonx.ai is called for exactly two things: a second opinion on unsure FIRs, and writing station briefs.</div>
            {(status?.llm_usage || []).length === 0 ? <div className="text-sm text-paper-500">Not used yet.</div> : (
              <table className="text-xs w-full max-w-2xl">
                <thead><tr className="text-paper-500 text-left"><th className="font-normal pb-1">Use</th><th className="font-normal pb-1">Calls</th><th className="font-normal pb-1">Tokens</th></tr></thead>
                <tbody>
                  {status.llm_usage.map((u) => (
                    <tr key={u.purpose} className="text-paper-300"><td className="py-0.5">{PURPOSE[u.purpose] || u.purpose}</td><td>{u.calls}</td><td>{u.tokens.toLocaleString("en-IN")}</td></tr>
                  ))}
                  <tr className="text-paper-100 border-t border-ink-700"><td className="pt-1">Total</td><td className="pt-1">{llmCalls}</td><td className="pt-1">{status.llm_tokens_this_month.toLocaleString("en-IN")} of {status.llm_monthly_budget.toLocaleString("en-IN")} monthly budget</td></tr>
                </tbody>
              </table>
            )}
          </div>
        </section>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="section-title">2. How accurate it is</div>
            <button disabled={busy} onClick={run} className="btn btn-primary">{busy ? "Measuring…" : "Measure again"}</button>
          </div>
          {m && !m.error ? (
            <>
              <div className="text-xs text-paper-500">
                Measured on {m.firs_evaluated} {m.split === "test" ? "test FIRs that were never used to tune the system" : `FIRs (${m.split} set)`} · {fmtDate(evaluation.created_at)}.
                FIRs uploaded without an answer sheet (e.g. your own) are processed normally but cannot be scored.
                The test data hides {m.clusters.planted_clusters} gangs (groups of FIRs by the same offenders) and look-alike decoy cases.
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                <Metric label="Crime category correct" value={pct(m.crime_major_accuracy)} help="Broad category (cyber, property, body, economic) matches the answer sheet." />
                <Metric label="Exact crime type correct" value={pct(m.crime_minor_accuracy)} help="The specific type (e.g. 'OTP/KYC bank fraud', 'Chain snatching') matches. 17 possible types." />
                <Metric label="Evidence found" value={pct(m.identifiers.recall)} help={`Phones, accounts, UPI IDs, IMEIs, vehicles and handles found in the text. ${pct(m.identifiers.precision)} of what was found is real (no false evidence).`} />
                <Metric label="Accused names found" value={pct(m.accused.recall)} help={`Named accused / aliases picked up from the FIR. ${m.accused.false_positive_firs} FIR(s) got a wrong name.`} />
                <Metric label="Groups are correct" value={pct(m.clusters.pairwise.precision)} help="When two FIRs are put in the same repeat-offender group, how often they truly belong together (no wrong links)." />
                <Metric label="Hidden gangs found" value={`${m.clusters.recovered_exactly} of ${m.clusters.planted_clusters}`} help="Gangs found completely, with exactly the right FIRs." good={m.clusters.recovered_exactly === m.clusters.planted_clusters} />
                <Metric label="Look-alike cases wrongly grouped" value={m.clusters.decoys_wrongly_clustered} help="Decoys have the same story as a gang but no shared evidence. They must NOT be grouped." good={m.clusters.decoys_wrongly_clustered === 0} />
                <Metric label="Method (MO) quality" value={m.mo_flags.f1} help="Score from 0 to 1 for detecting how the crime was done. The weakest part of the system." good={false} />
              </div>
              <div className="case-panel p-4 text-xs text-paper-300">
                Crime type accuracy by who decided: {Object.entries(m.accuracy_by_decider).map(([k, v]) => `${DECIDERS[k]?.[0] || k}: ${pct(v.accuracy)} of ${v.firs} FIRs`).join(" · ")}
              </div>
            </>
          ) : <div className="case-panel p-6 text-sm text-paper-500">Not measured yet. Load <span className="data-id">src/dataset/firs_main.txt</span> (it has the answer sheet), then click "Measure again".</div>}
        </section>

        <section className="space-y-3">
          <div className="section-title">3. Models in use</div>
          <div className="case-panel p-5 text-xs space-y-2">
            {[["decision", "Laya: reads each FIR and decides crime type, method and victim gender"],
              ["embedding", "IBM Granite Embedding: turns each FIR story into numbers to find similar stories"],
              ["generator", "IBM Granite LLM (watsonx.ai): second opinion on unsure FIRs + writes station briefs"]].map(([k, what]) => {
              const c = caps[k] || {};
              return (
                <div key={k} className="flex flex-wrap justify-between gap-2 border-b border-ink-700 pb-2">
                  <span className="text-paper-100">{what}</span>
                  {c.available ? (
                    <span className="text-paper-300"><span className="data-id">{c.model_id}</span> · {c.device === "cuda" ? <span className="text-signal-green">on this computer's GPU</span> : c.device === "remote" ? <span className="text-accent">IBM Cloud</span> : <span className="text-signal-amber">on CPU</span>}{c.degraded ? " (fell back from GPU)" : ""}</span>
                  ) : <span className="text-signal-amber">not available: {c.reason || "model service offline"}</span>}
                </div>
              );
            })}
            {ready?.checks?.model_service?.gpu ? <div className="text-paper-500">GPU: {ready.checks.model_service.gpu.device}, {ready.checks.model_service.gpu.allocated_mb} MB used by the models</div> : null}
          </div>
        </section>
      </div>
    </div>
  );
}
