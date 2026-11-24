"""Settings surface for the Claude subscription lane (fork PR #2): VALXEL_CLAUDE_AUTH,
VALXEL_SUBSCRIPTION_MAX_SESSIONS and VALXEL_CLAUDE_PROXY_URL — their defaults, env overrides, and the
unrecognised-value fallback. Underpins REQ-001 (opt-in auth, default `gateway`) and REQ-007 (the
one-line revert, which rests on that default)."""

import logging

import pytest

from valxel_sdlc.config import load_settings

_LANE_ENV = ("VALXEL_CLAUDE_AUTH", "VALXEL_SUBSCRIPTION_MAX_SESSIONS", "VALXEL_CLAUDE_PROXY_URL")


def _load(tmp_path):
    return load_settings(mode="stub", database_url="", artifact_dir=tmp_path / "artifacts",
                         governance_source="local")


@pytest.fixture(autouse=True)
def _clear_lane_env(monkeypatch):
    """Start every test from an unset lane, so the host environment can't colour the result."""
    for name in _LANE_ENV:
        monkeypatch.delenv(name, raising=False)


def test_defaults_when_unset(tmp_path):
    """Unset env is the metered gateway: the default every runtime behaves as today under (REQ-001)."""
    s = _load(tmp_path)
    assert (s.claude_auth, s.subscription_max_sessions, s.claude_proxy_url) == ("gateway", 2, "")


def test_env_overrides_are_read(tmp_path, monkeypatch):
    monkeypatch.setenv("VALXEL_CLAUDE_AUTH", "subscription")
    monkeypatch.setenv("VALXEL_SUBSCRIPTION_MAX_SESSIONS", "5")
    monkeypatch.setenv("VALXEL_CLAUDE_PROXY_URL", "https://anthropic.vx.mattpenrice.com")
    s = _load(tmp_path)
    assert s.claude_auth == "subscription"
    assert s.subscription_max_sessions == 5
    assert s.claude_proxy_url == "https://anthropic.vx.mattpenrice.com"


def test_claude_auth_is_normalised(tmp_path, monkeypatch):
    """Surrounding whitespace and case don't matter: the loader strips and lowercases."""
    monkeypatch.setenv("VALXEL_CLAUDE_AUTH", "  SubScription  ")
    assert _load(tmp_path).claude_auth == "subscription"


def test_unrecognised_claude_auth_falls_back_and_warns(tmp_path, monkeypatch, caplog):
    """A typo surfaces as a WARNING and reverts to gateway rather than silently mis-routing."""
    monkeypatch.setenv("VALXEL_CLAUDE_AUTH", "subscriptio")
    with caplog.at_level(logging.WARNING, logger="valxel_sdlc.config"):
        s = _load(tmp_path)
    assert s.claude_auth == "gateway"
    assert any("VALXEL_CLAUDE_AUTH" in m and "subscriptio" in m for m in caplog.messages)
