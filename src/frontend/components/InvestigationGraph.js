"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { forceX, forceY } from "d3-force";
import { fmtDate, fmtMoney, IDENTITY_LABELS } from "../lib/api";
import { useThemeColors } from "../lib/theme";

// canvas graph (uses window), so it is loaded only in the browser
const ForceGraph2D = dynamic(() => import("./ForceGraphClient"), { ssr: false });

const CATEGORY = {
  cyber: { color: "#4C9BE8", label: "Cyber crime" },
  property: { color: "#D9A441", label: "Property crime" },
  body: { color: "#E0654A", label: "Crime against the body" },
  economic: { color: "#6FB386", label: "Economic offence" },
};
const IDENTITY_COLOR = {
  phone: "#10B981", bank_account: "#F5B942", upi_id: "#F59E0B", imei: "#A78BFA", vehicle: "#FB923C",
  online_handle: "#22D3EE", accused_name: "#F472B6", accused_alias: "#F472B6",
};
const PATTERN_COLOR = "rgba(217,164,65,0.55)";

/**
 * Props:
 *   graph   API graph: nodes {type: "fir"|"identity"}, edges {kind: "EVIDENCE"|"PATTERN"}
 *   focusId optional FIR id to highlight
 *   height  canvas height in px
 */
export default function InvestigationGraph({ graph, focusId, height = 620, initialMode = "network" }) {
  const wrapRef = useRef(null);
  const fgRef = useRef(null);                             // graph instance (the library returns a new handle per render)
  const [ready, setReady] = useState(false);
  const fitPending = useRef(true);
  const onInstance = useCallback((instance) => { if (instance) { fgRef.current = instance; setReady(true); } }, []);
  const [width, setWidth] = useState(900);
  const [mode, setMode] = useState(initialMode);          // network | timeline
  const [showLabels, setShowLabels] = useState(true);
  const [hover, setHover] = useState(null);
  const [selected, setSelected] = useState(null);
  const theme = useThemeColors();
  const T = theme || { bg: "#0B1012", fg: "#E9ECEC", subtle: "#8B979E", c: (_n, a) => `rgba(139,151,158,${a})` };

  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(320, Math.floor(e.contentRect.width))));
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  // ------------------------------------------------------------------ data (rebuilt per mode, so positions reset)
  const data = useMemo(() => {
    const firs = (graph?.nodes || []).filter((n) => n.type === "fir");
    const identities = (graph?.nodes || []).filter((n) => n.type === "identity");
    const time = (n) => (n.registered_at ? new Date(n.registered_at).getTime() : 0);
    // order of occurrence inside each repeat-offender group: 1st, 2nd, ...
    const order = {};
    const byCluster = {};
    firs.forEach((f) => { (byCluster[f.cluster_id || f.id] ||= []).push(f); });
    Object.values(byCluster).forEach((list) => list.sort((a, b) => time(a) - time(b)).forEach((f, i) => { order[f.id] = i + 1; }));

    const nodes = [
      ...firs.map((f) => ({ ...f, kind: "fir", order: order[f.id], t: time(f) })),
      ...identities.map((n) => ({ ...n, kind: "identity" })),
    ];
    const links = (graph?.edges || []).map((e) => ({ ...e }));
    const firGroup = Object.fromEntries(firs.map((f) => [f.id, f.cluster_id || f.id]));
    nodes.forEach((n) => {
      if (n.kind === "fir") n.group = firGroup[n.id];
      else {
        const l = links.find((e) => e.target === n.id || e.source === n.id);
        n.group = l ? firGroup[l.source === n.id ? l.target : l.source] : n.id;
      }
    });
    // network view: each group gets its own cell on a grid so gangs do not overlap
    const groups = [...new Set(nodes.map((n) => n.group))];
    const cols = Math.ceil(Math.sqrt(groups.length));
    const CELL = 340;
    const cell = Object.fromEntries(groups.map((g, i) => [g, {
      x: ((i % cols) - (cols - 1) / 2) * CELL, y: (Math.floor(i / cols) - (Math.ceil(groups.length / cols) - 1) / 2) * CELL }]));
    nodes.forEach((n) => { n.cellX = cell[n.group].x; n.cellY = cell[n.group].y; });

    let axis = null;
    if (mode === "timeline" && firs.length) {
      // x = date registered; each group is a "staircase": 1st case at the top, each later case one step lower
      const ts = firs.map(time).filter(Boolean);
      const min = Math.min(...ts), max = Math.max(...ts);
      const span = Math.max(max - min, 1);
      const W = Math.max(1000, firs.length * 110);
      const STEP = 70, GAP = 110;
      const x = (t) => -W / 2 + ((t - min) / span) * W;
      const clusterKeys = Object.keys(byCluster).sort((a, b) =>
        Math.min(...byCluster[a].map(time)) - Math.min(...byCluster[b].map(time)));
      const laneTop = {};
      let y = 0;
      clusterKeys.forEach((k) => { laneTop[k] = y; y += byCluster[k].length * STEP + GAP; });
      const firPos = {};
      nodes.forEach((n) => {
        if (n.kind !== "fir") return;
        n.fx = x(n.t || min);
        n.fy = laneTop[n.cluster_id || n.id] + (n.order - 1) * STEP - y / 2;
        firPos[n.id] = n;
      });
      // shared evidence sits to the right of the first FIR that contains it, level with the FIRs it joins
      nodes.forEach((n) => {
        if (n.kind !== "identity") return;
        const linked = links.filter((l) => l.target === n.id || l.source === n.id)
          .map((l) => firPos[l.source === n.id ? l.target : l.source]).filter(Boolean)
          .sort((a, b) => a.t - b.t);
        if (!linked.length) return;
        n.fx = linked[0].fx + 60;
        n.fy = linked.reduce((sum, f) => sum + f.fy, 0) / linked.length + 25;
      });
      axis = { min, max, x, top: -y / 2 - 60, bottom: y / 2 };
    }
    return { nodes, links, axis };
  }, [graph, mode]);

  const neighbours = useMemo(() => {
    const m = {};
    data.links.forEach((l) => {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      (m[s] ||= new Set()).add(t);
      (m[t] ||= new Set()).add(s);
    });
    return m;
  }, [data]);

  const active = hover || selected;
  const isLit = useCallback((id) => !active || id === active.id || neighbours[active.id]?.has(id), [active, neighbours]);
  const linkLit = useCallback((l) => {
    if (!active) return true;
    const s = typeof l.source === "object" ? l.source.id : l.source;
    const t = typeof l.target === "object" ? l.target.id : l.target;
    return s === active.id || t === active.id;
  }, [active]);

  useEffect(() => {
    const fg = fgRef.current;
    if (!ready || !fg) return;
    fg.d3Force("charge")?.strength(mode === "network" ? -110 : -30).distanceMax(220);
    fg.d3Force("link")?.distance((l) => (l.kind === "PATTERN" ? 120 : 45)).strength((l) => (l.kind === "PATTERN" ? 0.05 : 0.8));
    fg.d3Force("center", null);
    fg.d3Force("x", mode === "network" ? forceX((n) => n.cellX).strength(0.2) : null);
    fg.d3Force("y", mode === "network" ? forceY((n) => n.cellY).strength(0.2) : null);
    fitPending.current = true;                    // fit once the layout has settled (see onEngineStop)
    fg.d3ReheatSimulation?.();
    // fit again while the layout settles (the engine-stop fit alone can fire before the groups spread out)
    const timers = [1500, 3500, 6000].map((ms) => setTimeout(() => fgRef.current?.zoomToFit(600, 80), ms));
    return () => timers.forEach(clearTimeout);
  }, [ready, mode, data]);

  // ------------------------------------------------------------------ drawing
  // on big graphs, case labels appear only after zooming in (less clutter in the overview)
  const labelScale = data.nodes.length > 40 ? 1.1 : 0.55;

  const drawNode = useCallback((node, ctx, scale) => {
    const lit = isLit(node.id);
    ctx.globalAlpha = lit ? 1 : 0.12;
    if (node.kind === "fir") {
      const color = CATEGORY[node.crime_major]?.color || T.subtle;
      const r = node.id === focusId ? 9 : 7;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = T.bg;
      ctx.fill();
      ctx.lineWidth = node.id === focusId ? 3 : 2;
      ctx.strokeStyle = color;
      ctx.stroke();
      if (node.cluster_id && node.order) {
        ctx.fillStyle = color;
        ctx.font = `bold ${7}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(node.order), node.x, node.y + 0.5);
      }
      if (showLabels && scale > labelScale) {
        ctx.font = `${10 / Math.min(scale, 1.6)}px sans-serif`;
        ctx.fillStyle = T.fg;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillText(node.id, node.x, node.y + r + 2);
        ctx.fillStyle = T.subtle;
        ctx.fillText(`${node.station || ""} · ${node.registered_at ? fmtDate(node.registered_at) : ""}`,
          node.x, node.y + r + 2 + 12 / Math.min(scale, 1.6));
      }
    } else {
      const color = IDENTITY_COLOR[node.identity_type] || "#22D3EE";
      const s = 6;
      ctx.beginPath();
      ctx.moveTo(node.x, node.y - s);
      ctx.lineTo(node.x + s, node.y);
      ctx.lineTo(node.x, node.y + s);
      ctx.lineTo(node.x - s, node.y);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
      if (showLabels && scale > labelScale + 0.15) {
        ctx.font = `${9 / Math.min(scale, 1.6)}px monospace`;
        ctx.fillStyle = color;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillText(node.label, node.x, node.y + s + 2);
      }
    }
    ctx.globalAlpha = 1;
  }, [isLit, focusId, showLabels, labelScale, T]);

  const drawAxis = useCallback((ctx, scale) => {
    const ax = data.axis;
    if (!ax) {
      // network view: write "Group K-00x" above each repeat-offender group
      const boxes = {};
      data.nodes.forEach((n) => {
        if (n.kind !== "fir" || !n.cluster_id || n.x === undefined) return;
        const b = (boxes[n.cluster_id] ||= { x: 0, n: 0, top: Infinity });
        b.x += n.x; b.n += 1; b.top = Math.min(b.top, n.y);
      });
      ctx.save();
      ctx.font = `bold ${13 / Math.min(scale, 1.4)}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      Object.entries(boxes).forEach(([id, b]) => {
        ctx.fillStyle = T.c("fg", active && active.group !== id ? 0.15 : 0.75);
        ctx.fillText(`Group ${id}`, b.x / b.n, b.top - 22 / Math.min(scale, 1.4));
      });
      ctx.restore();
      return;
    }
    const d = new Date(ax.min);
    d.setDate(1);
    ctx.save();
    ctx.font = `${11 / scale}px sans-serif`;
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    for (let t = d.getTime(); t <= ax.max; ) {
      const px = ax.x(Math.max(t, ax.min));
      ctx.strokeStyle = T.c("fg-subtle", 0.25);
      ctx.lineWidth = 1 / scale;
      ctx.beginPath(); ctx.moveTo(px, ax.top); ctx.lineTo(px, ax.bottom); ctx.stroke();
      ctx.fillStyle = T.subtle;
      ctx.fillText(new Date(t).toLocaleDateString("en-IN", { month: "short", year: "numeric" }), px + 4 / scale, ax.top);
      const next = new Date(t); next.setMonth(next.getMonth() + 1); t = next.getTime();
    }
    ctx.restore();
  }, [data, active, T]);

  const firs = data.nodes.filter((n) => n.kind === "fir");
  const identityTypes = [...new Set(data.nodes.filter((n) => n.kind === "identity").map((n) => n.identity_type))];
  const hasPattern = data.links.some((l) => l.kind === "PATTERN");
  const sel = selected;
  const selLinks = sel ? data.nodes.filter((n) => neighbours[sel.id]?.has(n.id)) : [];

  return (
    <div className="relative">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2 px-1">
        <div className="flex border border-ink-600 font-mono text-[11px] uppercase tracking-[0.06em]">
          {[["network", "Network view"], ["timeline", "Timeline view"]].map(([k, label]) => (
            <button key={k} onClick={() => { setMode(k); setSelected(null); }}
              className={`px-3 py-1.5 ${mode === k ? "bg-navy text-white" : "text-paper-300 hover:bg-ink-800"}`}>
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-4 text-xs text-paper-300">
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} /> labels</label>
          <button onClick={() => fgRef.current?.zoomToFit(600, 60)} className="btn btn-secondary btn-sm">Fit to screen</button>
        </div>
      </div>
      {mode === "timeline" ? (
        <div className="text-[11px] text-paper-500 px-1 mb-2">
          Left → right = date registered (month lines at the top). Each group reads top → bottom: the number in a case is its order in time (1 = first), and the diamonds show the evidence that carried over from one case to the next.
        </div>
      ) : null}

      <div ref={wrapRef} className="relative border border-ink-700 bg-ink-950">
        <ForceGraph2D
          onInstance={onInstance}
          graphData={data}
          width={width}
          height={height}
          backgroundColor={T.bg}
          nodeRelSize={6}
          nodeCanvasObject={drawNode}
          onRenderFramePre={(ctx, scale) => drawAxis(ctx, scale)}
          nodePointerAreaPaint={(node, color, ctx) => { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(node.x, node.y, 10, 0, 2 * Math.PI); ctx.fill(); }}
          linkColor={(l) => (linkLit(l) ? (l.kind === "PATTERN" ? PATTERN_COLOR : IDENTITY_COLOR[l.identity_type] || T.subtle) : T.c("fg-subtle", 0.15))}
          linkWidth={(l) => (l.kind === "PATTERN" ? 1.2 : linkLit(l) && active ? 3 : 2)}
          linkLineDash={(l) => (l.kind === "PATTERN" ? [5, 4] : null)}
          linkDirectionalParticles={(l) => (l.kind === "EVIDENCE" && linkLit(l) ? 2 : 0)}
          linkDirectionalParticleWidth={3}
          linkDirectionalParticleSpeed={0.006}
          linkDirectionalParticleColor={(l) => IDENTITY_COLOR[l.identity_type] || T.fg}
          onNodeHover={(n) => setHover(n || null)}
          onNodeClick={(n) => { setSelected(n); fgRef.current?.centerAt(n.x, n.y, 600); }}
          onBackgroundClick={() => setSelected(null)}
          cooldownTicks={mode === "timeline" ? 60 : 250}
          onEngineStop={() => { if (fitPending.current) { fitPending.current = false; fgRef.current?.zoomToFit(600, 80); } }}
          d3VelocityDecay={0.35}
        />

        <div className="absolute left-3 bottom-3 bg-ink-900/90 border border-ink-700 p-3 text-[11px] text-paper-300 space-y-1 max-w-[240px]">
          <div className="label mb-1">Legend</div>
          {Object.entries(CATEGORY).filter(([k]) => firs.some((f) => f.crime_major === k)).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2"><span className="inline-block w-3 h-3 rounded-full border-2" style={{ borderColor: v.color }} /> case: {v.label}</div>
          ))}
          {identityTypes.map((t) => (
            <div key={t} className="flex items-center gap-2"><span className="inline-block w-2.5 h-2.5 rotate-45" style={{ background: IDENTITY_COLOR[t] }} /> shared {IDENTITY_LABELS[t]?.toLowerCase() || t}</div>
          ))}
          <div className="flex items-center gap-2"><span className="inline-block w-5 border-t-2 border-paper-300" /> shared evidence</div>
          {hasPattern ? <div className="flex items-center gap-2"><span className="inline-block w-5 border-t-2 border-dashed border-signal-amber" /> similar story only (weak)</div> : null}
        </div>

        {sel ? (
          <div className="absolute right-3 top-3 w-72 bg-ink-900/95 border border-ink-600 p-4 text-xs space-y-2">
            <div className="flex justify-between items-start">
              <div className="text-paper-100 font-medium data-id">{sel.kind === "fir" ? sel.id : sel.label}</div>
              <button onClick={() => setSelected(null)} className="text-paper-500 hover:text-paper-100">✕</button>
            </div>
            {sel.kind === "fir" ? (
              <>
                <div className="text-paper-300">{sel.crime_minor_label}</div>
                <div className="text-paper-500">{sel.station} ({sel.district}) · {fmtDate(sel.registered_at)} · {fmtMoney(sel.amount)}</div>
                {sel.cluster_id ? <div className="text-paper-500">Group {sel.cluster_id} · case #{sel.order} in time order</div> : null}
                <div className="text-paper-300">{sel.summary}</div>
                <Link href={`/firs/${encodeURIComponent(sel.id)}`} className="inline-block link">Open case file ›</Link>
              </>
            ) : (
              <>
                <div className="text-paper-500">Shared {IDENTITY_LABELS[sel.identity_type]?.toLowerCase()} found in {selLinks.length} FIR(s):</div>
                {selLinks.sort((a, b) => (a.t || 0) - (b.t || 0)).map((f) => (
                  <Link key={f.id} href={`/firs/${encodeURIComponent(f.id)}`} className="block text-paper-300 hover:text-accent">
                    · {f.id} · {f.station} · {fmtDate(f.registered_at)}
                  </Link>
                ))}
              </>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
