"""The slow operation this whole task exists to get out of the request path
-- stands in for a real call to an LLM API: several seconds of network
latency, and a provider that occasionally errors out. Swapping in a real
`anthropic.Anthropic().messages.create(...)` call is the only change needed
to go from simulated to real; nothing about the job/worker/retry/alert
machinery around it has to change.
"""
from __future__ import annotations

import time

SLOW_CALL_SECONDS = 3.0


class AIProviderError(Exception):
    pass


def call_ai_provider(text: str, mode: str | None, attempts_before_this_call: int) -> dict:
    """`mode` is a testing hook, not something a real caller would send:
    - "always_fail": every call raises -- proves retries exhaust and an alert fires.
    - "flaky": fails on the first two attempts, succeeds on the third --
      proves a job can fail and still complete once retried.
    - anything else: succeeds after the simulated delay.
    """
    time.sleep(SLOW_CALL_SECONDS)

    if mode == "always_fail":
        raise AIProviderError("simulated AI provider outage -- this call never succeeds")

    if mode == "flaky" and attempts_before_this_call < 2:
        raise AIProviderError(
            f"simulated transient AI provider timeout (attempt {attempts_before_this_call + 1})"
        )

    words = text.split()
    summary = " ".join(words[:12]) + ("..." if len(words) > 12 else "")
    return {"summary": summary, "word_count": len(words)}
