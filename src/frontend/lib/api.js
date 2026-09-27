// Client for the CrimeFIR core API (src/core_api). All data comes from the backend; nothing is mocked.
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(message, status, offline = false) {
    super(message);
    this.status = status;
    this.offline = offline;
  }
}

function errorFromBody(status, text, fallback) {
  let detail = fallback;
  try {
    const body = JSON.parse(text);
    detail = typeof body.detail === "string" ? body.detail
      : Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join("; ") : JSON.stringify(body.detail);
  } catch (_) { /* keep fallback */ }
  if (status >= 500 && !detail) detail = "The server had a problem. Please try again.";
  return new ApiError(detail || `Request failed (${status})`, status);
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, { cache: "no-store", ...options });
  } catch (_) {
    throw new ApiError("Failed to fetch", 0, true);
  }
  if (!res.ok) throw errorFromBody(res.status, await res.text(), res.statusText);
  return res.json();
}

/**
 * Upload with real progress. Returns { promise, abort }.
 * onProgress({ loaded, total, percent, rate, remainingS }) is called while the bytes are sent.
 */
function uploadWithProgress(file, onProgress) {
  const xhr = new XMLHttpRequest();
  const started = performance.now();
  const promise = new Promise((resolve, reject) => {
    xhr.open("POST", `${BASE_URL}/api/batches`);
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      const seconds = Math.max((performance.now() - started) / 1000, 0.001);
      const rate = e.loaded / seconds;
      onProgress?.({ loaded: e.loaded, total: e.total, percent: (e.loaded / e.total) * 100, rate,
        remainingS: rate > 0 ? (e.total - e.loaded) / rate : null });
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)); } catch (_) { reject(new ApiError("Unexpected response from the server", xhr.status)); }
      } else reject(errorFromBody(xhr.status, xhr.responseText, xhr.statusText));
    };
    xhr.onerror = () => reject(new ApiError("Failed to fetch", 0, true));
    xhr.onabort = () => { const e = new ApiError("Upload cancelled", 0); e.cancelled = true; reject(e); };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
  return { promise, abort: () => xhr.abort() };
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
  uploadWithProgress,
  uploadText: (text) => request("/api/batches/text", json("POST", { text })),
  batches: () => request("/api/batches?limit=50"),
  batch: (id) => request(`/api/batches/${id}`),
  cancelBatch: (id) => request(`/api/batches/${id}/cancel`, { method: "POST" }),
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
export const fmtBytes = (n) => {
  if (!n && n !== 0) return "—";
  if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${n} B`;
};
export const fmtDuration = (s) => {
  if (s === null || s === undefined || !Number.isFinite(s)) return "—";
  s = Math.max(0, Math.round(s));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, "0")}s`;
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
};
export const fmtDateTime = (d) => (d ? new Date(d.endsWith?.("Z") || /[+-]\d\d:\d\d$/.test(d) ? d : `${d}Z`)
  .toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");
export const pct =(x) => (x || x === 0 ? `${Math.round(x * 100)}%` : "—");
