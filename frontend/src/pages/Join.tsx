import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PreferenceForm, { PreferenceFormValues } from "../components/PreferenceForm";
import { api } from "../lib/api";
import { getDeviceId, getPartnerForSession, setPartnerForSession } from "../lib/identity";

export default function Join() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    const existing = getPartnerForSession(sessionId);
    if (!existing) {
      setPartnerForSession(sessionId, "B");
    }
    api.joinSession(sessionId).catch(() => {
      // session might already be past waiting_b, that's fine
    });
  }, [sessionId]);

  async function handleSubmit(values: PreferenceFormValues) {
    if (!sessionId) return;
    setSubmitting(true);
    setError(null);
    try {
      const partner = getPartnerForSession(sessionId) || "B";
      const resp = await api.submitPreferences(sessionId, {
        partner,
        ...values,
        device_id: getDeviceId(),
      });
      if (resp.status === "swiping") {
        navigate(`/s/${sessionId}/swipe`);
      } else {
        navigate(`/s/${sessionId}/waiting`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h2>You've been invited to movie night</h2>
      <p>Tell us what you're in the mood for. Your partner won't see this until you both match.</p>
      <PreferenceForm onSubmit={handleSubmit} submitting={submitting} />
      {error && <p style={{ color: "var(--accent-dark)" }}>{error}</p>}
    </div>
  );
}
