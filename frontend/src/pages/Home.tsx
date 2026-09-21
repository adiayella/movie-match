import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { getPairId, setPairId, setPartnerForSession } from "../lib/identity";

export default function Home() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function startSession() {
    setLoading(true);
    setError(null);
    try {
      const existingPairId = getPairId();
      const resp = await api.createSession(existingPairId);
      setPairId(resp.pair_id);
      setPartnerForSession(resp.session_id, "A");
      navigate(`/s/${resp.session_id}/create`, { state: { session: resp } });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="center-col">
      <h1>Movie Match</h1>
      <p>
        Two people, one couch, zero arguments. Swipe together and find tonight's
        watch in seconds.
      </p>
      <button className="btn-primary" onClick={startSession} disabled={loading}>
        {loading ? "Starting..." : "Start a new movie night"}
      </button>
      {error && <p style={{ color: "var(--accent-dark)" }}>{error}</p>}
    </div>
  );
}
