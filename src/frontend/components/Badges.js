import { IDENTITY_LABELS } from "../lib/api";

const TONE = {
  red: "border-signal-red/50 text-signal-red bg-signal-red/5",
  amber: "border-signal-amber/50 text-signal-amber bg-signal-amber/5",
  green: "border-signal-green/50 text-signal-green bg-signal-green/5",
  blue: "border-signal-blue/50 text-signal-blue bg-signal-blue/5",
  grey: "border-ink-600 text-paper-300 bg-ink-800",
};

export function Tag({ tone = "grey", children, title }) {
  return <span title={title} className={`pill ${TONE[tone]}`}>{children}</span>;
}

export function RiskBadge({ risk, score }) {
  const tone = risk === "HIGH" ? "red" : risk === "MEDIUM" ? "amber" : "grey";
  return <Tag tone={tone}>{risk === "HIGH" ? "High" : risk === "MEDIUM" ? "Medium" : "Low"} risk{score !== undefined ? ` · ${score}` : ""}</Tag>;
}

export function LinkBadge({ kind, score }) {
  const evidence = kind === "EVIDENCE";
  return <Tag tone={evidence ? "red" : "amber"}>{evidence ? "Shared evidence" : "Similar story"} · {Math.round((score || 0) * 100)}%</Tag>;
}

export function EntityChip({ type, value, role }) {
  return (
    <span className="inline-flex items-center gap-1.5 border border-ink-700 bg-ink-800 px-2 py-1 text-xs">
      <span className="label text-[10px]">{IDENTITY_LABELS[type] || type}</span>
      <span className="data-id text-paper-100">{value}</span>
      {role && role !== "offender" ? <span className="text-[11px] text-paper-500">({role})</span> : null}
    </span>
  );
}

export function CrimeTag({ children }) {
  return <Tag tone="blue">{children}</Tag>;
}

const STATUS = {
  ANALYZED: ["Analysed", "green"],
  NEEDS_REVIEW: ["Needs review", "amber"],
  FAILED: ["Failed", "red"],
  PROCESSING: ["Processing", "blue"],
  QUEUED: ["Queued", "grey"],
  // batches
  COMPLETED: ["Completed", "green"],
  COMPLETED_WITH_ERRORS: ["Completed with errors", "amber"],
  RECEIVED: ["Received", "blue"],
  LINKING: ["Linking cases", "blue"],
  CANCELLING: ["Stopping", "amber"],
  CANCELLED: ["Stopped", "grey"],
};

export function StatusBadge({ status }) {
  const [label, tone] = STATUS[status] || [status?.toLowerCase(), "grey"];
  return <Tag tone={tone}>{label}</Tag>;
}

export function DecidedBy({ by, confidence }) {
  const conf = confidence || confidence === 0 ? `${Math.round(confidence * 100)}%` : null;
  if (by === "llm") {
    return (
      <span className="text-xs text-paper-500">
        Decided by <span className="text-paper-300 font-medium">IBM Granite</span> (second opinion{conf ? `; Laya was only ${conf} sure` : ""})
      </span>
    );
  }
  const label = { laya: "Laya", rules: "keyword rules (fallback)", officer: "an officer" }[by] || by;
  return (
    <span className="text-xs text-paper-500">
      Decided by <span className="text-paper-300 font-medium">{label}</span>
      {conf && by === "laya" ? ` · ${conf} confident` : ""}
    </span>
  );
}
