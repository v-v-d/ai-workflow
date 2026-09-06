# Pipeline commands

Set `PIPELINE` to `<skill-dir>/scripts/pipeline.py` in the examples below.

## Initialize and inspect

```bash
python3 "$PIPELINE" init --repo . --feature-id FEATURE-001 --title "Repeat payment" --business-request business-request.md
python3 "$PIPELINE" status --feature-dir .ai-sdlc/features/FEATURE-001-repeat-payment
```

If `init` created the template and it was then edited, register its final content before requirements:

```bash
python3 "$PIPELINE" sync-business-request --feature-dir <dir> --source <dir>/01-business-request.md
```

## Submit and review an upstream artifact

```bash
python3 "$PIPELINE" submit --feature-dir <dir> --stage requirements --source requirements.md
python3 "$PIPELINE" decide --feature-dir <dir> --stage requirements --kind ai --verdict approved --feedback-file review.md
python3 "$PIPELINE" decide --feature-dir <dir> --stage requirements --kind human --verdict approved
```

Use `changes_requested` for either reviewer. The producer then submits a new revision.

## Create implementation work

```bash
python3 "$PIPELINE" add-impl-stage --feature-dir <dir> --stage-id STAGE-001 --title "Payment retry API"
python3 "$PIPELINE" add-item --feature-dir <dir> --stage-id STAGE-001 --kind task --item-id TASK-001 --title "Add retry endpoint"
python3 "$PIPELINE" add-item --feature-dir <dir> --stage-id STAGE-001 --kind e2e --item-id E2E-001 --title "Retry failed payment"
```

## Submit and review implementation items

```bash
python3 "$PIPELINE" item-submit --feature-dir <dir> --stage-id STAGE-001 --kind task --item-id TASK-001 --artifact-ref branch/feature-001-task-001 --evidence task-001.patch
python3 "$PIPELINE" item-decide --feature-dir <dir> --stage-id STAGE-001 --kind task --item-id TASK-001 --review-kind ai --verdict approved --feedback-file code-review.md
python3 "$PIPELINE" item-decide --feature-dir <dir> --stage-id STAGE-001 --kind task --item-id TASK-001 --review-kind human --verdict approved
```

Repeat with `--kind e2e`.

## Verify stage

```bash
python3 "$PIPELINE" verify-stage --feature-dir <dir> --stage-id STAGE-001 --result passed --report playwright-report.md
```

Failure examples:

```bash
python3 "$PIPELINE" verify-stage --feature-dir <dir> --stage-id STAGE-001 --result failed --owner task --item-id TASK-001 --report failure.md
python3 "$PIPELINE" verify-stage --feature-dir <dir> --stage-id STAGE-001 --result failed --owner architecture --report failure.md
```

## Route backward

```bash
python3 "$PIPELINE" reopen --feature-dir <dir> --stage architecture --feedback-file final-feedback.md
```

Route final implementation feedback to a specific item when possible:

```bash
python3 "$PIPELINE" reopen-item --feature-dir <dir> --stage-id STAGE-001 --kind task --item-id TASK-001 --feedback "Incorrect retry behavior"
```
