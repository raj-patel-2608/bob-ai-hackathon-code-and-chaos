// Client for the CrimeFIR core API (src/core_api). All data comes from the backend; nothing is mocked.
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, { cache: "no-store", ...options });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (_) {
      /* keep statusText */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body ?? {}),
});

const qs = (params) => {
  const clean = Object.fromEntries(
    Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== "")
  );
  const s = new URLSearchParams(clean).toString();
  return s ? `?${s}` : "";
};

export const api = {
  baseUrl: BASE_URL,
  ready: () => request("/api/health/ready"),
  systemStatus: () => request("/api/system/status"),
  dashboard: () => request("/api/dashboard"),
  // ingestion
  uploadFile: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/batches", { method: "POST", body: form });
  },
  uploadText: (text) => request("/api/batches/text", json("POST", { text })),
  batches: () => request("/api/batches"),
  batch: (id) => request(`/api/batches/${id}`),
  retryBatch: (id) => request(`/api/batches/${id}/retry-failed`, json("POST")),
  // case files
  firs: (params) => request(`/api/firs${qs(params)}`),
  fir: (id) => request(`/api/firs/${encodeURIComponent(id)}`),
  related: (id) => request(`/api/firs/${encodeURIComponent(id)}/related`),
  review: (id, body) => request(`/api/firs/${encodeURIComponent(id)}/review`, json("POST", body)),
  stations: () => request("/api/stations"),
  // intelligence
  offenders: (params) => request(`/api/offenders${qs(params)}`),
  offender: (id) => request(`/api/offenders/${encodeURIComponent(id)}`),
  graph: (params) => request(`/api/graph${qs(params)}`),
  trends: (stationId, params) => request(`/api/stations/${stationId}/trends${qs(params)}`),
  reports: (stationId) => request(`/api/stations/${stationId}/reports`),
  createReport: (stationId, body) => request(`/api/stations/${stationId}/reports`, json("POST", body)),
  // quality
  evaluation: () => request("/api/evaluation/latest"),
  runEvaluation: (split) => request(`/api/evaluation/run${qs({ split })}`, { method: "POST" }),
};

// Adapts the API graph ({fir|identity} nodes, EVIDENCE/PATTERN edges) to the ForceGraph component's shape.
export function toForceGraph(graph, focusId) {
  const nodes = (graph?.nodes || []).map((n) =>
    n.type === "fir"
      ? {
          ...n,
          type: "FIR",
          label: n.id,
          crime_type: n.crime_minor_label || "Unclassified",
          date: n.registered_at ? n.registered_at.slice(0, 10) : "",
          is_focus: n.id === focusId,
        }
      : {
          id: n.id,
          type: "ENTITY",
          entity_type: n.identity_type,
          label: n.label,
          raw_value: n.label,
        }
  );
  const firCount = {};
  (graph?.edges || []).forEach((e) => {
    if (e.kind === "EVIDENCE") firCount[e.target] = (firCount[e.target] || 0) + 1;
  });
  nodes.forEach((n) => {
    if (n.type === "ENTITY") n.fir_count = firCount[n.id] || 0;
  });
  const edges = (graph?.edges || []).map((e) =>
    e.kind === "EVIDENCE"
      ? { source: e.source, target: e.target, relation: `HAS_${(e.identity_type || "ENTITY").toUpperCase()}` }
      : { source: e.source, target: e.target, relation: "POTENTIALLY_RELATED", score: e.score }
  );
  return { nodes, edges };
}

export const IDENTITY_LABELS = {
  phone: "Phone",
  bank_account: "Bank account",
  upi_id: "UPI ID",
  imei: "IMEI",
  vehicle: "Vehicle",
  online_handle: "Online handle",
  accused_name: "Accused name",
  accused_alias: "Accused alias",
  claimed_identity: "Claimed identity",
};

export const fmtMoney = (n) => (n || n === 0 ? `Rs ${Number(n).toLocaleString("en-IN")}` : "—");
export const fmtDate = (d) => (d ? new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—");
export const pct = (x) => (x || x === 0 ? `${Math.round(x * 100)}%` : "—");
