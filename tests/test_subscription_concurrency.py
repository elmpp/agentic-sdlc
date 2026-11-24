"""Bounded concurrency for subscription ``claude_code`` sessions (REQ-006 / AC-006).

``claude_code._subscription_slot`` hands each session a slot from a process-global
``BoundedSemaphore`` sized by ``VALXEL_SUBSCRIPTION_MAX_SESSIONS`` (default 2) when
``VALXEL_CLAUDE_AUTH=subscription``, and an inert ``contextlib.nullcontext`` otherwise. These are
offline checks of that slot: the cap of two, the third session that waits, and that gateway/default
mode is never throttled. The full ``ClaudeCodeRuntime.run`` session path is exercised by the live
harness. The ``getattr`` defaults also let the slot run before the REQ-001 settings surface
co-merges (a sibling drain member), a contract these tests pin."""

import contextlib
import threading
import time
import types

import pytest

from valxel_sdlc.runtime import claude_code


@pytest.fixture(autouse=True)
def _fresh_semaphore(monkeypatch):
    # The slot is a process-global, created once and cached (its size is fixed at first use), so
    # each test starts from a clean slate rather than inheriting another test's semaphore.
    monkeypatch.setattr(claude_code, "_SUB_SEM", None)


def _settings(auth="subscription", **kw):
    # A stub standing in for the REQ-001 Settings surface (claude_auth / subscription_max_sessions).
    return types.SimpleNamespace(claude_auth=auth, **kw)


def test_gateway_mode_is_a_nullcontext_and_creates_no_semaphore():
    # REQ-006: the cap applies only in subscription mode; gateway mode is inert.
    slot = claude_code._subscription_slot(_settings(auth="gateway", subscription_max_sessions=2))
    assert isinstance(slot, contextlib.nullcontext)
    assert claude_code._SUB_SEM is None
    with slot:  # entering throttles nothing
        pass


def test_absent_req001_settings_default_to_gateway():
    # Before REQ-001 co-merges, a bare settings object must not raise and must read as gateway, so
    # the gateway hot path stays byte-for-byte unchanged (no new AttributeError on the shared path).
    slot = claude_code._subscription_slot(types.SimpleNamespace())
    assert isinstance(slot, contextlib.nullcontext)
    assert claude_code._SUB_SEM is None


def test_subscription_mode_returns_the_one_shared_semaphore():
    settings = _settings(subscription_max_sessions=2)
    first = claude_code._subscription_slot(settings)
    second = claude_code._subscription_slot(settings)
    assert first is second is claude_code._SUB_SEM
    assert not isinstance(first, contextlib.nullcontext)
    assert hasattr(first, "acquire") and hasattr(first, "release")


def test_default_cap_is_two_when_max_sessions_unset():
    # subscription_max_sessions absent -> default 2 (threading's own default would be 1).
    claude_code._subscription_slot(_settings())
    sem = claude_code._SUB_SEM
    assert sem is not None
    assert sem.acquire(blocking=False)      # slot 1
    assert sem.acquire(blocking=False)      # slot 2
    assert not sem.acquire(blocking=False)  # slot 3 would block
    sem.release()
    sem.release()


def test_at_most_two_hold_a_slot_and_the_third_waits():
    # AC-006: with the cap at 2, three concurrent subscription launches -> at most two hold a slot
    # at once and the third blocks on acquire until one releases.
    settings = _settings(subscription_max_sessions=2)
    lock = threading.Lock()
    entered = 0
    peak = 0
    hold = threading.Event()

    def worker():
        nonlocal entered, peak
        with claude_code._subscription_slot(settings):
            with lock:
                entered += 1
                peak = max(peak, entered)
            hold.wait(timeout=5)  # keep the slot held so the third contends for it
            with lock:
                entered -= 1

    threads = [threading.Thread(target=worker, name=f"sub-{i}") for i in range(3)]
    for t in threads:
        t.start()
    try:
        # Wait until two sessions hold a slot; the third must still be blocked on acquire.
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with lock:
                if entered >= 2:
                    break
            time.sleep(0.01)
        time.sleep(0.15)  # settle: a wrongly-unbounded third would slip in during this window
        with lock:
            assert entered == 2, f"expected exactly two holders, saw {entered}"
            assert peak == 2, f"the cap of two was exceeded (peak {peak})"
    finally:
        hold.set()  # release the holders so the third proceeds and the threads can finish
        for t in threads:
            t.join(timeout=5)
    assert all(not t.is_alive() for t in threads), "a subscription worker never finished"
    with lock:
        assert peak == 2, f"more than two sessions held a slot at once (peak {peak})"
