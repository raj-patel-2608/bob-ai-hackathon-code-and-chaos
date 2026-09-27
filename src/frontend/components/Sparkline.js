export default function Sparkline({ data }) {
  const entries = Object.entries(data || {});
  if (entries.length === 0) {
    return <div className="text-sm text-paper-500">No trend data yet.</div>;
  }

  const width = 560;
  const height = 140;
  const padding = 24;
  const values = entries.map(([, v]) => v);
  const max = Math.max(...values, 1);

  const stepX = entries.length > 1 ? (width - padding * 2) / (entries.length - 1) : 0;
  const points = entries.map(([, v], i) => {
    const x = padding + i * stepX;
    const y = height - padding - (v / max) * (height - padding * 2);
    return [x, y];
  });

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${p[0]},${p[1]}`).join(" ");
  const areaPath = `${linePath} L${points[points.length - 1][0]},${height - padding} L${points[0][0]},${
    height - padding
  } Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto">
      <line
        x1={padding}
        y1={height - padding}
        x2={width - padding}
        y2={height - padding}
        style={{ stroke: "rgb(var(--border-strong))" }}
        strokeWidth="1"
      />
      <path d={areaPath} style={{ fill: "rgb(var(--accent) / 0.12)" }} stroke="none" />
      <path d={linePath} fill="none" style={{ stroke: "rgb(var(--accent))" }} strokeWidth="2" />
      {points.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="2.5" style={{ fill: "rgb(var(--khaki))" }} />
      ))}
      {entries.map(([label], i) => (
        <text
          key={label}
          x={points[i][0]}
          y={height - 6}
          fontSize="9"
          style={{ fill: "rgb(var(--fg-subtle))" }}
          textAnchor="middle"
        >
          {label}
        </text>
      ))}
    </svg>
  );
}
