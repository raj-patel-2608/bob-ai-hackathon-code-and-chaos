import { api } from "../lib/api";

export default function ErrorBox({ error }) {
  if (!error) return null;
  const offline = /Failed to fetch|NetworkError/i.test(error);
  return (
    <div className="case-panel stripe-red p-5 text-sm text-paper-300">
      {offline ? (
        <>
          Could not reach the CrimeFIR API at <span className="data-id">{api.baseUrl}</span>. Start it from{" "}
          <span className="data-id">src/core_api</span> (see docs/setup-guide.md).
        </>
      ) : (
        error
      )}
    </div>
  );
}
