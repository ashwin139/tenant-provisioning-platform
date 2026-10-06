SELF-SERVICE SAAS TENANT PROVISIONING PLATFORM
CLAUDE BUILD GUIDE
===============================================

PURPOSE
-------
This guide is intended to be given to Claude as a structured, phase-by-phase build plan for a 2–4 hour Platform Product Engineer assessment.

IMPORTANT:
- AI usage is required for the assessment.
- The goal is to show that YOU are directing the work.
- Do not ask Claude to silently invent or expand scope.
- Keep the actual implementation small, explainable, and defensible.
- Preserve the full Claude conversation as the AI interaction log.


==================================================
STEP 1 — MASTER CONTEXT FOR CLAUDE
==================================================

I am completing a 2–4 hour engineering assessment for a Platform Product Engineer role.

The assessment is evaluating product judgment, solution/capability design, API design, workflow orchestration, prototype quality, failure handling, pragmatic scope, backlog/handoff thinking, and how I use AI.

I want you to act as my senior pair programmer and technical reviewer. I will make the product and architecture decisions. Do not silently expand scope. If you recommend a change, explain why before implementing it.

## Product use case

We are building a prototype called:

Self-Service SaaS Tenant Provisioning Platform

### User

Application engineers / platform consumers responsible for onboarding new SaaS customers.

### Problem

Provisioning a new SaaS tenant often requires several manual infrastructure, application, configuration, and data operations. This creates platform-team dependency, slow tenant onboarding, inconsistent execution, and poor recovery when part of the workflow fails.

### Product hypothesis

A self-service API backed by a stateful provisioning workflow can reduce tenant provisioning lead time and platform-team toil while providing consistent execution and recoverability.

### Primary product metric

Median tenant provisioning lead time:

tenant request accepted → tenant READY

Secondary metrics we may mention:
- provisioning success rate
- retry success rate
- manual interventions per tenant
- self-service adoption rate
- P95 provisioning lead time

## Prototype scope

The prototype MUST implement:

1. REST API using Python and FastAPI.
2. CLI using Python Typer.
3. Tenant creation workflow.
4. Explicit workflow state.
5. Multiple sequential workflow steps.
6. Intentional failure injection.
7. Resume-after-failure / retry.
8. Idempotent handling of previously completed steps.
9. Workflow/status visibility.
10. Local execution with minimal setup.
11. Automated tests for happy path and failure/retry.
12. Documentation explaining what is prototype versus what the production engineering pod should build.

### Workflow

The provisioning workflow should be:

REQUESTED
→ VALIDATING
→ PROVISIONING_DATA
→ CONFIGURING
→ DEPLOYING
→ VERIFYING
→ READY

On any workflow error:

→ FAILED

The tenant should retain:
- failed step
- error message
- completed steps

Retry should resume from the failed/incomplete point and NOT unnecessarily repeat successfully completed non-idempotent work.

### Operations represented by the prototype

1. Validate tenant request
2. Provision tenant data/database
3. Configure tenant
4. Deploy application
5. Run health check

These operations are simulated adapters. We are NOT actually provisioning AWS, Kubernetes, Terraform, RDS, etc.

Use realistic adapter interfaces so they could later be replaced by production integrations.

## Required API

Use /api/v1.

Minimum endpoints:

### Create tenant

POST /api/v1/tenants

Example request:

{
  "name": "acme",
  "region": "ca-central-1",
  "plan": "standard",
  "tenant_model": "pooled"
}

### Get tenant

GET /api/v1/tenants/{tenant_id}

The response should include current state plus step-level workflow execution information.

### Retry tenant

POST /api/v1/tenants/{tenant_id}/retry

Retry should continue safely after partial failure.

Optional only if time permits:

DELETE /api/v1/tenants/{tenant_id}

## Failure injection

We need an easy and explicit way to demonstrate failure.

Support something equivalent to:

--fail-step deploy

from the CLI.

The API may expose a development/demo-only failure injection field or configuration.

Example demonstration:

python cli.py create-tenant globex --fail-step deploy

Expected conceptual output:

✓ validation
✓ data provisioning
✓ configuration
✗ deployment

Tenant state: FAILED

Then:

python cli.py retry <tenant-id>

Expected:

Skipping already completed steps...
✓ deployment
✓ health check

Tenant state: READY

## Tenancy decision

The API contract should include:

tenant_model

Allowed conceptual values:

- pooled
- siloed

For this prototype, only pooled needs to be implemented.

If siloed is requested, return a clear unsupported-capability response rather than pretending it works.

This demonstrates that the API anticipates future multi-tenant capability without overbuilding the prototype.

## Persistence

Keep persistence deliberately simple.

Prefer an in-memory repository unless lightweight SQLite materially improves the demonstration without adding complexity.

The README must explicitly state this is a prototype choice and that production requires durable persistence.

## Architecture

Target architecture:

CLI
→ FastAPI
→ Tenant service/workflow
→ workflow state machine
→ adapters:
   - data provisioner
   - tenant configurator
   - deployer
   - health checker

Adapters should be deliberately separated from orchestration logic.

## Suggested project layout

tenant-platform/
├── README.md
├── requirements.txt
├── cli.py
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── repository.py
│   ├── workflow/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── states.py
│   └── services/
│       ├── __init__.py
│       ├── data.py
│       ├── configuration.py
│       ├── deployment.py
│       └── healthcheck.py
├── tests/
│   └── test_workflow.py
└── docs/
    ├── product-brief.md
    ├── capability-map.md
    └── architecture.md

Adjust this structure only if there is a strong reason.

## Engineering principles

Keep this prototype small.

Prioritize:
- readable code
- explicit state
- clean API contract
- clear error handling
- idempotency
- failure recovery
- developer experience
- demonstrable workflow

Do NOT unnecessarily add:
- Kubernetes
- Terraform
- AWS SDK
- Docker Compose infrastructure
- React
- authentication
- message queues
- Temporal
- PostgreSQL
- elaborate design patterns

Those belong in the production roadmap/backlog.

## Production handoff

The prototype should establish contracts and behavior.

The production engineering pod would own items such as:

- authentication
- RBAC
- durable database persistence
- real workflow orchestration such as Temporal or AWS Step Functions
- Terraform/Pulumi integrations
- Kubernetes/EKS integrations
- secrets management
- audit logging
- observability
- tracing
- rate limiting
- quotas
- policy-as-code
- retries/backoff/timeouts
- multi-region support
- pooled and siloed tenant isolation
- CI/CD
- SLOs
- production testing
- disaster recovery

## Capability map

Prototype capabilities should include:

Self-service:
- create tenant
- inspect tenant
- retry failed tenant

Provisioning:
- validate request
- data provisioning
- tenant configuration
- application deployment
- health verification

Workflow/reliability:
- state tracking
- failure capture
- completed-step tracking
- retry
- idempotent resume

Future capabilities:
- delete/deprovision
- rollback/compensation
- authentication/RBAC
- policy/guardrails
- quotas
- silo tenancy
- observability
- audit
- production orchestration

## Git expectations

We need meaningful incremental commits rather than one final commit.

Do NOT automatically squash everything.

When we reach logical milestones, suggest concise commit messages.

Examples:

1. docs: define tenant provisioning product scope
2. feat: add tenant API contract and models
3. feat: implement provisioning workflow
4. feat: add failure injection and retry
5. feat: add CLI developer experience
6. test: cover happy path and recovery
7. docs: add production handoff and backlog

## Important AI-log requirement

The assessment requires the full AI interaction log.

Do NOT fabricate an AI interaction log.

Our actual conversation is the evidence.

When explaining decisions, clearly identify:
- options considered
- tradeoffs
- why we chose something
- scope we deliberately cut
- course corrections

This needs to demonstrate that I am directing the work.

## Working method

Do NOT build the entire project immediately.

We will work through phases.

For each phase:
1. briefly explain what we are doing and why;
2. make only the requested changes;
3. show important files created/changed;
4. tell me exactly how to test that phase;
5. flag any decision I should make;
6. suggest the next logical commit.

Wait for my next phase instruction before expanding scope.

A successful prototype must remain understandable enough that I can personally explain every important design decision during an interview.


==================================================
STEP 2 — PHASE 1: PRODUCT DEFINITION ONLY
==================================================

PHASE 1 — PRODUCT DEFINITION ONLY

Do not write application code yet.

Based on the agreed Self-Service SaaS Tenant Provisioning Platform, create:

1. docs/product-brief.md
2. docs/capability-map.md
3. docs/architecture.md

Keep each concise.

### product-brief.md

Include:

- Background
- Primary user/persona
- Jobs to be done
- Problem statement
- Product hypothesis
- Proposed developer experience
- Primary success metric
- Secondary metrics
- Prototype scope
- Explicit non-goals
- Risks/assumptions
- What the production pod owns after handoff

For the primary metric use:

Median Tenant Provisioning Lead Time
from accepted request to READY.

Do not invent real baseline performance data.

If an example baseline is useful, explicitly mark it as hypothetical.

### capability-map.md

Organize capabilities into:

1. Self-Service
2. Tenant Lifecycle
3. Provisioning
4. Deployment
5. Workflow Reliability
6. Governance
7. Observability
8. Day-2 Operations

Clearly identify each capability as one of:

- Prototype
- Production MVP
- Future

Include a simple Mermaid capability diagram if useful.

### architecture.md

Describe:

CLI → REST API → Workflow Engine → Adapters

Explain:
- API boundary
- orchestration boundary
- adapter pattern
- workflow states
- retry/resume behavior
- why infrastructure integrations are simulated
- what would change in production

Include a Mermaid architecture diagram.

Keep the solution defensible and pragmatic for a 2–4 hour assessment.

After creating the documents, summarize the top five product/architecture decisions that I should be prepared to defend in an interview.

Do not proceed to implementation.

Suggested commit:
git add .
git commit -m "docs: define tenant provisioning product scope"


==================================================
STEP 3 — PHASE 2: API AND DOMAIN MODEL
==================================================

PHASE 2 — DOMAIN MODEL AND API CONTRACT

Now implement the minimum FastAPI skeleton.

Do not implement the complete workflow yet.

Create the application models and API contract for:

POST /api/v1/tenants
GET /api/v1/tenants/{tenant_id}

Requirements:

1. Use Pydantic models.
2. Generate tenant IDs safely, for example UUIDs.
3. Explicitly model workflow status using enums.
4. Model individual workflow steps and their states.
5. Include:
   - tenant_id
   - name
   - plan
   - region
   - tenant_model
   - status
   - current_step
   - failed_step
   - error
   - workflow step history
   - timestamps where useful
6. Allow pooled tenancy.
7. Reject or clearly mark siloed as unsupported by the prototype.
8. Implement a small repository abstraction.
9. Use in-memory persistence for the prototype unless there is a compelling reason otherwise.
10. Return sensible HTTP status codes and structured errors.

Do NOT implement fake cloud provisioning yet.

Keep business logic out of FastAPI route handlers where practical.

Also create a minimal test confirming:
- tenant can be created
- tenant can be retrieved
- unsupported tenancy is rejected correctly

After implementation:

1. show how to install dependencies;
2. show how to launch the FastAPI server;
3. provide curl examples;
4. run the tests;
5. explain the API design choices;
6. suggest one git commit message.

Stop there.

Suggested commit:
git commit -am "feat: add tenant API contract and models"


==================================================
STEP 4 — PHASE 3: WORKFLOW ENGINE
==================================================

PHASE 3 — IMPLEMENT THE MULTI-STEP WORKFLOW

Implement the tenant provisioning workflow.

Required states:

REQUESTED
VALIDATING
PROVISIONING_DATA
CONFIGURING
DEPLOYING
VERIFYING
READY
FAILED

Workflow:

1. Validate request
2. Provision data
3. Configure tenant
4. Deploy application
5. Health check
6. READY

Create separate adapters/services for each operation.

The infrastructure actions should be simulated but must be real executable Python functions/classes.

Each simulated operation should:
- receive tenant context;
- log what it is doing;
- take a small configurable amount of simulated time if useful;
- return a structured result;
- support safe repeat invocation/idempotent behavior.

The orchestration layer must:
- explicitly update state;
- record successful steps;
- record failure;
- identify the failed step;
- retain error detail;
- never mark a tenant READY unless every required step succeeds.

Do not yet implement retry or failure injection.

Add tests for the successful complete workflow.

I want the design to remain simple enough to explain without framework magic.

After implementation:
- run tests;
- show one successful API request and resulting workflow state;
- explain how orchestration is separated from provisioning adapters;
- explain where a production workflow engine such as Temporal/Step Functions could replace the prototype implementation;
- suggest a git commit.

Do not proceed to retries yet.

Suggested commit:
git commit -am "feat: implement tenant provisioning workflow"


==================================================
STEP 5 — PHASE 4: FAILURE HANDLING
==================================================

PHASE 4 — ADD CONTROLLED FAILURE INJECTION

The assessment explicitly requires failure partway through the workflow.

Add a DEMO/TEST mechanism that lets me intentionally fail a selected workflow step.

Support at least:

- data
- configure
- deploy
- verify

The mechanism must be clearly documented as prototype/demo-only and NOT presented as a production API capability.

A create request should be able to result in a workflow like:

✓ validate
✓ provision data
✓ configure
✗ deploy

Tenant:
status = FAILED
failed_step = DEPLOYING

Preserve all successfully completed state.

The API response/status endpoint must make the failure obvious.

Do not implement retry yet.

Add tests that verify:
1. deployment can intentionally fail;
2. tenant ends in FAILED;
3. failed_step is correct;
4. earlier successful steps remain recorded;
5. later steps are not executed.

Show me exactly how to invoke the failure from the API.

Run tests and suggest the next commit.

Suggested commit:
git commit -am "feat: add workflow failure injection"


==================================================
STEP 6 — PHASE 5: RETRY, RESUME, IDEMPOTENCY
==================================================

PHASE 5 — RETRY, RESUME, AND IDEMPOTENCY

Implement:

POST /api/v1/tenants/{tenant_id}/retry

The retry behavior is critical.

Scenario:

validate = SUCCESS
data = SUCCESS
configure = SUCCESS
deploy = FAILED

When retry is requested:

- validation must not unnecessarily recreate work;
- data provisioning must not create a second resource;
- tenant configuration must not duplicate configuration;
- deployment should retry;
- health verification should execute only after deployment succeeds.

The state machine must safely resume from completed state.

Demonstrate idempotency in a simple, explicit way.

Do not over-engineer this with an orchestration framework.

For the simulated data provisioner, generate/store a fake resource identifier such as:

db-<tenant-id>

Repeated calls should return/reuse the existing identifier instead of creating another fake resource.

Clear the injected failure appropriately so a retry can succeed, or provide an explicit mechanism for doing so.

Add tests proving:

1. failed workflow can retry;
2. retry reaches READY;
3. previously provisioned data is not duplicated;
4. completed steps remain consistent;
5. retrying a READY tenant is either safely idempotent or returns a clear contractually defined response.

Explain your retry semantics and why they are appropriate for this prototype.

Also explain how production implementations might use:
- idempotency keys;
- durable workflow history;
- retries/backoff;
- compensation;
- Temporal/Step Functions.

Do not implement those production mechanisms.

Run the tests and suggest a commit.

Suggested commit:
git commit -am "feat: add idempotent workflow retry"


==================================================
STEP 7 — PHASE 6: CLI DEVELOPER EXPERIENCE
==================================================

PHASE 6 — BUILD THE DEVELOPER CLI

Create a thin CLI using Typer.

The CLI should talk to the FastAPI service through HTTP rather than importing and bypassing the API.

Commands:

python cli.py create-tenant NAME

Options:

--region
--plan
--tenant-model
--fail-step

Then:

python cli.py status TENANT_ID

and:

python cli.py retry TENANT_ID

Output should be developer-friendly.

Example successful experience:

Creating tenant: acme

✓ Validate
✓ Provision data
✓ Configure tenant
✓ Deploy application
✓ Verify health

Tenant ID: ...
Status: READY

Failure:

✓ Validate
✓ Provision data
✓ Configure tenant
✗ Deploy application

Status: FAILED
Failed step: DEPLOYING
Error: Simulated deployment failure

Then retry:

Resuming tenant...

- Validate: already complete
- Data: already complete
- Configuration: already complete
✓ Deployment
✓ Health verification

Status: READY

Do not add a graphical UI.

Keep output professional and easy to demo in a terminal.

Handle common API errors gracefully.

Update requirements as necessary.

Show the exact commands for the three-part demo:
1. happy path
2. failed provisioning
3. retry/recovery

Suggest a git commit.

Suggested commit:
git commit -am "feat: add tenant provisioning CLI"


==================================================
STEP 8 — PHASE 7: TESTS AND QUALITY REVIEW
==================================================

PHASE 7 — TEST THE PROTOTYPE

Review the implementation before adding anything new.

Create/complete automated tests for the most important product behavior.

At minimum test:

1. tenant creation
2. successful end-to-end workflow
3. retrieval/status
4. unsupported tenant model
5. failure during deployment
6. state after failure
7. retry after failure
8. completed operations are not duplicated
9. final READY state after recovery
10. retry behavior for a tenant that is already READY

Prefer meaningful behavior tests over excessive unit test coverage.

Then run all tests.

Also perform a short code review looking specifically for:

- state transition bugs
- duplicated orchestration logic
- API/business logic leaking together
- retry errors
- mutable global state problems
- unclear naming
- weak HTTP error behavior
- unnecessary complexity

Fix only issues that materially improve the prototype.

Do not add production infrastructure.

Report:
- tests executed
- result
- any issues found and fixed
- remaining known prototype limitations

Suggest a git commit.

Suggested commit:
git commit -am "test: cover workflow failure and recovery"


==================================================
STEP 9 — PHASE 8: FINAL README
==================================================

PHASE 8 — WRITE THE FINAL README

Create a polished but concise README.md.

The README should let an evaluator understand the project in about 5 minutes.

Structure it approximately as:

# Self-Service SaaS Tenant Provisioning Platform

## Why this problem

Explain the platform/customer problem.

## User

Application engineers / platform consumers onboarding SaaS tenants.

## Product hypothesis

Describe why self-service + workflow orchestration should improve the experience.

## Demo

Show:

happy path

failure path

retry/recovery path

## Architecture

Include a Mermaid diagram:

CLI
→ FastAPI
→ Workflow
→ simulated adapters

## Workflow

Show the states and failure path.

## API

Document:
POST tenant
GET tenant
POST retry

## Running locally

Exact setup commands.

Assume a clean machine with an appropriate Python version.

## Demo commands

Exact commands evaluator can copy.

## Failure recovery and idempotency

Explain the implementation plainly.

## Prototype decisions

Explain important scope choices, especially:

- in-memory persistence
- simulated infrastructure
- hand-written workflow/state machine
- CLI instead of React
- only pooled tenancy implemented

Explain WHY each choice was made within the 2–4 hour assessment.

## Production handoff

Explain what the developer pod should build next.

## Metrics

Primary:
Median tenant provisioning lead time.

Secondary:
self-service adoption, success rate, retry success, manual intervention.

## Known limitations

Be candid.

Do not claim this is production ready.

The tone should communicate engineering judgment rather than apologizing for the prototype.

After writing it, check every command in the README against the actual repository and make sure they are accurate.

Suggest a git commit.


==================================================
STEP 10 — PHASE 9: PRODUCTION HANDOFF BACKLOG
==================================================

PHASE 9 — CREATE THE PRODUCTION HANDOFF BACKLOG

I need a production backlog that demonstrates that I understand how the prototype becomes a real platform product.

Create approximately 12–18 GitHub issue drafts.

Sequence them by dependency and risk.

Use categories/milestones such as:

M1 — Production Foundations
M2 — Real Provisioning
M3 — Reliability & Operability
M4 — Governance & Scale

Potential areas include:

- durable persistence
- authentication
- authorization/RBAC
- idempotency strategy
- production workflow engine
- retry/backoff/timeouts
- audit log
- Terraform infrastructure adapter
- Kubernetes deployment adapter
- secrets management
- observability/tracing
- metrics instrumentation
- policy-as-code
- quotas
- tenant deprovisioning
- compensation/rollback
- siloed tenant model
- CI/CD and integration testing

For every issue include:

- Title
- Why / product outcome
- Scope
- Acceptance criteria
- Dependencies
- Capability category
- Suggested priority

Do not imply all features need to be built immediately.

Clearly explain the sequencing.

Place the drafts somewhere suitable in the repository, for example docs/backlog.md, so I can use them to create actual GitHub issues.

Also identify the first 5 issues you recommend actually creating first and explain why.

IMPORTANT:
If the assessment requires the backlog as actual GitHub Issues, manually create those GitHub Issues after Claude drafts them. A Markdown backlog alone may not satisfy that requirement.


==================================================
STEP 11 — PHASE 10: FINAL ASSESSMENT REVIEW
==================================================

Act as the hiring panel for a senior Platform Product Engineer.

Review the completed repository against these assessment dimensions:

1. Product judgment
2. Clear user/problem
3. Adoption rationale
4. Capability design
5. API contract
6. Workflow quality
7. Failure handling
8. Idempotency/recovery
9. Prototype scope
10. Developer experience
11. Handoff thinking
12. Production backlog
13. Metrics
14. Technical credibility
15. README/setup quality

Be critical.

For each dimension give:

- Strong
- Adequate
- Weak

and briefly explain why.

Then identify the FIVE highest-value improvements that can realistically be completed within 30 minutes.

Do not recommend:
- React
- Kubernetes
- Terraform
- AWS deployment
- Temporal
- large-scale rewrites

unless an existing implementation is fundamentally broken.

Also identify anything in the repository that I may struggle to explain in an interview because it appears unnecessarily complicated or AI-generated.

Finally, give me ten likely interview questions about my design, with concise points I should understand to answer them myself.

Do not modify code until after completing the review.


==================================================
STEP 12 — PHASE 11: 5-MINUTE DEMO PREPARATION
==================================================

Help me prepare a 5-minute live demonstration of this prototype.

The demo should tell a PRODUCT story rather than becoming a code walkthrough.

Structure it around:

1. User/problem — ~30 seconds
2. Product/API concept — ~30 seconds
3. Happy-path tenant provisioning — ~60 seconds
4. Intentional mid-workflow failure — ~60 seconds
5. Retry/resume/idempotency — ~60 seconds
6. Prototype versus production-pod boundary — ~45 seconds
7. Metric and expected outcome — ~30 seconds

Give me:

- exact commands to run;
- what I should say while each command runs;
- expected outputs;
- backup steps if a command fails;
- 5 likely evaluator questions immediately after the demo.

Do not invent functionality that is not actually implemented in the repository.


==================================================
THE THREE COMMANDS THAT SHOULD TELL THE STORY
==================================================

1. HAPPY PATH

python cli.py create-tenant acme

Expected concept:
✓ Validate
✓ Provision data
✓ Configure tenant
✓ Deploy application
✓ Verify health

Status: READY


2. FAILURE PATH

python cli.py create-tenant globex --fail-step deploy

Expected concept:
✓ Validate
✓ Provision data
✓ Configure tenant
✗ Deploy application

Status: FAILED
Failed step: DEPLOYING


3. RETRY / RECOVERY

python cli.py retry <GLOBEX_TENANT_ID>

Expected concept:
Skipping previously completed work...
✓ Deployment
✓ Health verification

Status: READY


==================================================
IMPORTANT SCOPE RULE
==================================================

DO NOT turn this into:

React
+
FastAPI
+
Postgres
+
Redis
+
Temporal
+
Terraform
+
AWS
+
EKS
+
ArgoCD

The assessment is not asking for a production platform.

The prototype should demonstrate:
- a real user problem
- a clean self-service contract
- multi-step orchestration
- failure handling
- resume/retry
- idempotency
- clear platform-product thinking
- a sensible production handoff

The evaluator should come away thinking:

“This candidate understands what the product needs to do, understands the technical contracts and failure semantics, can prove the concept personally, and knows exactly where the prototype stops and the production pod begins.”


==================================================
FINAL REMINDERS
==================================================

1. Keep the AI interaction log.
2. Use meaningful Git commits throughout the build.
3. Do not squash the entire project into one commit.
4. Make sure the repository is PUBLIC before submission if the assessment requires that.
5. Make sure README commands actually work.
6. Create actual GitHub Issues if the deliverable explicitly requires GitHub Issues.
7. Be prepared to explain every important design choice.
8. Do not claim simulated infrastructure is real infrastructure.
9. Do not claim invented baseline metrics as real.
10. Prefer a small, working, defensible prototype over a broad, unfinished one.
