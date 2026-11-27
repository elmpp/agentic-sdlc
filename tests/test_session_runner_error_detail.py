"""A failed session tells the tool why (its container log is gone by the time anyone looks)."""

from valxel_sdlc.session_runner import _failed


class ResultError(Exception):
    def __init__(self):
        super().__init__("Claude Code returned an error result")
        self.subtype, self.terminal_reason, self.api_error_status = "success", "api_error", 400
        self.errors, self.result = ["prompt is too long"], "API Error: 400 prompt is too long"


def test_a_result_error_carries_its_reason():
    out = _failed(ResultError())
    assert out["ok"] is False and out["detail"]["terminal_reason"] == "api_error"
    assert "api_error_status=400" in out["error"] and "prompt is too long" in out["error"]


def test_a_plain_error_is_unchanged():
    assert _failed(ValueError("x")) == {"ok": False, "error": "ValueError", "transient": False}
