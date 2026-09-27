import Link from "next/link";
import InfoTip from "./InfoTip";

export default function StatCard({ label, value, sub, stripe = "amber", info, href }) {
  const body = (
    <div className={`case-panel stripe-${stripe} px-5 py-4 h-full ${href ? "hover:bg-ink-800/60" : ""}`}>
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-paper-500">
        <span>{label}</span>
        {info ? <InfoTip text={info} /> : null}
      </div>
      <div className="font-serif text-3xl text-paper-100 mt-1 whitespace-nowrap overflow-hidden text-ellipsis">{value}</div>
      {sub ? <div className="text-xs text-paper-500 mt-1">{sub}</div> : null}
    </div>
  );
  return href ? <Link href={href} className="block h-full">{body}</Link> : body;
}
