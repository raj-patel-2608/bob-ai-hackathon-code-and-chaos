export default function BarList({ data, colorClass = "bg-signal-blue" }) {
  const entries = Object.entries(data || {});
  const max = Math.max(1, ...entries.map(([, v]) => v));

  if (entries.length === 0) {
    return <div className="text-sm text-paper-500">No data yet.</div>;
  }

  return (
    <div className="space-y-2.5">
      {entries.map(([label, value]) => (
        <div key={label}>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-paper-300">{label}</span>
            <span className="data-id text-paper-500">{value}</span>
          </div>
          <div className="h-1.5 bg-ink-700 w-full">
            <div
              className={`h-1.5 ${colorClass}`}
              style={{ width: `${Math.max(4, (value / max) * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
