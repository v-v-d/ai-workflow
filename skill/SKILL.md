---
name: feature-pipeline
description: Run a software feature through a product-to-code pipeline with requirements, UX, architecture, test planning, implementation, E2E verification, independent AI reviews, and mandatory human approval gates. Use when the user asks to design, implement, continue, inspect, or revise a feature through this governed workflow.
---

# Feature Pipeline

Treat the repository as the durable source of truth. Do not rely on chat history for the current stage, approved version, or outstanding feedback.

## Start or resume

1. Locate `scripts/pipeline.py` relative to this `SKILL.md`.
2. For a new feature, first write the business request from `assets/business-request.md`, then pass it to `pipeline.py init --business-request <file>`. If the generated draft was edited instead, immediately register it with `sync-business-request` before submitting requirements.
3. For an existing feature, run `pipeline.py status --feature-dir <path>` before doing any work.
4. Read [references/workflow.md](references/workflow.md) for the current stage only. Read the artifact section linked there before producing that artifact.
5. Use `pipeline.py` for every state transition, artifact submission, review decision, implementation item, verification result, and backward route. Never edit `state.json` manually.

## Non-negotiable gates

- Requirements, UX, architecture, and test plan each require an independent AI review followed by explicit human approval.
- A producer must address every blocking finding before resubmitting.
- The reviewer must not edit or silently repair the producer's artifact.
- Human approval applies only to the exact recorded artifact revision and hash.
- Stop the turn whenever `state.json` says `waiting_for_human`. Present the artifact, its diff, AI findings, open questions, and the exact decision requested.
- Interpret plain approval only for the currently pending gate. For rejection or requested changes, record the user's feedback and route to the producer for the same stage.
- Never merge, deploy, publish, or release without separate authorization supplied by the user or repository policy.

## Agent roles

Use focused subagents when delegation is available and allowed. Give each one only the approved upstream artifacts and tools needed for its role. Use a separate context for reviewers. Read [references/roles.md](references/roles.md) before delegating.

Route higher-abstraction product and architecture work to the strongest suitable model available. Use a smaller coding model only for bounded tasks whose contracts, writable scope, and acceptance criteria are explicit. Escalate after two failed implementation attempts or whenever the task reveals an unresolved architecture, security, data-migration, or concurrency decision.

## Artifact rules

Artifacts are Markdown unless the repository or template calls for another format. Copy the relevant template from `assets/`, fill it completely, and keep stable IDs for requirements, screens, decisions, tasks, tests, and E2E cases. Read [references/artifacts.md](references/artifacts.md) before creating or revising an artifact.

Submit an artifact with:

```bash
python3 <skill-dir>/scripts/pipeline.py submit \
  --feature-dir <feature-dir> \
  --stage <requirements|design|architecture|test_plan|acceptance> \
  --source <artifact-file>
```

Record reviews and human decisions with the commands documented in [references/commands.md](references/commands.md).

## Implementation

After the test plan is approved, read [references/implementation.md](references/implementation.md). Create vertical implementation stages, then create both development tasks and E2E items for each stage. Development and E2E authoring may run in parallel when their writable paths do not overlap. Verification is a join after both branches are approved.

Run repository-defined formatting, lint, build, unit, integration, and E2E commands. Prefer `AGENTS.md`, project scripts, and CI configuration over guessed commands. Record observable evidence; an agent's claim that checks passed is not evidence.

## Backward changes

When final review or verification exposes an upstream defect, route it with `pipeline.py reopen`. The script marks downstream artifacts stale. Re-run only the invalidated portion, but require fresh AI and human approvals for every changed artifact.

## Completion

The feature is complete only when:

- all upstream artifacts have approved recorded revisions;
- every implementation and E2E item is approved;
- every implementation stage has a passing verification report;
- the product acceptance report is submitted;
- the human explicitly approves final acceptance.

Then report what was built, the checks run, known limitations, and where the durable feature record lives.
