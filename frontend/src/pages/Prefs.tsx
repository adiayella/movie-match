import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PreferenceForm, { PreferenceFormValues } from "../components/PreferenceForm";
import { api } from "../lib/api";
import { getDeviceId, getPartnerForSession, setPartnerForSession } from "../lib/identity";

export default function Prefs() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(values: PreferenceFormValues) {
    if (!sessionId) return;
    setSubmitting(true);
    setError(null);
    try {
      const partner = getPartnerForSession(sessionId) || "A";
      const resp = await api.submitPreferences(sessionId, {
        partner,
        ...values,
        device_id: getDeviceId(),
      });
      // The backend decides the real slot (keyed by device_id) -- lock that
      // in rather than trusting our pre-submission guess.
      if (resp.partner) {
        setPartnerForSession(sessionId, resp.partner);
      }
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
      <h2>Your preferences</h2>
      <p>Fill this out independently — your partner is doing the same on their device.</p>
      <PreferenceForm onSubmit={handleSubmit} submitting={submitting} />
      {error && <p style={{ color: "var(--accent-dark)" }}>{error}</p>}
    </div>
  );
}
