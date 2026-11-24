---
schema: gc.build.implementation-summary.v1
workflow:
  id: as-6fb
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
    - path: beads/as-8hx
      hash: bead:as-8hx
      ids:
        - REQ-010
    - path: docs/features/valxel-homelab-factory/build/openchoreo-0tools-triage.md
      hash: sha256:a600074148b410ec75a92564782f5a24d3dc36cc284ab8b17604323e201671cb
  coverage:
    - id: REQ-010
      status: covered
---

# Implementation summary — OpenChoreo MCP "0 tools" triage (as-8hx)

## Summary

Owned boundary `as-8hx` (REQ-010) is a **triage-and-verdict** task: root-cause the OpenChoreo MCP
`tools/list`-returns-0 fault, check the `on-ivs3w.3` `iss` issuer change first, and record an
ours/estate verdict. The code fix is conditional on an "ours" verdict.

**Verdict: ESTATE.** The fault and fix live in OpenChoreo/Thunder configuration (the identity
provider's issuer and the MCP service client's scope/audience grant), owned by the
`oeverpad-network` rig. Accordingly this bead changes **no Valxel tool code**, files a handoff
ticket to `oeverpad-network`, and mints **no** follow-up implementation bead (that path is gated on
"ours"). The full analysis is the triage artifact
`docs/features/valxel-homelab-factory/build/openchoreo-0tools-triage.md`.

## Intended Behavior

- The triage (REQ-010, a behavior requirement) is performed and recorded with the `iss`-issuer
  finding and an explicit ours/estate verdict — satisfied by the triage artifact.
- Because the verdict is estate, the estate owner receives an actionable handoff ticket and the
  `agentic-sdlc` tool code is left unchanged (AC-010's "issuer fine → file a ticket, no tool code
  changes" branch).
- Key finding recorded: a *clean* "0 tools" (empty `tools/list`, no exception) cannot be a hard
  issuer rejection — in Valxel's client that would raise and crash `valxel dev cluster check`
  (`cluster.py:267` calls `tool_names()` with no try/except; `mcp_client.py:95-103` turns auth
  failures into a raised `McpError`). The house pattern (`api/mcp.py:79-94`,
  `tests/test_mcp_server.py:106-113`) confirms a wrong `iss` yields 401, not an empty list. So the
  symptom is OpenChoreo+Thunder authorizing the token but exposing zero tools — an estate
  authz/scope outcome.

## Changed Files

| File | Change | Note |
| --- | --- | --- |
| `docs/features/valxel-homelab-factory/build/openchoreo-0tools-triage.md` | added | The triage artifact: symptom, first `iss` check, root-cause, verdict (estate), handoff ticket, evidence index. |
| `docs/features/valxel-homelab-factory/build/implementation-summary-as-8hx.md` | added | This `gc.build.implementation-summary.v1` artifact. |

No files under `src/`, `tests/`, `config/`, or `deploy/` were modified — consistent with the estate
verdict ("change NO tool code").

## Verification

No live OpenChoreo/k3d cluster, `kubectl`, or `valxel` CLI is reachable in this headless worker, and
the test extras (`pytest`, `mcp`) are not installed, so the empirical AC-010 command
(`valxel dev cluster check` against a corrected cluster) is handed to the estate owner in the
ticket. The verifications runnable here both passed:

| Check | Command | Result |
| --- | --- | --- |
| No tool code changed (estate contract) | `git -C /home/gc/src/agentic-sdlc/worktrees/as-8hx status --porcelain` | PASS — only `docs/features/valxel-homelab-factory/build/*.md` added; nothing under `src/`, `tests/`, `config/`, `deploy/`. |
| Build-artifact schema gate (final proof) | `GC_BEAD_ID=as-257 GC_RIG_ROOT=/home/gc/src/agentic-sdlc <gc.check_path>/build-artifact-valid.sh` | PASS — `build artifact valid: schema=gc.build.implementation-summary.v1`. |

- **First verification command** (`git status --porcelain`): observed only the two documentation
  files added under `docs/features/valxel-homelab-factory/build/`; **PASS**.
- **Final proof command** (the pack's `build-artifact-valid.sh`, the gate on this step): validates
  this summary against `gc.build.implementation-summary.v1`; observed **PASS**
  (`build artifact valid`).

## Remaining Risks

- **Issuer branch unconfirmed on a live cluster.** The verdict is drawn from code at `21db417`; if a
  live reproduction shows Valxel sending a wrong `resource`/audience or a stale
  `VALXEL_OPENCHOREO_TOKEN_URL` host after `on-ivs3w.3`, the verdict flips to "ours" and a Valxel
  overlay/config fix (not tool logic) would be needed. The estate ticket asks for that confirmation.
- **Handoff dependency.** Stage 2 of the homelab plan stays blocked until `oeverpad-network`
  completes the Thunder/OpenChoreo config fix; this bead only assigns ownership and evidence, it
  does not unblock the cluster.
- **No follow-up bead minted here by design.** If later evidence reclassifies the fault as "ours",
  a follow-up implementation bead must be minted against the build root `as-hww` at that point.

### Requirement coverage

| ID | Status |
| --- | --- |
| REQ-010 | covered |
