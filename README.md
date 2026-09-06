# ai-workflow

Repository-native governed SDLC workflow for taking a feature from a business request through requirements, UX, architecture, test planning, implementation, E2E verification, independent AI reviews, and mandatory human approval gates.

The workflow instructions are in [`skill/SKILL.md`](skill/SKILL.md). Durable feature state is stored under `.ai-sdlc/features/`, and **must be changed only through `scripts/pipeline.py`**.

## Quick start

Create a business request from `assets/business-request.md`, then initialize a feature:

```bash
python3 scripts/pipeline.py init \
  --repo . \
  --feature-id FEATURE-001 \
  --title "Repeat payment" \
  --business-request business-request.md
```

Inspect the durable state before doing any work:

```bash
python3 scripts/pipeline.py status \
  --feature-dir .ai-sdlc/features/FEATURE-001-repeat-payment
```

Run the state-machine tests:

```bash
python3 -m unittest discover -s tests -v
```

## Repository layout

```text
scripts/pipeline.py          durable state-machine CLI
skill/SKILL.md               agent operating contract
skill/references/            workflow, roles, artifacts, review and command contracts
assets/                      artifact/review templates
schemas/state.schema.json    durable state shape
.ai-sdlc/features/           generated feature records
```

No external Python packages are required by `pipeline.py`.
