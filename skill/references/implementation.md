# Implementation workflow

## Prepare stages

After architecture and test plan approval, add each vertical stage in dependency order. Add at least one development task and one E2E case before authoring begins. If a proposed stage cannot support both branches, change the decomposition upstream instead of silently bypassing a branch.

## Development item

1. Create or select an isolated branch/worktree.
2. Give the developer one `TASK-NNN`, approved inputs, allowed paths, and required checks.
3. Run deterministic checks.
4. Save the exact diff or equivalent reviewable record to a file and submit it with the code reference using `item-submit --evidence`.
5. Run an independent AI review and record it.
6. If approved, stop for human review of the exact diff.
7. Record approval or feedback with `item-decide`.

## E2E item

Follow the same loop for one `E2E-NNN`. It may be authored against agreed contracts, mocks, or a partial environment while product code is in progress. Approval requires a meaningful execution or an explicit reason execution must wait for the join.

## Join and verification

When every item in a stage is human-approved, deploy/start the integration target and run the stage E2E set. Save reports, traces, screenshots, and videos where available. Record the result with `verify-stage --report`; a report is mandatory for both passing and failing results.

Reopening an item invalidates that stage and every transitive dependent stage. After the correction, re-run verification for each stale dependent stage in dependency order even if its own code did not change.

For failure, include an owner and evidence:

- `task`: reopen a specific development task.
- `e2e`: reopen a specific E2E item.
- `environment`: keep the stage at verification failure and repair the environment.
- `requirements`, `design`, `architecture`, or `test_plan`: route upstream and invalidate downstream work.
- `unknown`: stop for human triage.

Do not proceed to a dependent stage until all dependencies are verified.
