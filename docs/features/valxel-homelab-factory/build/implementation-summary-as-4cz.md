---
schema: gc.build.implementation-summary.v1
workflow:
  id: as-jhs
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
    - path: beads/as-4cz
      hash: bead:as-4cz
      ids:
        - REQ-002
        - REQ-003
        - REQ-004
        - REQ-007
        - REQ-008
    - path: src/valxel_sdlc/runtime/claude_code.py
      hash: sha256:b9c0b560846c20dba8d8b9513c46c5a6d628307a11febda68c757a1c55606721
    - path: tests/test_subscription_lane.py
      hash: sha256:a9cd0f3a6d9558d7bf6fca1b6b447d428ae890e02e3bffe11fac38bbf8cd97c3
  coverage:
    - id: REQ-002
      status: covered
    - id: REQ-003
      status: covered
    - id: REQ-004
      status: covered
    - id: REQ-007
      status: covered
    - id: REQ-008
      status: covered
---

# Implementation summary — subscription-lane credential seam (as-4cz)

## Summary

Owned boundary `as-4cz` (REQ-002/003/004/007/008): the credential seam that lets a `claude_code`
session run on the Claude subscription instead of a minted LLM-gateway token. Implemented in
`src/valxel_sdlc/runtime/claude_code.py`:

- New module helper `subscription_env(settings) -> dict[str,str]` returning the session env overlay
  `{ANTHROPIC_BASE_URL: settings.claude_proxy_url, CLAUDE_CODE_OAUTH_TOKEN: <token>,
  ANTHROPIC_API_KEY: "", ANTHROPIC_AUTH_TOKEN: ""}`; it reads the token via
  `secret_ring.get("CLAUDE_CODE_OAUTH_TOKEN")` and raises `ProviderUnavailable` (naming the setting
  and the missing secret) when absent, so the role's `fallback:` list takes over.
- In `_run`, inside the same `contextlib.ExitStack`, the single `if gateway_sessions.configured():`
  guard became a subscription-**first** two-way branch: `if settings.claude_auth == "subscription":`
  applies the overlay and mints no gateway token; `elif gateway_sessions.configured():` keeps the
  existing gateway mint branch byte-for-byte.

> **Integration dependency (REQ-001).** This slice consumes `settings.claude_auth` and
> `settings.claude_proxy_url`, which the REQ-001 settings surface adds to `config.Settings`. REQ-001
> is a sibling drain member and is **not present in this worktree** (base `9066544`), so this slice
> is correct-by-construction against that interface and becomes runnable once the two merge
> together. See Remaining Risks.

## Intended Behavior

- **REQ-002 (swap):** in subscription mode a `claude_code` session gets the proxy base URL and the
  OAuth token and no minted `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`.
- **REQ-003 (generic + strict):** `gateway_sessions.configured()` stays true in subscription mode,
  so `VALXEL_LLM_GATEWAY_URL` remains set and the one-call generic roles keep the gateway; the
  subscription-first ordering is what stops the seam minting a gateway token for `claude_code`.
  `strict.py` is untouched and sees no new finding.
- **REQ-004 (confinement, incl. remote + scrub):** the overlay rides only the `claude_code`
  session's `kwargs["env"]`; `sandbox.MODEL_KEYS["claude_code"]` carries `CLAUDE_CODE_OAUTH_TOKEN`/
  `ANTHROPIC_BASE_URL` while `codex`/`generic` do not, so `sandbox.session_env` blanks them there.
  The remote path carries the same `kwargs["env"]` into the pod spec via
  `session_runner.spec_for(task, kwargs, …)` (`claude_code.py` `_run_remote`), and the token rides
  the existing `secret_scrub` path in transcripts/logs. The two `""` blanks are load-bearing:
  without them `session_env` would auto-load a stored Console key and it would out-rank the OAuth
  login (`sandbox.py:96-103`).
- **REQ-007 (revert):** with `claude_auth != "subscription"` the seam takes the unchanged `elif`
  gateway branch — revert is intrinsic, no flag teardown needed.
- **REQ-008 (metering):** the overlay is additive, so the telemetry env `session_options` already
  merged (`CLAUDE_CODE_ENABLE_TELEMETRY=1` + `OTEL_*`) survives into the launched session.

## Changed Files

| File | Change | Note |
| --- | --- | --- |
| `src/valxel_sdlc/runtime/claude_code.py` | modified (+27/-2) | `secret_ring` import; `subscription_env()` helper; `_run` subscription-first branch (gateway branch body byte-for-byte unchanged). |
| `tests/test_subscription_lane.py` | added | Offline unit/structural tests: the swap, the load-bearing blanks, the missing-token error, codex confinement, telemetry survival. |
| `docs/features/valxel-homelab-factory/build/implementation-summary-as-4cz.md` | added | This `gc.build.implementation-summary.v1` artifact. |

No change to `config.py` (REQ-001's boundary), `sandbox.py`, `gateway_sessions.py`, or `strict.py`.

## Verification

**Environment limitation (recorded, not worked around):** this headless implementation worker has
no `ruff`, `mypy`, or `pytest`, and the package and its deps (e.g. `httpx`) are not importable here,
so the acceptance suite could not be executed. Additionally the REQ-001 settings surface
(`claude_auth`/`claude_proxy_url`) is not in this worktree, so the session-path ACs run only after
that sibling slice merges. The checks that WERE runnable here all passed:

| Check | Command | Result |
| --- | --- | --- |
| Syntax (first verification command) | `python3 -m py_compile src/valxel_sdlc/runtime/claude_code.py tests/test_subscription_lane.py` | PASS (exit 0) |
| Gateway path bytes unchanged (AC-001/AC-007 static proof) | `git diff -- src/valxel_sdlc/runtime/claude_code.py` | PASS — only `if`→`elif` + the new subscription branch; the gateway `try/except GatewayUnavailable → ProviderUnavailable` and `kwargs["env"]` merge are byte-identical. |
| Overlay logic (isolated) | standalone replica of the `subscription_env` body | PASS — overlay shape incl. both `""` blanks, additive merge keeps telemetry, blank wins over a pre-existing key, missing-token → `ProviderUnavailable`. |
| Artifact schema gate (final proof) | `GC_BEAD_ID=as-67s GC_RIG_ROOT=/home/gc/src/agentic-sdlc <gc.check_path>/build-artifact-valid.sh` | PASS — `build artifact valid: schema=gc.build.implementation-summary.v1`. |

- **First verification command** (`py_compile`): both changed files compile; observed **PASS**.
- **Final proof command** (the pack `build-artifact-valid.sh`): validates this summary against
  `gc.build.implementation-summary.v1`; observed **PASS**.

**Deferred to the live suite + REQ-001 integration (written, not executed here):** AC-001 (default
session-env snapshot equals today's gateway env), AC-002 (swap at the session level), AC-003
(generic still mints a gateway token; `strict.py:57/:60` no new finding), AC-004 remote-spec +
transcript scrub, AC-008 at the session level. The new `tests/test_subscription_lane.py` covers the
offline-verifiable core (swap, blanks, confinement, metering, error path) and runs under `pytest`
once the extras are installed and REQ-001 is merged.

## Remaining Risks

- **REQ-001 must co-merge (highest).** This slice references `settings.claude_auth` /
  `settings.claude_proxy_url`. If it lands before REQ-001 adds those `Settings` fields, every
  `claude_code` run raises `AttributeError` on the subscription check — breaking the default path.
  Integration/`close-source-anchor` must order/merge REQ-001 with (or before) this slice; the
  `review` step should confirm the fields exist at merge.
- **ACs unexecuted in-worker.** The implementation worker lacks the test/lint/type toolchain and the
  package, so AC-001..AC-008, `ruff`, and `mypy` were not run here. Correctness rests on static
  review, the byte-identical gateway diff, and the isolated overlay-logic check. The downstream
  `review` step and CI are the verification backstop. (This is an environment gap worth fixing so
  code beads can be AC-verified in-worker.)
- **Proxy forwarding (out of this boundary).** The overlay assumes `settings.claude_proxy_url` is a
  pass-through proxy that forwards `anthropic-beta` unchanged (the OAuth capability header); that
  proxy/estate route is separate work (plan §Subscription lane).

### Requirement coverage

| ID | Status |
| --- | --- |
| REQ-002 | covered |
| REQ-003 | covered |
| REQ-004 | covered |
| REQ-007 | covered |
| REQ-008 | covered |
