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
  const [lastValues, setLastValues] = useState<PreferenceFormValues | null>(null);

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

  async function submit(values: PreferenceFormValues) {
    if (!sessionId) return;
    setSubmitting(true);
    setError(null);
    setLastValues(values);
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
      if (resp.error) {
        // Both preferences were submitted but building tonight's shortlist
        // failed (e.g. TMDB unreachable) -- surface it instead of silently
        // leaving both partners stuck on "waiting" forever.
        setError(resp.error);
        return;
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

  if (error) {
    return (
      <div className="center-col">
        <h2>Couldn't build tonight's shortlist</h2>
        <p className="error-text">{error}</p>
        <button
          className="btn-primary"
          disabled={submitting}
          onClick={() => lastValues && submit(lastValues)}
        >
          {submitting ? "Retrying..." : "Try again"}
        </button>
      </div>
    );
  }

  return (
    <div>
      <h2>You've been invited to movie night</h2>
      <p>Tell us what you're in the mood for. Your partner won't see this until you both match.</p>
      <PreferenceForm onSubmit={submit} submitting={submitting} />
    </div>
  );
}
