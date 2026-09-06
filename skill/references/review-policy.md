# Review policy

Write reviews using `assets/review.md`. Each finding has an ID, severity, exact location or stable ID, evidence, required change, and affected upstream/downstream IDs.

Severities:

- `blocking`: cannot proceed without correction.
- `high`: likely user, security, data, or operational failure; normally blocking.
- `medium`: material weakness with bounded impact.
- `low`: optional improvement.

`approved` is valid only when there are no unresolved blocking or high findings. Do not approve with vague caveats.

## Requirements rubric

Check business-request fidelity, actor and permission coverage, main/alternate/negative flows, rule consistency, measurable acceptance criteria, non-goals, terminology, edge cases, and explicit uncertainty.

## Design rubric

Check all requirement mappings, complete user journeys, navigation consistency, loading/empty/error/validation/permission states, accessibility, responsive behavior, content clarity, and implementation feasibility.

## Architecture rubric

Check repository evidence, boundary fit, API/data compatibility, migration safety, transactionality, concurrency, security, failure recovery, observability, rollout, rollback, testability, DAG completeness, and task sizing.

## Test-plan rubric

Check traceability, risk prioritization, meaningful assertions, negative and permission scenarios, environment/data feasibility, E2E boundaries, flakiness controls, and regression coverage.

## Code rubric

Check conformance to task and architecture, correctness, regressions, security, data integrity, concurrency, failure behavior, compatibility, and meaningful tests. Automated formatting is not an AI review concern.

## E2E rubric

Check that the test proves the linked requirement, fails for the target defect, uses stable selectors, controls data, avoids arbitrary sleep, isolates state, captures useful failure evidence, and has no hidden order dependency.
