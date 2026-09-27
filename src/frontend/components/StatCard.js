import Link from "next/link";
import InfoTip from "./InfoTip";

export default function StatCard({ label, value, sub, stripe = "blue", info, href }) {
  const body = (
    <div className={`case-panel stripe-${stripe} px-4 py-3.5 h-full transition-colors ${href ? "hover:bg-ink-800/50" : ""}`}>
      <div className="flex items-center gap-2 label">
        <span>{label}</span>
        {info ? <InfoTip text={info} /> : null}
      </div>
      <div className="font-mono text-[26px] leading-9 font-medium text-paper-100 mt-1 whitespace-nowrap overflow-hidden text-ellipsis tabular-nums">{value}</div>
      {sub ? <div className="text-xs text-paper-500 mt-0.5">{sub}</div> : null}
    </div>
  );
  return href ? <Link href={href} className="block h-full">{body}</Link> : body;
}
