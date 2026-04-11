import { COLORS, styles } from "./kycTheme";

export function KycNavbar() {
  return (
    <nav style={styles.navbar}>
      <div style={styles.logo}>
        <div style={styles.logoIcon}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 12L8 4L14 12" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        FinServe
      </div>
      <div style={{ fontSize: 13, color: COLORS.textMuted }}>
        Secure KYC Portal ·{" "}
        <span style={{ color: COLORS.success, fontWeight: 600 }}>🔒 256-bit SSL</span>
      </div>
    </nav>
  );
}
