import { useState, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { COLORS, styles } from "./kycTheme";
import { KycNavbar } from "./KycNavbar";
import { VIDEO_SESSION_ACCESS_STORAGE_KEY } from "./sessionAuth.js";

const KYC_API = import.meta.env.VITE_KYC_API_URL || "http://localhost:8001";

const videoChatStyles = {
  main: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "48px 24px",
    minHeight: "calc(100vh - 60px)",
  },
  dialog: {
    ...styles.card,
    maxWidth: 440,
    width: "100%",
    marginBottom: 0,
    boxShadow: "0 4px 24px rgba(26, 26, 46, 0.08)",
  },
  sessionBox: {
    background: COLORS.blueLight,
    border: `1px solid #c3d9f5`,
    borderRadius: 8,
    padding: "12px 14px",
    fontSize: 13,
    color: COLORS.text,
    wordBreak: "break-all",
    fontFamily: "ui-monospace, monospace",
    marginBottom: 20,
  },
};

export default function VideoChat() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const sessionFromUrl = searchParams.get("session") || "";

  const [aadhaar, setAadhaar] = useState("");
  const [focused, setFocused] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const sessionLabel = useMemo(() => sessionFromUrl || "—", [sessionFromUrl]);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    const digits = aadhaar.replace(/\D/g, "");
    if (!sessionFromUrl) {
      setError("Missing session. Open this page from the link in your email.");
      return;
    }
    if (digits.length !== 12) {
      setError("Enter a valid 12-digit Aadhaar number.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${KYC_API}/video-session/verify-aadhaar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionFromUrl,
          aadhaar_number: digits,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const d = data.detail;
        const errMsg =
          typeof d === "string"
            ? d
            : Array.isArray(d)
              ? d.map((x) => x.msg || JSON.stringify(x)).join(" ")
              : data.message || "Verification failed.";
        setError(errMsg);
        setLoading(false);
        return;
      }
      if (data.access_token) {
        try {
          sessionStorage.setItem(VIDEO_SESSION_ACCESS_STORAGE_KEY, data.access_token);
        } catch (_) {
          /* ignore quota / private mode */
        }
      }
      navigate("/", { replace: true });
    } catch (err) {
      console.error(err);
      setError("Could not reach the server. Is the KYC backend running?");
      setLoading(false);
    }
  };

  return (
    <div style={styles.app}>
      <link
        href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap"
        rel="stylesheet"
      />
      <KycNavbar />
      <div style={videoChatStyles.main}>
        <div style={videoChatStyles.dialog}>
          <div style={styles.stepHeader}>
            <div style={styles.stepBadge}>Video session</div>
            <h1 style={{ ...styles.stepTitle, fontSize: 22 }}>Confirm your identity</h1>
            <p style={styles.stepSubtitle}>
              Enter the Aadhaar number you used during KYC to continue with the agent.
            </p>
          </div>

          <div style={styles.fieldGroup}>
            <span style={styles.label}>Session ID</span>
            <div style={videoChatStyles.sessionBox}>{sessionLabel}</div>
          </div>

          <form onSubmit={submit}>
            <div style={styles.fieldGroup}>
              <label style={styles.label} htmlFor="aadhaar-video">
                Aadhaar number
              </label>
              <input
                id="aadhaar-video"
                type="text"
                inputMode="numeric"
                autoComplete="off"
                placeholder="12-digit Aadhaar"
                value={aadhaar}
                onChange={(e) => setAadhaar(e.target.value.replace(/\D/g, "").slice(0, 12))}
                style={{
                  ...styles.input,
                  ...(focused ? styles.inputFocused : {}),
                }}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
              />
              <div style={styles.helpText}>We match this with your verified KYC record for this session.</div>
            </div>

            {error && (
              <div
                style={{
                  padding: 12,
                  backgroundColor: COLORS.errorLight,
                  border: `1px solid #fecaca`,
                  borderRadius: 8,
                  color: COLORS.error,
                  fontSize: 13,
                  marginBottom: 12,
                }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              style={{
                ...styles.btnPrimary,
                marginTop: 0,
                opacity: loading ? 0.7 : 1,
                cursor: loading ? "wait" : "pointer",
              }}
              disabled={loading}
            >
              {loading ? "Verifying…" : "Continue"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
