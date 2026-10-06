# Product Brief — Self-Service SaaS Tenant Provisioning

> Status: prototype. Numbers marked *(hypothetical)* are illustrative, not measured.

## Background

A B2B SaaS company runs a multi-tenant product. Every new customer (a "tenant") needs
a database/schema, tenant configuration (plan limits, feature flags, region), an
application deployment or routing entry, and a health check before the customer can log in.

Today this is a platform-team ticket. A platform engineer runs scripts and console steps
by hand, in order, and tells the requester when it is done.

## Primary user

**Application engineer on a product or onboarding team** who is asked to stand up a new
customer tenant (often after a deal closes or for a pilot/POC). They know *what* the tenant
needs (name, region, plan) but do not own the infrastructure and should not need to.

Secondary user: **platform engineer**, who today executes the ticket and later operates
the self-service path.

## Jobs to be done

- "When a customer is signed, I want their tenant ready the same day, so onboarding isn't blocked on another team's queue."
- "When provisioning breaks halfway, I want to see exactly where and resume it, not file a second ticket."
- (Platform) "I want every tenant built the same way, so I stop debugging snowflakes."

## Problem statement

Tenant provisioning is a multi-step, multi-system workflow executed manually through a
ticket queue. This causes:

1. **Lead time** — days of queue time for minutes of work *(hypothetical: 2–5 days vs. ~15 min of hands-on effort)*.
2. **Platform toil** — repetitive work that doesn't scale with sales.
3. **Inconsistency** — manual steps drift; tenants differ in subtle ways.
4. **Poor recovery** — when step 4 of 5 fails, there's no record of what completed, so people redo or skip steps by guesswork.

## Product hypothesis

If application engineers can request a tenant through a **self-service API/CLI backed by a
stateful, resumable workflow**, then median provisioning lead time drops from days to
minutes, platform tickets for tenant creation drop toward zero, and partial failures
are recovered by retry instead of escalation.

## Why they'd adopt it

- It is **faster than the ticket** on day one — the only real adoption lever for internal platforms.
- It is **one command** with the inputs they already know (name, region, plan).
- Failure is **visible and recoverable by them** (`status`, `retry`), so they don't lose control by giving up the ticket.
- Platform team keeps the guardrails (validated inputs, standard steps), so they'll endorse it rather than resist it.

## Proposed developer experience

```
python cli.py create-tenant acme --region ca-central-1 --plan standard
✓ Validate  ✓ Provision data  ✓ Configure  ✓ Deploy  ✓ Verify
Status: READY

python cli.py status <tenant-id>
python cli.py retry  <tenant-id>   # resumes from the failed step; completed work is not repeated
```

The CLI is a thin client over a REST API (`/api/v1/tenants`), so a portal (e.g. Backstage)
or CI pipeline can use the same contract later.

## Primary success metric

**Median Tenant Provisioning Lead Time** — from request accepted (`created_at`) to
tenant `READY` (`ready_at`). Captured per tenant in the prototype; exposed via
`GET /api/v1/metrics`.

Why this one: it is the user-visible outcome, it moves only if the whole workflow works,
and it maps directly to the business pain (customer waiting to go live).

## Secondary metrics

| Metric | Why |
|---|---|
| Self-service adoption rate (% of new tenants via API vs. ticket) | Proves people choose it |
| Provisioning success rate (first attempt) | Workflow/adapters quality |
| Retry success rate | Is recovery actually working |
| Manual interventions per tenant | Residual toil |
| P95 lead time | Tail experience, not just median |

## Prototype scope

- REST API (FastAPI): create, get, retry; metrics.
- CLI (Typer) over HTTP.
- Explicit 5-step workflow state machine with per-step state and timestamps.
- Async execution: create returns `202`, CLI polls status.
- SQLite persistence (state survives an API restart).
- Demo-only failure injection on any step (fails first attempt).
- Retry that resumes from the failed step; adapters idempotent per tenant.
- `pooled` tenancy only; `siloed` rejected with an explicit unsupported error.
- Automated tests for happy path, failure, and recovery.

## Explicit non-goals

- Real infrastructure (AWS, Kubernetes, Terraform, RDS) — adapters are simulated behind real interfaces.
- Authentication/RBAC, quotas, policy-as-code.
- Deprovisioning and rollback/compensation (optional stretch only).
- Web UI.
- Production workflow engine (Temporal / Step Functions).

## Risks and assumptions

| Assumption / risk | Mitigation |
|---|---|
| Lead time is dominated by queue time, not execution time | Validate with ticket data before building M2 |
| Teams trust automation with customer-facing tenants | Visible step status, retry, audit trail |
| Steps can be made idempotent in real systems | Called out as a design constraint for every real adapter |
| Siloed customers have different needs | Kept in the API contract, deferred in implementation |
| Retry alone isn't enough for permanent failures | Compensation/deprovision is a backlog item |

## What the production pod owns after handoff

The prototype fixes the **contract and behaviour**: API shape, workflow states, retry and
idempotency semantics, and the metric. The pod owns making it real: authN/Z, durable
database and workflow history (Postgres + Temporal/Step Functions), real adapters
(Terraform/Kubernetes/secrets), timeouts/backoff, compensation and deprovisioning,
audit, observability, quotas/policy, siloed tenancy, CI/CD and SLOs.
See `docs/capability-map.md` and the GitHub Issues backlog.
