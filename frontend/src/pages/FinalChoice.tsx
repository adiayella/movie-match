import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, TitleCard } from "../lib/api";

export default function FinalChoice() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [top5, setTop5] = useState<(TitleCard & { score: number })[]>([]);
  const [choosing, setChoosing] = useState(false);

  useEffect(() => {
    const stored = sessionStorage.getItem(`top5_${sessionId}`);
    if (stored) {
      setTop5(JSON.parse(stored));
    }
  }, [sessionId]);

  async function pick(tmdbId: number) {
    if (!sessionId) return;
    setChoosing(true);
    try {
      const resp = await api.finalize(sessionId, tmdbId);
      sessionStorage.setItem(
        `match_${sessionId}`,
        JSON.stringify({
          tmdb_id: resp.tmdb_id,
          title_info: {
            title: resp.title,
            year: resp.year,
            poster_url: resp.poster_url,
            synopsis: resp.synopsis,
          },
          ott_platforms: resp.ott_platforms,
        })
      );
      navigate(`/s/${sessionId}/match`);
    } finally {
      setChoosing(false);
    }
  }

  if (top5.length === 0) {
    return (
      <div className="center-col">
        <p>No shortlist found. Try swiping again from the start.</p>
      </div>
    );
  }

  return (
    <div>
      <h2>Neither round found a mutual match</h2>
      <p>Here are your top 5 closest picks — pick one together.</p>
      <div className="top5-list">
        {top5.map((t) => (
          <div className="card top5-item" key={t.tmdb_id}>
            {t.poster_url && <img src={t.poster_url} alt={t.title} />}
            <div style={{ flex: 1 }}>
              <h3>
                {t.title} {t.year ? `(${t.year})` : ""}
              </h3>
              <p>{t.score}/2 partners liked this</p>
              <button
                className="btn-primary"
                disabled={choosing}
                onClick={() => pick(t.tmdb_id)}
              >
                We'll watch this
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
