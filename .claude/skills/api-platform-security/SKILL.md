---
name: api-platform-security
description: Platform security conventions for the microservice estate this scanner reviews — the Kong ingress trust model (why `X-User-Id` is trustworthy and must not be reported as header spoofing) and the `/external/`, `/public/`, `/internal/` route-prefix exposure tiers. Load when writing or tuning `security_prompt.md`, triaging a scan result, judging whether a finding about identity headers or JWT verification is a false positive, or rating the severity of an endpoint by who can reach it.
---

# Platform security conventions

Context for every repo under `REPOS_ROOT`. These services do **not** stand
alone — they sit behind a shared gateway that has already done work for them.
Findings that ignore that produce false positives, so this is triage-critical.

The canonical copy of these rules lives in the **"Platform architecture"
section of `security_prompt.md`** — that is what the scanning agent actually
reads. This skill is the human/agent-facing explanation. **If you change one,
change both.**

## 1. The request path

```
internet client
  -> load balancer
    -> Kong ingress
      -> Kong plugin (verifies Authorization: Bearer <token>, sets X-User-Id)
        -> microservice
```

The client sends `Authorization: Bearer <token>`. The Kong plugin verifies the
token at the ingress and **sets** `X-User-Id` on the upstream request. Any
`X-User-Id` the client tried to send is overwritten. The header only carries a
value downstream because the token already verified.

### What this means for findings

`X-User-Id` is a **trusted, gateway-set** value inside a backend service.

**Do NOT report** — these are false positives on this platform:

- "Authentication decision made from a client-supplied header"
- "`X-User-Id` can be spoofed / header injection lets an attacker impersonate"
- "Service does not verify the JWT" / "no token validation middleware"
- "Identity taken from a header instead of the token"

**Still report** — the trust model has edges:

| Situation | Why it is real | Category |
|---|---|---|
| Handler falls back to a user id from query string, body or path param when the header is missing | That fallback *is* client-controlled | `authentication` |
| Role / tenant / plan / `is_admin` read from a client-supplied header, body field or claim the gateway does **not** set | Kong asserts identity, not entitlement | `authorization` |
| Route the gateway does not front (see §2), so the plugin never runs | No verification happened at all | `authentication` / `config_infra` |
| Object fetched by a path id with no `owner_id == X-User-Id` (or `tenant_id`) check | `X-User-Id` proves *who*, never *what they may access* | `authorization` (BOLA/IDOR) |

The last row is the important one: the Kong trust model removes the
authentication class of finding, and removes none of the authorization class.
Ownership and tenant scoping remain fully in scope.

## 2. Route prefixes declare exposure

The segment after the project route is the exposure tier:

| Path shape | Reachable from | Notes |
|---|---|---|
| `/<project>/external/<version>/<api>` | The internet | Untrusted callers, full attack surface |
| `/<project>/public/<version>/<api>` | The internet | Untrusted callers, and typically unauthenticated — weigh hardest |
| `/<project>/internal/<version>/<api>` | Other microservices in the cluster only | Not routed from the internet |

Rating rules:

- `external` / `public`: full severity. `authenticated: false` on a `public`
  route is the documented norm, not something to hedge about.
- `internal` only: normally **one severity level lower** — the attacker needs an
  in-cluster foothold first. Say so in `impact`, and put "requires in-cluster
  network position" in `prerequisites`. Never drop the finding: internal routes
  are exactly what lateral movement and any SSRF you find are aiming at.
- An endpoint that *should* be internal (admin, debug, batch, migration,
  inter-service) sitting on a `public`/`external` prefix is **itself a finding** —
  `authorization` or `config_infra`, usually High.
- Always fill `endpoint` with the full path so the tier is visible in the report.
- Reports (phase 33, report-side, not prompt guidance): a finding on a `external`/`public` route is never hidden by a cross-repo
  "not upheld" verdict; it stays listed as disputed. A control in one calling service does not protect a route the internet reaches directly.
- One handler under several mounts: `endpoint` lists each (`/external/v1; /internal/v1`), most exposed first. The engine checks public/external on the WAF, matches callers on `/internal`, shows Exposure; internal-only flaws sit one level lower and are decided from callers or `in_cluster` (REQ-0127).

## 3. Where to edit

| Change | File |
|---|---|
| What the scanning agent is told | `security_prompt.md`, "Platform architecture" section |
| This explanation | this file |
| Repo-level summary | `docs/guide/toolkit-reference.md`, "Platform security model" |
| Operator-facing docs | `README.md` |

Nothing in `scan_batch.sh`, `report_common.sh` or the report scripts encodes
these rules — they are prompt-level triage guidance only.
