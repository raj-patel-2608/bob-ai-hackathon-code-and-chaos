export default function BarList({ data, colorClass = "bg-accent" }) {
  const entries = Object.entries(data || {});
  const max = Math.max(1, ...entries.map(([, v]) => v));

  if (entries.length === 0) {
    return <div className="text-sm text-paper-500">No data yet.</div>;
  }

  return (
    <div className="space-y-3">
      {entries.map(([label, value]) => (
        <div key={label}>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-paper-300">{label}</span>
            <span className="font-mono text-paper-100 tabular-nums">{value}</span>
          </div>
          <div className="h-2 bg-ink-800 w-full">
            <div className={`h-full ${colorClass}`} style={{ width: `${Math.max(2, (value / max) * 100)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
