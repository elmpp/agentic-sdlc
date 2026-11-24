---
schema: gc.build.implementation-summary.v1
workflow:
  id: as-eh9
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
    - path: beads/as-cfi
      hash: bead:as-cfi
    - path: src/valxel_sdlc/laptop/github_apps.py
      hash: sha256:73e4b7e9d866ddb7b51f6effcbb968c5c417155e3e66b5f011c61117ae763093
    - path: src/valxel_sdlc/laptop/__init__.py
      hash: sha256:af03e1b83497c4066ceb7504cec532450caa6dd9ae1ff8c5b1fe6bc93c44a115
    - path: src/valxel_sdlc/vm/bundle/README.md
      hash: sha256:42f56bd54b9884a70420c02a7def3905b8dd565ac5a7d954c7e0cfd2ae3743af
    - path: tests/test_laptop_github_apps.py
      hash: sha256:ed57b760ef9fab5963ed215ba66c789c5ca3532ec95978d06802b85f7642efbc
  coverage:
    - id: AC-001
      status: covered
    - id: AC-002
      status: covered
    - id: AC-003
      status: covered
    - id: AC-004
      status: covered
    - id: AC-005
      status: covered
---

# Implementation summary — VM-tier GitHub App registration: the localhost manifest bug (as-cfi)

## Summary

Owned boundary `as-cfi`: GitHub now rejects a GitHub App manifest whose webhook (hook) URL is a
localhost address — `"Hook url is not supported because it isn't reachable over the public Internet
(localhost)"` — which breaks App registration whenever the manifest flow is used for the VM tier.

**Required first check — does the VM tier have its own App-registration path with the same bug?**
No. The VM tier (`src/valxel_sdlc/vm/__init__.py`, `valxel vm init|doctor|up|down|backup|restore|
upgrade`) does **not** register GitHub Apps at all. It only *consumes* already-registered App
credentials: `init` leaves `VALXEL_GITHUB_APP_PRIVATE_KEY`, `VALXEL_GITHUB_PROVISIONER_PRIVATE_KEY`
and `VALXEL_GITHUB_OAUTH_CLIENT_SECRET` as empty operator-supplied secret files, and `doctor` names
them as missing. The **only** App-manifest construction in the whole repo is
`src/valxel_sdlc/laptop/github_apps.py::manifest()` (verified by grepping the tree for
`hook_attributes` / `callback_urls` / `app-manifests` — it is the sole match). So there is no
separate VM-tier bug to fix; the single shared manifest builder is the thing that must learn to emit
a public base URL so it can register Apps for the VM tier (stage 1 needs public base
`https://valxel.vx.mattpenrice.com` with the webhook delivered via the CF tunnel at
`/api/webhooks/github`).

The fix, per the handover contract, is exactly: **add a `--base-url` option, and omit
`hook_attributes` and `default_events` when there is no public URL.**

## Intended Behavior

`manifest(app, *, name, port, redirect, base_url="")` now has two modes:

- **Public base URL given (the VM tier)** — e.g. `--base-url https://valxel.vx.mattpenrice.com`. The
  App's homepage (`url`), OAuth `callback_urls` / `setup_url` and `hook_attributes.url` all point at
  the base URL (`{base}/api/connections/github/callback`, `{base}/api/webhooks/github`), the webhook
  is registered **active**, and `default_events` is included so GitHub delivers the App's events.
- **No base URL (a laptop, the default)** — homepage and callback stay on `http://localhost:{port}`
  (GitHub accepts localhost there), and `hook_attributes` **and** `default_events` are **omitted
  entirely** from the manifest. GitHub rejects a localhost hook URL, so the laptop ships no webhook
  and the existing watcher polls for CI/PR changes instead (unchanged behavior, now expressed by
  omission rather than an inactive localhost hook).

A new `public_base(base_url)` helper normalises/validates the value up front: it trims a trailing
slash, returns `""` for an empty value, and raises `ValueError` for anything that is not an
absolute, publicly reachable `http(s)` URL — including `localhost`, `127.0.0.1`, `0.0.0.0`, `::1`
and `*.localhost`. `register()` validates **before** opening the browser, and `github_apps.main()`
turns that `ValueError` into a clean one-line message (exit 1) rather than a traceback. `base_url`
is plumbed CLI → `main` → `register` → `_Flow` → `manifest`, and the `dev github-apps` subparser
gains `--base-url`.

The VM operator README (`vm/bundle/README.md`) gains a short "register the two GitHub Apps against
this VM" block showing `valxel dev github-apps --org <org> --base-url https://valxel.example.com`,
closing the previously-undocumented gap of *how* an operator obtains the Delivery/Provisioning Apps
the VM tier requires.

## Changed Files

- `src/valxel_sdlc/laptop/github_apps.py` — new `public_base()` validator; `manifest()` takes
  `base_url` and omits `hook_attributes`/`default_events` without a public URL; `_Flow` stores and
  forwards `base_url`; `register()` validates up front and accepts `base_url`; `main()` reads
  `args.base_url` and catches `ValueError`.
- `src/valxel_sdlc/laptop/__init__.py` — `dev github-apps` gains the `--base-url` argument;
  `callback_urls` docstring clarified as the laptop case.
- `src/valxel_sdlc/vm/bundle/README.md` — operator instructions to register the Apps against the VM
  with `--base-url`, and to place the resulting ids/keys/webhook secret into `.env` / `secrets/`.
- `tests/test_laptop_github_apps.py` — updated the laptop manifest test to assert the webhook and
  events are omitted; added a public-base-URL manifest test, a `public_base` validation test, a
  `register(base_url=...)` end-to-end plumbing test, and a localhost-rejection test; `_drive` can
  now capture the posted manifests.

## Verification

Run from inside the worktree (`/home/gc/src/agentic-sdlc/worktrees/as-cfi`). This worker image has
no `pytest`/project install and no `ruff`, so the added pytest cases are part of the deliverable for
the `review` stage + CI; the behavior itself was proven here by importing the module under test via
the `src` path and exercising it directly.

| Check | Command | Observed |
| --- | --- | --- |
| First verification — syntax of all changed Python | `python3 -m py_compile src/valxel_sdlc/laptop/github_apps.py src/valxel_sdlc/laptop/__init__.py tests/test_laptop_github_apps.py` | PASS |
| Laptop manifest omits webhook + events; public manifest includes active webhook + events; `public_base` rejects localhost/loopback/relative/non-http | direct import via `src` path, assertions on `manifest()` / `public_base()` | PASS |
| `register(base_url=...)` end-to-end through the real `_Flow` HTTP server posts 2 public manifests; a localhost `--base-url` is rejected before the browser opens | standalone replica of the register-level tests | PASS |
| No new non-ASCII (RUF001/2/3 ratchet) and no added line > 120 chars (E501) | `grep -nP '[^\x00-\x7F]'` + added-line length scan over the diff | PASS |
| Final proof — artifact schema gate | `GC_BEAD_ID=as-9vp GC_RIG_ROOT=/home/gc/src/agentic-sdlc /home/gc/.gc/cache/repos/b4d65b1bd6b05cc9c9c2c600b964f97c533aec5c393b7d43d7aa642401541b44/gascity/assets/scripts/checks/build-artifact-valid.sh` | PASS — `build artifact valid: schema=gc.build.implementation-summary.v1` |

- **First verification command** (`py_compile`): all three changed Python files compile; observed **PASS**.
- **Final proof command** (the pack `build-artifact-valid.sh`): validates this summary against
  `gc.build.implementation-summary.v1`; observed **PASS**.

## Remaining Risks

- **ACs not executed under `pytest` in-worker (medium).** The worker lacks the test/lint/type
  toolchain and the installed package, so the five new/updated pytest cases, `ruff` and `mypy` were
  not run here. Correctness rests on `py_compile`, the direct `src`-path behavioral checks, and the
  end-to-end `register()` replica. The `review` stage and CI are the backstop. (An environment gap
  worth fixing so code beads can be AC-verified in-worker.)
- **Webhook-secret reconciliation for the VM tier (operational, out of this boundary).** When an App
  is registered with an active webhook, GitHub returns its own webhook secret
  (`VALXEL_GITHUB_WEBHOOK_SECRET`), while `valxel vm init` generates its own. The operator must copy
  GitHub's returned secret into the VM's `secrets/VALXEL_GITHUB_WEBHOOK_SECRET` so signature
  verification agrees; the README notes this, but no code enforces it. Full automation of VM-tier
  credential placement is separate work.
- **OAuth callback host (low).** The public manifest reuses the established
  `/api/connections/github/callback` path (asserted by existing tests and routed in
  `connections.py`); only the host changes to the base URL. No route change was needed.

### Requirement coverage

Acceptance criteria for this boundary (the bead carries no pre-numbered REQ ids):

- **AC-001** — VM-tier App-registration path checked; finding: it has none of its own (consumes
  credentials only), so the shared `laptop/github_apps.py` manifest builder is the fix site.
- **AC-002** — `--base-url` added and plumbed CLI → `main` → `register` → `_Flow` → `manifest`.
- **AC-003** — With a public base URL, homepage/callback/setup/webhook point at it, webhook active,
  events included.
- **AC-004** — Without a public base URL, `hook_attributes` and `default_events` are omitted.
- **AC-005** — A localhost / non-public / malformed `--base-url` is rejected before the browser opens.

| ID | Status |
| --- | --- |
| AC-001 | covered |
| AC-002 | covered |
| AC-003 | covered |
| AC-004 | covered |
| AC-005 | covered |
