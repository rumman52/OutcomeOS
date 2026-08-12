# OutcomeOS Milestone 2 recovery and implementation prompt

Use the pre-run configuration first, then give the prompt below to one Codex Cloud task. The prompt
is deliberately evidence-gated: milestone names, plans, and earlier green runs are not proof that the
current commit satisfies a gate.

## User pre-run configuration

1. Configure the OutcomeOS Codex environment for **Python 3.12**, **Node.js 22**, and **pnpm
   10.14.0**, then reset its cached environment after saving any runtime or setup change.
2. In the network-enabled setup script, run `pnpm install --frozen-lockfile`. If the repository's
   genuine uv lockfile exists, run `uv sync --project apps/api --frozen`. If it is absent, run the
   repository-appropriate `uv lock --project apps/api`, inspect the resulting lockfile for embedded
   credentials and private-index tokens, and then run the frozen sync. Do not fabricate or hand-edit
   either lockfile.
3. If agent-phase dependency access is necessary, allow only package hosts required by the locked
   project. Do not enable unrestricted browsing merely to install dependencies.

## Codex Cloud prompt

```text
You are recovering and implementing OutcomeOS Milestone 2 in repository rumman52/OutcomeOS. Work
autonomously through the evidence gates below, but remain strictly inside the authorization boundary.
Treat source, migrations, tests, and CI results—not branch names, commit subjects, pull-request titles,
plans, or claims—as evidence. The design-time baseline was main commit
7244a7638088fd53c95dd27c9b5010f690171c30 (the merge of PR #13), but you must discover and record
the actual current main head before branching. PR #13 reportedly added only
docs/superpowers/plans/2026-08-12-outcomeos-milestone2-event-pipeline.md and did not implement or
verify Milestone 2; confirm this from its changed-file list and report rather than trusting this prompt.

MISSION AND STOP CONDITION

Close evidence-supported Milestone 1 defects without weakening controls; implement the full
provider-neutral Milestone 2 event-ingestion and durable-processing pipeline; prove deterministic
work locally and real PostgreSQL 17/pgvector plus S3-compatible behavior in GitHub Actions; leave one
draft pull request open and unmerged. Stop before Milestone 3, deployment, production/customer
access, or any live provider connection.

AUTHORIZATION

You may inspect the repository, Git history, PRs, workflow runs, and all applicable AGENTS.md files;
create one feature branch from a clean, confirmed, then-current main head; use dependencies installed
during the configured setup; add or repair tests, application code, additive migrations, CI,
Makefile targets, safe environment examples, and documentation necessary for Milestone 1 closure and
Milestone 2; make focused commits using exact-path staging; push only that feature branch; open exactly
one draft PR into main; inspect Actions results and logs; and push focused corrective commits.

You must not merge, commit to or modify main directly, deploy, access production/customer systems,
use production secrets/customer payloads/real provider credentials, rewrite history, force-push,
discard user work, edit an applied migration, or weaken security, typing, lint, coverage, RLS,
migration, integration, or E2E gates. Never substitute SQLite, mocks, emulators, or skipped tests for
mandatory PostgreSQL or real S3-compatible verification. Do not implement contracts, attribution,
outcome qualification, billing, ledger, disputes, payments, AI decisions, postbacks, or any Milestone
3-or-later capability.

PHASE A — PREFLIGHT AND RECOVERY AUDIT

1. Read every applicable AGENTS.md plus README, Makefile, environment examples, dependency metadata,
   lockfiles, workflows, migrations, source, tests, and milestone/status documentation. More deeply
   nested instructions win within their scope.
2. Record repository, remotes, current branch, exact main SHA, dirty/untracked state, recent history,
   migration revisions/heads, lockfile locations and integrity, actual Python/Node/pnpm/uv versions,
   and existing CI behavior. Verify Python is 3.12, Node is 22, and pnpm is 10.14.0; requested
   environment settings alone are not evidence.
3. Inspect PR #13 with GitHub and Git, including its changed files and reported verification. Classify
   every Milestone 1 and Milestone 2 requirement as present, partial, absent, or unverified, citing
   repository evidence.
4. Preserve all unrelated work. Do not clean, reset, stash, overwrite, or amend it. Create exactly one
   clearly named feature branch only from a clean, fetched, confirmed main base. If that cannot be
   done safely, stop with the exact obstruction and handoff commands.
5. Use the synchronized environment. Never silently resolve or upgrade dependencies. If a genuine uv
   lockfile was generated in setup, inspect it for credentials/private-index tokens, review its diff,
   and defer committing it until the Milestone 1 dependency tests pass. If a lockfile already existed,
   use only frozen sync.

PHASE B — MILESTONE 1 CLOSURE AND FIRST CI GATE

1. Write a focused failing test before each behavioral repair. Based on observed evidence, repair
   strict Ruff, formatting, mypy, unit/coverage, clean Next.js build, deterministic Playwright,
   migration, authentication, authorization, tenant isolation, forced RLS, and production fail-closed
   defects. Do not broaden scope or weaken an invariant to make a test green.
2. Ensure demo authentication and mock integrations fail closed at startup whenever
   APP_ENV=production, regardless of other enabling flags. Derive tenant context from authenticated
   server-side principals; require tenant context in repositories; include positive and cross-tenant
   negative tests.
3. Make integration targets exit non-zero with a clear diagnostic when required service/configuration
   prerequisites are absent. A local lack of Docker, psql, PostgreSQL, or MinIO is a recorded local
   environment limitation, not permission to skip or mock a mandatory gate.
4. Validate the genuine uv lockfile and frozen installations. Run focused tests, strict lint/types,
   unit tests with at least 90% Python coverage, clean web/API builds, migration static checks, and
   locally available deterministic checks. Record exact commands and outcomes; never call a skipped,
   cancelled, interrupted, timed-out, or unavailable check successful.
5. Make the first coherent Milestone 1 closure commit with exact-path staging. Push only the feature
   branch and open exactly one DRAFT pull request to main. The PR title/body must state recovery scope,
   gates, security impact, current limitations, and that it must not be merged yet. Record base/head
   SHAs and the PR URL. Do not open another PR later.
6. Use that draft PR's Actions run on the exact pushed SHA to prove Milestone 1. Inspect every failed
   job and its logs. Never blindly rerun: rerun only a demonstrated transient infrastructure failure;
   deterministic failures require a focused test/code correction and commit. Do not describe
   Milestone 1 as passed or begin Milestone 2 while a security-critical authentication,
   authorization, PostgreSQL, RLS, tenant-isolation, production-config, or migration check is failing
   or unavailable.

PHASE C — MILESTONE 2 PERSISTENCE, STORAGE, AND INGRESS

Use test-driven, focused modules. Keep domain policy out of HTTP routes, React components, worker
runners, and SDK adapters. Treat API/event contracts as versioned interfaces and update producers,
consumers, contract tests, and documentation together.

1. Add the next additive, reversible Alembic revision without modifying existing revisions. Model
   tenant-scoped integration endpoints, encrypted secret versions, webhook receipts, canonical
   events, outbox jobs, job attempts, CSV imports/errors, replay lineage, reconciliation runs/
   anomalies, and payload-free worker heartbeats. Maintain exactly one intended Alembic head.
2. Every tenant-owned row, query, cache/object key, event, job, audit record, and credential carries an
   immutable tenant_id. Use composite tenant foreign keys, tenant-inclusive uniqueness, forced RLS,
   immutable-tenant and append-only protections, conflict constraints, explicit state constraints,
   and least privilege. Never perform an unscoped lookup followed by an in-memory tenant check.
3. Implement high-entropy public endpoint resolution without exposing tenant identity. Encrypt secret
   versions with AES-256-GCM or an equivalent authenticated-encryption construction, authenticated
   context, production-managed key material, bounded overlap/rotation, redaction, and production
   fail-closed validation. Never log or return secret material.
4. Verify webhook HMAC-SHA-256 over the exact raw request bytes before parsing business data. Enforce
   bounded body size, timestamp/replay window, constant-time comparison, strict canonical parsing,
   explicit consent behavior, and tenant-scoped idempotency. Atomically persist receipt, canonical
   event, and original outbox job with defined duplicate-versus-conflict behavior. An invalid signature
   must not reach parsing or persistence.
5. Add a provider-neutral object-storage port and S3-compatible implementation for raw evidence.
   Use tenant-prefixed deterministic keys, conditional create semantics, digest/length verification,
   bounded I/O, encryption/configuration expectations, retention boundaries, tenant-safe read/head/
   delete, and production fail-closed configuration. Do not present an in-memory adapter as integration
   evidence.
6. Expose only focused tenant-authorized management APIs and the public webhook ingress needed for
   Milestone 2. HTTP handlers translate requests/responses; repositories and domain services enforce
   policy and transaction boundaries.

PHASE D — DURABLE PROCESSING AND OPERATIONS

1. Implement PostgreSQL job claiming with FOR UPDATE SKIP LOCKED, atomic state transitions, unique
   opaque lease tokens, lease deadlines, heartbeats, bounded exponential retry, persisted attempts,
   terminal dead letters, crash recovery, stale-owner rejection, graceful shutdown, continuous mode,
   and deterministic --once operation. Persist only safe payload-free worker health metadata.
2. Make event persistence and initial outbox creation atomic. Preserve at-least-once semantics and make
   handlers idempotent; never claim exactly-once delivery. Enforce ownership on renew/complete/fail so
   a stale worker cannot mutate a reclaimed job.
3. Add tenant-authorized dead-letter list/detail/replay with immutable lineage, audit metadata,
   idempotent concurrent replay, and no mutation of the original accounting/history record.
4. Add reconciliation that repairs only enumerated, deterministic, safe inconsistencies. Record
   sanitized anomalies for unsafe/ambiguous cases; do not hide or auto-correct them.
5. Add bounded, streaming, asynchronous, idempotent CSV ingestion through the same canonical event
   service. Enforce byte/row/field/header/encoding/schema limits, persist safe per-row errors and
   counters, handle partial results and object failures, and maintain tenant isolation.
6. Keep routes, repositories, canonical/domain policy, handlers, storage clients, import services,
   operations, and worker runtime in small focused modules. Never put domain rules in runner code.

PHASE E — TEST MATRIX, CI, DOCUMENTATION, AND PR CONVERGENCE

1. Add focused tests before implementation for all changed behavior. The mandatory matrix includes:
   - signed webhook success; raw-byte sensitivity; rotation overlap/expiry; replay-window rejection;
     duplicate and conflict semantics; invalid-signature-before-parse; transaction rollback/atomicity;
   - real PostgreSQL 17/pgvector clean migration, restricted-role forced RLS, positive/negative tenant
     isolation, concurrency, lifecycle, immutable tenant IDs, and composite tenant foreign keys;
   - concurrent SKIP LOCKED claims, lease loss/stale owner, retry, dead letter, replay, reconciliation,
     heartbeat, graceful shutdown, and crash recovery;
   - real S3-compatible put, conditional duplicate put, read, head, digest mismatch, tenant separation,
     retention boundaries, and safe delete;
   - CSV byte/row/field limits, encoding, header/schema, partial results, idempotency, object failure,
     lease recovery, and cross-tenant access;
   - malformed/missing/insecure production configuration and demo/mock production fail-closed cases;
   - deterministic web build and Playwright E2E; and
   - clean migration, upgrades from every supported baseline, downgrade/upgrade round trip, and exactly
     one intended Alembic head.
2. Configure GitHub Actions on an Ubuntu GitHub-hosted runner with Node 22, pnpm 10.14.0, Python 3.12,
   `pnpm install --frozen-lockfile`, and frozen uv sync. Use PostgreSQL 17 with pgvector and separate
   migration-owner and restricted application identities. Use a real S3-compatible service such as
   MinIO with health checks and test-only credentials. Bind service ports only to runner loopback and
   never expose or reuse credentials outside the disposable job.
3. CI must run strict lint/format/type checks, unit tests with >=90% Python coverage, the entire real
   PostgreSQL and S3 integration matrix with zero mandatory skips, deterministic builds and Playwright
   E2E, migration validation/round trips/one-head checks, secret scanning, and `git diff --check`.
   Assert zero skipped mandatory integration tests rather than relying on pytest collection behavior.
4. Make `make verify` honestly execute every required gate, including integration and E2E, and fail
   non-zero with a clear message when prerequisites are absent. Do not retain a success path that merely
   prints that a required check is available elsewhere.
5. Update .env.example with names and safe descriptions only, plus README and architecture, security,
   event catalog, integrations, operations, setup, API/webhook, storage/retention, worker/retry,
   replay/reconciliation, CSV, and implementation-status documentation. Describe only executable,
   exact-SHA-verified behavior as implemented; clearly label local/test adapters, no-live-provider
   status, at-least-once semantics, and any unverified limitation.
6. Continue on the same feature branch and same draft PR. Commit coherent slices with exact-path
   staging. For every pushed head SHA, inspect every workflow job and failed log. Fix deterministic
   defects with focused tests/code and commits. Rerun a job without code changes only when logs prove a
   transient GitHub/service failure. Continue until the complete required gate passes on the exact
   current head SHA or an external blocker is proven.

DEPENDENCY, FAILURE, AND EVIDENCE RULES

- Use checked-in lockfiles and frozen installs. Never fabricate a uv lockfile, hand-edit generated
  lockfiles, run an unconstrained upgrade, or silently resolve during the agent phase. Trace dependency
  failures to setup, lockfile, cache, or network configuration and report the evidence.
- Missing local containers or clients do not justify weakening tests. Required real-service evidence
  comes from Actions on the exact pushed commit.
- Preserve unrelated changes and never use destructive Git operations. Stage exact paths, inspect each
  staged diff, and use focused commit messages. Never amend published commits or force-push.
- Passing evidence belongs to one exact SHA and workflow run. A green job from another commit, a local
  mock, or a plan is not evidence. Record pass/fail/skip counts and coverage from machine output.
- If credentials cannot push or create the one draft PR, stop with exact handoff commands and all local
  commit SHAs. If Actions cannot start because of billing, permissions, service availability, or an
  external outage, stop with the exact run URL (if one exists), logs/conclusion, and prerequisite.
- If a security-critical PostgreSQL, RLS, encryption, tenant-isolation, production-fail-closed, or
  migration check fails or is unavailable, do not claim completion and do not proceed to Milestone 3.
- Never call a failed, skipped, cancelled, interrupted, timed-out, flaky, or unavailable check passed.

COMPLETION BOUNDARY AND FINAL REPORT

Complete only when Milestone 1 is verified on the feature branch, Milestone 2 is implemented in code
and migrations, the complete Actions gate is green on the exact final head SHA, PostgreSQL/pgvector and
real S3-compatible mandatory tests have zero skips, Python coverage is >=90%, migration validation and
required round trips pass with exactly one intended head, and exactly one draft PR remains open and
unmerged. No deployment, production access, live provider integration, Milestone 3, or later work may
have occurred.

The final report must enumerate: repository; base and head branches; starting and ending SHAs; every
commit SHA/subject; draft PR URL/state; exact workflow run URL, run SHA, and every job conclusion;
test pass/fail/skip counts by suite; Python coverage; migration revisions/head and round-trip evidence;
implemented routes and versioned event/API contracts; security and tenant-isolation implications;
local and external limitations; every command/check that did not pass; and an explicit statement that
the PR was not merged and no forbidden activity occurred. Include exact commands and concise output
evidence. Only after this evidence-backed report may the user proceed to OutcomeOS Milestone 3 Part 1.
```
