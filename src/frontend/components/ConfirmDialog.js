"use client";

import { useEffect, useState } from "react";

// In-page confirmation dialog (not a browser popup). For destructive actions the user must type `confirmWord`.
export default function ConfirmDialog({ open, title, message, confirmLabel = "Delete", busyLabel = "Working…", tone = "danger",
  confirmWord, onConfirm, onCancel }) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape" && !busy) { setTyped(""); onCancel(); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;
  const ready = !confirmWord || typed.trim().toUpperCase() === confirmWord.toUpperCase();
  const run = async () => {
    setBusy(true);
    try { await onConfirm(); } finally { setBusy(false); setTyped(""); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-[2px] flex items-center justify-center p-4" onClick={() => !busy && onCancel()}>
      <div role="dialog" aria-modal="true" className="case-panel w-full max-w-md p-6 space-y-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-3">
          <div className={`w-9 h-9 shrink-0 rounded-full flex items-center justify-center ${tone === "danger" ? "bg-signal-red/10 text-signal-red" : "bg-signal-amber/10 text-signal-amber"}`}>
            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /></svg>
          </div>
          <div>
            <div className="text-base font-semibold text-paper-100">{title}</div>
            <div className="text-sm text-paper-300 leading-relaxed mt-1">{message}</div>
          </div>
        </div>
        {confirmWord ? (
          <label className="block text-xs text-paper-500">
            Type <span className="data-id font-semibold text-paper-100">{confirmWord}</span> to confirm
            <input autoFocus value={typed} onChange={(e) => setTyped(e.target.value)} className="input w-full mt-1.5 data-id" />
          </label>
        ) : null}
        <div className="flex justify-end gap-2 pt-1">
          <button disabled={busy} onClick={() => { setTyped(""); onCancel(); }} className="btn btn-secondary">Cancel</button>
          <button disabled={!ready || busy} onClick={run} className={`btn ${tone === "danger" ? "btn-danger" : "btn-primary"}`}>
            {busy ? busyLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
