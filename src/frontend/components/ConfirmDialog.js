"use client";

import { useState } from "react";

// In-page confirmation dialog (not a browser popup). For destructive actions the user must type `confirmWord`.
export default function ConfirmDialog({ open, title, message, confirmLabel = "Delete", confirmWord, onConfirm, onCancel }) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  if (!open) return null;
  const ready = !confirmWord || typed.trim().toUpperCase() === confirmWord.toUpperCase();
  const run = async () => {
    setBusy(true);
    try { await onConfirm(); } finally { setBusy(false); setTyped(""); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onCancel}>
      <div className="case-panel stripe-red w-full max-w-md p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
        <div className="font-serif text-xl text-paper-100">{title}</div>
        <div className="text-sm text-paper-300 leading-relaxed">{message}</div>
        {confirmWord ? (
          <div className="text-xs text-paper-500">
            Type <span className="data-id text-paper-100">{confirmWord}</span> to confirm
            <input autoFocus value={typed} onChange={(e) => setTyped(e.target.value)}
              className="mt-1 w-full bg-ink-950 border border-ink-600 px-3 py-2 text-sm text-paper-100 data-id focus:outline-none focus:border-signal-red" />
          </div>
        ) : null}
        <div className="flex justify-end gap-2">
          <button onClick={() => { setTyped(""); onCancel(); }} className="border border-ink-600 text-paper-100 text-sm px-4 py-2">Cancel</button>
          <button disabled={!ready || busy} onClick={run} className="bg-signal-red text-paper-100 text-sm font-medium px-4 py-2 disabled:opacity-40">
            {busy ? "Deleting…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
