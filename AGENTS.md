# Agent instructions

For feature work in this repository, read `skill/SKILL.md` first and follow it as the governing workflow contract.

Non-negotiable repository rules:

- Treat `.ai-sdlc/features/*/state.json` as durable workflow state.
- Read state through `python3 scripts/pipeline.py status --feature-dir <dir>` before resuming a feature.
- Never edit `state.json` manually; use `scripts/pipeline.py` for every transition.
- Requirements, design, architecture, and test plan require independent AI review and explicit human approval.
- Implementation tasks and E2E items each require independent AI review and explicit human approval before stage verification.
- Stop whenever the pipeline reports a pending human gate.
- Do not merge, deploy, publish, or release without separate explicit authorization.
