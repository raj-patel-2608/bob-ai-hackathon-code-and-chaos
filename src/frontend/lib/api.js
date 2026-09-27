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
  deleteBatch: (id) => request(`/api/batches/${id}`, { method: "DELETE" }),
  resetAll: () => request("/api/system/reset", { method: "POST" }),
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

export const fmtMoney = (n) => (n || n === 0 ? `₹${Number(n).toLocaleString("en-IN")}` : "—");
// compact Indian units for headline numbers: ₹14.22 Cr, ₹5.3 L
export const fmtMoneyShort = (n) => {
  if (!n && n !== 0) return "—";
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)} L`;
  return `₹${Number(n).toLocaleString("en-IN")}`;
};
export const fmtDate = (d) => (d ? new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—");
export const pct = (x) => (x || x === 0 ? `${Math.round(x * 100)}%` : "—");
