"""Optional LangSmith tracing bootstrap."""

import os


def bootstrap() -> None:
    api_key = os.getenv("LANGSMITH_API_KEY", "")
    if not api_key:
        print("[LangSmith] LANGSMITH_API_KEY not set — tracing disabled.")
        return
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGCHAIN_ENDPOINT"] = os.getenv(
        "LANGSMITH_ENDPOINT",
        "https://api.smith.langchain.com",
    )
    os.environ["LANGCHAIN_PROJECT"] = os.getenv(
        "LANGSMITH_PROJECT",
        "tier8-loan-negotiation",
    )
    print(f"[LangSmith] Tracing enabled → project: {os.environ['LANGCHAIN_PROJECT']}")
