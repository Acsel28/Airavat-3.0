from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "database.db"

STT_LOGS_DDL = """
CREATE TABLE IF NOT EXISTS stt_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    turn_number       INTEGER NOT NULL,
    timestamp         TEXT NOT NULL,
    audio_file_path   TEXT NOT NULL,
    transcript        TEXT NOT NULL,
    confidence        REAL,
    duration_seconds  REAL,
    language          TEXT,
    whisper_model     TEXT NOT NULL DEFAULT 'base',
    stage             TEXT,
    is_consent        INTEGER DEFAULT 0
);
"""


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(STT_LOGS_DDL)
    conn.commit()
    conn.close()


def insert_log(*, session_id: str, turn_number: int, audio_file_path: str, transcript: str,
               confidence: float, duration_seconds: float, language: str, stage: str,
               is_consent: bool) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO stt_logs (
            session_id, turn_number, timestamp, audio_file_path, transcript,
            confidence, duration_seconds, language, stage, is_consent
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            int(turn_number),
            datetime.now(timezone.utc).isoformat(),
            audio_file_path,
            transcript,
            float(confidence),
            float(duration_seconds),
            language,
            stage,
            1 if is_consent else 0,
        ),
    )
    conn.commit()
    conn.close()
