-- ═══════════════════════════════════════════════════════════════════════════
-- AIRAVAT Loan Agent — Neon PostgreSQL Schema
-- Run this once against your Neon DB to create tables.
-- The loan_agent.py also calls _run_migrations() on startup which is idempotent.
-- ═══════════════════════════════════════════════════════════════════════════

-- 1. Every conversation turn (user + agent messages, multi-turn)
CREATE TABLE IF NOT EXISTS loan_conversations (
    id             SERIAL PRIMARY KEY,
    session_id     TEXT NOT NULL,
    user_id        INTEGER,                      -- FK to kyc_users.id (soft ref)
    role           TEXT NOT NULL CHECK (role IN ('user', 'agent')),
    message        TEXT NOT NULL,
    intent         TEXT,                         -- loan_purpose / phase extracted
    extracted_json JSONB DEFAULT '{}',           -- full extracted fields snapshot
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lc_session ON loan_conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_lc_user    ON loan_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_lc_created ON loan_conversations(created_at DESC);

-- 2. Final approved loan application (one per session)
CREATE TABLE IF NOT EXISTS loan_applications (
    id                  SERIAL PRIMARY KEY,
    session_id          TEXT NOT NULL UNIQUE,
    user_id             INTEGER,
    loan_id             TEXT NOT NULL,           -- e.g. "HL_001"
    loan_name           TEXT NOT NULL,           -- e.g. "Home Purchase"
    loan_type           TEXT NOT NULL,           -- e.g. "Home Loan"
    requested_amount    BIGINT,                  -- what user asked for
    approved_amount     BIGINT,                  -- what was agreed
    interest_rate       NUMERIC(5, 2),           -- final negotiated rate
    tenure_months       INTEGER,
    processing_fee      NUMERIC(12, 2),
    monthly_emi         NUMERIC(12, 2),
    negotiation_rounds  INTEGER DEFAULT 0,
    status              TEXT DEFAULT 'pending'
                            CHECK (status IN ('pending', 'approved', 'rejected')),
    extracted_profile   JSONB DEFAULT '{}',      -- full user profile at time of approval
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    approved_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_la_session ON loan_applications(session_id);
CREATE INDEX IF NOT EXISTS idx_la_user    ON loan_applications(user_id);
CREATE INDEX IF NOT EXISTS idx_la_status  ON loan_applications(status);

-- 3. Agent working memory per session (phase, extracted profile, negotiation state)
CREATE TABLE IF NOT EXISTS loan_agent_state (
    session_id          TEXT PRIMARY KEY,
    user_id             INTEGER,
    recommended_loan_id TEXT,                    -- loan_id from catalog
    extracted_profile   JSONB DEFAULT '{}',      -- accumulated extracted fields
    negotiation_state   JSONB DEFAULT '{}',      -- {current_rate, current_amount, rounds, ...}
    conversation_phase  TEXT DEFAULT 'discovery'
                            CHECK (conversation_phase IN (
                                'discovery', 'profiling', 'recommendation',
                                'negotiation', 'confirmation', 'done'
                            )),
    turn_count          INTEGER DEFAULT 0,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════════
-- Verification: list all 3 tables
-- ═══════════════════════════════════════════════════════════════════════════
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public'
--   AND table_name IN ('loan_conversations', 'loan_applications', 'loan_agent_state');
