/**
 * LoanOfferModal — Final loan offer display with accept / negotiate actions.
 * Shown when the agent reaches "confirmation" or "done" phase.
 */
import React, { useState } from "react";

function formatINR(amount) {
  if (!amount && amount !== 0) return "—";
  const num = Number(amount);
  if (num >= 10_000_000) return `₹${(num / 10_000_000).toFixed(2)} Cr`;
  if (num >= 100_000) return `₹${(num / 100_000).toFixed(2)} L`;
  return `₹${num.toLocaleString("en-IN")}`;
}

function StatCard({ label, value, highlight }) {
  return (
    <div
      className="loan-stat-card"
      style={highlight ? { borderColor: "#6366f1", background: "#eef2ff" } : {}}
    >
      <p className="loan-stat-label">{label}</p>
      <p className="loan-stat-value" style={highlight ? { color: "#4f46e5" } : {}}>
        {value}
      </p>
    </div>
  );
}

export default function LoanOfferModal({
  offer,
  onAccept,
  onNegotiate,
  onClose,
  loading,
  sessionUserName,
}) {
  const [showBreakdown, setShowBreakdown] = useState(false);

  if (!offer) return null;

  const rateReduced =
    offer.original_rate && offer.interest_rate < offer.original_rate;
  const bpsReduced = rateReduced
    ? Math.round((offer.original_rate - offer.interest_rate) * 100)
    : 0;

  const totalPayable =
    offer.monthly_emi * offer.tenure_months + offer.processing_fee;
  const totalInterest = totalPayable - offer.amount;

  return (
    <div className="loan-modal-overlay" id="loan-offer-modal">
      <div className="loan-modal-card">
        {/* Header */}
        <div className="loan-modal-header">
          <div className="loan-modal-header-left">
            <div className="loan-modal-badge">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="white"
                strokeWidth="2"
              >
                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p className="loan-modal-eyebrow">Personalised Loan Offer</p>
              <h2 className="loan-modal-title">{offer.loan_name}</h2>
              <p className="loan-modal-subtitle">{offer.loan_type}</p>
            </div>
          </div>
          {rateReduced && (
            <div className="loan-negotiated-badge">
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
                <polyline points="17 6 23 6 23 12" />
              </svg>
              Rate negotiated ↓ {bpsReduced} bps
            </div>
          )}
        </div>

        {/* User greeting */}
        {sessionUserName && (
          <p className="loan-modal-greeting">
            Hi <strong>{sessionUserName}</strong>, here's your tailored offer:
          </p>
        )}

        {/* Stats grid */}
        <div className="loan-stats-grid">
          <StatCard label="Loan Amount" value={formatINR(offer.amount)} />
          <StatCard
            label="Interest Rate"
            value={`${offer.interest_rate?.toFixed(2)}% p.a.`}
            highlight={rateReduced}
          />
          <StatCard label="Tenure" value={`${offer.tenure_months} months`} />
          <StatCard
            label="Monthly EMI"
            value={formatINR(offer.monthly_emi)}
            highlight
          />
        </div>

        {/* Processing fee row */}
        <div className="loan-fee-row">
          <span className="loan-fee-label">Processing Fee</span>
          <span className="loan-fee-value">{formatINR(offer.processing_fee)}</span>
        </div>

        {/* Breakdown toggle */}
        <button
          className="loan-breakdown-toggle"
          onClick={() => setShowBreakdown((v) => !v)}
        >
          {showBreakdown ? "Hide" : "Show"} repayment breakdown
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            style={{
              transform: showBreakdown ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.2s",
            }}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        {showBreakdown && (
          <div className="loan-breakdown-panel">
            <div className="loan-breakdown-row">
              <span>Principal</span>
              <span>{formatINR(offer.amount)}</span>
            </div>
            <div className="loan-breakdown-row">
              <span>Total Interest</span>
              <span>{formatINR(Math.round(totalInterest))}</span>
            </div>
            <div className="loan-breakdown-row">
              <span>Processing Fee</span>
              <span>{formatINR(offer.processing_fee)}</span>
            </div>
            <div className="loan-breakdown-row loan-breakdown-row--total">
              <span>Total Payable</span>
              <span>{formatINR(Math.round(totalPayable))}</span>
            </div>
            {offer.negotiation_rounds > 0 && (
              <div className="loan-negotiation-note">
                ✦ Rate negotiated over {offer.negotiation_rounds} round
                {offer.negotiation_rounds > 1 ? "s" : ""} — original rate was{" "}
                {offer.original_rate?.toFixed(2)}% p.a.
              </div>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="loan-modal-actions">
          <button
            id="loan-accept-btn"
            className="loan-btn loan-btn--accept"
            onClick={onAccept}
            disabled={loading}
          >
            {loading ? (
              <span className="loan-btn-spinner" />
            ) : (
              <>
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                Accept Offer
              </>
            )}
          </button>
          <button
            id="loan-negotiate-btn"
            className="loan-btn loan-btn--negotiate"
            onClick={onNegotiate}
            disabled={loading}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
            Negotiate Terms
          </button>
          <button
            id="loan-close-btn"
            className="loan-btn loan-btn--close"
            onClick={onClose}
            disabled={loading}
          >
            Continue Chatting
          </button>
        </div>

        {/* Disclaimer */}
        <p className="loan-disclaimer">
          * This is a preliminary offer based on your conversation profile. Final
          terms are subject to credit &amp; document verification.
        </p>
      </div>
    </div>
  );
}
