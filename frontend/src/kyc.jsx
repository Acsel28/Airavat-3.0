import { useState, useEffect, useRef } from "react";
import { COLORS, styles } from "./kycTheme";
import { KycNavbar } from "./KycNavbar";
import axios from "axios";
import { initializeApp } from "firebase/app";
import { getAuth, signInWithPhoneNumber, RecaptchaVerifier } from "firebase/auth";

// Firebase Configuration
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

let auth = null;
if (firebaseConfig.apiKey && firebaseConfig.authDomain) {
  try {
    const firebaseApp = initializeApp(firebaseConfig);
    auth = getAuth(firebaseApp);
    console.log("✅ Firebase initialized successfully");
  } catch (error) {
    console.error("❌ Firebase initialization failed:", error);
    console.warn("⚠️ Add Firebase credentials to .env.local to enable phone OTP verification");
  }
} else {
  console.warn("⚠️ Firebase environment variables not set. Phone OTP will not work.");
  console.log("📌 Create .env.local with VITE_FIREBASE_* variables");
}

const COOLDOWN_TIME = 30; // seconds between OTP resend attempts

// Temporarily commented out Aadhaar OTP step
const STEPS = ["Details", "Email OTP", "Aadhaar", /* "Aadhaar OTP" */ "PAN", "Face Capture", "KYC Review", "Sign & Submit"];

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
function StepAadhaar({ data, onNext }) {
  const [uploaded, setUploaded] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [aadhaarFile, setAadhaarFile] = useState(null);
  const [error, setError] = useState("");
  const [extractedData, setExtractedData] = useState(null);
  const fileRef = useRef();

  const handleFile = async (file) => {
    if (!file) return;
    
    console.log("📄 File selected:", file);
    console.log("File details:", {
      name: file.name,
      size: file.size,
      type: file.type
    });

    setAadhaarFile(file);
    setProcessing(true);
    setError("");

    try {
      // Create FormData for sending file + name
      const formData = new FormData();
      formData.append("file", file);
      formData.append("string", data.name);

      console.log("📤 Sending to backend - /verify-aadhaar");
      console.log("Request data:", {
        name: data.name,
        fileName: file.name,
        fileSize: file.size
      });

      const response = await fetch("http://localhost:8001/verify-aadhaar", {
        method: "POST",
        body: formData,
      });

      const result = await response.json();
      console.log("📥 Backend response:", result);

      if (result.status === "success") {
        console.log("✅ Aadhaar verified successfully!");
        console.log("Extracted data:", result.data);
        setExtractedData(result.data);
        setUploaded(true);
      } else {
        console.error("❌ Verification failed:", result.message);
        setError(result.message || "Failed to verify Aadhaar");
      }
    } catch (err) {
      console.error("❌ Network error:", err);
      setError("Network error. Please try again.");
    } finally {
      setProcessing(false);
    }
  };

  const submit = async () => {
    if (!extractedData) {
      setError("Please upload an Aadhaar document first.");
      return;
    }

    console.log(" Submitting Aadhaar step with data:", {
      aadhaar: extractedData.aadhaar_number,
      name: extractedData.name,
      dob: extractedData.dob,
      gender: extractedData.gender,
      mobile: extractedData.phone,
    });

    onNext({
      aadhaar: extractedData.aadhaar_number,
      aadhaarData: extractedData,
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
          onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
        >
          <input 
            ref={fileRef} 
            type="file" 
            accept="image/*,.pdf" 
            style={{ display: "none" }} 
            onChange={(e) => handleFile(e.target.files[0])}
          />
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

        {error && <div style={styles.errorText}>{error}</div>}

        <button style={styles.btnPrimary} onClick={submit}>
          Verify & Continue 
        </button>
      </div>
      <div style={{ fontSize: 12, color: COLORS.textMuted, textAlign: "center", lineHeight: 1.8 }}>
        🔐 Your Aadhaar data is processed as per UIDAI guidelines and is never stored on our servers.
      </div>
    </div>
  );
}

// Step 4: Aadhaar OTP (Firebase Phone Authentication)
function StepAadhaarOTP({ aadhaarData, email, onNext }) {
  // aadhaarData.mobile is the raw 10-digit number extracted from Aadhaar (no +91)
  let extractedPhone = aadhaarData?.mobile?.replace(/\D/g, "") ?? "";
  
  const [phoneInput, setPhoneInput] = useState(extractedPhone || ""); // Allow manual input if not extracted
  const [otpSent, setOtpSent]       = useState(false);
  const [otpSending, setOtpsending] = useState(false);
  const [otp, setOtp]               = useState(["", "", "", "", "", ""]);
  const [verifying, setVerifying]   = useState(false);
  const [error, setError]           = useState("");
  const [cooldown, setCooldown]     = useState(0);
  const refs = useRef([]);
  
  // Use phoneInput if manual entry, otherwise use extracted
  const phone = phoneInput || extractedPhone;
 
  /* -------------------- COOLDOWN TICKER -------------------- */
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => setCooldown((p) => p - 1), 1000);
    return () => clearInterval(timer);
  }, [cooldown]);
 
  /* -------------------- SEND OTP -------------------- */
  const sendOTP = async () => {
    setError("");

    // Verify auth is initialized
    if (!auth) {
      console.error("❌ Firebase auth is not initialized");
      setError("Firebase is not configured properly.");
      return;
    }
 
    if (!phone || phone.length !== 10) {
      setError("Could not read a valid 10-digit mobile number.");
      return;
    }
 
    setOtpsending(true);
    try {
      // Clear previous reCAPTCHA if it exists to avoid "container already has content" errors
      if (window.recaptchaVerifier) {
        try {
          window.recaptchaVerifier.clear();
        } catch (e) {
          console.warn("Could not clear reCAPTCHA:", e);
        }
        window.recaptchaVerifier = null;
      }

      // 1. Correct Constructor Order: (auth, containerId, options)
      console.log("🔐 Initializing reCAPTCHA verifier...");
      window.recaptchaVerifier = new RecaptchaVerifier(
        auth,
        "recaptcha-container",
        { 
          size: "invisible",
          callback: () => { console.log("reCAPTCHA resolved"); }
        }
      );

      const fullPhone = `+91${phone}`;
      console.log("📤 Sending OTP via Firebase to:", fullPhone);
      
      // 2. Call signInWithPhoneNumber
      const confirmationResult = await signInWithPhoneNumber(
        auth,
        fullPhone,
        window.recaptchaVerifier
      );
      
      window.confirmationResult = confirmationResult;
      console.log("✅ OTP sent successfully via Firebase");
 
      setOtpsending(false);
      setOtpSent(true);
      setCooldown(60); // Assuming COOLDOWN_TIME is 60
    } catch (err) {
      console.error("❌ OTP send failed:", err);
      setOtpsending(false);
      
      // Cleanup on failure
      if (window.recaptchaVerifier) {
        window.recaptchaVerifier.clear();
        window.recaptchaVerifier = null;
      }
      
      setError(err.message || "Failed to send OTP. Please try again.");
    }
  };
 
  /* -------------------- VERIFY OTP -------------------- */
  const verifyOTP = async () => {
    setError("");
    const code = otp.join("");
    if (code.length < 6) { setError("Please enter the complete 6-digit OTP."); return; }
 
    setVerifying(true);
    try {
      console.log("🔐 Verifying OTP with Firebase");
      await window.confirmationResult.confirm(code);
      console.log("✅ Firebase OTP verification successful!");
      setVerifying(false);
      onNext({ aadhaarVerified: true, firebaseVerified: true });
    } catch (err) {
      console.error("❌ OTP verification failed:", err);
      setVerifying(false);
      if (err.code === "auth/invalid-verification-code") {
        setError("Invalid OTP. Please check and try again.");
      } else if (err.code === "auth/code-expired") {
        setError("OTP has expired. Please request a new one.");
        setOtpSent(false); 
      } else {
        setError("OTP verification failed. Please try again.");
      }
    }
  };
 
  /* -------------------- OTP INPUT HELPERS -------------------- */
  const handleOtpChange = (i, val) => {
    if (!/^\d?$/.test(val)) return;
    const next = [...otp];
    next[i] = val;
    setOtp(next);
    setError("");
    if (val && i < 5) refs.current[i + 1]?.focus();
  };
 
  const handleOtpKeyDown = (i, e) => {
    if (e.key === "Backspace" && !otp[i] && i > 0) refs.current[i - 1]?.focus();
  };
 
  const maskedPhone = phone
    ? `+91 ${phone.slice(0, 2)}XXXXXX${phone.slice(-2)}`
    : aadhaarData?.mobile;
 
  return (
    <div>
      <div style={styles.stepHeader}>
        <div style={styles.stepBadge}>Step 4 of 7 · Aadhaar OTP</div>
        <h1 style={styles.stepTitle}>Verify Aadhaar mobile OTP</h1>
        <p style={styles.stepSubtitle}>
          {otpSent
            ? <>OTP sent to <strong>{maskedPhone}</strong>. Enter it below to confirm.</>
            : <>We'll send an OTP to <strong>{maskedPhone}</strong>, the mobile number linked to your Aadhaar.</>}
        </p>
      </div>
 
      {/* Extracted Aadhaar details */}
      <div style={{ ...styles.card, background: COLORS.blueLight, border: `1px solid #c3d9f5` }}>
        <div style={{ fontSize: 13, color: COLORS.blue, fontWeight: 600, marginBottom: 12 }}>📋 Extracted Aadhaar Details</div>
        {[
          ["Name",            aadhaarData?.name],
          ["Date of Birth",   aadhaarData?.dob],
          ["Gender",          aadhaarData?.gender],
          ["Mobile (linked)", maskedPhone],
        ].map(([l, v]) => (
          <div key={l} style={{ display: "flex", gap: 12, padding: "6px 0", borderBottom: `1px solid #d4e5f5` }}>
            <span style={{ fontSize: 12, color: COLORS.textMuted, minWidth: 130 }}>{l}</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: COLORS.text }}>{v}</span>
          </div>
        ))}
      </div>
 
      {/* Invisible reCAPTCHA anchor */}
      <div id="recaptcha-container" />
 
      <div style={styles.card}>
        {!otpSent ? (
          <>
            <div style={{ fontSize: 14, color: COLORS.textMuted, marginBottom: 20, lineHeight: 1.7 }}>
              An SMS OTP will be dispatched via Firebase to your Aadhaar-linked number.
            </div>
            
            {!extractedPhone && (
              <div style={{ marginBottom: 16 }}>
                <label style={styles.label}>📱 Mobile Number (Enter manually)</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <span style={{ ...styles.input, alignContent: "center", color: COLORS.textMuted, flex: 0.15 }}>+91</span>
                  <input
                    type="tel"
                    placeholder="9876543210"
                    value={phoneInput}
                    onChange={(e) => {
                      const val = e.target.value.replace(/\D/g, "").slice(0, 10);
                      setPhoneInput(val);
                    }}
                    maxLength="10"
                    style={{ ...styles.input, flex: 1 }}
                  />
                </div>
              </div>
            )}
            
            {error && (
              <div style={{ ...styles.errorText, marginBottom: 12, padding: "10px 14px", background: COLORS.errorLight, borderRadius: 8 }}>
                {error}
              </div>
            )}
            
            <button
              style={{ ...styles.btnPrimary, opacity: (otpSending || !phone || phone.length !== 10) ? 0.7 : 1, cursor: (otpSending || !phone || phone.length !== 10) ? "not-allowed" : "pointer" }}
              onClick={sendOTP}
              disabled={otpSending || !phone || phone.length !== 10}
            >
              {otpSending ? "Sending OTP…" : `Send OTP to +91 ${phone ? phone.slice(0, 2) : "XX"}XXXXXX${phone ? phone.slice(-2) : "XX"}`}
            </button>
          </>
        ) : (
          <>
            <div style={styles.otpContainer}>
              {otp.map((d, i) => (
                <input
                  key={i}
                  ref={el => refs.current[i] = el}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={d}
                  onChange={e => handleOtpChange(i, e.target.value)}
                  onKeyDown={e => handleOtpKeyDown(i, e)}
                  style={{ ...styles.otpInput, ...(d ? { borderColor: COLORS.blue } : {}) }}
                />
              ))}
            </div>
 
            {error && (
              <div style={{ ...styles.errorText, textAlign: "center", marginBottom: 8, padding: "8px 14px", background: COLORS.errorLight, borderRadius: 8 }}>
                {error}
              </div>
            )}
 
            <button
              style={{ ...styles.btnPrimary, opacity: verifying ? 0.7 : 1, cursor: verifying ? "wait" : "pointer" }}
              onClick={verifyOTP}
              disabled={verifying}
            >
              {verifying ? "Verifying…" : "Confirm & Proceed →"}
            </button>
 
            <div style={{ textAlign: "center", marginTop: 16, fontSize: 13, color: COLORS.textMuted }}>
              {cooldown > 0 ? (
                <>Resend OTP in <strong>{cooldown}s</strong></>
              ) : (
                <span
                  style={{ color: COLORS.blue, cursor: "pointer", fontWeight: 600 }}
                  onClick={() => { setOtp(["","","","","",""]); setError(""); sendOTP(); }}
                >
                  Resend OTP
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// Step 5: PAN Upload
function StepPAN({ data, onNext }) {
  const [pan, setPan] = useState("");
  const [uploaded, setUploaded] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [panFile, setPanFile] = useState(null);
  const [error, setError] = useState("");
  const [extractedData, setExtractedData] = useState(null);
  const fileRef = useRef();

  const handleFile = async (file) => {
    if (!file) return;
    
    console.log("📄 PAN file selected:", file);
    console.log("File details:", {
      name: file.name,
      size: file.size,
      type: file.type
    });

    setPanFile(file);
    setProcessing(true);
    setError("");

    try {
      // Create FormData for sending file + name
      const formData = new FormData();
      formData.append("file", file);
      formData.append("input", data.name);

      console.log("📤 Sending to backend - /verify-pan");
      console.log("Request data:", {
        name: data.name,
        fileName: file.name,
        fileSize: file.size
      });

      const response = await fetch("http://localhost:8001/verify-pan", {
        method: "POST",
        body: formData,
      });

      const result = await response.json();
      console.log("📥 Backend response:", result);

      if (result.status === "success") {
        console.log("✅ PAN verified successfully!");
        console.log("Extracted data:", result.data);
        setExtractedData(result.data);
        setPan(result.data.pan_number || "");
        setUploaded(true);
      } else {
        console.error("❌ Verification failed:", result.message);
        setError(result.message || "Failed to verify PAN");
      }
    } catch (err) {
      console.error("❌ Network error:", err);
      setError("Network error. Please try again.");
    } finally {
      setProcessing(false);
    }
  };

  const submit = async () => {
    if (!extractedData) {
      setError("Please upload a PAN document first.");
      return;
    }

    if (!pan) {
      setError("PAN number could not be extracted. Please try again.");
      return;
    }

    console.log("📤 Submitting PAN step with data:", {
      pan: pan,
      name: extractedData.name,
      father_name: extractedData.father_name,
    });

    onNext({
      pan: pan,
      panData: extractedData,
    });
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
          style={{ ...styles.uploadBox, ...(dragging ? styles.uploadBoxActive : {}) }}
          onClick={() => fileRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
        >
          <input 
            ref={fileRef} 
            type="file" 
            accept="image/*,.pdf" 
            style={{ display: "none" }} 
            onChange={(e) => handleFile(e.target.files[0])}
          />
          {processing ? (
            <>
              <span style={styles.uploadIcon}>⏳</span>
              <div style={{ fontWeight: 600, fontSize: 14 }}>Reading PAN card...</div>
              <div style={styles.helpText}>This may take a few seconds</div>
            </>
          ) : uploaded ? (
            <>
              <span style={styles.successBadge}>✓ PAN card uploaded & details extracted</span>
              <div style={{ ...styles.helpText, marginTop: 8 }}>Details extracted. Click to re-upload.</div>
            </>
          ) : (
            <>
              <span style={styles.uploadIcon}>🪪</span>
              <div style={{ fontWeight: 600, fontSize: 14 }}>Upload PAN card</div>
              <div style={styles.helpText}>JPG, PNG, or PDF · max 5MB</div>
            </>
          )}
        </div>

        <div style={styles.divider} />

        {error && <div style={styles.errorText}>{error}</div>}

        {extractedData && (
          <div style={{ ...styles.card, background: COLORS.blueLight, border: `1px solid #c3d9f5`, marginBottom: 16 }}>
            <div style={{ fontSize: 13, color: COLORS.blue, fontWeight: 600, marginBottom: 12 }}>📋 Extracted PAN Details</div>
            {[
              ["PAN Number", extractedData.pan_number],
              ["Name", extractedData.name],
              ["Father's Name", extractedData.father_name],
            ].map(([l, v]) => (
              <div key={l} style={{ display: "flex", gap: 12, padding: "6px 0", borderBottom: `1px solid #d4e5f5` }}>
                <span style={{ fontSize: 12, color: COLORS.textMuted, minWidth: 130 }}>{l}</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: COLORS.text }}>{v || "—"}</span>
              </div>
            ))}
          </div>
        )}

        <button style={styles.btnPrimary} onClick={submit}>Continue to KYC Review →</button>
      </div>
    </div>
  );
}

// Step 5.5: Face Capture
function StepFaceCapture({ onNext }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [faceImage, setFaceImage] = useState(null);
  const [cameraActive, setCameraActive] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!cameraActive) return;
    
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } })
      .then(stream => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          console.log("📹 Camera started successfully");
        }
      })
      .catch(err => {
        console.error("❌ Camera access denied:", err);
        setError("Camera access denied. Please allow camera access to proceed.");
      });

    return () => {
      if (videoRef.current && videoRef.current.srcObject) {
        videoRef.current.srcObject.getTracks().forEach(track => track.stop());
      }
    };
  }, [cameraActive]);

  const capturePhoto = () => {
    if (videoRef.current && canvasRef.current) {
      const context = canvasRef.current.getContext("2d");
      context.drawImage(videoRef.current, 0, 0, 400, 300);
      const imageData = canvasRef.current.toDataURL("image/jpeg");
      setFaceImage(imageData);
      setCameraActive(false);
      console.log("📸 Face image captured");
    }
  };

  const retakPhoto = () => {
    setFaceImage(null);
    setCameraActive(true);
    setError("");
  };

  const submit = () => {
    if (!faceImage) {
      setError("Please capture a face photo to proceed.");
      return;
    }
    console.log("📤 Submitting face capture...");
    onNext({ faceImage });
  };

  return (
    <div>
      <div style={styles.stepHeader}>
        <div style={styles.stepBadge}>Step 6 of 8 · Face Verification</div>
        <h1 style={styles.stepTitle}>Verify your identity with face</h1>
        <p style={styles.stepSubtitle}>Please ensure good lighting and look directly at the camera.</p>
      </div>
      <div style={styles.card}>
        {!faceImage ? (
          <>
            <div style={{ position: "relative", marginBottom: 20 }}>
              <video
                ref={videoRef}
                autoPlay
                playsInline
                style={{
                  width: "100%",
                  borderRadius: 12,
                  border: `2px solid ${COLORS.blue}`,
                  display: cameraActive ? "block" : "none"
                }}
              />
              {error && <div style={{ ...styles.errorText, marginTop: 12 }}>{error}</div>}
            </div>
            <button 
              style={styles.btnPrimary} 
              onClick={capturePhoto}
              disabled={!cameraActive}
            >
              📸 Capture Photo
            </button>
          </>
        ) : (
          <>
            <img 
              src={faceImage} 
              alt="Captured face" 
              style={{ width: "100%", borderRadius: 12, marginBottom: 16 }}
            />
            <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
              <button 
                style={{ ...styles.btnPrimary, flex: 1 }} 
                onClick={submit}
              >
                Confirm & Continue
              </button>
              <button 
                style={{ ...styles.btnSecondary, flex: 1 }} 
                onClick={retakPhoto}
              >
                Retake Photo
              </button>
            </div>
          </>
        )}
      </div>
      <canvas ref={canvasRef} width={400} height={300} style={{ display: "none" }} />
      <div style={{ fontSize: 12, color: COLORS.textMuted, textAlign: "center", lineHeight: 1.8 }}>
        🔐 Your face image is used only for identity verification and is securely stored.
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
function StepSignature({ formData, onNext }) {
  const canvasRef = useRef();
  const [drawing, setDrawing] = useState(false);
  const [hasSignature, setHasSignature] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
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

  const submit = async () => {
    if (!hasSignature) return;
    if (!agreed) return;

    setError("");
    setSubmitting(true);

    try {
      console.log("📤 Submitting KYC data to backend...");
      
      // Convert face image from data URL to blob
      const faceImageBlob = await fetch(formData.faceImage).then(res => res.blob());
      
      // Create FormData
      const submitFormData = new FormData();
      submitFormData.append("full_name", formData.name);
      submitFormData.append("email", formData.email);
      submitFormData.append("dob", formData.aadhaarData?.dob || "");
      submitFormData.append("gender", formData.aadhaarData?.gender || "");
      submitFormData.append("mobile", formData.aadhaarData?.mobile || "");
      submitFormData.append("aadhaar", formData.aadhaar || "");
      submitFormData.append("pan", formData.pan || "");
      submitFormData.append("face_image", faceImageBlob, "face.jpg");

      console.log("📋 KYC Data:", {
        full_name: formData.name,
        email: formData.email,
        dob: formData.aadhaarData?.dob,
        gender: formData.aadhaarData?.gender,
        mobile: formData.aadhaarData?.mobile,
        aadhaar: formData.aadhaar,
        pan: formData.pan,
      });

      const response = await fetch("http://localhost:8001/submit-kyc", {
        method: "POST",
        body: submitFormData,
      });

      const result = await response.json();
      console.log("📥 Backend response:", result);

      if (result.status === "success") {
        console.log("✅ KYC submitted successfully!");
        setSubmitting(false);
        onNext({ signed: true, kyc_submitted: true, user_id: result.user_id });
      } else {
        console.error("❌ KYC submission failed:", result.message);
        setError(result.message || "Failed to submit KYC");
        setSubmitting(false);
      }
    } catch (err) {
      console.error("❌ Error submitting KYC:", err);
      setError("Error submitting KYC. Please try again.");
      setSubmitting(false);
    }
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

        {error && (
          <div style={{
            marginTop: 16,
            padding: 12,
            backgroundColor: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 8,
            color: "#dc2626",
            fontSize: 13,
          }}>
            ❌ {error}
          </div>
        )}

        <button
          style={{
            ...styles.btnPrimary,
            marginTop: 20,
            opacity: hasSignature && agreed && !submitting ? 1 : 0.5,
            cursor: hasSignature && agreed && !submitting ? "pointer" : "not-allowed",
          }}
          onClick={submit}
          disabled={submitting}
        >
          {submitting ? "Submitting..." : "Submit KYC Application ✓"}
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
      <h1 style={{ ...styles.stepTitle, textAlign: "center" }}>Your KYC application has been verified</h1>
      <p style={{ color: COLORS.textMuted, fontSize: 15, lineHeight: 1.7, marginBottom: 32 }}>
        Please check your mail to start a session with an agent and get instant loan approval.
      </p>
      <div style={{ background: COLORS.blueLight, borderRadius: 10, padding: "20px 24px", textAlign: "left", border: `1px solid #c3d9f5`, marginBottom: 24 }}>
        {[
          ["Application ID", "FIN-KYC-2026-84721"],
          ["Status", "Verified"],
          ["Next step", "Check email · agent video session"],
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
      case 2: return <StepAadhaar data={formData} onNext={advance} />;
      // case 3: return <StepAadhaarOTP aadhaarData={formData.aadhaarData} email={formData.email} onNext={advance} />; // COMMENTED OUT - Skip Aadhaar OTP for now
      case 3: return <StepPAN data={formData} onNext={advance} />;
      case 4: return <StepFaceCapture onNext={advance} />;
      case 5: return <StepKYCReview allData={formData} onNext={() => advance({})} />;
      case 6: return <StepSignature formData={formData} onNext={advance} />;
      case 7: return <SuccessScreen />;
      default: return null;
    }
  };

  return (
    <div style={styles.app}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
      <KycNavbar />
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