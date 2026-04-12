from __future__ import annotations

import itertools
import os
import re
import time
import warnings
from collections import deque

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from workflow1.config import GEMINI_MODEL, LLM_MAX_REQUESTS_PER_MIN
from workflow1.agent.prompts import LLM_KEYS_MISSING_ERROR

load_dotenv()

warnings.filterwarnings(
    "ignore",
    message="Convert_system_message_to_human will be deprecated!",
    category=UserWarning,
)

_raw_keys: list[str] = [
    os.getenv("GOOGLE_API_KEY_1", ""),
    os.getenv("GOOGLE_API_KEY_2", ""),
    os.getenv("GOOGLE_API_KEY_3", ""),
]
_valid_keys: list[str] = [k for k in _raw_keys if k.strip()]
_pool: itertools.cycle[str] | None = None
_call_times: deque[float] = deque()


def _should_rotate_keys() -> bool:
    return os.getenv("LLM_ROTATE_KEYS", "false").strip().lower() in {"1", "true", "yes"}


def _get_pool() -> itertools.cycle[str]:
    global _pool
    if _pool is not None:
        return _pool
    if not _valid_keys:
        raise RuntimeError(LLM_KEYS_MISSING_ERROR)
    if not _should_rotate_keys():
        _pool = itertools.cycle([_valid_keys[0]])
        return _pool
    _pool = itertools.cycle(_valid_keys)
    return _pool


def get_llm(temperature: float = 0.3) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=next(_get_pool()),
        temperature=temperature,
        convert_system_message_to_human=True,
    )


def _acquire_rate_limit() -> None:
    max_per_min = int(os.getenv("LLM_MAX_REQUESTS_PER_MIN", LLM_MAX_REQUESTS_PER_MIN))
    if max_per_min <= 0:
        return
    now = time.monotonic()
    window_start = now - 60
    while _call_times and _call_times[0] < window_start:
        _call_times.popleft()
    if len(_call_times) >= max_per_min:
        sleep_for = 60 - (now - _call_times[0])
        if sleep_for > 0:
            time.sleep(sleep_for)
    _call_times.append(time.monotonic())


def invoke_llm(messages: list[dict], temperature: float = 0.3):
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
    for attempt in range(max_retries + 1):
        _acquire_rate_limit()
        llm = get_llm(temperature=temperature)
        try:
            return llm.invoke(messages)
        except Exception as exc:  # Keep broad: underlying client errors vary.
            message = str(exc)
            retry_match = re.search(r"Please retry in ([0-9.]+)s", message)
            if "RESOURCE_EXHAUSTED" in message and retry_match and attempt < max_retries:
                sleep_for = float(retry_match.group(1))
                time.sleep(max(0.0, sleep_for))
                continue
            raise
