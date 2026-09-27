"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { StatusBadge } from "../../components/Badges";
import ConfirmDialog from "../../components/ConfirmDialog";
import ErrorBox from "../../components/ErrorBox";
import PageHeader from "../../components/PageHeader";
import { api, fmtBytes, fmtDateTime, fmtDuration } from "../../lib/api";

const MAX_MB = 10;
const MAX_FIRS = 1000;
const ACCEPT = [".txt", ".jsonl", ".json", ".csv"];
const ACTIVE = ["RECEIVED", "PROCESSING", "LINKING", "CANCELLING"];

const PLACEHOLDER = `FIR No.: 0412/2026
District: Ahmedabad City    Police Station: Navrangpura
Date & Time of FIR: 14/08/2026 16:40
Complainant / Informant: ..., age 67, retired bank clerk
Accused: Unknown caller
First Information contents:
I got a call from 98765 43210 saying he is from SBI card department ...
---
(next FIR)`;

const STEPS = [
  ["extract", "Evidence extraction", "Phones, accounts, UPI IDs, vehicles, amounts, accused"],
  ["decide", "Crime classification", "Laya model on this computer"],
  ["enrich", "Second opinion", "IBM Granite on watsonx.ai, only for uncertain FIRs"],
  ["embed", "Similarity fingerprint", "IBM Granite Embedding"],
];

// ---------------------------------------------------------------- helpers

function countRecords(name, text) {
  const ext = name.toLowerCase().slice(name.lastIndexOf("."));
  if (ext === ".txt") return text.split(/\n\s*-{3,}\s*\n/).filter((t) => t.trim()).length;
  if (ext === ".jsonl") return text.split("\n").filter((l) => l.trim()).length;
  if (ext === ".json") {
    try { const d = JSON.parse(text); return Array.isArray(d) ? d.length : Array.isArray(d.firs) ? d.firs.length : null; } catch (_) { return null; }
  }
  if (ext === ".csv") {                         // count rows outside quoted fields, minus the header
    let rows = 0, quoted = false;
    for (let i = 0; i < text.length; i += 1) {
      if (text[i] === '"') quoted = !quoted;
      else if (text[i] === "\n" && !quoted) rows += 1;
    }
    if (!text.endsWith("\n")) rows += 1;
    return Math.max(0, rows - 1);
  }
  return null;
}

function validateFile(file) {
  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
  if (!ACCEPT.includes(ext)) return `"${file.name}" is not a supported file. Use ${ACCEPT.join(", ")}.`;
  if (file.size > MAX_MB * 1024 * 1024) return `"${file.name}" is ${fmtBytes(file.size)}. The limit is ${MAX_MB} MB per upload.`;
  if (file.size === 0) return `"${file.name}" is empty.`;
  return null;
}

function ProgressBar({ value, tone = "bg-accent", indeterminate = false, height = "h-2" }) {
  return (
    <div className={`${height} w-full bg-ink-800 overflow-hidden`}>
      {indeterminate ? <div className={`h-full w-2/5 ${tone} bar-indeterminate`} />
        : <div className={`h-full ${tone} transition-[width] duration-500 ease-out`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />}
    </div>
  );
}

const Icon = ({ d, className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);
const FILE_ICON = "M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm7 0v5h5";
const UPLOAD_ICON = "M12 16V4m0 0l-4 4m4-4l4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3";

// ---------------------------------------------------------------- current job (processing progress)

function JobCard({ job, onStop, onDismiss }) {
  if (!job) {
    return (
      <div className="case-panel h-full">
        <div className="panel-head"><span className="section-title">Processing status</span></div>
        <div className="p-6 text-sm text-paper-500">No job running. Upload a file or paste FIRs; the progress of each step appears here.</div>
      </div>
    );
  }
  const total = job.created || 0;
  const done = job.firs_done || 0;
  const running = ACTIVE.includes(job.status);
  const stopped = job.status === "CANCELLED";
  const discarded = Math.max(0, (job.total || 0) - (job.duplicates || 0) - total);
  const percent = total ? (done / total) * 100 : 100;
  const rate = job.elapsed_s > 0 && done > 0 ? done / job.elapsed_s : null;
  const eta = running && rate ? (total - done) / rate : null;
  const review = job.fir_status?.NEEDS_REVIEW || 0;
  const failed = job.fir_status?.FAILED || 0;

  return (
    <div className="case-panel">
      <div className="panel-head"><span className="section-title">Processing status</span><StatusBadge status={job.status} /></div>
      <div className="p-5 space-y-5">
      <div className="min-w-0">
        <div className="label mb-0.5">File</div>
        <div className="data-id text-paper-100 truncate" title={job.filename}>{job.filename}</div>
      </div>

      {total === 0 ? (
        <div className="text-sm text-paper-300">
          No new FIRs: all {job.duplicates} FIR(s) in this upload were already in the system, so nothing was added.
        </div>
      ) : (
        <>
          <div>
            <div className="flex items-end justify-between mb-2">
              <div className="font-mono text-3xl font-medium text-paper-100 tabular-nums">{stopped ? "Stopped" : `${Math.floor(percent)}%`}</div>
              <div className="text-xs text-paper-500 text-right tabular-nums">
                {stopped ? (
                  <><span className="text-paper-100 font-medium">{done}</span> FIRs kept · {discarded} discarded</>
                ) : (
                  <><span className="text-paper-100 font-medium">{done}</span> of {total} FIRs analysed{running ? <> · {total - done} remaining</> : null}</>
                )}
              </div>
            </div>
            <ProgressBar value={percent} tone={job.status === "CANCELLED" ? "bg-paper-500" : job.status === "COMPLETED" ? "bg-signal-green" : "bg-accent"}
              indeterminate={job.status === "LINKING" || job.status === "CANCELLING"} height="h-2.5" />
            <div className="flex justify-between text-xs text-paper-500 mt-2 tabular-nums">
              <span>Elapsed {fmtDuration(job.elapsed_s)}{rate ? ` · ${(rate * 60).toFixed(0)} FIRs/min` : ""}</span>
              <span>{job.status === "LINKING" ? "Linking cases and finding groups…" : job.status === "CANCELLING" ? "Stopping after the current step…"
                : running ? (eta !== null ? `About ${fmtDuration(eta)} left` : "Estimating time left…") : job.finished_at ? `Finished ${fmtDateTime(job.finished_at)}` : ""}</span>
            </div>
          </div>

          <div className="space-y-3">
            {STEPS.map(([key, label, help]) => {
              const c = job.stages?.[key] || {};
              const finished = (c.SUCCEEDED || 0) + (c.SKIPPED || 0) + (c.FAILED || 0);
              const stepTotal = Object.values(c).reduce((a, b) => a + b, 0) || total;
              const isRunning = (c.RUNNING || 0) > 0;
              return (
                <div key={key}>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="flex items-center gap-2 text-paper-100">
                      <span className={`w-2 h-2 ${finished === stepTotal ? "bg-signal-green" : isRunning ? "bg-accent animate-pulse" : "bg-ink-600"}`} />
                      {label} <span className="text-paper-500 hidden xl:inline">· {help}</span>
                    </span>
                    <span className="text-paper-500 tabular-nums">
                      {key === "enrich" && c.SUCCEEDED ? `${c.SUCCEEDED} sent to Granite · ` : ""}{finished}/{stepTotal}
                      {c.FAILED ? <span className="text-signal-red"> · {c.FAILED} failed</span> : null}
                    </span>
                  </div>
                  <ProgressBar value={stepTotal ? (finished / stepTotal) * 100 : 0} tone={c.FAILED ? "bg-signal-amber" : "bg-signal-green"} height="h-1.5" />
                </div>
              );
            })}
          </div>
        </>
      )}

      {job.duplicates && total ? <div className="text-xs text-paper-500">{job.duplicates} FIR(s) were already in the system and were skipped.</div> : null}
      {review ? <div className="text-xs text-signal-amber">{review} FIR(s) need an officer check · <Link href="/firs?needs_review=true" className="underline">review now</Link></div> : null}
      {failed ? <div className="text-xs text-signal-red">{failed} FIR(s) failed.</div> : null}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-ink-700 -mx-5 px-5 pt-4">
        {running ? (
          <button onClick={onStop} disabled={job.status !== "PROCESSING" && job.status !== "RECEIVED"} className="btn btn-danger-outline btn-sm">
            <Icon d="M6 6h12v12H6z" className="w-3.5 h-3.5" /> Stop processing
          </button>
        ) : (
          <div className="flex gap-2">
            <Link href="/offenders" className="btn btn-primary btn-sm">View repeat offenders</Link>
            <Link href="/firs" className="btn btn-secondary btn-sm">Case files</Link>
          </div>
        )}
        {!running ? <button onClick={onDismiss} className="btn btn-ghost btn-sm">Close</button> : <span className="muted">You can leave this page; processing continues.</span>}
      </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- page

export default function UploadPage() {
  const [tab, setTab] = useState("file");
  const [file, setFile] = useState(null);                 // { file, count }
  const [dragging, setDragging] = useState(false);
  const [upload, setUpload] = useState(null);             // { loaded, total, percent, rate, remainingS }
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [job, setJob] = useState(null);
  const [history, setHistory] = useState(null);
  const [confirm, setConfirm] = useState(null);           // { kind: "delete" | "all" | "stop", batch }
  const abortRef = useRef(null);
  const inputRef = useRef(null);

  const loadHistory = useCallback(async () => {
    try {
      const list = await api.batches();
      setHistory(list);
      return list;
    } catch (e) {
      setError(e);
      setHistory([]);
      return [];
    }
  }, []);

  // on open: resume following a job that is still running
  useEffect(() => {
    loadHistory().then((list) => {
      const running = list.find((b) => ACTIVE.includes(b.status));
      if (running) api.batch(running.id).then(setJob).catch(() => {});
    });
  }, [loadHistory]);

  // poll the job while it runs
  useEffect(() => {
    if (!job || !ACTIVE.includes(job.status)) return;
    const t = setTimeout(() => {
      api.batch(job.id).then((b) => {
        setJob(b);
        if (!ACTIVE.includes(b.status)) loadHistory();
      }).catch((e) => { if (e.status === 404) setJob(null); else setError(e); });
    }, 1200);
    return () => clearTimeout(t);
  }, [job, loadHistory]);

  const pickFile = async (f) => {
    setError(null); setNotice(null);
    if (!f) return;
    const problem = validateFile(f);
    if (problem) { setFile(null); setError(problem); return; }
    let count = null;
    try { count = countRecords(f.name, await f.text()); } catch (_) { /* count is only a hint */ }
    if (count !== null && count > MAX_FIRS) { setError(`"${f.name}" has about ${count} FIRs. The limit is ${MAX_FIRS} per upload; split the file.`); return; }
    setFile({ file: f, count });
  };

  const accepted = async (res) => {
    if (res.created === 0) setNotice(`Nothing new: all ${res.duplicates} FIR(s) were already in the system.`);
    setJob(await api.batch(res.batch_id));
    loadHistory();
  };

  const startUpload = async () => {
    if (!file) return;
    setError(null); setNotice(null);
    setUpload({ loaded: 0, total: file.file.size, percent: 0, rate: 0, remainingS: null });
    const { promise, abort } = api.uploadWithProgress(file.file, setUpload);
    abortRef.current = abort;
    try {
      const res = await promise;
      setFile(null);
      await accepted(res);
    } catch (e) {
      if (e.cancelled) setNotice("Upload cancelled. Nothing was added.");
      else setError(e);
    } finally {
      abortRef.current = null;
      setUpload(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const sendText = async () => {
    setSending(true); setError(null); setNotice(null);
    try {
      await accepted(await api.uploadText(text));
      setText("");
    } catch (e) {
      setError(e);
    } finally {
      setSending(false);
    }
  };

  const runConfirm = async () => {
    const { kind, batch } = confirm;
    try {
      if (kind === "stop") {
        await api.cancelBatch(batch.id);
        setJob(await api.batch(batch.id));
        setNotice("Stopping. FIRs that were already analysed are kept; the rest are discarded.");
      } else if (kind === "all") {
        await api.resetAll();
        setJob(null);
        setNotice("All data deleted. The system is empty.");
      } else {
        const r = await api.deleteBatch(batch.id);
        if (job?.id === batch.id) setJob(null);
        setNotice(`Deleted "${batch.filename}" (${r.firs_deleted} FIRs). Repeat-offender groups recalculated: ${r.clusters_now} now.`);
      }
      await loadHistory();
    } catch (e) {
      setError(e);
    } finally {
      setConfirm(null);
    }
  };

  const pasteCount = text.trim() ? text.split(/\n\s*-{3,}\s*\n/).filter((t) => t.trim()).length : 0;
  const busy = Boolean(upload) || sending;

  return (
    <div>
      <PageHeader title="Add FIRs" description="Upload a file or paste FIR text. Each FIR is then analysed in the background." />
      <div className="px-8 py-5 space-y-5">
        {error ? <ErrorBox error={error} onDismiss={() => setError(null)} /> : null}
        {notice ? (
          <div className="border border-signal-green/40 border-l-[3px] border-l-signal-green bg-signal-green/5 px-4 py-3 text-sm text-paper-100 flex items-center justify-between gap-3">
            <span>{notice}</span>
            <button onClick={() => setNotice(null)} className="text-paper-500 hover:text-paper-100" aria-label="Dismiss">✕</button>
          </div>
        ) : null}

        <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">
          {/* ------------------------------------------------ input */}
          <div className="xl:col-span-3 case-panel">
            <div className="flex border-b border-ink-700 bg-ink-800">
              {[["file", "Upload file"], ["paste", "Paste text"]].map(([k, label]) => (
                <button key={k} onClick={() => setTab(k)} disabled={busy}
                  className={`px-5 py-2.5 font-mono text-[12px] uppercase tracking-[0.08em] border-r border-ink-700 transition-colors ${tab === k ? "bg-surface text-paper-100 font-medium shadow-[inset_0_3px_0_rgb(var(--khaki))]" : "text-paper-500 hover:text-paper-100"}`}>
                  {label}
                </button>
              ))}
            </div>

            {tab === "file" ? (
              <div className="p-5 space-y-4">
                {!file ? (
                  <label
                    onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={(e) => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files?.[0]); }}
                    className={`flex flex-col items-center justify-center text-center border-2 border-dashed px-6 py-12 cursor-pointer transition-colors ${
                      dragging ? "border-accent bg-accent/5" : "border-ink-600 hover:border-accent/60 hover:bg-ink-800/40"}`}>
                    <div className="text-paper-500 mb-3"><Icon d={UPLOAD_ICON} className="w-8 h-8" /></div>
                    <div className="text-sm text-paper-100"><span className="font-medium text-accent">Choose a file</span> or drag it here</div>
                    <div className="text-xs text-paper-500 mt-1">TXT (FIRs separated by ---), JSONL, JSON or CSV · up to {MAX_FIRS.toLocaleString("en-IN")} FIRs · {MAX_MB} MB</div>
                    <input ref={inputRef} type="file" accept={ACCEPT.join(",")} className="hidden" onChange={(e) => pickFile(e.target.files?.[0])} />
                  </label>
                ) : (
                  <div className="border border-ink-700 p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 border border-ink-700 bg-ink-800 text-paper-500 flex items-center justify-center shrink-0"><Icon d={FILE_ICON} /></div>
                      <div className="min-w-0 flex-1">
                        <div className="data-id text-paper-100 truncate">{file.file.name}</div>
                        <div className="text-xs text-paper-500">{fmtBytes(file.file.size)}{file.count !== null ? ` · about ${file.count.toLocaleString("en-IN")} FIRs` : ""}</div>
                      </div>
                      {!upload ? <button onClick={() => { setFile(null); if (inputRef.current) inputRef.current.value = ""; }} className="btn btn-ghost btn-sm">Remove</button> : null}
                    </div>
                    {upload ? (
                      <div className="mt-4">
                        <div className="flex justify-between text-xs mb-1.5 tabular-nums">
                          <span className="text-paper-100 font-medium">{upload.percent >= 100 ? "Processing on server…" : `Uploading ${Math.floor(upload.percent)}%`}</span>
                          <span className="text-paper-500">
                            {fmtBytes(upload.loaded)} of {fmtBytes(upload.total)}
                            {upload.percent < 100 && upload.rate ? ` · ${fmtBytes(upload.rate)}/s · ${fmtDuration(upload.remainingS)} left` : ""}
                          </span>
                        </div>
                        <ProgressBar value={upload.percent} indeterminate={upload.percent >= 100} />
                      </div>
                    ) : null}
                    <div className="flex justify-end gap-2 mt-4">
                      {upload ? (
                        <button onClick={() => abortRef.current?.()} disabled={upload.percent >= 100} className="btn btn-secondary">Cancel upload</button>
                      ) : (
                        <button onClick={startUpload} className="btn btn-primary"><Icon d={UPLOAD_ICON} className="w-4 h-4" /> Upload and analyse</button>
                      )}
                    </div>
                  </div>
                )}
                <div className="text-xs text-paper-500">
                  Sample files in <span className="data-id">src/dataset/</span>: <span className="data-id">firs_main.txt</span> (400 FIRs),{" "}
                  <span className="data-id">demo_live_batch.txt</span> (6 new FIRs), <span className="data-id">firs_unrelated.txt</span> (60 standalone FIRs).
                </div>
              </div>
            ) : (
              <div className="p-5 space-y-3">
                <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={PLACEHOLDER} rows={13} disabled={sending}
                  className="input w-full data-id text-xs leading-relaxed resize-y" />
                <div className="flex flex-wrap justify-between items-center gap-2">
                  <span className="text-xs text-paper-500">
                    {pasteCount ? `${pasteCount} FIR${pasteCount > 1 ? "s" : ""} detected` : "Separate FIRs with a line containing only ---"}
                  </span>
                  <div className="flex gap-2">
                    {text ? <button onClick={() => setText("")} disabled={sending} className="btn btn-ghost">Clear</button> : null}
                    <button onClick={sendText} disabled={sending || text.trim().length < 20} className="btn btn-primary">{sending ? "Sending…" : "Analyse"}</button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ------------------------------------------------ progress */}
          <div className="xl:col-span-2">
            <JobCard job={job} onStop={() => setConfirm({ kind: "stop", batch: job })} onDismiss={() => setJob(null)} />
          </div>
        </div>

        {/* ------------------------------------------------ history */}
        <div className="case-panel overflow-hidden">
          <div className="panel-head">
            <div className="flex items-baseline gap-3">
              <span className="section-title">Upload history</span>
              <span className="muted hidden md:inline">Deleting an upload removes its FIRs and recalculates the repeat-offender groups.</span>
            </div>
            {history?.length ? <button onClick={() => setConfirm({ kind: "all" })} className="btn btn-danger-outline btn-sm">Delete all data</button> : null}
          </div>
          {!history ? <div className="px-5 py-6 text-sm text-paper-500">Loading…</div> : history.length === 0 ? (
            <div className="px-5 py-10 text-center text-sm text-paper-500">No uploads yet.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-ink-700">
                    {["File", "FIRs", "Status", "Uploaded", "Time taken", ""].map((h) => <th key={h} className="text-left label font-normal px-5 py-2.5 whitespace-nowrap">{h}</th>)}
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-700">
                  {history.map((b) => {
                    const running = ACTIVE.includes(b.status);
                    return (
                      <tr key={b.id} className={job?.id === b.id ? "bg-accent/5" : "hover:bg-ink-800/40"}>
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <Icon d={FILE_ICON} className="w-4 h-4 text-paper-500 shrink-0" />
                            <span className="data-id text-paper-100 truncate max-w-[280px]" title={b.filename}>{b.filename}</span>
                            <span className="text-xs text-paper-500 shrink-0">{b.source === "api" ? "pasted" : fmtBytes(b.size_bytes)}</span>
                          </div>
                        </td>
                        <td className="px-5 py-3 tabular-nums whitespace-nowrap">
                          <span className="text-paper-100">{b.created}</span>
                          {b.duplicates ? <span className="text-xs text-paper-500"> · {b.duplicates} duplicate{b.duplicates > 1 ? "s" : ""}</span> : null}
                          {running && b.created ? <span className="text-xs text-paper-500"> · {Math.round(b.progress * 100)}%</span> : null}
                        </td>
                        <td className="px-5 py-3"><StatusBadge status={b.status} /></td>
                        <td className="px-5 py-3 text-paper-300 whitespace-nowrap">{fmtDateTime(b.created_at)}</td>
                        <td className="px-5 py-3 text-paper-300 whitespace-nowrap tabular-nums">{running ? "running…" : fmtDuration(b.elapsed_s)}</td>
                        <td className="px-5 py-3">
                          <div className="flex justify-end gap-1.5">
                            <button onClick={() => api.batch(b.id).then(setJob).catch(setError)} className="btn btn-ghost btn-sm">{running ? "Progress" : "Details"}</button>
                            <button disabled={running} onClick={() => setConfirm({ kind: "delete", batch: b })}
                              title={running ? "Stop it first, or wait until it finishes" : "Delete this upload"} className="btn btn-danger-outline btn-sm">Delete</button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(confirm)}
        tone={confirm?.kind === "stop" ? "warning" : "danger"}
        title={confirm?.kind === "all" ? "Delete all data?" : confirm?.kind === "stop" ? "Stop processing?" : "Delete this upload?"}
        message={confirm?.kind === "all"
          ? "Every FIR, its analysis, evidence, links, repeat-offender groups, station briefs and uploaded files will be permanently deleted."
          : confirm?.kind === "stop"
            ? "FIRs that are already fully analysed are kept; the rest of this upload is discarded. Uploading the same file again later only adds the missing FIRs."
            : confirm ? `"${confirm.batch.filename}" and its ${confirm.batch.created} FIR(s) will be permanently deleted, with their analysis, evidence and links. Repeat-offender groups are recalculated from the remaining FIRs.` : ""}
        confirmLabel={confirm?.kind === "all" ? "Delete everything" : confirm?.kind === "stop" ? "Stop processing" : "Delete upload"}
        busyLabel={confirm?.kind === "stop" ? "Stopping…" : "Deleting…"}
        confirmWord={confirm?.kind === "all" ? "DELETE" : undefined}
        onConfirm={runConfirm}
        onCancel={() => setConfirm(null)} />
    </div>
  );
}
