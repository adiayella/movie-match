import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useSessionRealtime } from "../lib/supabase";
import { api } from "../lib/api";
import { getPartnerForSession } from "../lib/identity";

export default function Waiting() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { status } = useSessionRealtime(sessionId ?? null);

  useEffect(() => {
    if (status === "swiping" && sessionId) {
      navigate(`/s/${sessionId}/swipe`);
    }
  }, [status, sessionId, navigate]);

  // Realtime only notifies of changes that happen *after* the subscription
  // connects, so also check current status directly (covers page loads/
  // reconnects that land after the transition already happened) and poll
  // as a safety net in case the realtime socket never delivers the event.
  useEffect(() => {
    if (!sessionId) return;
    const partner = getPartnerForSession(sessionId) || "A";
    let cancelled = false;

    async function check() {
      try {
        const resp = await api.getSession(sessionId!, partner);
        if (!cancelled && resp.session.status === "swiping") {
          navigate(`/s/${sessionId}/swipe`);
        }
      } catch {
        // ignore, will retry on next poll/realtime event
      }
    }

    check();
    const interval = setInterval(check, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [sessionId, navigate]);

  return (
    <div className="center-col">
      <div className="spinner" />
      <h2>Waiting for your partner...</h2>
      <p>Once you've both submitted your preferences, we'll build tonight's shortlist.</p>
    </div>
  );
}
