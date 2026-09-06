# Artifact contracts

Every artifact contains its feature ID, revision, input revisions, author role, assumptions, open questions, and stable item IDs. Never renumber an existing ID; mark obsolete items explicitly.

## Functional requirements

Include business goal, non-goals, actors, glossary, main and alternative scenarios, business rules, permissions, validation, errors, acceptance criteria, analytics/telemetry expectations, non-functional expectations, assumptions, questions, and requirement IDs `FR-NNN`.

Acceptance criteria must be observable. Prefer Given/When/Then when it improves precision.

## UX/UI design

Include requirement mapping, journeys `FLOW-NNN`, screens `SCREEN-NNN`, navigation, component behavior, content, accessibility, responsive behavior, and loading/empty/error/permission states. Link or embed prototype evidence when generated.

## Architecture and decomposition

Include current-system findings, proposed design, component boundaries, API and event contracts, data model and migrations, security, failure behavior, observability, compatibility, rollout, rollback, alternatives, decisions `ADR-NNN`, risks, and vertical stages `STAGE-NNN`.

Each task `TASK-NNN` must have requirement links, dependencies, allowed scope, acceptance criteria, required checks, risk, and associated tests. Decomposition is a DAG, not an unordered checklist.

## Test plan

Include strategy, scope, environments, data, unit/integration/contract/E2E cases, negative and permission cases, regression scope, stability policy, and IDs `TEST-NNN` and `E2E-NNN`. Provide a traceability table from every critical requirement to implementation tasks and tests.

## Acceptance report

Include the exact accepted artifact revisions, requirement coverage, UX conformance, architecture conformance, task completion, CI evidence, E2E evidence, unresolved findings, known limitations, and recommendation `ready_for_human_acceptance` or `changes_required`.
