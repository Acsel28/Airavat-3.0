from __future__ import annotations

import sqlite3
from pathlib import Path

import chromadb
from dotenv import load_dotenv

from loans8.db.setup_chroma import setup_chroma
from loans8.db.setup_sqlite import setup_sqlite

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "tier8.db"
CHROMA_PATH = BASE_DIR / "chroma_store"
COLLECTION_NAME = "loan_catalog"


def _is_data_ready() -> bool:
    if not DB_PATH.exists():
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        loan_count = conn.execute("SELECT COUNT(*) FROM loans").fetchone()[0]
    except sqlite3.Error:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if int(loan_count) < 18:
        return False

    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        collection = client.get_collection(COLLECTION_NAME)
        ids = collection.get(include=[]).get("ids", [])
    except Exception:
        return False

    return len(set(ids)) >= 18


def ensure_db_ready() -> None:
    load_dotenv()
    if not _is_data_ready():
        setup_sqlite()
        setup_chroma()
