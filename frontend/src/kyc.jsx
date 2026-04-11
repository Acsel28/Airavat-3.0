import { useState, useEffect, useRef } from "react";

const COLORS = {
  blue: "#387ED1",
  blueDark: "#2563B0",
  blueLight: "#EBF3FC",
  text: "#1a1a2e",
  textMuted: "#6b7280",
  border: "#e5e7eb",
  bg: "#f9fafb",
  white: "#ffffff",
  success: "#16a34a",
  successLight: "#f0fdf4",
  error: "#dc2626",
  errorLight: "#fef2f2",
  accent: "#FF6B00",
};

const styles = {
  app: {
    fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
    minHeight: "100vh",
    background: COLORS.bg,
    color: COLORS.text,
  },
  navbar: {
    background: COLORS.white,
    borderBottom: `1px solid ${COLORS.border}`,
    padding: "0 40px",
    height: 60,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    position: "sticky",
    top: 0,
    zIndex: 100,
  },
  logo: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontWeight: 700,
    fontSize: 20,
    color: COLORS.blue,
    letterSpacing: "-0.5px",
  },
  logoIcon: {
    width: 28,
    height: 28,
    background: COLORS.blue,
    borderRadius: 6,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  pageContainer: {
    maxWidth: 560,
    margin: "0 auto",
    padding: "48px 24px 80px",
  },
  stepHeader: {
    marginBottom: 32,
  },
  stepBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    background: COLORS.blueLight,
    color: COLORS.blue,
    fontSize: 12,
    fontWeight: 600,
    padding: "4px 12px",
    borderRadius: 20,
    marginBottom: 16,
    letterSpacing: "0.4px",
    textTransform: "uppercase",
  },
  stepTitle: {
    fontSize: 26,
    fontWeight: 700,
    color: COLORS.text,
    margin: "0 0 8px",
    letterSpacing: "-0.5px",
  },
  stepSubtitle: {
    fontSize: 15,
    color: COLORS.textMuted,
    margin: 0,
    lineHeight: 1.6,
  },
  card: {
    background: COLORS.white,
    border: `1px solid ${COLORS.border}`,
    borderRadius: 12,
    padding: 28,
    marginBottom: 16,
  },
  label: {
    display: "block",
    fontSize: 13,
    fontWeight: 600,
    color: COLORS.text,
    marginBottom: 6,
    letterSpacing: "0.2px",
  },
  input: {
    width: "100%",
    padding: "11px 14px",
    fontSize: 15,
    border: `1.5px solid ${COLORS.border}`,
    borderRadius: 8,
    outline: "none",
    background: COLORS.white,
    color: COLORS.text,
    boxSizing: "border-box",
    transition: "border-color 0.15s",
    fontFamily: "inherit",
  },
  inputFocused: {
    borderColor: COLORS.blue,
  },
  fieldGroup: {
    marginBottom: 20,
  },
  btnPrimary: {
    width: "100%",
    padding: "13px 24px",
    background: COLORS.blue,
    color: COLORS.white,
    border: "none",
    borderRadius: 8,
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
    transition: "background 0.15s, transform 0.1s",
    letterSpacing: "0.2px",
    marginTop: 8,
  },
  btnSecondary: {
    padding: "10px 20px",
    background: "transparent",
    color: COLORS.blue,
    border: `1.5px solid ${COLORS.blue}`,
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    transition: "background 0.15s",
    fontFamily: "inherit",
  },
  otpContainer: {
    display: "flex",
    gap: 10,
    justifyContent: "center",
    margin: "20px 0",
  },
  otpInput: {
    width: 50,
    height: 54,
    textAlign: "center",
    fontSize: 22,
    fontWeight: 700,
    border: `1.5px solid ${COLORS.border}`,
    borderRadius: 8,
    outline: "none",
    background: COLORS.white,
    color: COLORS.text,
    fontFamily: "inherit",
    transition: "border-color 0.15s",
  },
  progressBar: {
    display: "flex",
    gap: 6,
    marginBottom: 36,
  },
  progressStep: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    background: COLORS.border,
    transition: "background 0.3s",
  },
  progressStepActive: {
    background: COLORS.blue,
  },
  progressStepDone: {
    background: COLORS.blue,
    opacity: 0.4,
  },
  infoRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    padding: "10px 0",
    borderBottom: `1px solid ${COLORS.border}`,
  },
  infoLabel: {
    fontSize: 13,
    color: COLORS.textMuted,
    fontWeight: 500,
    minWidth: 140,
  },
  infoValue: {
    fontSize: 14,
    color: COLORS.text,
    fontWeight: 600,
    textAlign: "right",
    flex: 1,
  },
  uploadBox: {
    border: `2px dashed ${COLORS.border}`,
    borderRadius: 10,
    padding: "32px 24px",
    textAlign: "center",
    cursor: "pointer",
    transition: "border-color 0.15s, background 0.15s",
    background: COLORS.bg,
  },
  uploadBoxActive: {
    borderColor: COLORS.blue,
    background: COLORS.blueLight,
  },
  uploadIcon: {
    fontSize: 32,
    marginBottom: 10,
    display: "block",
  },
  successBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    background: COLORS.successLight,
    color: COLORS.success,
    fontSize: 13,
    fontWeight: 600,
    padding: "6px 14px",
    borderRadius: 20,
    marginTop: 10,
  },
  signatureBox: {
    border: `1.5px solid ${COLORS.border}`,
    borderRadius: 8,
    background: "#fefefe",
    height: 160,
    position: "relative",
    cursor: "crosshair",
    overflow: "hidden",
  },
  signaturePlaceholder: {
    position: "absolute",
    inset: 0,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: COLORS.border,
    fontSize: 14,
    pointerEvents: "none",
    userSelect: "none",
  },
  termsText: {
    fontSize: 12,
    color: COLORS.textMuted,
    lineHeight: 1.7,
    marginTop: 16,
  },
  helpText: {
    fontSize: 12,
    color: COLORS.textMuted,
    marginTop: 6,
    lineHeight: 1.5,
  },
  errorText: {
    fontSize: 12,
    color: COLORS.error,
    marginTop: 4,
  },
  divider: {
    height: 1,
    background: COLORS.border,
    margin: "20px 0",
  },
  successScreen: {
    textAlign: "center",
    padding: "48px 24px",
  },
  successIcon: {
    width: 80,
    height: 80,
    background: COLORS.successLight,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    margin: "0 auto 24px",
    fontSize: 36,
  },
};

const STEPS = ["Details", "Email OTP", "Aadhaar", "Aadhaar OTP", "PAN", "KYC Review", "Sign & Submit"];

function Navbar() {
  return (
    <nav style={styles.navbar}>
      <div style={styles.logo}>
        <div style={styles.logoIcon}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 12L8 4L14 12" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        FinServe
      </div>
      <div style={{ fontSize: 13, color: COLORS.textMuted }}>
        Secure KYC Portal · <span style={{ color: COLORS.success, fontWeight: 600 }}>🔒 256-bit SSL</span>
      </div>
    </nav>
  );
}

function ProgressBar({ current, total }) {
  return (
    <div style={styles.progressBar}>
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          style={{
            ...styles.progressStep,
            ...(i < current ? styles.progressStepDone : {}),
            ...(i === current ? styles.progressStepActive : {}),
          }}
        />
      ))}
    </div>
  );
}

function FocusInput({ style, ...props }) {
  const [focused, setFocused] = useState(false);
  return (
    <input
      {...props}
      style={{ ...styles.input, ...(focused ? styles.inputFocused : {}), ...style }}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
    />
  );
}

// Step 1: Name & Email
function StepDetails({ onNext }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const validate = () => {
    const e = {};
    if (!name.trim() || name.trim().split(" ").length < 2) e.name = "Please enter your full name (first and last)";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) e.email = "Please enter a valid email address";
    return e;
  };

  const submit = async () => {
    const e = validate();
    if (Object.keys(e).length) { setErrors(e); return; }
    
    try {
      setLoading(true);
      setErrors({});
      
      // Send OTP to email
      const response = await fetch("http://localhost:8001/send-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      const result = await response.json();
      
      if (result.status !== "success") {
        setErrors({ email: result.message || "Failed to send OTP" });
        return;
      }
      
      // Proceed to next step only if OTP sent successfully
      onNext({ name: name.trim(), email: email.trim() });
    } catch (err) {
      setErrors({ email: "Network error. Please try again." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={styles.stepHeader}>
        <div style={styles.stepBadge}>Step 1 of 7 · Personal Details</div>
        <h1 style={styles.stepTitle}>Let's get you started</h1>
        <p style={styles.stepSubtitle}>Enter your details to begin the KYC verification process.</p>
      </div>
      <div style={styles.card}>
        <div style={styles.fieldGroup}>
          <label style={styles.label}>Full name (as per PAN card)</label>
          <FocusInput
            type="text"
            placeholder="e.g. Rajesh Kumar Sharma"
            value={name}
            onChange={e => { setName(e.target.value); setErrors({}); }}
          />
          {errors.name && <div style={styles.errorText}>{errors.name}</div>}
        </div>
        <div style={styles.fieldGroup}>
          <label style={styles.label}>Email address</label>
          <FocusInput
            type="email"
            placeholder="e.g. rajesh@example.com"
            value={email}
            onChange={e => { setEmail(e.target.value); setErrors({}); }}
          />
          {errors.email && <div style={styles.errorText}>{errors.email}</div>}
          <div style={styles.helpText}>An OTP will be sent to this email for verification.</div>
        </div>
        <button style={{ ...styles.btnPrimary, opacity: loading ? 0.6 : 1 }} onClick={submit} disabled={loading}>
          {loading ? "Sending OTP..." : "Continue →"}
        </button>
      </div>
      <div style={{ fontSize: 12, color: COLORS.textMuted, textAlign: "center", lineHeight: 1.7 }}>
        By continuing, you agree to our <span style={{ color: COLORS.blue }}>Terms of Service</span> and <span style={{ color: COLORS.blue }}>Privacy Policy</span>.
      </div>
    </div>
  );
}

// Step 2: Email OTP
function StepEmailOTP({ data, onNext }) {
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [error, setError] = useState("");
  const [resent, setResent] = useState(false);
  const [timer, setTimer] = useState(30);
  const [loading, setLoading] = useState(false);
  const refs = useRef([]);

  useEffect(() => {
    if (timer > 0) {
      const t = setTimeout(() => setTimer(timer - 1), 1000);
      return () => clearTimeout(t);
    }
  }, [timer]);

  const sendOTP = async () => {
    try {
      const response = await fetch("http://localhost:8001/send-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.email }),
      });
      const result = await response.json();
      if (result.status !== "success") {
        setError(result.message || "Failed to send OTP");
      }
    } catch (err) {
      setError("Network error. Please try again.");
    }
  };

  const handleChange = (i, val) => {
    if (!/^\d?$/.test(val)) return;
    const next = [...otp];
    next[i] = val;
    setOtp(next);
    setError("");
    if (val && i < 5) refs.current[i + 1]?.focus();
  };

  const handleKeyDown = (i, e) => {
    if (e.key === "Backspace" && !otp[i] && i > 0) refs.current[i - 1]?.focus();
  };

  const submit = async () => {
    const code = otp.join("");
    if (code.length < 6) { setError("Please enter the complete 6-digit OTP."); return; }
    
    try {
      setLoading(true);
      const response = await fetch("http://localhost:8001/verify-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.email, otp: code }),
      });
      const result = await response.json();
      if (result.status === "success") {
        onNext({ emailVerified: true });
      } else {
        setError(result.message || "Invalid OTP");
      }
    } catch (err) {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    setResent(true);
    setTimer(30);
    setOtp(["", "", "", "", "", ""]);
    await sendOTP();
    setTimeout(() => setResent(false), 3000);
  };

  return (
    <div>
      <div style={styles.stepHeader}>
        <div style={styles.stepBadge}>Step 2 of 7 · Email Verification</div>
        <h1 style={styles.stepTitle}>Verify your email</h1>
        <p style={styles.stepSubtitle}>We've sent a 6-digit OTP to <strong>{data.email}</strong></p>
      </div>
      <div style={styles.card}>
        <div style={styles.otpContainer}>
          {otp.map((d, i) => (
            <input
              key={i}
              ref={el => refs.current[i] = el}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={d}
              onChange={e => handleChange(i, e.target.value)}
              onKeyDown={e => handleKeyDown(i, e)}
              disabled={loading}
              style={{
                ...styles.otpInput,
                ...(d ? { borderColor: COLORS.blue } : {}),
                opacity: loading ? 0.6 : 1,
              }}
            />
          ))}
        </div>
        {error && <div style={{ ...styles.errorText, textAlign: "center" }}>{error}</div>}
        {resent && <div style={{ textAlign: "center", color: COLORS.success, fontSize: 13, marginTop: 4 }}>OTP resent successfully!</div>}
        <button style={{ ...styles.btnPrimary, opacity: loading ? 0.6 : 1 }} onClick={submit} disabled={loading}>
          {loading ? "Verifying..." : "Verify OTP"}
        </button>
        <div style={{ textAlign: "center", marginTop: 16, fontSize: 13, color: COLORS.textMuted }}>
          {timer > 0
            ? <>Resend OTP in <strong>{timer}s</strong></>
            : <span style={{ color: COLORS.blue, cursor: "pointer", fontWeight: 600 }} onClick={resend}>Resend OTP</span>
          }
        </div>
      </div>
      <div style={{ fontSize: 12, color: COLORS.textMuted, textAlign: "center" }}>
        Didn't receive it? Check your spam folder or <span style={{ color: COLORS.blue }}>change email</span>.
      </div>
    </div>
  );
}

// Step 3: Aadhaar Upload
function StepAadhaar({ onNext }) {
  const [uploaded, setUploaded] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [aadhaar, setAadhaar] = useState("");
  const [error, setError] = useState("");
  const fileRef = useRef();

  const handleFile = () => {
    setProcessing(true);
    setTimeout(() => {
      setProcessing(false);
      setUploaded(true);
    }, 1800);
  };

  const submit = () => {
    const clean = aadhaar.replace(/\s/g, "");
    if (clean.length !== 12 || !/^\d+$/.test(clean)) {
      setError("Please enter a valid 12-digit Aadhaar number.");
      return;
    }
    onNext({
      aadhaar: clean,
      aadhaarData: {
        name: "Rajesh Kumar Sharma",
        dob: "15/04/1990",
        gender: "Male",
        address: "12, Sector 7, Dwarka, New Delhi – 110075",
        mobile: "98765XXXXX",
        fatherName: "Suresh Kumar Sharma",
      },
    });
  };

  return (
    <div>
      <div style={styles.stepHeader}>
        <div style={styles.stepBadge}>Step 3 of 7 · Aadhaar Verification</div>
        <h1 style={styles.stepTitle}>Upload your Aadhaar card</h1>
        <p style={styles.stepSubtitle}>We'll extract your details automatically. Your data is encrypted and secure.</p>
      </div>
      <div style={styles.card}>
        <div
          style={{ ...styles.uploadBox, ...(dragging ? styles.uploadBoxActive : {}) }}
          onClick={() => fileRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); handleFile(); }}
        >
          <input ref={fileRef} type="file" accept="image/*,.pdf" style={{ display: "none" }} onChange={handleFile} />
          {processing ? (
            <>
              <span style={styles.uploadIcon}>⏳</span>
              <div style={{ fontWeight: 600, fontSize: 14 }}>Extracting details...</div>
              <div style={styles.helpText}>This may take a few seconds</div>
            </>
          ) : uploaded ? (
            <>
              <span style={styles.successBadge}>✓ Aadhaar uploaded successfully</span>
              <div style={{ ...styles.helpText, marginTop: 8 }}>Details extracted. Click to re-upload.</div>
            </>
          ) : (
            <>
              <span style={styles.uploadIcon}>📄</span>
              <div style={{ fontWeight: 600, fontSize: 14, color: COLORS.text }}>Upload front side of Aadhaar</div>
              <div style={styles.helpText}>Drag & drop or click to browse · JPG, PNG, PDF (max 5MB)</div>
            </>
          )}
        </div>

        <div style={{ ...styles.divider, marginTop: 24 }} />

        <div style={styles.fieldGroup}>
          <label style={styles.label}>Or enter Aadhaar number manually</label>
          <FocusInput
            type="text"
            placeholder="XXXX XXXX XXXX"
            maxLength={14}
            value={aadhaar}
            onChange={e => {
              const v = e.target.value.replace(/\D/g, "").slice(0, 12);
              setAadhaar(v.replace(/(.{4})/g, "$1 ").trim());
              setError("");
            }}
          />
          {error && <div style={styles.errorText}>{error}</div>}
        </div>

        <button style={styles.btnPrimary} onClick={submit}>
          Verify & Send OTP →
        </button>
      </div>
      <div style={{ fontSize: 12, color: COLORS.textMuted, textAlign: "center", lineHeight: 1.8 }}>
        🔐 Your Aadhaar data is processed as per UIDAI guidelines and is never stored on our servers.
      </div>
    </div>
  );
}

// Step 4: Aadhaar OTP
function StepAadhaarOTP({ aadhaarData, onNext }) {
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [error, setError] = useState("");
  const [timer, setTimer] = useState(30);
  const refs = useRef([]);

  useEffect(() => {
    if (timer > 0) {
      const t = setTimeout(() => setTimer(timer - 1), 1000);
      return () => clearTimeout(t);
    }
  }, [timer]);

  const handleChange = (i, val) => {
    if (!/^\d?$/.test(val)) return;
    const next = [...otp];
    next[i] = val;
    setOtp(next);
    setError("");
    if (val && i < 5) refs.current[i + 1]?.focus();
  };

  const handleKeyDown = (i, e) => {
    if (e.key === "Backspace" && !otp[i] && i > 0) refs.current[i - 1]?.focus();
  };

  const submit = () => {
    if (otp.join("").length < 6) { setError("Please enter the complete 6-digit OTP."); return; }
    onNext({ aadhaarVerified: true });
  };

  return (
    <div>
      <div style={styles.stepHeader}>
        <div style={styles.stepBadge}>Step 4 of 7 · Aadhaar OTP</div>
        <h1 style={styles.stepTitle}>Verify Aadhaar mobile OTP</h1>
        <p style={styles.stepSubtitle}>An OTP has been sent to the mobile number linked with your Aadhaar ({aadhaarData?.mobile}).</p>
      </div>

      <div style={{ ...styles.card, background: COLORS.blueLight, border: `1px solid #c3d9f5` }}>
        <div style={{ fontSize: 13, color: COLORS.blue, fontWeight: 600, marginBottom: 12 }}>📋 Extracted Aadhaar Details</div>
        {[
          ["Name", aadhaarData?.name],
          ["Date of Birth", aadhaarData?.dob],
          ["Gender", aadhaarData?.gender],
          ["Father's Name", aadhaarData?.fatherName],
          ["Address", aadhaarData?.address],
          ["Mobile (linked)", aadhaarData?.mobile],
        ].map(([l, v]) => (
          <div key={l} style={{ display: "flex", gap: 12, padding: "6px 0", borderBottom: `1px solid #d4e5f5` }}>
            <span style={{ fontSize: 12, color: COLORS.textMuted, minWidth: 130 }}>{l}</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: COLORS.text }}>{v}</span>
          </div>
        ))}
        <div style={{ marginTop: 10, fontSize: 12, color: COLORS.blue }}>These fields are pre-filled and locked after OTP verification.</div>
      </div>

      <div style={styles.card}>
        <div style={styles.otpContainer}>
          {otp.map((d, i) => (
            <input
              key={i}
              ref={el => refs.current[i] = el}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={d}
              onChange={e => handleChange(i, e.target.value)}
              onKeyDown={e => handleKeyDown(i, e)}
              style={{ ...styles.otpInput, ...(d ? { borderColor: COLORS.blue } : {}) }}
            />
          ))}
        </div>
        {error && <div style={{ ...styles.errorText, textAlign: "center" }}>{error}</div>}
        <button style={styles.btnPrimary} onClick={submit}>Confirm & Proceed →</button>
        <div style={{ textAlign: "center", marginTop: 16, fontSize: 13, color: COLORS.textMuted }}>
          {timer > 0 ? <>Resend in <strong>{timer}s</strong></> : <span style={{ color: COLORS.blue, cursor: "pointer", fontWeight: 600 }} onClick={() => setTimer(30)}>Resend OTP</span>}
        </div>
      </div>
    </div>
  );
}

// Step 5: PAN Upload
function StepPAN({ onNext }) {
  const [pan, setPan] = useState("");
  const [uploaded, setUploaded] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef();

  const handleFile = () => {
    setProcessing(true);
    setTimeout(() => {
      setProcessing(false);
      setUploaded(true);
      setPan("ABJPS1234C");
    }, 1800);
  };

  const submit = () => {
    if (!/^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(pan.toUpperCase())) {
      setError("Please enter a valid PAN number (e.g. ABCDE1234F).");
      return;
    }
    onNext({ pan: pan.toUpperCase(), panData: { pan: pan.toUpperCase(), name: "RAJESH KUMAR SHARMA", dob: "15/04/1990" } });
  };

  return (
    <div>
      <div style={styles.stepHeader}>
        <div style={styles.stepBadge}>Step 5 of 7 · PAN Verification</div>
        <h1 style={styles.stepTitle}>Upload your PAN card</h1>
        <p style={styles.stepSubtitle}>Your PAN card links your financial identity. Details will be auto-extracted.</p>
      </div>
      <div style={styles.card}>
        <div
          style={{ ...styles.uploadBox, ...(uploaded ? styles.uploadBoxActive : {}) }}
          onClick={() => fileRef.current?.click()}
        >
          <input ref={fileRef} type="file" accept="image/*,.pdf" style={{ display: "none" }} onChange={handleFile} />
          {processing ? (
            <>
              <span style={styles.uploadIcon}>⏳</span>
              <div style={{ fontWeight: 600, fontSize: 14 }}>Reading PAN card...</div>
            </>
          ) : uploaded ? (
            <span style={styles.successBadge}>✓ PAN card uploaded & details extracted</span>
          ) : (
            <>
              <span style={styles.uploadIcon}>🪪</span>
              <div style={{ fontWeight: 600, fontSize: 14 }}>Upload PAN card</div>
              <div style={styles.helpText}>JPG, PNG, or PDF · max 5MB</div>
            </>
          )}
        </div>

        <div style={styles.divider} />

        <div style={styles.fieldGroup}>
          <label style={styles.label}>PAN number</label>
          <FocusInput
            type="text"
            placeholder="e.g. ABCDE1234F"
            maxLength={10}
            value={pan}
            onChange={e => { setPan(e.target.value.toUpperCase()); setError(""); }}
            style={{ fontFamily: "monospace", letterSpacing: 2 }}
          />
          {error && <div style={styles.errorText}>{error}</div>}
          <div style={styles.helpText}>PAN is auto-filled when you upload the card above.</div>
        </div>
        <button style={styles.btnPrimary} onClick={submit}>Continue to KYC Review →</button>
      </div>
    </div>
  );
}

// Step 6: KYC Review
function StepKYCReview({ allData, onNext }) {
  const rows = [
    ["Full Name", allData.name],
    ["Email Address", allData.email],
    ["Date of Birth", allData.aadhaarData?.dob],
    ["Gender", allData.aadhaarData?.gender],
    ["Father's Name", allData.aadhaarData?.fatherName],
    ["Residential Address", allData.aadhaarData?.address],
    ["Mobile Number", allData.aadhaarData?.mobile],
    ["Aadhaar Number", `XXXX XXXX ${allData.aadhaar?.slice(-4)}`],
    ["PAN Number", allData.pan],
  ];

  return (
    <div>
      <div style={styles.stepHeader}>
        <div style={styles.stepBadge}>Step 6 of 7 · KYC Review</div>
        <h1 style={styles.stepTitle}>Review your KYC details</h1>
        <p style={styles.stepSubtitle}>Please verify all information carefully before proceeding to sign.</p>
      </div>
      <div style={styles.card}>
        <div style={{ fontSize: 13, fontWeight: 700, color: COLORS.blue, marginBottom: 16, textTransform: "uppercase", letterSpacing: "0.5px" }}>
          Personal & Identity Details
        </div>
        {rows.map(([l, v]) => (
          <div key={l} style={styles.infoRow}>
            <span style={styles.infoLabel}>{l}</span>
            <span style={styles.infoValue}>{v || "—"}</span>
          </div>
        ))}
        <div style={{ marginTop: 16, padding: "12px 14px", background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 8, fontSize: 12, color: "#92400e", lineHeight: 1.6 }}>
          ⚠️ Locked fields are sourced from Aadhaar & PAN and cannot be edited. If there is a discrepancy, please contact support.
        </div>
      </div>

      <div style={styles.card}>
        <div style={{ fontSize: 13, fontWeight: 700, color: COLORS.blue, marginBottom: 16, textTransform: "uppercase", letterSpacing: "0.5px" }}>
          Declaration
        </div>
        <p style={{ fontSize: 13, color: COLORS.textMuted, lineHeight: 1.8, margin: 0 }}>
          I hereby declare that the information furnished above is true, complete, and correct to the best of my knowledge and belief. I understand that in case any of the above information is found to be false or untrue or misleading or misrepresenting, I am aware that I may be held liable for it.
        </p>
        <button style={{ ...styles.btnPrimary, marginTop: 20 }} onClick={onNext}>
          Proceed to Digital Signature →
        </button>
      </div>
    </div>
  );
}

// Step 7: Digital Signature
function StepSignature({ onNext }) {
  const canvasRef = useRef();
  const [drawing, setDrawing] = useState(false);
  const [hasSignature, setHasSignature] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const lastPos = useRef(null);

  const getPos = (e, canvas) => {
    const rect = canvas.getBoundingClientRect();
    const source = e.touches ? e.touches[0] : e;
    return { x: source.clientX - rect.left, y: source.clientY - rect.top };
  };

  const startDraw = (e) => {
    e.preventDefault();
    setDrawing(true);
    const canvas = canvasRef.current;
    lastPos.current = getPos(e, canvas);
  };

  const draw = (e) => {
    e.preventDefault();
    if (!drawing) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const pos = getPos(e, canvas);
    ctx.beginPath();
    ctx.strokeStyle = "#1a1a2e";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.moveTo(lastPos.current.x, lastPos.current.y);
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();
    lastPos.current = pos;
    setHasSignature(true);
  };

  const stopDraw = () => setDrawing(false);

  const clear = () => {
    const canvas = canvasRef.current;
    canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
    setHasSignature(false);
  };

  const submit = () => {
    if (!hasSignature) return;
    if (!agreed) return;
    onNext({ signed: true });
  };

  return (
    <div>
      <div style={styles.stepHeader}>
        <div style={styles.stepBadge}>Step 7 of 7 · Digital Signature</div>
        <h1 style={styles.stepTitle}>Sign your KYC form</h1>
        <p style={styles.stepSubtitle}>Draw your signature in the box below using your mouse or finger.</p>
      </div>
      <div style={styles.card}>
        <label style={styles.label}>Your signature</label>
        <div style={styles.signatureBox}>
          <canvas
            ref={canvasRef}
            width={500}
            height={160}
            style={{ width: "100%", height: "100%", display: "block" }}
            onMouseDown={startDraw}
            onMouseMove={draw}
            onMouseUp={stopDraw}
            onMouseLeave={stopDraw}
            onTouchStart={startDraw}
            onTouchMove={draw}
            onTouchEnd={stopDraw}
          />
          {!hasSignature && (
            <div style={styles.signaturePlaceholder}>Sign here</div>
          )}
        </div>
        {hasSignature && (
          <button style={{ ...styles.btnSecondary, marginTop: 8, fontSize: 12, padding: "6px 14px" }} onClick={clear}>
            Clear & redo
          </button>
        )}

        <div style={{ marginTop: 20 }}>
          <label style={{ display: "flex", gap: 10, alignItems: "flex-start", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={agreed}
              onChange={e => setAgreed(e.target.checked)}
              style={{ marginTop: 3, accentColor: COLORS.blue, width: 15, height: 15 }}
            />
            <span style={{ fontSize: 13, color: COLORS.textMuted, lineHeight: 1.7 }}>
              I confirm that I have read and agree to the <span style={{ color: COLORS.blue }}>KYC Terms & Conditions</span>, <span style={{ color: COLORS.blue }}>Privacy Policy</span>, and <span style={{ color: COLORS.blue }}>NBFC Disclosure Document</span>. I consent to the processing of my personal and financial data for the purpose of KYC compliance.
            </span>
          </label>
        </div>

        <button
          style={{
            ...styles.btnPrimary,
            marginTop: 20,
            opacity: hasSignature && agreed ? 1 : 0.5,
            cursor: hasSignature && agreed ? "pointer" : "not-allowed",
          }}
          onClick={submit}
        >
          Submit KYC Application ✓
        </button>
      </div>
    </div>
  );
}

// Success Screen
function SuccessScreen() {
  return (
    <div style={styles.successScreen}>
      <div style={styles.successIcon}>🎉</div>
      <h1 style={{ ...styles.stepTitle, textAlign: "center" }}>KYC submitted successfully!</h1>
      <p style={{ color: COLORS.textMuted, fontSize: 15, lineHeight: 1.7, marginBottom: 32 }}>
        Your KYC application has been received. Our team will review and verify your documents within <strong>24–48 business hours</strong>. You'll receive a confirmation on your registered email.
      </p>
      <div style={{ background: COLORS.blueLight, borderRadius: 10, padding: "20px 24px", textAlign: "left", border: `1px solid #c3d9f5`, marginBottom: 24 }}>
        {[
          ["Application ID", "FIN-KYC-2026-84721"],
          ["Status", "Under Review"],
          ["Estimated TAT", "24–48 business hours"],
        ].map(([l, v]) => (
          <div key={l} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid #d4e5f5" }}>
            <span style={{ fontSize: 13, color: COLORS.textMuted }}>{l}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: COLORS.text }}>{v}</span>
          </div>
        ))}
      </div>
      <button style={styles.btnPrimary} onClick={() => window.location.reload()}>
        Return to Home
      </button>
    </div>
  );
}

export default function App() {
  const [step, setStep] = useState(0);
  const [formData, setFormData] = useState({});

  const advance = (data) => {
    setFormData(prev => ({ ...prev, ...data }));
    setStep(s => s + 1);
  };

  const renderStep = () => {
    switch (step) {
      case 0: return <StepDetails onNext={advance} />;
      case 1: return <StepEmailOTP data={formData} onNext={advance} />;
      case 2: return <StepAadhaar onNext={advance} />;
      case 3: return <StepAadhaarOTP aadhaarData={formData.aadhaarData} onNext={advance} />;
      case 4: return <StepPAN onNext={advance} />;
      case 5: return <StepKYCReview allData={formData} onNext={() => advance({})} />;
      case 6: return <StepSignature onNext={advance} />;
      case 7: return <SuccessScreen />;
      default: return null;
    }
  };

  return (
    <div style={styles.app}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
      <Navbar />
      <div style={styles.pageContainer}>
        {step < 7 && (
          <>
            <ProgressBar current={step} total={STEPS.length} />
            <div style={{ fontSize: 12, color: COLORS.textMuted, marginBottom: 24, display: "flex", justifyContent: "space-between" }}>
              <span>{STEPS[step]}</span>
              <span>{step + 1} / {STEPS.length}</span>
            </div>
          </>
        )}
        {renderStep()}
      </div>
    </div>
  );
}