"""A session that reaches its dollar cap escalates the phase instead of being retried forever."""

import pytest

from valxel_sdlc.gateway.providers import BudgetExhausted
from valxel_sdlc.session_runner import _failed


class ResultError(Exception):
    def __init__(self):
        super().__init__("Claude Code returned an error result")
        self.subtype, self.terminal_reason, self.api_error_status = "error_max_budget_usd", "budget_exhausted", None
        self.errors, self.result = [], ""
        self.data = {"subtype": "error_max_budget_usd", "total_cost_usd": 0.41}


def test_the_runner_reports_the_budget_stop_and_its_spend():
    out = _failed(ResultError())
    assert out["detail"]["subtype"] == "error_max_budget_usd" and out["detail"]["total_cost_usd"] == 0.41


def test_the_runtime_raises_budget_exhausted(monkeypatch):
    from valxel_sdlc import session_runner
    from valxel_sdlc.runtime import claude_code

    monkeypatch.setattr(session_runner, "spec_for", lambda *a, **k: {})
    monkeypatch.setattr(session_runner, "run_with_steps", lambda spec, steps: _failed(ResultError()))
    monkeypatch.setattr(claude_code, "steps_for", lambda task: None)
    rt = claude_code.ClaudeCodeRuntime.__new__(claude_code.ClaudeCodeRuntime)
    rt.plugins_for = lambda role: []

    class Tags:
        feature_id = "F-1"

    class Task:
        tags, resume, fresh_tail, session_mode, role = Tags(), "", "", "fresh", "architect"

        class layers:
            tail = ""

    with pytest.raises(BudgetExhausted) as e:
        rt._run_remote(Task(), "m", {"max_budget_usd": 0.16}, store=None, scratch="/tmp")
    assert e.value.spent_usd == 0.41
