"use client";

import ForceGraph2D from "react-force-graph-2d";

// next/dynamic does not forward refs; the graph instance is handed back through `onInstance` instead.
export default function ForceGraphClient({ onInstance, ...props }) {
  return <ForceGraph2D ref={onInstance} {...props} />;
}
