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
    // Arriving via the invite link/QR always means you're Partner B — set
    // this unconditionally. (Not "only if unset": if this browser also
    // created the session, e.g. someone testing solo in two tabs, the
    // creator's "A" would already be sitting in this session's shared
    // localStorage and must be overridden here, not preserved.)
    setPartnerForSession(sessionId, "B");
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
      // The backend decides the real slot (keyed by device_id) -- lock that
      // in rather than trusting our pre-submission guess. Two people both
      // arriving via this same join route (e.g. both just opened the
      // shared link) would otherwise both guess "B".
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
      <h2>You've been invited to movie night</h2>
      <p>Tell us what you're in the mood for. Your partner won't see this until you both match.</p>
      <PreferenceForm onSubmit={handleSubmit} submitting={submitting} />
      {error && <p style={{ color: "var(--accent-dark)" }}>{error}</p>}
    </div>
  );
}
