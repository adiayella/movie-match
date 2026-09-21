import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import SwipeDeck from "../components/SwipeDeck";
import { api, TitleCard } from "../lib/api";
import { getDeviceId, getPartnerForSession } from "../lib/identity";
import { useSessionRealtime } from "../lib/supabase";

export default function Swipe() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [pool, setPool] = useState<TitleCard[] | null>(null);
  const [round, setRound] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const { status, lastEvent } = useSessionRealtime(sessionId ?? null);

  const partner = sessionId ? getPartnerForSession(sessionId) || "A" : "A";

  const loadPool = useCallback(async () => {
    if (!sessionId) return;
    try {
      const resp = await api.getSession(sessionId, partner, getDeviceId());
      setPool(resp.pool);
      setRound(resp.session.round);
      if (resp.session.status === "matched") {
        navigate(`/s/${sessionId}/match`);
      } else if (resp.session.status === "final_choice") {
        navigate(`/s/${sessionId}/final`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load titles");
    }
  }, [sessionId, partner, navigate]);

  useEffect(() => {
    loadPool();
  }, [loadPool]);

  useEffect(() => {
    if (status === "matched" && sessionId) {
      navigate(`/s/${sessionId}/match`);
    } else if (status === "final_choice" && sessionId) {
      navigate(`/s/${sessionId}/final`);
    } else if (lastEvent === "session" && sessionId) {
      // round bumped by partner finishing before us; reload pool
      loadPool();
    }
  }, [status, lastEvent, sessionId, navigate, loadPool]);

  async function handleSwipe(card: TitleCard, direction: "left" | "right") {
    if (!sessionId) return;
    try {
      const resp = await api.submitSwipe(sessionId, {
        partner,
        tmdb_id: card.tmdb_id,
        round,
        direction,
        device_id: getDeviceId(),
      });
      if (resp.matched) {
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
      } else if (resp.final_choice) {
        sessionStorage.setItem(`top5_${sessionId}`, JSON.stringify(resp.top5 || []));
        navigate(`/s/${sessionId}/final`);
      } else if (resp.round_complete && resp.next_round) {
        loadPool();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to submit swipe");
    }
  }

  if (error) {
    return (
      <div className="center-col">
        <p style={{ color: "var(--accent-dark)" }}>{error}</p>
      </div>
    );
  }

  if (!pool) {
    return (
      <div className="center-col">
        <div className="spinner" />
        <p>Loading tonight's shortlist...</p>
      </div>
    );
  }

  return (
    <div>
      <h2>Round {round}</h2>
      <p>Swipe right if you'd watch it, left to pass.</p>
      <SwipeDeck cards={pool} onSwipe={handleSwipe} />
    </div>
  );
}
