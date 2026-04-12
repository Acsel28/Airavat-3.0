"""One-time local datastore setup for Tier 8."""

from __future__ import annotations

from dotenv import load_dotenv

from loans8.db.setup_chroma import setup_chroma
from loans8.db.setup_sqlite import setup_sqlite


def main() -> None:
    load_dotenv()
    print("=== TIER 8 ONE-TIME SETUP ===")
    setup_sqlite()
    setup_chroma()
    print("Setup complete. You can now run: python main.py")


if __name__ == "__main__":
    main()
