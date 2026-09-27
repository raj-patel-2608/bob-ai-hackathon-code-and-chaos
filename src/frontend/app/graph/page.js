"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import ErrorBox from "../../components/ErrorBox";
import InfoTip from "../../components/InfoTip";
import InvestigationGraph from "../../components/InvestigationGraph";
import PageHeader from "../../components/PageHeader";
import { api } from "../../lib/api";
import { GLOSSARY } from "../../lib/glossary";

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
      .then(setGraph).catch((e) => setError(e.message));
  }, [fir, cluster, includePattern]);

  const firs = graph?.nodes.filter((n) => n.type === "fir").length || 0;
  const identities = graph?.nodes.filter((n) => n.type === "identity").length || 0;

  return (
    <div>
      <PageHeader title={fir ? `Links around ${fir}` : cluster ? `Group ${cluster}` : "Link graph"}
        description="Circles are FIRs, diamonds are the evidence they share (phone, bank account, UPI ID, vehicle…). Hover to focus, click for details, scroll to zoom, drag to move. Switch to Timeline view to see which case came first and where the same evidence appeared next."
        action={
          <div className="flex items-center gap-3">
            <label className="text-xs text-paper-300 flex items-center gap-2">
              <input type="checkbox" checked={includePattern} onChange={(e) => setIncludePattern(e.target.checked)} />
              also show similar-story links <InfoTip text={GLOSSARY.patternLink} align="right" />
            </label>
            {fir || cluster ? <Link href="/graph" className="border border-signal-blue text-signal-blue text-xs px-3 py-2">Show all</Link> : null}
          </div>
        } />
      <div className="p-8 space-y-3">
        <div className="text-xs text-paper-500">{firs} FIRs · {identities} pieces of shared evidence</div>
        <ErrorBox error={error} />
        {!graph ? <div className="case-panel p-12 text-center text-sm text-paper-500">Building graph…</div>
          : graph.nodes.length === 0 ? <div className="case-panel p-8 text-sm text-paper-500">No linked FIRs yet.</div>
          : <div className="case-panel p-3"><InvestigationGraph graph={graph} focusId={fir} height={640} /></div>}
      </div>
    </div>
  );
}

export default function GraphPage() {
  return <Suspense fallback={<div className="p-8 text-sm text-paper-500">Loading…</div>}><GraphInner /></Suspense>;
}
