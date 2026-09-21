import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { CreateSessionResponse } from "../lib/api";
import { setPartnerForSession } from "../lib/identity";

export default function CreateShare() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [session, setSession] = useState<CreateSessionResponse | null>(
    (location.state as { session?: CreateSessionResponse } | null)?.session ?? null
  );
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (sessionId) {
      setPartnerForSession(sessionId, "A");
    }
  }, [sessionId]);

  if (!session) {
    return (
      <div className="center-col">
        <p>
          Session info not found. If you refreshed this page, go back home and
          start again.
        </p>
        <button className="btn-secondary" onClick={() => navigate("/")}>
          Back home
        </button>
      </div>
    );
  }

  async function handleShare() {
    if (!session) return;
    const byteCharacters = atob(session.qr_png_base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const file = new File([byteArray], "movie-match-qr.png", { type: "image/png" });

    if (navigator.share) {
      try {
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
          await navigator.share({
            title: "Movie Match",
            text: "Join me to pick tonight's movie!",
            files: [file],
          });
          return;
        }
        await navigator.share({
          title: "Movie Match",
          text: "Join me to pick tonight's movie!",
          url: session.join_url,
        });
        return;
      } catch {
        // user cancelled or share failed, fall through
      }
    }
    await navigator.clipboard.writeText(session.join_url);
    setCopied(true);
  }

  function copyLink() {
    if (!session) return;
    navigator.clipboard.writeText(session.join_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="center-col">
      <h2>Invite your partner</h2>
      <p>Have them scan this QR code or open the link to join.</p>
      <div className="qr-box">
        <img
          src={`data:image/png;base64,${session.qr_png_base64}`}
          alt="Join QR code"
        />
        <div className="join-link-row">
          <input type="text" readOnly value={session.join_url} />
          <button className="btn-secondary" onClick={copyLink}>
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
        <button className="btn-primary" style={{ width: "100%" }} onClick={handleShare}>
          Share
        </button>
      </div>
      <button
        className="btn-secondary"
        onClick={() => navigate(`/s/${sessionId}/prefs`)}
      >
        Continue to your preferences
      </button>
    </div>
  );
}
