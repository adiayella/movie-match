import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { getPairId, getPartnerForSession } from "../lib/identity";

export default function Rate() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [rating, setRating] = useState(0);
  const [submitted, setSubmitted] = useState(false);

  async function submitRating() {
    if (!sessionId || rating === 0) return;
    const pairId = getPairId();
    const stored = sessionStorage.getItem(`match_${sessionId}`);
    if (!pairId || !stored) {
      setSubmitted(true);
      return;
    }
    const parsed = JSON.parse(stored);
    const tmdbId = parsed?.tmdb_id;
    const partner = getPartnerForSession(sessionId) || "A";
    if (tmdbId) {
      await api.submitRating({ pair_id: pairId, tmdb_id: tmdbId, partner, rating });
    }
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <div className="center-col">
        <h2>Thanks!</h2>
        <p>Enjoy your movie night. We'll use this to get smarter next time.</p>
        <button className="btn-secondary" onClick={() => navigate("/")}>
          Back home
        </button>
      </div>
    );
  }

  return (
    <div className="center-col">
      <h2>How was it?</h2>
      <p>Rate tonight's pick (you can do this after watching too).</p>
      <div className="stars">
        {[1, 2, 3, 4, 5].map((n) => (
          <span
            key={n}
            className={`star ${n <= rating ? "filled" : ""}`}
            onClick={() => setRating(n)}
          >
            ★
          </span>
        ))}
      </div>
      <button className="btn-primary" onClick={submitRating} disabled={rating === 0}>
        Submit rating
      </button>
      <button className="btn-secondary" onClick={() => navigate("/")}>
        Skip
      </button>
    </div>
  );
}
