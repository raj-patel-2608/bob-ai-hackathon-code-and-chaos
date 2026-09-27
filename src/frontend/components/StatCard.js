export default function StatCard({ label, value, sub, stripe = "amber" }) {
  return (
    <div className={`case-panel stripe-${stripe} px-5 py-4`}>
      <div className="text-[11px] uppercase tracking-wide text-paper-500">{label}</div>
      <div className="font-serif text-3xl text-paper-100 mt-1">{value}</div>
      {sub ? <div className="text-xs text-paper-500 mt-1">{sub}</div> : null}
    </div>
  );
}
