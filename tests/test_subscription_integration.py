"""Integration tests for the subscription lane: real ``load_settings()`` → seam → semaphore path.

These tests drive the composed behaviour that the per-item offline tests could not cover because
each item kept its own stub settings object. Here we construct a real ``Settings`` via
``load_settings()`` with ``VALXEL_CLAUDE_AUTH=subscription`` and verify that the fields the
runtime reads (``claude_auth``, ``claude_proxy_url``, ``subscription_max_sessions``) flow through
correctly end-to-end. (AC-002/AC-004/AC-006 end-to-end, F2 of the assembly review.)
"""

import contextlib
import threading
import time

import pytest

from valxel_sdlc.config import load_settings
from valxel_sdlc.runtime import claude_code
from valxel_sdlc.runtime.claude_code import subscription_env


@pytest.fixture(autouse=True)
def _fresh_semaphore(monkeypatch):
    monkeypatch.setattr(claude_code, "_SUB_SEM", None)


@pytest.fixture()
def subscription_settings(monkeypatch):
    monkeypatch.setenv("VALXEL_CLAUDE_AUTH", "subscription")
    monkeypatch.setenv("VALXEL_CLAUDE_PROXY_URL", "https://anthropic.proxy.vx.example")
    monkeypatch.setenv("VALXEL_SUBSCRIPTION_MAX_SESSIONS", "2")
    return load_settings()


def test_load_settings_subscription_fields(subscription_settings):
    # load_settings() with VALXEL_CLAUDE_AUTH=subscription populates all three subscription fields
    # that the runtime reads (REQ-001: the settings surface exists and is correct).
    s = subscription_settings
    assert s.claude_auth == "subscription"
    assert s.claude_proxy_url == "https://anthropic.proxy.vx.example"
    assert s.subscription_max_sessions == 2


def test_subscription_env_end_to_end_with_real_settings(monkeypatch, subscription_settings):
    # AC-002 end-to-end: real Settings from load_settings() → subscription_env() yields the proxy
    # base URL and OAuth token with no minted gateway credential (ANTHROPIC_API_KEY blanked).
    monkeypatch.setattr(claude_code.secret_ring, "get",
                        lambda name, *a, **k: "oauth-fixture-token" if name == "CLAUDE_CODE_OAUTH_TOKEN" else "")
    env = subscription_env(subscription_settings)
    assert env["ANTHROPIC_BASE_URL"] == "https://anthropic.proxy.vx.example"
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "oauth-fixture-token"
    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["ANTHROPIC_AUTH_TOKEN"] == ""


def test_subscription_slot_with_real_settings_returns_semaphore(subscription_settings):
    # AC-006 end-to-end (settings path): _subscription_slot() with a real Settings that has
    # claude_auth="subscription" returns the process-global semaphore, not a nullcontext.
    slot = claude_code._subscription_slot(subscription_settings)
    assert not isinstance(slot, contextlib.nullcontext)
    assert slot is claude_code._SUB_SEM


def test_third_concurrent_subscription_launch_blocks_with_real_settings(subscription_settings):
    # AC-006 end-to-end (concurrency path): with max_sessions=2 and a real Settings object,
    # exactly two slots are held at once and the third launch blocks until one releases.
    lock = threading.Lock()
    entered = 0
    peak = 0
    hold = threading.Event()

    def worker():
        nonlocal entered, peak
        with claude_code._subscription_slot(subscription_settings):
            with lock:
                entered += 1
                peak = max(peak, entered)
            hold.wait(timeout=5)
            with lock:
                entered -= 1

    threads = [threading.Thread(target=worker, name=f"sub-{i}") for i in range(3)]
    for t in threads:
        t.start()
    try:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with lock:
                if entered >= 2:
                    break
            time.sleep(0.01)
        time.sleep(0.15)
        with lock:
            assert entered == 2, f"expected exactly two holders, saw {entered}"
            assert peak == 2, f"cap of two was exceeded (peak {peak})"
    finally:
        hold.set()
        for t in threads:
            t.join(timeout=5)
    with lock:
        assert peak == 2, f"more than two sessions held a slot at once (peak {peak})"
