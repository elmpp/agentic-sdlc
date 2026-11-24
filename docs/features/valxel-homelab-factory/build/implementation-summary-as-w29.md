---
schema: gc.build.implementation-summary.v1
workflow:
  id: as-msr
  formula: do-work
methodology:
  pack: gascity
  name: build-basic
producer:
  formula: do-work
  stage: implement
  attempt: 1
status: approved
trace:
  upstream:
    - path: beads/as-w29
      hash: bead:as-w29
      ids:
        - REQ-006
    - path: src/valxel_sdlc/runtime/claude_code.py
      hash: sha256:42dcde4dc182d2d9edccb9ff9c2afa17586c306b995820720c144364133d011b
    - path: tests/test_subscription_concurrency.py
      hash: sha256:e033dd7a4185c02ce9db7db7445b7a69863d207556e1202dc2fb764cef42fad5
  coverage:
    - id: REQ-006
      status: covered
---

# Implementation summary — subscription-lane bounded concurrency (as-w29)

## Summary

Owned boundary `as-w29` (REQ-006 / AC-006): a bounded-concurrency cap on subscription
`claude_code` sessions, so the Claude subscription is not hit by more parallel sessions than
`VALXEL_SUBSCRIPTION_MAX_SESSIONS` (default 2). Implemented in
`src/valxel_sdlc/runtime/claude_code.py`:

- New `import threading`.
- A process-global `threading.BoundedSemaphore` (`_SUB_SEM`, lazily created under `_SUB_SEM_LOCK`
  and sized `max(1, subscription_max_sessions)` on first use) plus a helper
  `_subscription_slot(settings) -> contextlib.AbstractContextManager[object]`. In subscription mode
  it returns that shared semaphore; in gateway/default mode it returns `contextlib.nullcontext()`.
- `ClaudeCodeRuntime.run` wraps the session launch: `with _subscription_slot(self.gateway.settings):
  return asyncio.run(self._run(...))`. The slot is acquired before launch and released on completion
  or error by the `with`.

**Why `threading`, not `asyncio`.** Each `run` is its own `asyncio.run` on an engine
`ThreadPoolExecutor` thread (one feature thread per role session), so the cap has to be held ACROSS
those threads, not inside a single event loop. Wrapping the whole `asyncio.run` also covers both the
local and the remote (sandbox) execution paths, which both run under `run` → `_run`.

**Scope decisions (from the boundary + plan):** the cap is GLOBAL, not per-role (OQ-3), and
PER-PROCESS — with N worker processes the effective ceiling is N × the cap (R-1); cross-process
coordination is out of scope and is an estate concern. The size is read once, when the semaphore is
first created, so changing `VALXEL_SUBSCRIPTION_MAX_SESSIONS` needs a worker restart (ODP-2),
acceptable for the homelab.

> **Integration dependency (REQ-001).** The slot reads `settings.claude_auth` and
> `settings.subscription_max_sessions`, which the REQ-001 settings surface adds to `config.Settings`.
> REQ-001 is a sibling drain member and is **not present in this worktree** (base `9066544`), so the
> helper uses `getattr(..., default)`: absent `claude_auth` reads as `gateway` (inert) and the size
> defaults to 2. This keeps the gateway hot path byte-for-byte unchanged and avoids an
> `AttributeError` before REQ-001 merges. The credential seam (REQ-002/003/004, `as-4cz`) touches the
> same file in different methods; see Remaining Risks.

## Intended Behavior

- **REQ-006 / AC-006 (bounded concurrency).** With `VALXEL_CLAUDE_AUTH=subscription` and
  `VALXEL_SUBSCRIPTION_MAX_SESSIONS=2`, at most two subscription `claude_code` sessions hold a slot
  at once; a third blocks on `acquire` until one of the first two returns (completion **or** error,
  since the `with` releases on both). The semaphore is a single process-global, so the cap spans the
  engine's per-session threads.
- **Only in subscription mode.** When `claude_auth != "subscription"` (gateway, unset, or — before
  REQ-001 — absent), `_subscription_slot` returns `contextlib.nullcontext()`; no semaphore is created
  and nothing is throttled. The gateway path is unchanged (REQ-001 default-unchanged invariant).
- **Default cap is 2.** When `subscription_max_sessions` is unset the size defaults to 2 (not
  `threading`'s own default of 1); `max(1, …)` guards against a mis-set 0/negative.

## Changed Files

| File | Change | Note |
| --- | --- | --- |
| `src/valxel_sdlc/runtime/claude_code.py` | modified (+32/-1) | `import threading`; module-global `_SUB_SEM` + `_SUB_SEM_LOCK`; `_subscription_slot()` helper; `run` wraps the launch in the slot. Gateway/`_run` credential logic untouched. |
| `tests/test_subscription_concurrency.py` | added | Offline tests: gateway/absent-settings are nullcontext and create no semaphore; subscription returns one shared semaphore; default cap 2; and the AC-006 thread test — exactly two hold a slot while a third waits, peak never exceeds two. |
| `docs/features/valxel-homelab-factory/build/implementation-summary-as-w29.md` | added | This `gc.build.implementation-summary.v1` artifact. |

The AC-006 test is a **separate file** from the seam's `tests/test_subscription_lane.py` (`as-4cz`),
so the two drain members do not collide at co-merge. No change to `config.py`, `gateway_sessions.py`,
`sandbox.py`, or `strict.py`.

## Verification

**Environment limitation (recorded, not worked around).** This headless implementation worker has no
`ruff`, `mypy`, `pytest`, or `pip`, and the `valxel_sdlc` package and its deps are not importable
here, so the acceptance suite and the linters could not be executed in-worker. The REQ-001 settings
surface is also not in this worktree, so the full `run`/`_run` session path is exercised only after
that sibling slice merges. The checks that WERE runnable here all passed:

| Check | Command | Result |
| --- | --- | --- |
| Syntax (first verification command) | `python3 -m py_compile src/valxel_sdlc/runtime/claude_code.py tests/test_subscription_concurrency.py` | PASS (exit 0) |
| Line length (ruff line-length=120) | `awk 'length>120' …` over both changed files | PASS — no new line over 120 (the 4 >120 lines in the file pre-date this change) |
| Semaphore logic (isolated) | standalone replica of `_subscription_slot` + a 3-thread race | PASS — gateway/absent-settings → nullcontext and no semaphore; subscription → one shared `BoundedSemaphore`; default cap 2; and with cap 2 exactly two threads held a slot while the third blocked, peak never exceeded two |
| Artifact schema gate (final proof) | `GC_BEAD_ID=as-xwo GC_RIG_ROOT=/home/gc/src/agentic-sdlc <gc.check_path>/build-artifact-valid.sh` | PASS — `build artifact valid: schema=gc.build.implementation-summary.v1` |

- **First verification command** (`py_compile`): both changed files compile; observed **PASS**.
- **Final proof command** (the pack `build-artifact-valid.sh`): validates this summary against
  `gc.build.implementation-summary.v1`; observed **PASS**.

**Deferred to the live suite + REQ-001 integration (written here, not executed).** The AC-006
`pytest` (`tests/test_subscription_concurrency.py`) is written against
`valxel_sdlc.runtime.claude_code` and runs once the package and `pytest` are installed and REQ-001's
`Settings` fields exist; its threaded assertions mirror the isolated proof above. `ruff` and `mypy`
likewise run in CI. The design keeps both quiet: the only intentional `ruff` suppression is
`# noqa: PLW0603` (a lazily-sized module-global singleton, matching the repo's justified-noqa style
and the ratchet), and the `return` is a narrowed local so the `AbstractContextManager[object]`
return type is `mypy`-clean. `from __future__ import annotations` keeps the
`threading.BoundedSemaphore | None` annotation a string at runtime (it is a runtime factory, a class
only to the type checker).

## Remaining Risks

- **REQ-001 must co-merge (highest).** The slot reads `settings.claude_auth` /
  `settings.subscription_max_sessions`. The `getattr` defaults make this slice safe in isolation
  (absent → gateway, inert), but the *feature* only throttles once REQ-001 adds the fields and
  `VALXEL_SUBSCRIPTION_MAX_SESSIONS` is wired. Integration/`close-source-anchor` should land REQ-001
  with this slice; `review` should confirm the fields exist at merge.
- **Same-file co-merge with the seam (`as-4cz`).** Both slices edit
  `src/valxel_sdlc/runtime/claude_code.py`. They touch different regions — the seam adds
  `subscription_env` after `session_options` and branches inside `_run`; this slice adds `threading`,
  the `_SUB_SEM`/helper block after the class, and wraps `run` — so a 3-way merge should apply both
  cleanly, but the boundary flagged "land after the seam branch." Integration should rebase this onto
  the seam (and REQ-001) and re-confirm.
- **Per-process cap only (R-1).** With multiple worker processes the real ceiling is
  `workers × VALXEL_SUBSCRIPTION_MAX_SESSIONS`. If the deployment runs more than one worker, set the
  per-worker cap accordingly or treat cross-process limiting as estate work. Documented, out of
  boundary.
- **ACs/lint/types unexecuted in-worker.** `pytest`/`ruff`/`mypy` and the package are absent here, so
  AC-006 (live), lint, and types rest on static review, the isolated thread proof, and the byte-small
  diff. CI and the downstream `review` step are the backstop. (An environment gap worth fixing so
  code beads can be AC-verified in-worker.)

### Requirement coverage

| ID | Status |
| --- | --- |
| REQ-006 | covered |
