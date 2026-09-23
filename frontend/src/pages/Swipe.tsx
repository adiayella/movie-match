import { useCallback, useEffect, useRef, useState } from "react";
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
  const roundRef = useRef(round);
  roundRef.current = round;

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

  // Whoever finishes their deck first sits on "waiting for your partner",
  // and every transition out of it (match, round 2, final choice) is
  // triggered by the *other* device. Realtime alone is not enough to get
  // out of here -- if the socket never connects or drops, this screen
  // hangs forever. Poll the session as a safety net, and only react when
  // something actually changed so we don't reset the deck mid-swipe.
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;

    async function check() {
      try {
        const resp = await api.getSession(sessionId!, partner, getDeviceId());
        if (cancelled) return;
        if (resp.session.status === "matched") {
          navigate(`/s/${sessionId}/match`);
        } else if (resp.session.status === "final_choice") {
          navigate(`/s/${sessionId}/final`);
        } else if (resp.session.round !== roundRef.current) {
          setPool(resp.pool);
          setRound(resp.session.round);
        }
      } catch {
        // transient failure, next tick retries
      }
    }

    const interval = setInterval(check, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [sessionId, partner, navigate]);

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
      {/* keyed by round: a new round must reset the deck to card 0, otherwise
          the old index carries over and round 2 opens already "finished". */}
      <SwipeDeck key={round} cards={pool} onSwipe={handleSwipe} />
    </div>
  );
}
