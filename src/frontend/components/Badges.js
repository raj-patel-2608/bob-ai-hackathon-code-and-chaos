import { IDENTITY_LABELS } from "../lib/api";

export function RiskBadge({ risk, score }) {
  const cls =
    risk === "HIGH"
      ? "border-signal-red text-signal-red"
      : risk === "MEDIUM"
      ? "border-signal-amber text-signal-amber"
      : "border-ink-600 text-paper-300";
  return (
    <span className={`text-[11px] uppercase tracking-wide px-2 py-0.5 border ${cls}`}>
      {risk} risk{score !== undefined ? ` · ${score}` : ""}
    </span>
  );
}

export function LinkBadge({ kind, score }) {
  const evidence = kind === "EVIDENCE";
  return (
    <span
      className={`data-id text-[11px] px-2 py-0.5 border ${
        evidence ? "border-signal-red text-signal-red" : "border-signal-amber text-signal-amber"
      }`}
    >
      {evidence ? "evidence" : "pattern only"} · {Math.round((score || 0) * 100)}%
    </span>
  );
}

export function EntityChip({ type, value, role }) {
  return (
    <span className="inline-flex items-center gap-1.5 border border-ink-600 bg-ink-800 px-2 py-1 text-xs">
      <span className="text-paper-500 uppercase text-[10px]">{IDENTITY_LABELS[type] || type}</span>
      <span className="data-id text-paper-100">{value}</span>
      {role && role !== "offender" ? <span className="text-[10px] text-paper-500">({role})</span> : null}
    </span>
  );
}

export function CrimeTag({ children }) {
  return (
    <span className="text-[11px] uppercase tracking-wide text-signal-blue border border-signal-blue/40 px-2 py-0.5">
      {children}
    </span>
  );
}

export function StatusBadge({ status }) {
  const map = {
    ANALYZED: "text-signal-green border-signal-green/50",
    NEEDS_REVIEW: "text-signal-amber border-signal-amber/60",
    FAILED: "text-signal-red border-signal-red/60",
    PROCESSING: "text-signal-blue border-signal-blue/50",
    QUEUED: "text-paper-500 border-ink-600",
  };
  return (
    <span className={`text-[10px] uppercase tracking-wide border px-1.5 py-0.5 ${map[status] || "text-paper-500 border-ink-600"}`}>
      {status?.replace("_", " ").toLowerCase()}
    </span>
  );
}

export function DecidedBy({ by, confidence }) {
  const conf = confidence || confidence === 0 ? `${Math.round(confidence * 100)}%` : null;
  if (by === "llm") {
    return (
      <span className="text-[11px] text-paper-500">
        decided by <span className="text-paper-300">Granite LLM</span> (second opinion{conf ? `; Laya was only ${conf} sure` : ""})
      </span>
    );
  }
  const label = { laya: "Laya", rules: "rules (fallback)", officer: "officer" }[by] || by;
  return (
    <span className="text-[11px] text-paper-500">
      decided by <span className="text-paper-300">{label}</span>
      {conf && by === "laya" ? ` · ${conf} confident` : ""}
    </span>
  );
}
