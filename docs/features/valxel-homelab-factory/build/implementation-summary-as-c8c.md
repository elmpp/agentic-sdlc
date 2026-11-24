---
schema: gc.build.implementation-summary.v1
workflow:
  id: as-r54
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
    - path: beads/as-c8c
      hash: bead:as-c8c
      ids:
        - REQ-009
    - path: docs/self-hosted.md
      hash: sha256:66e8bb64d6c73e922a9573fd59abd31160cc2d2e40d04d45703f7a91488a29a2
  coverage:
    - id: REQ-009
      status: covered
---

# Implementation summary — document the subscription lane in the self-hosted guide (as-c8c)

## Summary

Owned boundary `as-c8c` (REQ-009, operator-facing documentation): document the Claude **subscription
lane** in the self-hosted operator guide. Added a new section **"6. The Claude subscription lane
(optional)"** to `docs/self-hosted.md` (the guide introduced in T-124), and renumbered the former
section 6 to **"7. Uninstall"** so the numbered install flow stays intact. No code change — this is a
docs-only slice that describes the operator surface of the credential-seam work (sibling `as-4cz`)
and the settings surface (REQ-001).

The new section documents, for an operator:

- **The three settings** — `VALXEL_CLAUDE_AUTH` (default `gateway`; `subscription` enables the
  lane), `VALXEL_CLAUDE_PROXY_URL` (the `ANTHROPIC_BASE_URL` pass-through proxy), and
  `VALXEL_SUBSCRIPTION_MAX_SESSIONS` (default `2`, the concurrency cap) — in a table, with the ODP-1
  note to reuse an existing estate proxy variable if one is already named.
- **The one-line revert (REQ-007):** set `VALXEL_CLAUDE_AUTH=gateway` (or unset) to put every role
  back on the gateway, no code or artifact change.
- **The secret contract (OQ-2):** `CLAUDE_CODE_OAUTH_TOKEN` is read from the configured secret store
  (files store: `VALXEL_SECRETS_DIR/CLAUDE_CODE_OAUTH_TOKEN`); provisioning (`claude setup-token`,
  escrow) and the proxy route are estate setup (OOS-001), consumed here only; a missing token fails
  the session as provider-unavailable so the role's `fallback:` takes over.
- **Remote-mode posture (plan-review PR-N2):** the long-lived `CLAUDE_CODE_OAUTH_TOKEN` flows into
  the session environment and, under sandbox/remote, the session pod spec — a deliberate reversal of
  the gateway's short-lived-token design; confinement still holds (`claude_code` only, `secret_scrub`)
  and LOCAL execution is recommended first (R-4).
- **Per-session budget ceiling (plan-review PR-N6):** losing the gateway's priced caps does not mean
  unbounded spend — the SDK client-side `max_budget_usd` session cap, the role's `max_turns`, and the
  concurrency cap all still apply, with the subscription's own limits as the outer ceiling.
- **Proxy header fidelity (R-3 / OQ-6):** the pass-through proxy MUST forward `anthropic-beta` and
  the session's `Authorization` unchanged (the OAuth capability rides on them) — an estate property
  the operator must ensure.

## Intended Behavior

- An operator reading `docs/self-hosted.md` top-to-bottom reaches the subscription lane as an
  optional section after "Back up and restore" and before "Uninstall", and can turn the lane on,
  revert it, provision its secret, and reason about its confinement and spend without reading the
  code.
- Every setting name in the section matches the implemented/declared surface: `VALXEL_CLAUDE_AUTH`
  and `VALXEL_CLAUDE_PROXY_URL` are the `VALXEL_`-prefixed forms of `settings.claude_auth` /
  `settings.claude_proxy_url`, which the credential seam consumes
  (`src/valxel_sdlc/runtime/claude_code.py`, commit `942a366`) and the REQ-001 settings surface adds
  to `config.Settings`; `VALXEL_SUBSCRIPTION_MAX_SESSIONS` follows the same convention
  (`load_settings` reads `VALXEL_<UPPER_SNAKE>`).
- The behavioural claims are accurate against the code: the subscription-first branch keeps the
  gateway for `generic` roles; `subscription_env()` reads `CLAUDE_CODE_OAUTH_TOKEN` via
  `secret_ring.get` and raises `ProviderUnavailable` when absent; `sandbox.MODEL_KEYS["claude_code"]`
  carries `ANTHROPIC_BASE_URL`/`CLAUDE_CODE_OAUTH_TOKEN` while `codex`/`generic` do not; the remote
  path carries the session env into the pod spec via `session_runner.spec_for`; `max_budget_usd` and
  `max_turns` are passed to the SDK session options (`claude_code.py:84-85`); a limit the CLI reports
  as text is treated as transient (`is_transient` → `ProviderUnavailable`).

## Changed Files

| File | Change | Note |
| --- | --- | --- |
| `docs/self-hosted.md` | modified (+73/-1) | New section "6. The Claude subscription lane (optional)" with six subsections (turn it on; revert; the token; confinement; spend; proxy requirements); former section 6 "Uninstall" renumbered to 7. |
| `docs/features/valxel-homelab-factory/build/implementation-summary-as-c8c.md` | added | This `gc.build.implementation-summary.v1` artifact. |

No source, test, config, or chart files changed.

## Verification

Docs-only change; verified structurally and against the implemented code (no application runtime is
exercised). The settings/behaviour were cross-checked against the credential-seam commit `942a366`
(`subscription_env`, the subscription-first branch), `sandbox.py` (`MODEL_KEYS`, `secret_scrub`),
`config.py` (`Settings`, `load_settings` env convention, `max_turns`/`max_call_usd`),
`secret_ring.py` (`VALXEL_SECRETS_DIR` files store), and the plan at
`docs/features/valxel-homelab-factory/planning/plan-light.md`.

| Check | Command | Result |
| --- | --- | --- |
| Structure/render (first verification command) | `grep -n '^## ' docs/self-hosted.md` + a Markdown heading/table scan (headings number 1–7 with no gap; every pipe-table row ≥ 2 columns) | PASS — sections 1–7 contiguous; 31 table rows, none malformed. |
| Required elements present | `grep -c` for each of the three settings, the revert, `CLAUDE_CODE_OAUTH_TOKEN`, `VALXEL_SECRETS_DIR/CLAUDE_CODE_OAUTH_TOKEN`, the pod-spec/remote note, `max_budget_usd`, `max_turns`, `anthropic-beta`, `Authorization`, `claude setup-token` | PASS — all present. |
| Setting-name accuracy | `git grep -n 'claude_auth\|claude_proxy_url' 942a366 -- src/*` cross-checked with the `VALXEL_<UPPER_SNAKE>` convention in `config.load_settings` | PASS — `VALXEL_CLAUDE_AUTH` / `VALXEL_CLAUDE_PROXY_URL` / `VALXEL_SUBSCRIPTION_MAX_SESSIONS` are the correct env forms. |
| Artifact schema gate (final proof command) | `GC_BEAD_ID=as-cgn GC_RIG_ROOT=/home/gc/src/agentic-sdlc "<gc.check_path>/build-artifact-valid.sh"` | PASS — `build artifact valid: schema=gc.build.implementation-summary.v1`. |

- **First verification command** (`grep '^## '` + Markdown scan): headings 1–7 contiguous, all
  tables well-formed, every required element present; observed **PASS**.
- **Final proof command** (the pack `build-artifact-valid.sh`): validates this summary against
  `gc.build.implementation-summary.v1`; observed **PASS**.

## Remaining Risks

- **Co-merge dependency.** This doc describes `VALXEL_CLAUDE_AUTH` / `VALXEL_CLAUDE_PROXY_URL` /
  `VALXEL_SUBSCRIPTION_MAX_SESSIONS` and `subscription_env()` behaviour. Those ship in sibling drain
  members — the REQ-001 settings surface (adds the `Settings` fields) and `as-4cz` (the credential
  seam) — which are not in this worktree (base `9066544`). If the doc merges well ahead of that code,
  it documents settings a running build does not yet honour. `close-source-anchor`/integration should
  land them together, or at least not release the guide section before the settings surface.
- **`VALXEL_SUBSCRIPTION_MAX_SESSIONS` semaphore.** The concurrency setting is documented as the
  lane's cap; the seam commit (`as-4cz`) implements the credential swap but not the semaphore itself
  (plan PR #2 step 4, a separate slice). If that slice is dropped, the documented default `2` would
  not be enforced. Flagged for the `review` step to confirm the setting is wired before release.
- **Estate-owned proxy behaviour.** The `anthropic-beta`/`Authorization` forwarding requirement is a
  property of the operator's proxy, which the tool cannot enforce; the doc states this as an operator
  responsibility rather than a guarantee.

### Requirement coverage

| ID | Status |
| --- | --- |
| REQ-009 | covered |
