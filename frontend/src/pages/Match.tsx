import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { api, OttPlatform } from "../lib/api";
import { getPartnerForSession } from "../lib/identity";

export default function Match() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [ott, setOtt] = useState<OttPlatform[]>([]);
  const [matchedTitle, setMatchedTitle] = useState<{
    title: string;
    year: number | null;
    poster_url: string | null;
    synopsis: string | null;
  } | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    const stored = sessionStorage.getItem(`match_${sessionId}`);
    if (stored) {
      const parsed = JSON.parse(stored);
      setMatchedTitle(parsed.title_info || null);
      setOtt(parsed.ott_platforms || []);
      return;
    }

    // Passive partner (didn't trigger the match) has no sessionStorage
    // hand-off, so fetch the match details the backend recorded.
    const partner = getPartnerForSession(sessionId) || "A";
    api
      .getSession(sessionId, partner)
      .then((resp) => {
        if (resp.match) {
          setMatchedTitle({
            title: resp.match.title,
            year: resp.match.year,
            poster_url: resp.match.poster_url,
            synopsis: resp.match.synopsis,
          });
          setOtt(resp.match.ott_platforms || []);
        }
      })
      .catch(() => {
        // leave the generic fallback message showing
      });
  }, [sessionId]);

  return (
    <div className="center-col">
      <motion.div
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 200, damping: 15 }}
      >
        <h1>It's a match!</h1>
      </motion.div>
      {matchedTitle ? (
        <div className="card" style={{ width: "100%" }}>
          {matchedTitle.poster_url && (
            <img
              src={matchedTitle.poster_url}
              alt={matchedTitle.title}
              style={{ width: "100%", borderRadius: 12, marginBottom: 12 }}
            />
          )}
          <h2>
            {matchedTitle.title} {matchedTitle.year ? `(${matchedTitle.year})` : ""}
          </h2>
          <p>{matchedTitle.synopsis}</p>
          <div className="ott-list">
            {ott.length === 0 && <p>No streaming info available right now.</p>}
            {ott.map((p) => (
              <a
                key={p.name}
                className="ott-pill"
                href={p.deep_link || "#"}
                target="_blank"
                rel="noreferrer"
              >
                {p.logo_url && <img src={p.logo_url} alt={p.name} />}
                {p.name}
              </a>
            ))}
          </div>
        </div>
      ) : (
        <p>You both liked the same title. Check the streaming options below.</p>
      )}
      <button
        className="btn-primary"
        onClick={() => navigate(`/s/${sessionId}/rate`)}
      >
        Continue
      </button>
    </div>
  );
}
