"""REQ-005 / AC-005 — a Claude Code subscription limit (5-hour or weekly) maps to
ProviderUnavailable, so the role's ``fallback:`` chain takes over.

The subscription limit surfaces as a human-readable result message, not an HTTP 429: the Claude
Code CLI reports "Claude usage limit reached. Your limit will reset at 3pm" (5-hour) or "Weekly
limit reached ..." (weekly) as the session result with ``is_error`` set. The stock "429" / "rate
limit" markers only appear when the limit surfaces as an SDK *exception* (the ``run`` path), so they
do not cover the result-message path (``_finish``); ``TRANSIENT_MARKERS`` carries the two plan-limit
phrases by name. Messages captured in claude-code issue 9236 and claudeissues 12789.
"""

import pytest

from valxel_sdlc.gateway import (
    InMemoryLedger,
    ModelGateway,
    ProviderUnavailable,
    StubProvider,
    is_transient,
)
from valxel_sdlc.runtime.claude_code import ClaudeCodeRuntime

FIVE_HOUR = "Claude usage limit reached. Your limit will reset at 3pm (America/New_York)"
WEEKLY = "Weekly limit reached · resets 10am (Asia/Seoul) · /upgrade to Max or turn on /extra-usage"


@pytest.mark.parametrize("message", [FIVE_HOUR, WEEKLY])
def test_subscription_limit_is_transient(message):
    # The result-message path: no "429" in the text, matched by the plan-usage phrasing.
    assert is_transient(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "Error code: 429 - {'type': 'rate_limit_error', 'message': 'rate limited'}",
        "overloaded_error: the model is temporarily overloaded",
    ],
)
def test_api_level_rate_limits_stay_transient(message):
    # The exception path (``run``): the API 429 was already covered by the stock markers; no regression.
    assert is_transient(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "Reached the maximum number of turns",  # a turn cap — a deliberate stop, not a provider outage
        "Cost limit reached: the session budget of $4.00 was exceeded",  # a budget cap — not transient
        "I can't help with that request.",  # a refusal
    ],
)
def test_non_plan_limits_are_not_transient(message):
    # The new markers stay narrow: a bare "limit reached" would wrongly trip these (plan-review R-2).
    assert is_transient(message) is False


def test_finish_raises_provider_unavailable_on_subscription_limit(settings):
    # The limit reported as an is_error result flows through _finish to ProviderUnavailable, so the
    # role fallback chain advances instead of surfacing the limit as a generic failure.
    runtime = ClaudeCodeRuntime(ModelGateway(settings, InMemoryLedger(), {"stub": StubProvider()}))
    out = {"is_error": True, "error": FIVE_HOUR}
    with pytest.raises(ProviderUnavailable):
        runtime._finish(task=None, model="anthropic/claude-sonnet-5-5", out=out, session_mode="fresh")
