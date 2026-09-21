import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useSessionRealtime } from "../lib/supabase";

export default function Waiting() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { status } = useSessionRealtime(sessionId ?? null);

  useEffect(() => {
    if (status === "swiping" && sessionId) {
      navigate(`/s/${sessionId}/swipe`);
    }
  }, [status, sessionId, navigate]);

  return (
    <div className="center-col">
      <div className="spinner" />
      <h2>Waiting for your partner...</h2>
      <p>Once you've both submitted your preferences, we'll build tonight's shortlist.</p>
    </div>
  );
}
