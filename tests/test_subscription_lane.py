"""The subscription-lane credential seam: a ``claude_code`` session on ``VALXEL_CLAUDE_AUTH=
subscription`` runs on the saved OAuth login through the pass-through proxy, holds no gateway or
Console credential, and keeps its telemetry env. These are offline, pure/structural checks of the
``subscription_env`` overlay and the ``sandbox`` allowlist that confines it; the full ``_run``
session path (AC-001/003/004-remote/007) needs the REQ-001 settings surface and the live session
harness and is exercised there."""

import types

import pytest

from valxel_sdlc import sandbox
from valxel_sdlc.gateway import ProviderUnavailable
from valxel_sdlc.runtime import claude_code
from valxel_sdlc.runtime.claude_code import subscription_env


def _settings(proxy="https://anthropic.vx.example"):
    # subscription_env reads only settings.claude_proxy_url; a stub keeps this test independent of
    # the REQ-001 Settings surface that adds claude_auth/claude_proxy_url.
    return types.SimpleNamespace(claude_proxy_url=proxy)


def test_subscription_env_swaps_in_the_proxy_and_oauth_token(monkeypatch):
    # AC-002: the swap — the proxy base URL and the subscription OAuth token, no minted gateway key.
    monkeypatch.setattr(claude_code.secret_ring, "get",
                        lambda name, *a, **k: "oauth-xyz" if name == "CLAUDE_CODE_OAUTH_TOKEN" else "")
    env = subscription_env(_settings("https://proxy.example"))
    assert env["ANTHROPIC_BASE_URL"] == "https://proxy.example"
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "oauth-xyz"


def test_subscription_env_blanks_the_console_key_and_auth_token(monkeypatch):
    # AC-004 (the load-bearing blanks): ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN are both in
    # sandbox.MODEL_KEYS["claude_code"], so sandbox.session_env would auto-load a stored key/token
    # and Claude Code would let it out-rank the OAuth login. The overlay must blank both.
    monkeypatch.setattr(claude_code.secret_ring, "get", lambda *a, **k: "oauth-xyz")
    env = subscription_env(_settings())
    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["ANTHROPIC_AUTH_TOKEN"] == ""
    assert {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"} <= set(sandbox.MODEL_KEYS["claude_code"])


def test_subscription_env_without_a_token_is_provider_unavailable(monkeypatch):
    # No escrowed token: fail with a message naming the setting and the missing secret, so the
    # role's fallback: list takes over rather than the session starting credential-less.
    monkeypatch.setattr(claude_code.secret_ring, "get", lambda *a, **k: "")
    with pytest.raises(ProviderUnavailable) as exc:
        subscription_env(_settings())
    assert "CLAUDE_CODE_OAUTH_TOKEN" in str(exc.value) and "subscription" in str(exc.value)


def test_confinement_claude_code_carries_the_token_codex_does_not():
    # AC-004 (structural confinement): the subscription credentials ride only a claude_code session.
    # sandbox.session_env passes them for claude_code (they are in its allowlist) and blanks them
    # for codex (they are not), so the token never reaches a non-Anthropic runtime.
    base = {"CLAUDE_CODE_OAUTH_TOKEN": "oauth-xyz", "ANTHROPIC_BASE_URL": "https://proxy.example",
            "PATH": "/usr/bin"}
    cc = sandbox.session_env("claude_code", "/home/s", base=base)
    assert cc["CLAUDE_CODE_OAUTH_TOKEN"] == "oauth-xyz"
    assert cc["ANTHROPIC_BASE_URL"] == "https://proxy.example"
    cx = sandbox.session_env("codex", "/home/s", base=base)
    assert cx["CLAUDE_CODE_OAUTH_TOKEN"] == ""
    assert cx["ANTHROPIC_BASE_URL"] == ""


def test_metering_env_survives_the_subscription_overlay(monkeypatch):
    # AC-008: _run merges the overlay as {**kwargs["env"], **subscription_env(settings)}; the
    # telemetry env session_options already merged is additive, so it survives — and the blank
    # still wins over a pre-existing Console key.
    monkeypatch.setattr(claude_code.secret_ring, "get", lambda *a, **k: "oauth-xyz")
    kwargs_env = {"CLAUDE_CODE_ENABLE_TELEMETRY": "1", "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel:4317",
                  "ANTHROPIC_API_KEY": "console-key"}
    merged = {**kwargs_env, **subscription_env(_settings())}
    assert merged["CLAUDE_CODE_ENABLE_TELEMETRY"] == "1"
    assert merged["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://otel:4317"
    assert merged["ANTHROPIC_API_KEY"] == ""
