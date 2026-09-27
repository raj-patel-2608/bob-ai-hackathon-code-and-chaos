"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import Link from "next/link";
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
} from "d3-force";

// Color palettes for different entity types and link strengths
const ENTITY_CONFIG = {
  phone: {
    color: "#10B981", // Emerald
    label: "Phone",
    icon: (
      <svg className="w-3.5 h-3.5 inline-block" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
      </svg>
    ),
  },
  bank_account: {
    color: "#F59E0B", // Amber Gold
    label: "Bank Account",
    icon: (
      <svg className="w-3.5 h-3.5 inline-block" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="2" y="5" width="20" height="14" rx="2" />
        <line x1="2" y1="10" x2="22" y2="10" />
      </svg>
    ),
  },
  account: {
    color: "#F59E0B",
    label: "Bank Account",
    icon: (
      <svg className="w-3.5 h-3.5 inline-block" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="2" y="5" width="20" height="14" rx="2" />
        <line x1="2" y1="10" x2="22" y2="10" />
      </svg>
    ),
  },
  device: {
    color: "#8B5CF6", // Purple Violet
    label: "Device ID / IMEI",
    icon: (
      <svg className="w-3.5 h-3.5 inline-block" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="5" y="2" width="14" height="20" rx="2" />
        <line x1="12" y1="18" x2="12.01" y2="18" />
      </svg>
    ),
  },
  vehicle: {
    color: "#F97316", // Warm Coral
    label: "Vehicle",
    icon: (
      <svg className="w-3.5 h-3.5 inline-block" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.5 3c-.1.2-.1.4-.1.6v5.5c0 .6.4 1 1 1h2" />
        <circle cx="7" cy="17" r="2" />
        <circle cx="17" cy="17" r="2" />
      </svg>
    ),
  },
  accused_name: {
    color: "#EC4899", // Rose / Pink
    label: "Suspect",
    icon: (
      <svg className="w-3.5 h-3.5 inline-block" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
};
// identifier types produced by the CrimeFIR API
ENTITY_CONFIG.upi_id = { ...ENTITY_CONFIG.bank_account, label: "UPI ID" };
ENTITY_CONFIG.imei = { ...ENTITY_CONFIG.device, label: "IMEI" };
ENTITY_CONFIG.accused_alias = { ...ENTITY_CONFIG.accused_name, label: "Accused alias" };
ENTITY_CONFIG.online_handle = { ...ENTITY_CONFIG.device, color: "#06B6D4", label: "Online handle" };

const DEFAULT_ENTITY_COLOR = "#06B6D4"; // Cyan fallback

const EDGE_COLORS = {
  STRONGLY_RELATED: "#EF4444", // Crimson
  POTENTIALLY_RELATED: "#F59E0B", // Amber
};

export default function ForceGraph({ graph }) {
  const containerRef = useRef(null);
  const svgRef = useRef(null);

  // Pan & Zoom transform: { x, y, scale }
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Selected node / hover node
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [hoveredEdge, setHoveredEdge] = useState(null);
  const [tooltip, setTooltip] = useState(null);

  // Search & Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [nodeTypeFilter, setNodeTypeFilter] = useState("ALL"); // ALL, FIR, ENTITY
  const [strengthFilter, setStrengthFilter] = useState("ALL"); // ALL, STRONG
  const [categoryFilter, setCategoryFilter] = useState("ALL");

  // Node positions map for interactive dragging
  const [nodePositions, setNodePositions] = useState({});
  const [initialLayoutDone, setInitialLayoutDone] = useState(false);

  // Panning & Dragging refs to avoid laggy state updates during gestures
  const isPanningRef = useRef(false);
  const panStartRef = useRef({ x: 0, y: 0, transformX: 0, transformY: 0 });
  const draggedNodeRef = useRef(null);
  const dragStartPosRef = useRef({ x: 0, y: 0, hasMoved: false });

  // 1. Process graph structure and degrees
  const processedGraph = useMemo(() => {
    if (!graph || !graph.nodes || graph.nodes.length === 0) return null;

    const nodes = graph.nodes.map((n) => ({ ...n }));
    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    const links = graph.edges
      .filter((e) => nodeById.has(e.source) && nodeById.has(e.target))
      .map((e) => ({ ...e }));

    // Calculate degrees (number of connections)
    const degreeMap = new Map();
    links.forEach((l) => {
      degreeMap.set(l.source, (degreeMap.get(l.source) || 0) + 1);
      degreeMap.set(l.target, (degreeMap.get(l.target) || 0) + 1);
    });

    nodes.forEach((n) => {
      const deg = degreeMap.get(n.id) || 0;
      n.degree = deg;
      if (n.type === "FIR") {
        n.radius = Math.max(14, Math.min(26, 14 + deg * 2.2));
      } else {
        n.radius = Math.max(10, Math.min(20, 10 + deg * 1.6));
      }
    });

    // Unique crime categories for filter
    const categories = Array.from(
      new Set(
        nodes
          .filter((n) => n.type === "FIR" && n.crime_type)
          .map((n) => n.crime_type)
      )
    ).sort();

    return { nodes, links, nodeById, categories };
  }, [graph]);

  // 2. Initial Force simulation calculation
  const runLayoutSimulation = useCallback(() => {
    if (!processedGraph) return;

    const { nodes, links } = processedGraph;
    const simNodes = nodes.map((n) => ({
      ...n,
      x: n.x ?? (Math.random() - 0.5) * 600,
      y: n.y ?? (Math.random() - 0.5) * 400,
    }));
    const simLinks = links.map((l) => ({ ...l }));

    const sim = forceSimulation(simNodes)
      .force(
        "link",
        forceLink(simLinks)
          .id((d) => d.id)
          .distance((l) => (l.relation?.startsWith("HAS_") ? 80 : 160))
          .strength(0.6)
      )
      .force(
        "charge",
        forceManyBody()
          .strength((d) => (d.type === "FIR" ? -380 : -190))
          .distanceMax(650)
      )
      .force("center", forceCenter(0, 0))
      .force("collide", forceCollide((d) => (d.radius || 14) + 18))
      .stop();

    // 250 ticks for settled, stable layout
    for (let i = 0; i < 260; i++) sim.tick();

    const newPos = {};
    simNodes.forEach((n) => {
      newPos[n.id] = { x: n.x, y: n.y };
    });

    setNodePositions(newPos);
    setInitialLayoutDone(true);
  }, [processedGraph]);

  useEffect(() => {
    runLayoutSimulation();
  }, [runLayoutSimulation]);

  // 3. Auto-fit to viewport
  const fitToScreen = useCallback(() => {
    if (!containerRef.current || !processedGraph) return;
    const rect = containerRef.current.getBoundingClientRect();
    const width = rect.width || 900;
    const height = rect.height || 600;

    const positions = Object.values(nodePositions);
    if (positions.length === 0) {
      setTransform({ x: width / 2, y: height / 2, scale: 0.9 });
      return;
    }

    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity;
    positions.forEach((p) => {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    });

    const graphWidth = maxX - minX + 160;
    const graphHeight = maxY - minY + 160;
    const scaleX = (width - 80) / graphWidth;
    const scaleY = (height - 80) / graphHeight;
    const scale = Math.max(0.2, Math.min(1.4, Math.min(scaleX, scaleY)));

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    setTransform({
      x: width / 2 - centerX * scale,
      y: height / 2 - centerY * scale,
      scale,
    });
  }, [processedGraph, nodePositions]);

  // Run fitToScreen when initial layout completes
  useEffect(() => {
    if (initialLayoutDone) {
      const timer = setTimeout(() => fitToScreen(), 60);
      return () => clearTimeout(timer);
    }
  }, [initialLayoutDone, fitToScreen]);

  // Center on a specific node
  const centerOnNode = useCallback(
    (nodeId) => {
      const pos = nodePositions[nodeId];
      if (!pos || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      setTransform((prev) => ({
        ...prev,
        x: rect.width / 2 - pos.x * prev.scale,
        y: rect.height / 2 - pos.y * prev.scale,
      }));
    },
    [nodePositions]
  );

  // 4. Smooth Mouse Wheel Zoom (centered on cursor)
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheel = (e) => {
      e.preventDefault();
      const rect = container.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const factor = e.deltaY < 0 ? 1.15 : 0.87;
      setTransform((prev) => {
        const newScale = Math.min(Math.max(prev.scale * factor, 0.15), 4.0);
        const newX = mouseX - (mouseX - prev.x) * (newScale / prev.scale);
        const newY = mouseY - (mouseY - prev.y) * (newScale / prev.scale);
        return { x: newX, y: newY, scale: newScale };
      });
    };

    container.addEventListener("wheel", handleWheel, { passive: false });
    return () => container.removeEventListener("wheel", handleWheel);
  }, []);

  // 5. Canvas Pan Gestures
  const handleCanvasMouseDown = (e) => {
    // Only pan if clicking canvas background, not nodes or UI buttons
    if (e.target.closest(".graph-node") || e.target.closest(".graph-ui")) return;

    isPanningRef.current = true;
    panStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      transformX: transform.x,
      transformY: transform.y,
    };
  };

  const handleMouseMove = (e) => {
    // A. Handle node dragging
    if (draggedNodeRef.current && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const graphX = (e.clientX - rect.left - transform.x) / transform.scale;
      const graphY = (e.clientY - rect.top - transform.y) / transform.scale;

      const dx = e.clientX - dragStartPosRef.current.x;
      const dy = e.clientY - dragStartPosRef.current.y;
      if (Math.hypot(dx, dy) > 4) {
        dragStartPosRef.current.hasMoved = true;
      }

      const nodeId = draggedNodeRef.current;
      setNodePositions((prev) => ({
        ...prev,
        [nodeId]: { x: graphX, y: graphY },
      }));
      return;
    }

    // B. Handle canvas panning
    if (isPanningRef.current) {
      const dx = e.clientX - panStartRef.current.x;
      const dy = e.clientY - panStartRef.current.y;
      setTransform((prev) => ({
        ...prev,
        x: panStartRef.current.transformX + dx,
        y: panStartRef.current.transformY + dy,
      }));
    }
  };

  const handleMouseUp = () => {
    if (draggedNodeRef.current) {
      if (!dragStartPosRef.current.hasMoved) {
        // Was a simple click: select node
        const clicked = processedGraph?.nodeById.get(draggedNodeRef.current);
        setSelectedNode((prev) => (prev?.id === clicked?.id ? null : clicked));
      }
      draggedNodeRef.current = null;
    }
    isPanningRef.current = false;
  };

  // Node mouse down: start dragging
  const handleNodeMouseDown = (e, node) => {
    e.stopPropagation();
    draggedNodeRef.current = node.id;
    dragStartPosRef.current = { x: e.clientX, y: e.clientY, hasMoved: false };
  };

  // 6. Connected neighbors calculation for spotlight effect
  const activeFocusId = selectedNode?.id || hoveredNode?.id;

  const { connectedNodeIds, connectedEdgeIndices } = useMemo(() => {
    const nodeIds = new Set();
    const edgeIndices = new Set();

    if (!activeFocusId || !processedGraph) {
      return { connectedNodeIds: null, connectedEdgeIndices: null };
    }

    nodeIds.add(activeFocusId);
    processedGraph.links.forEach((l, idx) => {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;

      if (s === activeFocusId) {
        nodeIds.add(t);
        edgeIndices.add(idx);
      } else if (t === activeFocusId) {
        nodeIds.add(s);
        edgeIndices.add(idx);
      }
    });

    return { connectedNodeIds: nodeIds, connectedEdgeIndices: edgeIndices };
  }, [activeFocusId, processedGraph]);

  // 7. Filtering logic
  const filteredNodes = useMemo(() => {
    if (!processedGraph) return [];
    return processedGraph.nodes.filter((n) => {
      if (nodeTypeFilter === "FIR" && n.type !== "FIR") return false;
      if (nodeTypeFilter === "ENTITY" && n.type !== "ENTITY") return false;
      if (categoryFilter !== "ALL" && n.type === "FIR" && n.crime_type !== categoryFilter) {
        return false;
      }
      return true;
    });
  }, [processedGraph, nodeTypeFilter, categoryFilter]);

  const visibleNodeIds = useMemo(() => {
    return new Set(filteredNodes.map((n) => n.id));
  }, [filteredNodes]);

  const filteredLinks = useMemo(() => {
    if (!processedGraph) return [];
    return processedGraph.links.filter((l) => {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      if (!visibleNodeIds.has(s) || !visibleNodeIds.has(t)) return false;
      if (strengthFilter === "STRONG" && l.relation !== "STRONGLY_RELATED") {
        return false;
      }
      return true;
    });
  }, [processedGraph, visibleNodeIds, strengthFilter]);

  // Search match logic
  const searchMatches = useMemo(() => {
    if (!searchQuery.trim() || !processedGraph) return [];
    const q = searchQuery.toLowerCase().trim();
    return processedGraph.nodes.filter((n) => {
      return (
        n.id.toLowerCase().includes(q) ||
        (n.label && n.label.toLowerCase().includes(q)) ||
        (n.crime_type && n.crime_type.toLowerCase().includes(q)) ||
        (n.station && n.station.toLowerCase().includes(q)) ||
        (n.accused_name && n.accused_name.toLowerCase().includes(q))
      );
    });
  }, [searchQuery, processedGraph]);

  const searchMatchIds = useMemo(() => {
    return new Set(searchMatches.map((n) => n.id));
  }, [searchMatches]);

  // Jump to first search match
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchMatches.length > 0) {
      const target = searchMatches[0];
      setSelectedNode(target);
      centerOnNode(target.id);
    }
  };

  if (!processedGraph) {
    return (
      <div className="p-12 text-center text-paper-500 font-mono text-sm bg-ink-950 border border-ink-700">
        No graph intelligence available. Ingest FIRs to build relationships.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`relative select-none overflow-hidden bg-ink-950 border border-ink-700 transition-all ${
        isFullscreen
          ? "fixed inset-0 z-50 w-screen h-screen"
          : "w-full h-[680px] rounded-sm"
      }`}
      onMouseDown={handleCanvasMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* SVG Canvas */}
      <svg
        ref={svgRef}
        className="w-full h-full cursor-grab active:cursor-grabbing"
      >
        <defs>
          {/* Subtle blueprint grid pattern that scales/pans */}
          <pattern
            id="graph-grid"
            width={40 * transform.scale}
            height={40 * transform.scale}
            patternUnits="userSpaceOnUse"
            patternTransform={`translate(${transform.x % (40 * transform.scale)},${
              transform.y % (40 * transform.scale)
            })`}
          >
            <circle cx="2" cy="2" r="1" fill="#212A30" opacity="0.6" />
          </pattern>

          {/* Glowing neon drop shadows for relationships */}
          <filter id="glow-red" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#EF4444" floodOpacity="0.8" />
          </filter>
          <filter id="glow-cyan" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#00F0FF" floodOpacity="0.9" />
          </filter>
          <filter id="glow-gold" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="3.5" floodColor="#F59E0B" floodOpacity="0.85" />
          </filter>
        </defs>

        {/* Blueprint Grid Background */}
        <rect width="100%" height="100%" fill="#0B1012" />
        <rect width="100%" height="100%" fill="url(#graph-grid)" />

        {/* Main Graph Content Group */}
        <g transform={`translate(${transform.x},${transform.y}) scale(${transform.scale})`}>
          {/* 1. EDGES */}
          <g className="edges-layer">
            {filteredLinks.map((l, i) => {
              const sId = typeof l.source === "object" ? l.source.id : l.source;
              const tId = typeof l.target === "object" ? l.target.id : l.target;
              const s = nodePositions[sId];
              const t = nodePositions[tId];
              if (!s || !t) return null;

              const isConnected =
                !connectedEdgeIndices || connectedEdgeIndices.has(i);
              const isFirLink = !l.relation?.startsWith("HAS_");
              const isStrong = l.relation === "STRONGLY_RELATED";

              let strokeColor = "#334155";
              let strokeWidth = 1.2;
              let dashArray = "none";
              let filter = "none";

              if (isFirLink) {
                strokeColor = EDGE_COLORS[l.relation] || "#4C7EA8";
                strokeWidth = isStrong ? 2.6 : 1.8;
                if (isStrong && isConnected) filter = "url(#glow-red)";
              } else {
                strokeColor = "#475569";
                dashArray = "3,3";
              }

              const edgeOpacity =
                connectedNodeIds && !isConnected ? 0.12 : isFirLink ? 0.9 : 0.6;

              const midX = (s.x + t.x) / 2;
              const midY = (s.y + t.y) / 2;

              return (
                <g
                  key={`edge-${i}`}
                  opacity={edgeOpacity}
                  className="transition-opacity duration-200 cursor-pointer"
                  onMouseEnter={(e) => {
                    setHoveredEdge(l);
                    const rect = containerRef.current.getBoundingClientRect();
                    setTooltip({
                      x: e.clientX - rect.left,
                      y: e.clientY - rect.top,
                      title: isFirLink
                        ? `${isStrong ? "STRONGLY RELATED" : "POTENTIALLY RELATED"} (${Math.round(
                            l.score * 100
                          )}%)`
                        : `SHARED ENTITY LINK`,
                      subtitle: `${sId} ⟷ ${tId}`,
                      meta: l.signals
                        ? `Evidence: ${Object.keys(l.signals).join(", ")}`
                        : l.relation,
                    });
                  }}
                  onMouseLeave={() => {
                    setHoveredEdge(null);
                    setTooltip(null);
                  }}
                >
                  <line
                    x1={s.x}
                    y1={s.y}
                    x2={t.x}
                    y2={t.y}
                    stroke={strokeColor}
                    strokeWidth={strokeWidth}
                    strokeDasharray={dashArray}
                    filter={filter}
                  />

                  {/* Midpoint score badge on FIR relationship links */}
                  {isFirLink && l.score && transform.scale > 0.6 && (
                    <g transform={`translate(${midX},${midY})`}>
                      <rect
                        x="-16"
                        y="-8"
                        width="32"
                        height="16"
                        rx="8"
                        fill="#10161A"
                        stroke={strokeColor}
                        strokeWidth="1"
                      />
                      <text
                        x="0"
                        y="3.5"
                        textAnchor="middle"
                        fontSize="9"
                        fontWeight="600"
                        fill={strokeColor}
                        className="font-mono select-none"
                      >
                        {Math.round(l.score * 100)}%
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </g>

          {/* 2. NODES */}
          <g className="nodes-layer">
            {filteredNodes.map((n) => {
              const pos = nodePositions[n.id];
              if (!pos) return null;

              const isFIR = n.type === "FIR";
              const isSelected = selectedNode?.id === n.id;
              const isHovered = hoveredNode?.id === n.id;
              const isFocus = n.is_focus;
              const isSearchMatch = searchMatchIds.has(n.id);
              const isConnected =
                !connectedNodeIds || connectedNodeIds.has(n.id);

              const opacity = connectedNodeIds && !isConnected ? 0.15 : 1;

              // Node color determination
              let fillColor = "#10161A";
              let strokeColor = "#3B82F6"; // FIR default
              let textColor = "#E9ECEC";

              if (isFIR) {
                strokeColor = isFocus ? "#00F0FF" : "#3B82F6";
              } else {
                const conf = ENTITY_CONFIG[n.entity_type] || {
                  color: DEFAULT_ENTITY_COLOR,
                };
                strokeColor = conf.color;
              }

              if (isSearchMatch) {
                strokeColor = "#F59E0B";
              }

              const r = n.radius || (isFIR ? 16 : 12);

              return (
                <g
                  key={n.id}
                  transform={`translate(${pos.x},${pos.y})`}
                  opacity={opacity}
                  className="graph-node cursor-pointer transition-opacity duration-200"
                  onMouseDown={(e) => handleNodeMouseDown(e, n)}
                  onMouseEnter={(e) => {
                    setHoveredNode(n);
                    const rect = containerRef.current.getBoundingClientRect();
                    setTooltip({
                      x: e.clientX - rect.left,
                      y: e.clientY - rect.top,
                      title: isFIR ? n.id : `${n.entity_type?.toUpperCase()}: ${n.label}`,
                      subtitle: isFIR
                        ? `${n.crime_type || "Unclassified"} • ${n.station || "Police Station"}`
                        : `Shared across ${n.fir_count || n.degree || 2} police cases`,
                      meta: isFIR
                        ? n.summary ? n.summary.slice(0, 110) + "…" : `Date: ${n.date || "N/A"}`
                        : "Click to inspect syndicate bridges",
                    });
                  }}
                  onMouseLeave={() => {
                    setHoveredNode(null);
                    setTooltip(null);
                  }}
                >
                  {/* Glowing halo when selected, hovered, or search match */}
                  {(isSelected || isHovered || isFocus || isSearchMatch) && (
                    <circle
                      r={r + 6}
                      fill="none"
                      stroke={isSearchMatch ? "#F59E0B" : isFocus ? "#00F0FF" : strokeColor}
                      strokeWidth="2.5"
                      opacity="0.8"
                      filter={
                        isSearchMatch
                          ? "url(#glow-gold)"
                          : isFocus
                          ? "url(#glow-cyan)"
                          : undefined
                      }
                      className={isFocus ? "animate-pulse" : ""}
                    />
                  )}

                  {/* Main Circle Body */}
                  <circle
                    r={r}
                    fill={fillColor}
                    stroke={strokeColor}
                    strokeWidth={isSelected ? 3 : 2}
                  />

                  {/* Inner glyph or text */}
                  {isFIR ? (
                    <text
                      textAnchor="middle"
                      dy="3.5"
                      fontSize={r > 18 ? "11" : "9"}
                      fontWeight="bold"
                      fill={strokeColor}
                      className="font-mono select-none pointer-events-none"
                    >
                      {n.degree > 0 ? n.degree : "FIR"}
                    </text>
                  ) : (
                    <circle
                      r={r * 0.45}
                      fill={strokeColor}
                      className="pointer-events-none"
                    />
                  )}

                  {/* Label underneath node with dark badge for high contrast */}
                  {(transform.scale > 0.5 || isSelected || isHovered || isSearchMatch || isFocus) && (
                    <g transform={`translate(0, ${r + 14})`}>
                      <rect
                        x={-(Math.max(n.label.length * 3.6, 24) + 6)}
                        y="-9"
                        width={Math.max(n.label.length * 7.2, 48) + 12}
                        height="17"
                        rx="4"
                        fill="#0B1012"
                        fillOpacity="0.85"
                        stroke="#212A30"
                        strokeWidth="0.8"
                      />
                      <text
                        x="0"
                        y="3"
                        textAnchor="middle"
                        fontSize={isFIR ? 10 : 9}
                        fontWeight={isFIR ? "600" : "400"}
                        fill={isFIR ? "#E9ECEC" : strokeColor}
                        className="font-mono select-none pointer-events-none"
                      >
                        {n.label.length > 20 ? n.label.slice(0, 18) + "…" : n.label}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </g>
        </g>
      </svg>

      {/* 8. TOP CONTROL & SEARCH TOOLBAR */}
      <div className="graph-ui absolute top-3 left-3 right-3 flex flex-wrap items-center justify-between gap-3 pointer-events-none">
        {/* Left: Search input */}
        <form
          onSubmit={handleSearchSubmit}
          className="pointer-events-auto flex items-center bg-ink-900/90 backdrop-blur border border-ink-700 px-3 py-1.5 rounded shadow-lg text-xs"
        >
          <svg className="w-3.5 h-3.5 text-paper-500 mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            placeholder="Search FIR, phone, bank account, suspect…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent text-paper-100 placeholder-paper-500 outline-none w-56 md:w-72 font-mono text-xs"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="text-paper-500 hover:text-paper-100 ml-1"
            >
              ✕
            </button>
          )}
          {searchMatches.length > 0 && (
            <span className="ml-2 px-1.5 py-0.5 rounded bg-amber-500/20 text-signal-amber font-mono text-[10px]">
              {searchMatches.length} match{searchMatches.length > 1 ? "es" : ""}
            </span>
          )}
        </form>

        {/* Right: Filter Buttons */}
        <div className="pointer-events-auto flex items-center gap-1.5 bg-ink-900/90 backdrop-blur border border-ink-700 p-1 rounded shadow-lg text-xs">
          <button
            onClick={() => setNodeTypeFilter("ALL")}
            className={`px-2.5 py-1 rounded text-xs font-mono transition-colors ${
              nodeTypeFilter === "ALL"
                ? "bg-signal-blue text-white"
                : "text-paper-500 hover:text-paper-100"
            }`}
          >
            All ({processedGraph.nodes.length})
          </button>
          <button
            onClick={() => setNodeTypeFilter("FIR")}
            className={`px-2.5 py-1 rounded text-xs font-mono transition-colors ${
              nodeTypeFilter === "FIR"
                ? "bg-signal-blue text-white"
                : "text-paper-500 hover:text-paper-100"
            }`}
          >
            Cases ({processedGraph.nodes.filter((n) => n.type === "FIR").length})
          </button>
          <button
            onClick={() => setNodeTypeFilter("ENTITY")}
            className={`px-2.5 py-1 rounded text-xs font-mono transition-colors ${
              nodeTypeFilter === "ENTITY"
                ? "bg-signal-amber text-ink-950 font-semibold"
                : "text-paper-500 hover:text-paper-100"
            }`}
          >
            Entities ({processedGraph.nodes.filter((n) => n.type === "ENTITY").length})
          </button>

          <div className="w-[1px] h-4 bg-ink-700 mx-1" />

          {/* Crime Category filter */}
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="bg-ink-950 border border-ink-700 text-paper-300 text-xs px-2 py-1 rounded outline-none"
          >
            <option value="ALL">All Crime Categories</option>
            {processedGraph.categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          <button
            onClick={() =>
              setStrengthFilter((prev) => (prev === "ALL" ? "STRONG" : "ALL"))
            }
            className={`px-2.5 py-1 rounded text-xs font-mono transition-colors border ${
              strengthFilter === "STRONG"
                ? "border-signal-red bg-signal-red/20 text-signal-red font-semibold"
                : "border-transparent text-paper-500 hover:text-paper-100"
            }`}
          >
            Strong Ties Only
          </button>
        </div>
      </div>

      {/* 9. FLOATING ZOOM & VIEW CONTROLS (BOTTOM-RIGHT) */}
      <div className="graph-ui absolute bottom-4 right-4 flex flex-col items-end gap-2 pointer-events-auto">
        {/* Zoom & Fit Toolbar */}
        <div className="flex items-center gap-1 bg-ink-900/90 backdrop-blur border border-ink-700 p-1 rounded shadow-xl text-paper-300 text-xs font-mono">
          <button
            onClick={() =>
              setTransform((prev) => ({
                ...prev,
                scale: Math.min(prev.scale * 1.25, 4.0),
              }))
            }
            title="Zoom In (+)"
            className="w-8 h-8 flex items-center justify-center rounded hover:bg-ink-700 hover:text-paper-100 transition-colors"
          >
            +
          </button>
          <span className="px-2 text-[11px] text-paper-500 min-w-[46px] text-center">
            {Math.round(transform.scale * 100)}%
          </span>
          <button
            onClick={() =>
              setTransform((prev) => ({
                ...prev,
                scale: Math.max(prev.scale * 0.8, 0.15),
              }))
            }
            title="Zoom Out (-)"
            className="w-8 h-8 flex items-center justify-center rounded hover:bg-ink-700 hover:text-paper-100 transition-colors"
          >
            −
          </button>
          <div className="w-[1px] h-4 bg-ink-700 mx-0.5" />
          <button
            onClick={fitToScreen}
            title="Fit graph to view"
            className="px-2.5 h-8 flex items-center gap-1 rounded hover:bg-ink-700 hover:text-paper-100 transition-colors"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
            </svg>
            Fit
          </button>
          <button
            onClick={runLayoutSimulation}
            title="Untangle / Re-layout physics"
            className="px-2.5 h-8 flex items-center gap-1 rounded hover:bg-ink-700 hover:text-paper-100 transition-colors"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
            </svg>
            Untangle
          </button>
          <div className="w-[1px] h-4 bg-ink-700 mx-0.5" />
          <button
            onClick={() => setIsFullscreen((prev) => !prev)}
            title="Toggle Fullscreen"
            className="w-8 h-8 flex items-center justify-center rounded hover:bg-ink-700 hover:text-paper-100 transition-colors"
          >
            {isFullscreen ? "✕" : "⤢"}
          </button>
        </div>
      </div>

      {/* 10. INTERACTIVE LEGEND (BOTTOM-LEFT) */}
      <div className="graph-ui absolute bottom-4 left-4 bg-ink-900/90 backdrop-blur border border-ink-700 p-2.5 rounded shadow-xl text-xs text-paper-300 pointer-events-auto">
        <div className="text-[10px] uppercase font-mono tracking-wider text-paper-500 mb-1.5">
          Entity Legend & Indicators
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-signal-blue border border-blue-400" />
            FIR Case
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#10B981]" />
            Phone
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#F59E0B]" />
            Bank Account
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#8B5CF6]" />
            Device / IMEI
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#F97316]" />
            Vehicle Plate
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#EC4899]" />
            Suspect Name
          </span>
          <span className="flex items-center gap-1.5 col-span-2 pt-1 border-t border-ink-700">
            <span className="w-4 h-0.5 bg-signal-red inline-block mr-1" />
            Strong (Score ≥ 70%)
            <span className="w-4 h-0.5 bg-[#8A6A2F] inline-block ml-2 mr-1" />
            Potential
          </span>
        </div>
      </div>

      {/* 11. HOVER TOOLTIP */}
      {tooltip && (
        <div
          className="pointer-events-none absolute z-40 max-w-xs bg-ink-900/95 backdrop-blur border border-ink-600 p-2.5 rounded shadow-2xl text-xs text-paper-100"
          style={{
            left: Math.min(tooltip.x + 16, (containerRef.current?.clientWidth || 900) - 280),
            top: Math.min(tooltip.y + 16, (containerRef.current?.clientHeight || 600) - 120),
          }}
        >
          <div className="font-mono font-semibold text-paper-100 mb-0.5">{tooltip.title}</div>
          <div className="text-[11px] text-paper-300 mb-1">{tooltip.subtitle}</div>
          {tooltip.meta && <div className="text-[10px] text-paper-500 font-mono">{tooltip.meta}</div>}
        </div>
      )}

      {/* 12. SIDE INSPECTOR DRAWER (WHEN NODE IS SELECTED) */}
      {selectedNode && (
        <div className="graph-ui absolute top-0 right-0 w-84 md:w-96 h-full bg-ink-900/95 backdrop-blur border-l border-ink-700 p-5 shadow-2xl z-30 overflow-y-auto pointer-events-auto">
          <div className="flex items-start justify-between mb-4 pb-3 border-b border-ink-700">
            <div>
              <span className="text-[10px] uppercase font-mono tracking-wider px-2 py-0.5 rounded bg-ink-800 border border-ink-600 text-paper-300">
                {selectedNode.type === "FIR" ? "CRIME CASE DOSSIER" : `SHARED ${selectedNode.entity_type?.toUpperCase()}`}
              </span>
              <h3 className="font-mono text-base font-semibold text-paper-100 mt-2">
                {selectedNode.label}
              </h3>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-paper-500 hover:text-paper-100 p-1 text-base font-mono"
            >
              ✕
            </button>
          </div>

          {selectedNode.type === "FIR" ? (
            <div className="space-y-4 text-xs">
              <div className="bg-ink-950 p-3 border border-ink-700 rounded">
                <div className="text-paper-500 text-[10px] uppercase font-mono mb-1">Classification</div>
                <div className="text-paper-100 font-medium mb-2">{selectedNode.crime_type || "Unclassified"}</div>
                <div className="grid grid-cols-2 gap-2 text-paper-300 text-[11px] font-mono">
                  <div>Station: {selectedNode.station || "N/A"}</div>
                  <div>Date: {selectedNode.date || "N/A"}</div>
                </div>
              </div>

              {selectedNode.summary && (
                <div>
                  <div className="text-paper-500 text-[10px] uppercase font-mono mb-1">Case Narrative</div>
                  <p className="text-paper-300 leading-relaxed bg-ink-950 p-3 border border-ink-700 rounded text-[11px]">
                    {selectedNode.summary}
                  </p>
                </div>
              )}

              {/* Action: Open Full FIR Dossier */}
              <Link
                href={`/firs/${encodeURIComponent(selectedNode.id)}`}
                className="block text-center bg-signal-blue hover:bg-blue-600 text-white font-mono text-xs py-2 px-3 rounded font-medium transition-colors"
              >
                Open Complete Case File ↗
              </Link>

              {/* Connected Shared Entities */}
              <div>
                <div className="text-paper-500 text-[10px] uppercase font-mono mb-2">
                  Connected Shared Entities
                </div>
                <div className="space-y-1.5">
                  {processedGraph.links
                    .filter((l) => {
                      const s = typeof l.source === "object" ? l.source.id : l.source;
                      const t = typeof l.target === "object" ? l.target.id : l.target;
                      return (s === selectedNode.id || t === selectedNode.id) && l.relation?.startsWith("HAS_");
                    })
                    .map((l, idx) => {
                      const entityId = (typeof l.source === "object" ? l.source.id : l.source) === selectedNode.id
                        ? (typeof l.target === "object" ? l.target.id : l.target)
                        : (typeof l.source === "object" ? l.source.id : l.source);
                      const entNode = processedGraph.nodeById.get(entityId);
                      return (
                        <div
                          key={`entity-item-${idx}`}
                          onClick={() => {
                            if (entNode) {
                              setSelectedNode(entNode);
                              centerOnNode(entNode.id);
                            }
                          }}
                          className="flex items-center justify-between p-2 bg-ink-950 hover:bg-ink-800 border border-ink-700 rounded cursor-pointer transition-colors"
                        >
                          <span className="font-mono text-paper-200">{entNode?.label || entityId}</span>
                          <span className="text-[10px] uppercase text-signal-amber font-mono">
                            {entNode?.entity_type}
                          </span>
                        </div>
                      );
                    })}
                </div>
              </div>

              {/* Connected Similar Cases */}
              <div>
                <div className="text-paper-500 text-[10px] uppercase font-mono mb-2">
                  Linked Cases ({processedGraph.links.filter((l) => {
                    const s = typeof l.source === "object" ? l.source.id : l.source;
                    const t = typeof l.target === "object" ? l.target.id : l.target;
                    return (s === selectedNode.id || t === selectedNode.id) && !l.relation?.startsWith("HAS_");
                  }).length})
                </div>
                <div className="space-y-2">
                  {processedGraph.links
                    .filter((l) => {
                      const s = typeof l.source === "object" ? l.source.id : l.source;
                      const t = typeof l.target === "object" ? l.target.id : l.target;
                      return (s === selectedNode.id || t === selectedNode.id) && !l.relation?.startsWith("HAS_");
                    })
                    .map((l, idx) => {
                      const otherId = (typeof l.source === "object" ? l.source.id : l.source) === selectedNode.id
                        ? (typeof l.target === "object" ? l.target.id : l.target)
                        : (typeof l.source === "object" ? l.source.id : l.source);
                      const otherNode = processedGraph.nodeById.get(otherId);
                      const isStrong = l.relation === "STRONGLY_RELATED";
                      return (
                        <div
                          key={`case-item-${idx}`}
                          onClick={() => {
                            if (otherNode) {
                              setSelectedNode(otherNode);
                              centerOnNode(otherNode.id);
                            }
                          }}
                          className="p-2.5 bg-ink-950 hover:bg-ink-800 border border-ink-700 rounded cursor-pointer transition-colors"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono font-semibold text-paper-100">{otherId}</span>
                            <span
                              className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                                isStrong
                                  ? "border-signal-red text-signal-red bg-signal-red/10"
                                  : "border-signal-amber text-signal-amber bg-signal-amber/10"
                              }`}
                            >
                              {Math.round((l.score || 0.7) * 100)}% match
                            </span>
                          </div>
                          <div className="text-[11px] text-paper-500">
                            {otherNode?.crime_type || "Linked case"} • {otherNode?.station}
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>
            </div>
          ) : (
            /* Entity Node View */
            <div className="space-y-4 text-xs">
              <div className="bg-ink-950 p-3 border border-ink-700 rounded">
                <div className="text-paper-500 text-[10px] uppercase font-mono mb-1">Bridge Entity</div>
                <div className="text-signal-amber font-mono font-semibold text-sm mb-2">{selectedNode.label}</div>
                <div className="text-[11px] text-paper-300">
                  Detected across <strong className="text-paper-100">{selectedNode.fir_count || selectedNode.degree || 2}</strong> separate police complaints.
                </div>
              </div>

              {/* Linked FIRs list */}
              <div>
                <div className="text-paper-500 text-[10px] uppercase font-mono mb-2">
                  Cases Linking to This Entity
                </div>
                <div className="space-y-2">
                  {processedGraph.links
                    .filter((l) => {
                      const s = typeof l.source === "object" ? l.source.id : l.source;
                      const t = typeof l.target === "object" ? l.target.id : l.target;
                      return (s === selectedNode.id || t === selectedNode.id) && l.relation?.startsWith("HAS_");
                    })
                    .map((l, idx) => {
                      const firId = (typeof l.source === "object" ? l.source.id : l.source) === selectedNode.id
                        ? (typeof l.target === "object" ? l.target.id : l.target)
                        : (typeof l.source === "object" ? l.source.id : l.source);
                      const firNode = processedGraph.nodeById.get(firId);
                      return (
                        <div
                          key={`ent-fir-${idx}`}
                          onClick={() => {
                            if (firNode) {
                              setSelectedNode(firNode);
                              centerOnNode(firNode.id);
                            }
                          }}
                          className="p-2.5 bg-ink-950 hover:bg-ink-800 border border-ink-700 rounded cursor-pointer transition-colors"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono font-semibold text-paper-100">{firId}</span>
                            <span className="text-[10px] text-paper-500 font-mono">{firNode?.date}</span>
                          </div>
                          <div className="text-[11px] text-paper-300">{firNode?.crime_type || "Complaint"}</div>
                          <div className="text-[10px] text-paper-500 font-mono mt-0.5">{firNode?.station}</div>
                        </div>
                      );
                    })}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
