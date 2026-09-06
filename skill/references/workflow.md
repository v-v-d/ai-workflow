# Workflow

Use this routing table after reading `state.json` through `pipeline.py status`.

| Current stage | Producer | Reviewer | Human gate | Artifact guidance |
|---|---|---|---|---|
| requirements | Product agent | Requirements reviewer | Required | `artifacts.md#functional-requirements` |
| design | Designer | Design reviewer | Required | `artifacts.md#uxui-design` |
| architecture | Architect | Architecture reviewer | Required | `artifacts.md#architecture-and-decomposition` |
| test_plan | Test planner | Test-plan reviewer | Required | `artifacts.md#test-plan` |
| implementation | Developer and E2E agents | Code and E2E reviewers | Required per item | `implementation.md` |
| acceptance | Product acceptance agent | No self-repair | Required | `artifacts.md#acceptance-report` |

## Producer-reviewer loop

1. Producer creates a complete draft from approved upstream artifacts and recorded feedback.
2. Submit the artifact with `pipeline.py submit`; this snapshots a numbered immutable revision.
3. An independent reviewer uses the relevant rubric from `review-policy.md` and writes a review file from `assets/review.md`.
4. Record the AI verdict. `changes_requested` returns to the producer. `approved` opens the human gate.
5. Stop and request the human decision. Do not begin the next stage in the same turn unless the human has already explicitly approved this exact revision.
6. On human changes, record the decision and create a new producer revision. On approval, advance.

After three AI review cycles without approval, ask the human to resolve the conflicting requirement or reviewer expectation. Do not loop indefinitely.

## Design production

Create the UX specification and, when useful, an interactive repository-native HTML prototype. Exercise important flows in a browser and capture screenshots. A prototype is evidence, not a replacement for the UX specification.

## Final acceptance

The product acceptance agent compares the accepted implementation against requirements, UX, architecture, decomposition, test plan, traceability, automated checks, and E2E evidence. It must list gaps rather than repairing them.

If the human rejects final acceptance, require an explicit route: `requirements`, `design`, `architecture`, `test_plan`, or `implementation`. Use `pipeline.py reopen`; do not guess a distant route when the feedback is ambiguous.
