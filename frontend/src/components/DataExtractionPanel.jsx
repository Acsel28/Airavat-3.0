/**
 * DataExtractionPanel – left sidebar showing real-time NLP-extracted KYC fields.
 * Fields: Full Name, Age, Monthly Income, Loan Purpose — each with a confidence bar.
 */
import React, { useEffect, useState } from "react";

function ConfidenceBar({ value, color }) {
  return (
    <div className="kyc-conf-bar">
      <div
        className="kyc-conf-fill"
        style={{ width: `${value}%`, background: color }}
      />
    </div>
  );
}

function DataField({ icon, label, value, confidence, onEdit }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || "");
  const [localValue, setLocalValue] = useState(value);
  const [localConf, setLocalConf] = useState(confidence);

  useEffect(() => {
    if (value && value !== localValue) {
      setLocalValue(value);
      setDraft(value);
      setLocalConf(confidence);
    }
  }, [value, confidence]);

  const color =
    localConf >= 85 ? "#22c55e" : localConf >= 60 ? "#f59e0b" : "#ef4444";

  const handleSave = () => {
    setLocalValue(draft);
    setLocalConf(92);
    setEditing(false);
    onEdit?.(draft);
  };

  return (
    <div className="kyc-data-field">
      <div className="kyc-data-field-header">
        <div className="kyc-data-field-icon">{icon}</div>
        <span className="kyc-data-field-label">{label}</span>
        {!editing && localValue && (
          <button
            className="kyc-edit-btn"
            onClick={() => setEditing(true)}
            title="Edit"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
          </button>
        )}
      </div>
      {editing ? (
        <div className="kyc-data-edit">
          <input
            className="kyc-data-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSave();
              if (e.key === "Escape") setEditing(false);
            }}
            autoFocus
          />
          <button className="kyc-save-btn" onClick={handleSave}>
            Save
          </button>
        </div>
      ) : (
        <div className="kyc-data-value">
          {localValue || <span className="kyc-data-empty">Waiting...</span>}
        </div>
      )}
      {localValue && (
        <>
          <ConfidenceBar value={localConf || 0} color={color} />
          <span className="kyc-conf-pct" style={{ color }}>
            {localConf || 0}%
          </span>
        </>
      )}
    </div>
  );
}

export default function DataExtractionPanel({
  extractedData,
  ageData,
  messages,
}) {
  // Derive values from messages and extractedData
  const [derived, setDerived] = useState({
    fullName: null,
    fullNameConf: 0,
    age: null,
    ageConf: 0,
    monthlyIncome: null,
    monthlyIncomeConf: 0,
    loanPurpose: null,
    loanPurposeConf: 0,
  });

  useEffect(() => {
    const text = messages.map((m) => m.text || "").join(" ");
    setDerived((prev) => {
      const next = { ...prev };
      // Name
      if (!next.fullName) {
        const nameMatch = text.match(
          /(?:my name is|I(?:'m| am)) ([A-Z][a-z]+ [A-Z][a-z]+)/i,
        );
        if (nameMatch) {
          next.fullName = nameMatch[1];
          next.fullNameConf = 96;
        }
      }
      // Loan purpose
      if (!next.loanPurpose) {
        if (/home renovation/i.test(text)) {
          next.loanPurpose = "Home Renovation";
          next.loanPurposeConf = 94;
        } else if (/education/i.test(text)) {
          next.loanPurpose = "Education";
          next.loanPurposeConf = 90;
        } else if (/business/i.test(text)) {
          next.loanPurpose = "Business";
          next.loanPurposeConf = 92;
        } else if (/car|vehicle/i.test(text)) {
          next.loanPurpose = "Vehicle Purchase";
          next.loanPurposeConf = 88;
        } else if (/medical/i.test(text)) {
          next.loanPurpose = "Medical";
          next.loanPurposeConf = 91;
        } else if (/personal loan/i.test(text)) {
          next.loanPurpose = "Personal Use";
          next.loanPurposeConf = 85;
        }
      }
      // Income
      if (!next.monthlyIncome) {
        const incomeMatch = text.match(/(\d+[\.,]?\d*)\s*(lakh|lac|k)/i);
        if (incomeMatch) {
          const val = incomeMatch[1].replace(",", "");
          const unit = incomeMatch[2].toLowerCase();
          const amount = unit === "k" ? `₹${val},000` : `₹${val} lakhs`;
          next.monthlyIncome = amount;
          next.monthlyIncomeConf = 72;
        }
      }
      // Age from ageData
      if (ageData?.average_age && !next.age) {
        next.age = Math.round(ageData.average_age);
        next.ageConf = Math.round(ageData.confidence || 88);
      }
      // Overrides from extractedData prop
      if (extractedData?.fullName) {
        next.fullName = extractedData.fullName;
        next.fullNameConf = 96;
      }
      if (extractedData?.monthlyIncome) {
        next.monthlyIncome = extractedData.monthlyIncome;
        next.monthlyIncomeConf = 72;
      }
      if (extractedData?.loanPurpose) {
        next.loanPurpose = extractedData.loanPurpose;
        next.loanPurposeConf = 94;
      }
      return next;
    });
  }, [messages, ageData, extractedData]);

  const filledCount = [
    derived.fullName,
    derived.age,
    derived.monthlyIncome,
    derived.loanPurpose,
  ].filter(Boolean).length;

  return (
    <div className="kyc-extraction-panel">
      <div className="kyc-extraction-header">
        <div className="kyc-extraction-icon">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
        </div>
        <div>
          <div className="kyc-extraction-title">Data Extraction</div>
          <div className="kyc-extraction-subtitle">Real-time NLP Analysis</div>
        </div>
      </div>

      <div className="kyc-extraction-progress">
        <div className="kyc-extraction-progress-bar">
          <div
            className="kyc-extraction-progress-fill"
            style={{ width: `${(filledCount / 4) * 100}%` }}
          />
        </div>
        <span className="kyc-extraction-progress-label">
          {filledCount}/4 fields
        </span>
      </div>

      <div className="kyc-fields-list">
        <DataField
          icon={
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          }
          label="FULL NAME"
          value={derived.fullName}
          confidence={derived.fullNameConf}
        />
        <DataField
          icon={
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
          }
          label="AGE"
          value={derived.age ? `${derived.age}` : null}
          confidence={derived.ageConf}
        />
        <DataField
          icon={
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
              <line x1="1" y1="10" x2="23" y2="10" />
            </svg>
          }
          label="MONTHLY INCOME"
          value={derived.monthlyIncome}
          confidence={derived.monthlyIncomeConf}
        />
        <DataField
          icon={
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          }
          label="LOAN PURPOSE"
          value={derived.loanPurpose}
          confidence={derived.loanPurposeConf}
        />
      </div>
    </div>
  );
}
