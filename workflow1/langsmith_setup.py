from __future__ import annotations

import os

from workflow1.agent.prompts import LANGSMITH_DISABLED, LANGSMITH_ENABLED_TEMPLATE


def bootstrap() -> None:
    key: str = os.getenv("LANGSMITH_API_KEY", "")
    if not key.strip():
        print(LANGSMITH_DISABLED)
        return
    os.environ["LANGSMITH_TRACING"] = os.getenv("LANGSMITH_TRACING", "true")
    os.environ["LANGSMITH_ENDPOINT"] = os.getenv(
        "LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"
    )
    os.environ["LANGSMITH_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "workflow1-onboarding")

    # Compatibility bridge for LangChain integrations that still read LANGCHAIN_* vars.
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = key
    os.environ["LANGCHAIN_ENDPOINT"] = os.environ["LANGSMITH_ENDPOINT"]
    os.environ["LANGCHAIN_PROJECT"] = os.environ["LANGSMITH_PROJECT"]

    print(LANGSMITH_ENABLED_TEMPLATE.format(project=os.environ["LANGSMITH_PROJECT"]))
