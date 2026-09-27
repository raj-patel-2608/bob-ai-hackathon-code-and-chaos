"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import ConfirmDialog from "../../components/ConfirmDialog";
import ErrorBox from "../../components/ErrorBox";
import PageHeader from "../../components/PageHeader";
import { api, fmtDate } from "../../lib/api";

const PLACEHOLDER = `Paste one or more FIRs. Put a line containing only --- between FIRs.

FIR No.: 0412/2026
District: Ahmedabad City    Police Station: Navrangpura
Date & Time of FIR: 14/08/2026 16:40
Complainant / Informant: ..., age 67, retired bank clerk
Accused: Unknown caller
First Information contents:
I got a call from 98765 43210 saying he is from SBI card department ...`;

const STAGES = [
  ["extract", "Find evidence", "phones, accounts, UPI IDs, vehicles, amounts, accused (rules)"],
  ["decide", "Classify crime", "crime category, type and method (Laya AI, local)"],
  ["enrich", "Second opinion", "only for unsure cases (IBM Granite on watsonx.ai)"],
  ["embed", "Story fingerprint", "for finding similar stories (IBM Granite Embedding)"],
];
const FINISHED = ["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"];

function StageBar({ counts, total }) {
  const done = (counts?.SUCCEEDED || 0) + (counts?.SKIPPED || 0);
  const failed = counts?.FAILED || 0;
  const w = (n) => `${total ? (n / total) * 100 : 0}%`;
  return (
    <div className="h-1.5 bg-ink-700 w-full flex">
      <div className="h-1.5 bg-signal-green transition-all duration-500" style={{ width: w(done) }} />
      <div className="h-1.5 bg-signal-red" style={{ width: w(failed) }} />
    </div>
  );
}

export default function UploadPage() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [active, setActive] = useState(null);
  const [history, setHistory] = useState([]);
  const [toDelete, setToDelete] = useState(null);      // batch object, or "ALL"
  const fileRef = useRef(null);

  const loadHistory = useCallback(() => api.batches().then(setHistory).catch(() => {}), []);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  useEffect(() => {
    if (!active || FINISHED.includes(active.status)) return;
    const t = setTimeout(() => api.batch(active.id).then(setActive).catch((e) => setError(e.message)), 1500);
    return () => clearTimeout(t);
  }, [active]);
  useEffect(() => { if (active && FINISHED.includes(active.status)) loadHistory(); }, [active, loadHistory]);

  const start = async (promise) => {
    setBusy(true); setError(null); setNotice(null);
    try {
      const accepted = await promise;
      if (accepted.created === 0) setNotice(`All ${accepted.duplicates} FIR(s) in this upload were already in the system, so nothing new was added.`);
      setActive(await api.batch(accepted.batch_id));
      setText("");
      loadHistory();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const confirmDelete = async () => {
    try {
      if (toDelete === "ALL") {
        await api.resetAll();
        setNotice("All data deleted. The system is empty.");
      } else {
        const r = await api.deleteBatch(toDelete.id);
        setNotice(`Deleted ${r.firs_deleted} FIR(s) from "${toDelete.filename}". Repeat-offender groups were recalculated (${r.clusters_now} now).`);
      }
      if (active && (toDelete === "ALL" || active.id === toDelete.id)) setActive(null);
      await loadHistory();
    } catch (e) {
      setError(e.message);
    } finally {
      setToDelete(null);
    }
  };

  const processing = active && !FINISHED.includes(active.status);
  return (
    <div>
      <PageHeader title="Add FIRs"
        description="Upload a file or paste FIR text. The upload returns immediately; each FIR then goes through the steps shown on the right in the background." />
      <div className="p-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="case-panel p-5">
            <div className="text-sm text-paper-100 font-medium">Upload a file</div>
            <div className="text-[11px] text-paper-500 mt-0.5 mb-3">.txt (FIRs separated by a line with ---), .jsonl, .json or .csv with a raw_text column · up to 1000 FIRs / 10 MB</div>
            <label className={`inline-block border border-signal-amber text-signal-amber text-sm px-4 py-2 ${busy ? "opacity-40" : "cursor-pointer hover:bg-signal-amber/10"}`}>
              {busy ? "Uploading…" : "Choose file"}
              <input ref={fileRef} type="file" accept=".txt,.csv,.json,.jsonl" className="hidden" disabled={busy}
                onChange={(e) => e.target.files?.[0] && start(api.uploadFile(e.target.files[0]))} />
            </label>
            <div className="text-[11px] text-paper-500 mt-3">
              Sample files in <span className="data-id">src/dataset/</span>: <span className="data-id">firs_main.txt</span> (400 FIRs with hidden gangs),{" "}
              <span className="data-id">demo_live_batch.txt</span> (6 new FIRs), <span className="data-id">firs_unrelated.txt</span> (60 standalone FIRs)
            </div>
          </div>

          <div className="case-panel p-5">
            <div className="text-sm text-paper-100 font-medium mb-3">Or paste FIR text</div>
            <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={PLACEHOLDER} rows={12}
              className="w-full bg-ink-950 border border-ink-600 p-3 text-xs data-id text-paper-100 focus:outline-none focus:border-signal-amber resize-y" />
            <div className="flex justify-between items-center mt-3">
              <span className="text-[11px] text-paper-500">{text.trim() ? `${text.split(/\n\s*-{3,}\s*\n/).filter((t) => t.trim()).length} FIR(s) detected` : ""}</span>
              <button onClick={() => start(api.uploadText(text))} disabled={busy || text.trim().length < 20}
                className="bg-signal-amber text-ink-950 text-sm font-medium px-4 py-2 disabled:opacity-40">Analyse</button>
            </div>
          </div>
          <ErrorBox error={error} />
          {notice ? <div className="case-panel stripe-green p-4 text-sm text-paper-300">{notice}</div> : null}
        </div>

        <div className="space-y-4">
          <div className="case-panel p-5">
            <div className="text-sm text-paper-100 font-medium mb-3">Progress</div>
            {!active ? <div className="text-sm text-paper-500">Upload FIRs to follow their progress here.</div> : (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs">
                  <span className="data-id text-paper-300">{active.filename}</span>
                  <span className={FINISHED.includes(active.status) ? "text-signal-green" : "text-signal-amber"}>
                    {processing ? "working…" : active.status === "COMPLETED" ? "done" : active.status.toLowerCase().replaceAll("_", " ")}
                  </span>
                </div>
                <div className="text-xs text-paper-500">
                  {active.created} new FIR(s){active.duplicates ? ` · ${active.duplicates} already in the system (skipped)` : ""} · {active.firs_done} of {active.created} finished
                </div>
                {STAGES.map(([key, label, help]) => (
                  <div key={key}>
                    <div className="flex justify-between text-[11px] mb-1">
                      <span className="text-paper-300">{label} <span className="text-paper-500">· {help}</span></span>
                      <span className="data-id text-paper-500">
                        {key === "enrich" && active.stages?.[key]?.SKIPPED ? `${active.stages[key].SKIPPED} not needed` : ""}
                      </span>
                    </div>
                    <StageBar counts={active.stages?.[key]} total={active.created} />
                  </div>
                ))}
                {active.fir_status?.NEEDS_REVIEW ? (
                  <div className="text-xs text-signal-amber">{active.fir_status.NEEDS_REVIEW} FIR(s) need an officer check · <Link href="/firs?needs_review=true" className="underline">open</Link></div>
                ) : null}
                {active.recent_errors?.length ? (
                  <div className="text-[11px] text-signal-red">{active.recent_errors.length} step(s) failed
                    <button onClick={() => api.retryBatch(active.id).then(() => api.batch(active.id)).then(setActive)} className="ml-2 underline">retry</button>
                  </div>
                ) : null}
                {active.status === "COMPLETED" || active.status === "COMPLETED_WITH_ERRORS" ? (
                  <div className="flex gap-4 text-xs">
                    <Link href="/offenders" className="text-signal-amber hover:underline">See repeat-offender groups ›</Link>
                    <Link href="/firs" className="text-signal-amber hover:underline">See case files ›</Link>
                  </div>
                ) : null}
              </div>
            )}
          </div>

          <div className="case-panel p-5">
            <div className="flex justify-between items-center mb-3">
              <div className="text-sm text-paper-100 font-medium">Uploaded batches</div>
              {history.length ? <button onClick={() => setToDelete("ALL")} className="text-[11px] text-signal-red hover:underline">Delete all data…</button> : null}
            </div>
            <div className="divide-y divide-ink-700">
              {history.map((b) => (
                <div key={b.id} className="py-2.5 flex items-center justify-between gap-3 text-xs">
                  <button onClick={() => api.batch(b.id).then(setActive)} className="text-left min-w-0 hover:text-signal-amber">
                    <div className="data-id text-paper-300 truncate">{b.filename}</div>
                    <div className="text-paper-500">{b.created} FIR(s) · {b.status.toLowerCase().replaceAll("_", " ")} · {fmtDate(b.created_at)}</div>
                  </button>
                  <button disabled={!FINISHED.includes(b.status)} onClick={() => setToDelete(b)}
                    title={FINISHED.includes(b.status) ? "Delete this batch" : "Wait until processing finishes"}
                    className="border border-signal-red/60 text-signal-red px-2.5 py-1 hover:bg-signal-red/10 disabled:opacity-30 shrink-0">Delete</button>
                </div>
              ))}
              {history.length === 0 ? <div className="text-sm text-paper-500">Nothing uploaded yet.</div> : null}
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(toDelete)}
        title={toDelete === "ALL" ? "Delete ALL data?" : "Delete this batch?"}
        message={toDelete === "ALL"
          ? "Every FIR, its analysis, evidence, links, repeat-offender groups, station briefs and uploaded files will be permanently deleted."
          : toDelete ? `"${toDelete.filename}" and its ${toDelete.created} FIR(s) will be permanently deleted, together with their analysis, evidence and links. Repeat-offender groups are recalculated from the remaining FIRs.` : ""}
        confirmLabel={toDelete === "ALL" ? "Delete everything" : "Delete batch"}
        confirmWord={toDelete === "ALL" ? "DELETE" : undefined}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)} />
    </div>
  );
}
