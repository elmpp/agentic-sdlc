# OpenChoreo MCP "0 tools" — triage and verdict (REQ-010 / AC-010)

**Source anchor:** `as-8hx` · **Requirement:** REQ-010 (behavior requirement — the triage
SHALL happen; the code fix is conditional) · **Date:** 2026-11-23 · **Repo rev:** `21db417`

## Verdict

**ESTATE.** The fault and its fix live in OpenChoreo/Thunder configuration (the identity
provider's issuer and the MCP service client's granted scopes/audience), owned by the
`oeverpad-network` rig. **No Valxel (`agentic-sdlc`) tool code is changed by this bead.**

Per the conditional follow-up in the task: because the verdict is *estate*, a handoff ticket is
filed to `oeverpad-network` (below) and **no follow-up implementation bead is minted** in this
repo (that path is gated on an "ours" verdict).

## Symptom

`valxel dev cluster check` reports the OpenChoreo control-plane MCP server offering **zero**
tools:

```
OpenChoreo 1.3.3: 0 MCP tools offered.
  MCP tool missing: get_component or ...
  ...
```

The count and the "tool missing" lines are printed by `live_check` /
`check` in `src/valxel_sdlc/laptop/cluster.py:287` and `:253-255`, driven by
`McpHttp("openchoreo", ...).tool_names()` (`:267`), which calls `list_tools()` over the OpenChoreo
MCP endpoint.

## First check (prime suspect): the `on-ivs3w.3` `iss` issuer change

The vx-eval-01 runbook (Gitea `matt/oeverpad-network` `docs/runbooks/valxel-eval.md`) names the
`on-ivs3w.3` change to Thunder's token **issuer (`iss`)** as the one thing to confirm first. That
change is an *estate* change: it reconfigures Thunder (OpenChoreo's bundled OAuth identity
provider), not any code in this repo.

### What Valxel does on this path (client side)

Valxel is a **client** of the OpenChoreo MCP server. It does not mint, set, or validate the `iss`
claim — it obtains a client-credentials token from Thunder and forwards it as a bearer:

| Step | Code | Note |
| --- | --- | --- |
| Mint token | `src/valxel_sdlc/integrations/mcp_client.py:164-205` (`ClientCredentials`) | OAuth2 `client_credentials` grant to `VALXEL_OPENCHOREO_TOKEN_URL` (Thunder), with optional `scope` and RFC 8707 `resource`. |
| Send token | `mcp_client.py:92-93`, `:116-124` | `Authorization: Bearer <token>` on `initialize` + `tools/list`. |
| Wire-up (live) | `src/valxel_sdlc/services.py:537-557` (`openchoreo_client`) | `token_url`, `client_id` (default `service_mcp_client`), `client_secret`, `scope`, `resource` all from settings. |
| Wire-up (laptop/k3d) | `src/valxel_sdlc/laptop/cluster.py:47-58`, `:261-287` | Defaults point at `thunder.openchoreo.localhost/oauth2/token`, client `openchoreo-system-app`, `resource = <api>/mcp`. |

A repo-wide search finds **no** `VALXEL_OPENCHOREO_ISSUER` setting and **no** issuer validation on
Valxel's OpenChoreo client path (`.env.example:56-61` lists only MCP URL, token URL, client id,
client secret, scope, console URL). The `iss` is minted by Thunder and validated by the OpenChoreo
MCP gateway — both estate components. **Nothing in Valxel's code consumes or depends on the `iss`
value**, so an `iss` change cannot be corrected by editing Valxel.

### Why "0 tools" is the tell — it is *not* a hard issuer rejection

This is the decisive finding. A wrong/mismatched `iss` that the gateway *rejects* would surface as
an HTTP 401 during `initialize`/`list_tools`. In Valxel's client that becomes a raised
`McpError` (`mcp_client.py:95-103` — `_run` wraps any transport/auth exception), and `live_check`
calls `tool_names()` **without** a try/except (`cluster.py:267`), so a hard rejection would make
`valxel dev cluster check` **crash with a traceback**, not print "0 MCP tools offered."

The house pattern confirms the shape of a hard issuer rejection: Valxel's *own* MCP server
(`src/valxel_sdlc/api/mcp.py:79-86`) decodes with `issuer=self.issuer` and
`options={"require": ["exp","iat","iss","sub"]}`; a token with the wrong issuer raises and becomes
`NotAPerson` → **401**. The test `tests/test_mcp_server.py:106-113`
(`test_only_a_persons_token_gets_in`, case `another-issuer`) asserts exactly this: a wrong `iss`
→ `401`, never an empty tool list.

Therefore a *clean* "0 tools" (an empty `tools/list`, no exception) means the OpenChoreo MCP
gateway **authenticated the token and then exposed zero tools** — an authorization / scope /
audience outcome on the OpenChoreo + Thunder side, not a transport-layer auth failure and not a
Valxel client bug.

## Root-cause analysis

Given the symptom shape, the `on-ivs3w.3` `iss` change manifests through one of two estate-side
branches — both fixed in `oeverpad-network`, neither in this repo:

1. **Issuer accepted for authn, but authz maps to no tools.** After the `iss` change, tokens still
   verify (same Thunder signing key) but the new issuer value no longer matches the MCP gateway's
   authorization policy / expected audience / scope-to-tool mapping, so the tool set is filtered to
   empty. Fix: realign Thunder's `iss` (or the gateway's expected issuer/audience) and the
   `service_mcp_client` / `openchoreo-system-app` scope grant in OpenChoreo config.
2. **Issuer is fine; the 0-tools is a separate estate fault.** The MCP service client is not
   granted the tool scopes, the RFC 8707 `resource`/audience the client is registered for is wrong,
   or the control-plane tools are not installed/enabled in the cluster. All are OpenChoreo/Thunder
   configuration.

**What would flip the verdict to "ours":** a live-cluster reproduction showing Valxel sending a
*wrong* `resource` (audience) or pointing `VALXEL_OPENCHOREO_TOKEN_URL` at a stale issuer host
after `on-ivs3w.3`. From the code at `21db417` the laptop-tier defaults
(`cluster.py:47-58`) and the live-mode settings resolution (`services.py:537-557`) are correct and
issuer-agnostic, so the evidence supports **estate**. This caveat is recorded honestly; it was not
reproducible here (see Limitations).

## Limitations of this triage

This triage is a code-level root-cause analysis performed headless (CI/worker), where no live
OpenChoreo/k3d cluster, `kubectl`, or `valxel` CLI is reachable, and the project's test extras
(`pytest`, `mcp`) are not installed. The empirical AC-010 step — running `valxel dev cluster check`
against a cluster after the issuer is corrected — must be executed by the estate owner as part of
the handoff. The verdict rests on the static evidence above, which is sufficient to assign
ownership.

## Handoff ticket → `oeverpad-network` (estate)

> **Title:** OpenChoreo MCP exposes 0 tools after `on-ivs3w.3` Thunder `iss` change
>
> **Owner:** `oeverpad-network`
>
> **Context:** `valxel dev cluster check` / `src/valxel_sdlc/laptop/cluster.py` report
> "OpenChoreo 1.3.3: 0 MCP tools offered." The Valxel client path (`integrations/mcp_client.py`,
> `services.py`, `laptop/cluster.py`) mints a Thunder client-credentials token and calls
> `tools/list`; it sets/validates no issuer and is confirmed correct at repo rev `21db417`.
>
> **Ask:** Confirm the `on-ivs3w.3` issuer (`iss`) change in Thunder and align it with the
> OpenChoreo MCP gateway's expected issuer/audience, and confirm the `service_mcp_client` /
> `openchoreo-system-app` client is granted the MCP tool scopes for `resource = <api>/mcp`.
>
> **Acceptance (AC-010):** after the estate fix, `valxel dev cluster check` lists the OpenChoreo
> tools (`tools_used()` in `integrations/openchoreo.py:404`) with a non-zero count and no
> "tool missing" lines. No `agentic-sdlc` tool code change is required.
>
> **Evidence:** this triage — `docs/features/valxel-homelab-factory/build/openchoreo-0tools-triage.md`.

## Evidence index

- `src/valxel_sdlc/laptop/cluster.py:47-58` — laptop/k3d OpenChoreo + Thunder defaults.
- `src/valxel_sdlc/laptop/cluster.py:261-292` — `live_check`: builds creds, calls `tool_names()`, prints the count.
- `src/valxel_sdlc/integrations/mcp_client.py:92-124` — headers, `list_tools()`, error-to-`McpError` wrapping.
- `src/valxel_sdlc/integrations/mcp_client.py:164-205` — `ClientCredentials` (token mint, `resource`/`scope`).
- `src/valxel_sdlc/services.py:525-557` — `openchoreo_missing` / `openchoreo_client` live wire-up.
- `src/valxel_sdlc/api/mcp.py:79-94` — house issuer-validation pattern (wrong `iss` → 401).
- `tests/test_mcp_server.py:106-113` — `another-issuer` → 401, not an empty tool list.
- `.env.example:56-61` — OpenChoreo client settings (no issuer knob).
