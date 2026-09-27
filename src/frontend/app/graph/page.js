"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import ErrorBox from "../../components/ErrorBox";
import ForceGraph from "../../components/ForceGraph";
import PageHeader from "../../components/PageHeader";
import { api, toForceGraph } from "../../lib/api";

function GraphInner() {
  const params = useSearchParams();
  const fir = params.get("fir");
  const cluster = params.get("cluster");
  const [includePattern, setIncludePattern] = useState(false);
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setGraph(null);
    api.graph({ fir_id: fir, cluster_id: cluster, include_pattern: includePattern })
      .then((g) => setGraph(toForceGraph(g, fir)))
      .catch((e) => setError(e.message));
  }, [fir, cluster, includePattern]);

  const firs = graph?.nodes.filter((n) => n.type === "FIR").length || 0;
  const identities = graph?.nodes.filter((n) => n.type === "ENTITY").length || 0;

  return (
    <div>
      <PageHeader eyebrow="Investigation graph"
        title={fir ? `Around ${fir}` : cluster ? `Cluster ${cluster}` : "All linked FIRs"}
        description="FIR nodes connect to the shared identifiers (bridge nodes) that link them. Dashed amber edges are pattern-only similarity, hidden by default. Scroll to zoom, drag to pan, click a node for details."
        action={
          <div className="flex items-center gap-3">
            <label className="text-xs text-paper-300 flex items-center gap-2">
              <input type="checkbox" checked={includePattern} onChange={(e) => setIncludePattern(e.target.checked)} />
              show pattern-only links
            </label>
            {fir || cluster ? <Link href="/graph" className="border border-signal-blue text-signal-blue text-xs px-3 py-2">Full graph</Link> : null}
          </div>
        } />
      <div className="p-8 space-y-4">
        <div className="text-xs text-paper-500">{firs} FIRs · {identities} shared identifiers</div>
        <ErrorBox error={error} />
        {!graph ? <div className="case-panel p-12 text-center text-sm text-paper-500">Building graph…</div>
          : graph.nodes.length === 0 ? <div className="case-panel p-8 text-sm text-paper-500">No links yet.</div>
          : <div className="case-panel p-2"><ForceGraph graph={graph} /></div>}
      </div>
    </div>
  );
}

export default function GraphPage() {
  return <Suspense fallback={<div className="p-8 text-sm text-paper-500">Loading…</div>}><GraphInner /></Suspense>;
}
