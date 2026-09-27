import { api } from "../lib/api";

// Shows API errors in plain words. "Offline" is shown only when the API really could not be reached.
export default function ErrorBox({ error, onDismiss }) {
  if (!error) return null;
  const message = typeof error === "string" ? error : error.message;
  const offline = (typeof error === "object" && error.offline) || /Failed to fetch|NetworkError|network error/i.test(message);
  return (
    <div className="border border-signal-red/40 border-l-[3px] border-l-signal-red bg-signal-red/5 px-4 py-3 text-sm text-paper-100 flex items-start gap-3">
      <svg viewBox="0 0 24 24" className="w-5 h-5 shrink-0 text-signal-red mt-px" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v4m0 4h.01" /></svg>
      <div className="flex-1">
        {offline ? (
          <>
            <div className="font-medium">Cannot reach the CrimeFIR API</div>
            <div className="text-paper-300 text-xs mt-0.5">Check that the core API is running at <span className="data-id">{api.baseUrl}</span> (see docs/setup-guide.md), then try again.</div>
          </>
        ) : message}
      </div>
      {onDismiss ? <button onClick={onDismiss} className="text-paper-500 hover:text-paper-100" aria-label="Dismiss">✕</button> : null}
    </div>
  );
}
