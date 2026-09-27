"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import ErrorBox from "../../components/ErrorBox";
import PageHeader from "../../components/PageHeader";
import { api, fmtDate } from "../../lib/api";

const PLACEHOLDER = `Paste one or more FIRs. Separate FIRs with a line containing only ---

FIR No.: 0412/2026
District: Ahmedabad City    Police Station: Navrangpura
Date & Time of FIR: 14/08/2026 16:40
Complainant / Informant: ..., age 67, retired bank clerk
Accused: Unknown caller
First Information contents:
I got a call from 98765 43210 saying he is from SBI card department ...`;

const STAGES = ["extract", "decide", "enrich", "embed"];
const STAGE_HELP = {
  extract: "rules: evidence, amounts, accused",
  decide: "Laya: crime type + methods",
  enrich: "Granite LLM for low confidence",
  embed: "Granite Embedding of the story",
};

function StageBar({ counts, total }) {
  const done = (counts?.SUCCEEDED || 0) + (counts?.SKIPPED || 0);
  const failed = counts?.FAILED || 0;
  const w = (n) => `${total ? (n / total) * 100 : 0}%`;
  return (
    <div className="h-1.5 bg-ink-700 w-full flex">
      <div className="h-1.5 bg-signal-green" style={{ width: w(done) }} />
      <div className="h-1.5 bg-signal-red" style={{ width: w(failed) }} />
    </div>
  );
}

export default function UploadPage() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [active, setActive] = useState(null);      // batch being watched
  const [history, setHistory] = useState([]);
  const fileRef = useRef(null);

  const loadHistory = useCallback(() => api.batches().then(setHistory).catch(() => {}), []);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  useEffect(() => {
    if (!active || ["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"].includes(active.status)) return;
    const t = setTimeout(() => api.batch(active.id).then(setActive).catch((e) => setError(e.message)), 1500);
    return () => clearTimeout(t);
  }, [active]);

  useEffect(() => {
    if (active && active.status?.startsWith("COMPLETED")) loadHistory();
  }, [active, loadHistory]);

  const start = async (promise) => {
    setBusy(true);
    setError(null);
    try {
      const accepted = await promise;
      setActive(await api.batch(accepted.batch_id));
      setText("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Ingestion"
        title="Ingest FIR batch"
        description="The upload returns immediately. FIRs are processed in the background in micro-batches: evidence extraction, crime classification (Laya), a second opinion from the Granite LLM when confidence is below 40%, and narrative embeddings. Links and clusters are rebuilt when the batch finishes."
      />
      <div className="p-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="case-panel p-5 flex items-center justify-between gap-4">
            <div>
              <div className="text-sm text-paper-100 font-medium">Upload a file</div>
              <div className="text-[11px] text-paper-500 mt-0.5">.txt (FIRs separated by ---), .jsonl, .json or .csv with a raw_text column · max 1000 FIRs</div>
            </div>
            <label className="border border-ink-600 text-paper-100 text-sm px-4 py-2 cursor-pointer whitespace-nowrap">
              {busy ? "Uploading…" : "Choose file"}
              <input ref={fileRef} type="file" accept=".txt,.csv,.json,.jsonl" className="hidden" disabled={busy}
                onChange={(e) => e.target.files?.[0] && start(api.uploadFile(e.target.files[0]))} />
            </label>
          </div>

          <div className="case-panel p-5">
            <div className="text-sm text-paper-100 font-medium mb-3">Or paste FIR text</div>
            <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={PLACEHOLDER} rows={14}
              className="w-full bg-ink-950 border border-ink-600 p-3 text-xs data-id text-paper-100 focus:outline-none focus:border-signal-amber resize-y" />
            <div className="flex justify-end mt-3">
              <button onClick={() => start(api.uploadText(text))} disabled={busy || text.trim().length < 20}
                className="bg-signal-amber text-ink-950 text-sm font-medium px-4 py-2 disabled:opacity-40">
                Run pipeline
              </button>
            </div>
          </div>
          <ErrorBox error={error} />
        </div>

        <div className="space-y-4">
          <div className="case-panel p-5">
            <div className="text-sm text-paper-100 font-medium mb-3">Batch progress</div>
            {!active ? (
              <div className="text-sm text-paper-500">Upload a batch to follow its progress here.</div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs">
                  <span className="data-id text-paper-300">{active.filename}</span>
                  <span className={active.status.startsWith("COMPLETED") ? "text-signal-green" : "text-signal-amber"}>{active.status}</span>
                </div>
                <div className="text-xs text-paper-500">
                  {active.created} new FIRs · {active.duplicates} duplicates skipped · {active.firs_done}/{active.created} done
                </div>
                {STAGES.map((s) => (
                  <div key={s}>
                    <div className="flex justify-between text-[11px] mb-1">
                      <span className="text-paper-300">{s} <span className="text-paper-500">· {STAGE_HELP[s]}</span></span>
                      <span className="data-id text-paper-500">
                        {Object.entries(active.stages?.[s] || {}).map(([k, v]) => `${k.toLowerCase()} ${v}`).join(" · ")}
                      </span>
                    </div>
                    <StageBar counts={active.stages?.[s]} total={active.created} />
                  </div>
                ))}
                {active.fir_status?.NEEDS_REVIEW ? (
                  <div className="text-xs text-signal-amber">
                    {active.fir_status.NEEDS_REVIEW} FIR(s) need officer review ·{" "}
                    <Link href="/firs?needs_review=true" className="underline">open review queue</Link>
                  </div>
                ) : null}
                {active.recent_errors?.length ? (
                  <div className="text-[11px] text-signal-red">
                    {active.recent_errors.length} stage error(s) recorded
                    <button onClick={() => api.retryBatch(active.id).then(() => api.batch(active.id)).then(setActive)}
                      className="ml-2 underline">retry failed</button>
                  </div>
                ) : null}
                {active.status.startsWith("COMPLETED") ? (
                  <Link href="/offenders" className="inline-block text-xs text-signal-amber hover:underline">
                    View flagged repeat offenders ›
                  </Link>
                ) : null}
              </div>
            )}
          </div>

          <div className="case-panel p-5">
            <div className="text-sm text-paper-100 font-medium mb-3">Recent batches</div>
            <div className="divide-y divide-ink-700">
              {history.map((b) => (
                <button key={b.id} onClick={() => api.batch(b.id).then(setActive)}
                  className="w-full text-left py-2 flex justify-between text-xs hover:bg-ink-800/50 px-1">
                  <span className="data-id text-paper-300">{b.filename}</span>
                  <span className="text-paper-500">{b.created} FIRs · {b.status.toLowerCase()} · {fmtDate(b.created_at)}</span>
                </button>
              ))}
              {history.length === 0 ? <div className="text-sm text-paper-500">No batches yet.</div> : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
