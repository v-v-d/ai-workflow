#!/usr/bin/env python3
"""Durable state machine for the governed feature-pipeline workflow.

The repository is the source of truth. This CLI is the supported writer for
`.ai-sdlc/features/*/state.json`.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UPSTREAM_STAGES = ["requirements", "design", "architecture", "test_plan"]
SUBMITTABLE_STAGES = [*UPSTREAM_STAGES, "acceptance"]
STAGE_FILES = {
    "requirements": "02-functional-spec.md",
    "design": "03-ux-spec.md",
    "architecture": "04-architecture.md",
    "test_plan": "05-test-plan.md",
    "acceptance": "06-acceptance-report.md",
}
NEXT_STAGE = {
    "requirements": "design",
    "design": "architecture",
    "architecture": "test_plan",
    "test_plan": "implementation",
    "acceptance": "complete",
}
VALID_VERIFY_OWNERS = {
    "task", "e2e", "environment", "requirements", "design",
    "architecture", "test_plan", "unknown",
}


class PipelineError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9а-яё]+", "-", value, flags=re.IGNORECASE)
    return value.strip("-") or "feature"


def require_file(path: Path) -> None:
    if not path.is_file():
        raise PipelineError(f"File does not exist: {path}")


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_state(feature_dir: Path) -> dict[str, Any]:
    path = feature_dir / "state.json"
    require_file(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PipelineError(f"Invalid state.json: {exc}") from exc


def save_state(feature_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json_atomic(feature_dir / "state.json", state)


def add_history(state: dict[str, Any], action: str, **details: Any) -> None:
    state.setdefault("history", []).append({"at": now_iso(), "action": action, **details})


def new_artifact_state() -> dict[str, Any]:
    return {
        "status": "not_started",
        "latest_revision": 0,
        "current": None,
        "ai_review": None,
        "human_review": None,
        "feedback": [],
        "stale": False,
    }


def new_item(kind: str, item_id: str, title: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "kind": kind,
        "title": title,
        "status": "draft",
        "submission_revision": 0,
        "artifact_ref": None,
        "evidence": None,
        "ai_review": None,
        "human_review": None,
        "feedback": [],
    }


def pending_gate(state: dict[str, Any]) -> dict[str, Any] | None:
    stage = state["current_stage"]
    if stage in SUBMITTABLE_STAGES:
        artifact = state["artifacts"][stage]
        if artifact["status"] == "waiting_for_human":
            return {
                "type": "artifact",
                "stage": stage,
                "revision": artifact["current"]["revision"],
                "sha256": artifact["current"]["sha256"],
            }
    if stage == "implementation":
        for impl_stage in state["implementation"]["stages"]:
            for kind in ("task", "e2e"):
                for item in impl_stage["items"][kind]:
                    if item["status"] == "waiting_for_human":
                        return {
                            "type": "item",
                            "stage_id": impl_stage["id"],
                            "kind": kind,
                            "item_id": item["id"],
                            "revision": item["submission_revision"],
                        }
    if state.get("waiting_for_human"):
        return {"type": "triage", "reason": state.get("human_gate_reason", "manual_triage")}
    return None


def require_no_human_gate(state: dict[str, Any], allow: dict[str, Any] | None = None) -> None:
    gate = pending_gate(state)
    if gate is None:
        return
    if allow and all(gate.get(key) == value for key, value in allow.items()):
        return
    raise PipelineError(f"Pipeline is waiting for human decision: {json.dumps(gate, ensure_ascii=False)}")


def require_current_stage(state: dict[str, Any], stage: str) -> None:
    if state["current_stage"] != stage:
        raise PipelineError(f"Current stage is {state['current_stage']!r}, not {stage!r}")


def snapshot_artifact(feature_dir: Path, stage: str, source: Path, revision: int) -> dict[str, Any]:
    require_file(source)
    revisions = feature_dir / "revisions" / stage
    revisions.mkdir(parents=True, exist_ok=True)
    snapshot = revisions / f"rev-{revision:03d}.md"
    shutil.copyfile(source, snapshot)
    canonical = feature_dir / STAGE_FILES[stage]
    shutil.copyfile(source, canonical)
    return {
        "revision": revision,
        "sha256": sha256_file(snapshot),
        "path": canonical.name,
        "snapshot": str(snapshot.relative_to(feature_dir)),
        "submitted_at": now_iso(),
    }


def store_file(feature_dir: Path, source: Path, directory: str, prefix: str) -> dict[str, Any]:
    require_file(source)
    target_dir = feature_dir / directory
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix or ".txt"
    target = target_dir / f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}{suffix}"
    shutil.copyfile(source, target)
    return {"path": str(target.relative_to(feature_dir)), "sha256": sha256_file(target)}


def get_impl_stage(state: dict[str, Any], stage_id: str) -> dict[str, Any]:
    for stage in state["implementation"]["stages"]:
        if stage["id"] == stage_id:
            return stage
    raise PipelineError(f"Implementation stage not found: {stage_id}")


def get_item(stage: dict[str, Any], kind: str, item_id: str) -> dict[str, Any]:
    for item in stage["items"][kind]:
        if item["id"] == item_id:
            return item
    raise PipelineError(f"{kind} item not found: {item_id}")


def ensure_dependencies_verified(state: dict[str, Any], stage: dict[str, Any]) -> None:
    for dependency in stage.get("depends_on", []):
        if get_impl_stage(state, dependency)["status"] != "verified":
            raise PipelineError(f"Dependency {dependency} is not verified")


def all_items_approved(stage: dict[str, Any]) -> bool:
    return bool(stage["items"]["task"] and stage["items"]["e2e"]) and all(
        item["status"] == "approved"
        for kind in ("task", "e2e")
        for item in stage["items"][kind]
    )


def dependent_stage_ids(state: dict[str, Any], root_id: str) -> set[str]:
    affected = {root_id}
    changed = True
    while changed:
        changed = False
        for stage in state["implementation"]["stages"]:
            if stage["id"] not in affected and any(dep in affected for dep in stage.get("depends_on", [])):
                affected.add(stage["id"])
                changed = True
    return affected


def mark_impl_stale_from(state: dict[str, Any], stage_id: str) -> None:
    for affected_id in dependent_stage_ids(state, stage_id):
        stage = get_impl_stage(state, affected_id)
        stage["stale"] = True
        stage["verification"] = None
        if stage["status"] == "verified":
            stage["status"] = "stale"


def reopen_upstream(state: dict[str, Any], target: str) -> None:
    if target not in UPSTREAM_STAGES:
        raise PipelineError(f"Unsupported upstream reopen target: {target}")
    index = UPSTREAM_STAGES.index(target)
    for stage_name in UPSTREAM_STAGES[index:]:
        artifact = state["artifacts"][stage_name]
        artifact["stale"] = True
        artifact["ai_review"] = None
        artifact["human_review"] = None
        if stage_name == target:
            artifact["status"] = "changes_requested"
        elif artifact["status"] != "not_started":
            artifact["status"] = "stale"
    for impl_stage in state["implementation"]["stages"]:
        impl_stage["stale"] = True
        impl_stage["verification"] = None
        if impl_stage["status"] == "verified":
            impl_stage["status"] = "stale"
    acceptance = state["artifacts"]["acceptance"]
    if acceptance["status"] != "not_started":
        acceptance["status"] = "stale"
        acceptance["stale"] = True
    state["current_stage"] = target
    state["waiting_for_human"] = False
    state.pop("human_gate_reason", None)


def cmd_init(args: argparse.Namespace) -> None:
    repo = Path(args.repo).resolve()
    business = Path(args.business_request).resolve()
    require_file(business)
    if not repo.is_dir():
        raise PipelineError(f"Repository does not exist: {repo}")
    feature_dir = repo / ".ai-sdlc" / "features" / f"{args.feature_id}-{slugify(args.title)}"
    if feature_dir.exists():
        raise PipelineError(f"Feature already exists: {feature_dir}")
    feature_dir.mkdir(parents=True)
    shutil.copyfile(business, feature_dir / "01-business-request.md")
    business_meta = {
        "revision": 1,
        "sha256": sha256_file(feature_dir / "01-business-request.md"),
        "path": "01-business-request.md",
        "synced_at": now_iso(),
    }
    state = {
        "schema_version": 1,
        "feature_id": args.feature_id,
        "title": args.title,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "current_stage": "requirements",
        "waiting_for_human": False,
        "business_request": business_meta,
        "artifacts": {stage: new_artifact_state() for stage in SUBMITTABLE_STAGES},
        "implementation": {"stages": []},
        "history": [],
    }
    add_history(state, "init", business_request=business_meta)
    save_state(feature_dir, state)
    print(feature_dir)


def cmd_status(args: argparse.Namespace) -> None:
    state = copy.deepcopy(load_state(Path(args.feature_dir).resolve()))
    state["pending_gate"] = pending_gate(state)
    state["waiting_for_human"] = state["pending_gate"] is not None
    print(json.dumps(state, ensure_ascii=False, indent=2))


def cmd_sync_business_request(args: argparse.Namespace) -> None:
    feature_dir = Path(args.feature_dir).resolve()
    source = Path(args.source).resolve()
    state = load_state(feature_dir)
    require_current_stage(state, "requirements")
    require_no_human_gate(state)
    require_file(source)
    shutil.copyfile(source, feature_dir / "01-business-request.md")
    meta = state["business_request"]
    meta["revision"] += 1
    meta["sha256"] = sha256_file(feature_dir / "01-business-request.md")
    meta["synced_at"] = now_iso()
    add_history(state, "sync-business-request", revision=meta["revision"], sha256=meta["sha256"])
    save_state(feature_dir, state)


def cmd_submit(args: argparse.Namespace) -> None:
    feature_dir = Path(args.feature_dir).resolve()
    state = load_state(feature_dir)
    require_current_stage(state, args.stage)
    require_no_human_gate(state)
    artifact = state["artifacts"][args.stage]
    revision = artifact["latest_revision"] + 1
    snapshot = snapshot_artifact(feature_dir, args.stage, Path(args.source).resolve(), revision)
    artifact.update({
        "status": "waiting_for_ai",
        "latest_revision": revision,
        "current": snapshot,
        "ai_review": None,
        "human_review": None,
        "stale": False,
    })
    state["waiting_for_human"] = False
    add_history(state, "submit", stage=args.stage, revision=revision, sha256=snapshot["sha256"])
    save_state(feature_dir, state)
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


def cmd_decide(args: argparse.Namespace) -> None:
    feature_dir = Path(args.feature_dir).resolve()
    state = load_state(feature_dir)
    require_current_stage(state, args.stage)
    artifact = state["artifacts"][args.stage]
    if not artifact["current"]:
        raise PipelineError("No submitted artifact")
    if args.kind == "ai":
        require_no_human_gate(state)
        if artifact["status"] != "waiting_for_ai":
            raise PipelineError(f"Artifact status must be waiting_for_ai, got {artifact['status']}")
        feedback = None
        if args.feedback_file:
            feedback = store_file(feature_dir, Path(args.feedback_file).resolve(), "reviews", f"{args.stage}-ai-r{artifact['current']['revision']:03d}")
        decision = {
            "verdict": args.verdict,
            "revision": artifact["current"]["revision"],
            "sha256": artifact["current"]["sha256"],
            "at": now_iso(),
            "feedback": feedback,
        }
        artifact["ai_review"] = decision
        if feedback:
            artifact["feedback"].append({"kind": "ai", **decision})
        if args.verdict == "approved":
            artifact["status"] = "waiting_for_human"
            state["waiting_for_human"] = True
        else:
            artifact["status"] = "changes_requested"
        add_history(state, "decide", stage=args.stage, kind="ai", verdict=args.verdict, revision=decision["revision"])
    else:
        require_no_human_gate(state, allow={"type": "artifact", "stage": args.stage})
        if artifact["status"] != "waiting_for_human":
            raise PipelineError(f"Artifact status must be waiting_for_human, got {artifact['status']}")
        feedback = None
        if args.feedback_file:
            feedback = store_file(feature_dir, Path(args.feedback_file).resolve(), "reviews", f"{args.stage}-human-r{artifact['current']['revision']:03d}")
        decision = {
            "verdict": args.verdict,
            "revision": artifact["current"]["revision"],
            "sha256": artifact["current"]["sha256"],
            "at": now_iso(),
            "feedback": feedback,
        }
        artifact["human_review"] = decision
        state["waiting_for_human"] = False
        if feedback:
            artifact["feedback"].append({"kind": "human", **decision})
        if args.verdict == "approved":
            artifact["status"] = "approved"
            state["current_stage"] = NEXT_STAGE[args.stage]
        else:
            artifact["status"] = "changes_requested"
        add_history(state, "decide", stage=args.stage, kind="human", verdict=args.verdict, revision=decision["revision"])
    save_state(feature_dir, state)


def cmd_add_impl_stage(args: argparse.Namespace) -> None:
    feature_dir = Path(args.feature_dir).resolve()
    state = load_state(feature_dir)
    require_current_stage(state, "implementation")
    require_no_human_gate(state)
    if any(stage["id"] == args.stage_id for stage in state["implementation"]["stages"]):
        raise PipelineError(f"Stage already exists: {args.stage_id}")
    dependencies = args.depends_on or []
    for dependency in dependencies:
        get_impl_stage(state, dependency)
    state["implementation"]["stages"].append({
        "id": args.stage_id,
        "title": args.title,
        "depends_on": dependencies,
        "status": "draft",
        "items": {"task": [], "e2e": []},
        "verification": None,
        "stale": False,
    })
    add_history(state, "add-impl-stage", stage_id=args.stage_id, title=args.title, depends_on=dependencies)
    save_state(feature_dir, state)


def cmd_add_item(args: argparse.Namespace) -> None:
    feature_dir = Path(args.feature_dir).resolve()
    state = load_state(feature_dir)
    require_current_stage(state, "implementation")
    require_no_human_gate(state)
    stage = get_impl_stage(state, args.stage_id)
    ensure_dependencies_verified(state, stage)
    if any(item["id"] == args.item_id for kind in ("task", "e2e") for item in stage["items"][kind]):
        raise PipelineError(f"Item ID already exists in stage: {args.item_id}")
    stage["items"][args.kind].append(new_item(args.kind, args.item_id, args.title))
    stage["status"] = "in_progress"
    add_history(state, "add-item", stage_id=args.stage_id, kind=args.kind, item_id=args.item_id, title=args.title)
    save_state(feature_dir, state)


def cmd_item_submit(args: argparse.Namespace) -> None:
    feature_dir = Path(args.feature_dir).resolve()
    state = load_state(feature_dir)
    require_current_stage(state, "implementation")
    require_no_human_gate(state)
    stage = get_impl_stage(state, args.stage_id)
    ensure_dependencies_verified(state, stage)
    item = get_item(stage, args.kind, args.item_id)
    evidence = store_file(feature_dir, Path(args.evidence).resolve(), "evidence", f"{args.stage_id}-{args.item_id}")
    item["submission_revision"] += 1
    item.update({
        "status": "waiting_for_ai",
        "artifact_ref": args.artifact_ref,
        "evidence": evidence,
        "ai_review": None,
        "human_review": None,
    })
    stage.update({"status": "in_progress", "verification": None, "stale": False})
    add_history(state, "item-submit", stage_id=args.stage_id, kind=args.kind, item_id=args.item_id,
                revision=item["submission_revision"], artifact_ref=args.artifact_ref, evidence=evidence)
    save_state(feature_dir, state)


def cmd_item_decide(args: argparse.Namespace) -> None:
    feature_dir = Path(args.feature_dir).resolve()
    state = load_state(feature_dir)
    require_current_stage(state, "implementation")
    stage = get_impl_stage(state, args.stage_id)
    item = get_item(stage, args.kind, args.item_id)
    if args.review_kind == "ai":
        require_no_human_gate(state)
        if item["status"] != "waiting_for_ai":
            raise PipelineError(f"Item status must be waiting_for_ai, got {item['status']}")
        feedback = None
        if args.feedback_file:
            feedback = store_file(feature_dir, Path(args.feedback_file).resolve(), "reviews", f"{args.stage_id}-{args.item_id}-ai")
        decision = {"verdict": args.verdict, "revision": item["submission_revision"], "at": now_iso(), "feedback": feedback}
        item["ai_review"] = decision
        if feedback:
            item["feedback"].append({"kind": "ai", **decision})
        if args.verdict == "approved":
            item["status"] = "waiting_for_human"
            state["waiting_for_human"] = True
        else:
            item["status"] = "changes_requested"
        add_history(state, "item-decide", stage_id=args.stage_id, kind=args.kind, item_id=args.item_id,
                    review_kind="ai", verdict=args.verdict, revision=item["submission_revision"])
    else:
        require_no_human_gate(state, allow={"type": "item", "stage_id": args.stage_id, "kind": args.kind, "item_id": args.item_id})
        if item["status"] != "waiting_for_human":
            raise PipelineError(f"Item status must be waiting_for_human, got {item['status']}")
        feedback = None
        if args.feedback_file:
            feedback = store_file(feature_dir, Path(args.feedback_file).resolve(), "reviews", f"{args.stage_id}-{args.item_id}-human")
        decision = {"verdict": args.verdict, "revision": item["submission_revision"], "at": now_iso(), "feedback": feedback}
        item["human_review"] = decision
        state["waiting_for_human"] = False
        if feedback:
            item["feedback"].append({"kind": "human", **decision})
        item["status"] = "approved" if args.verdict == "approved" else "changes_requested"
        add_history(state, "item-decide", stage_id=args.stage_id, kind=args.kind, item_id=args.item_id,
                    review_kind="human", verdict=args.verdict, revision=item["submission_revision"])
    save_state(feature_dir, state)


def cmd_verify_stage(args: argparse.Namespace) -> None:
    feature_dir = Path(args.feature_dir).resolve()
    state = load_state(feature_dir)
    require_current_stage(state, "implementation")
    require_no_human_gate(state)
    stage = get_impl_stage(state, args.stage_id)
    ensure_dependencies_verified(state, stage)
    report = store_file(feature_dir, Path(args.report).resolve(), "evidence", f"{args.stage_id}-verification")
    if args.result == "passed":
        if not all_items_approved(stage):
            raise PipelineError("At least one task and one E2E item are required, and every item must be human-approved")
        stage.update({
            "status": "verified",
            "stale": False,
            "verification": {"result": "passed", "report": report, "at": now_iso(), "owner": None, "item_id": None},
        })
        add_history(state, "verify-stage", stage_id=args.stage_id, result="passed", report=report)
        stages = state["implementation"]["stages"]
        if stages and all(candidate["status"] == "verified" for candidate in stages):
            state["current_stage"] = "acceptance"
    else:
        if not args.owner:
            raise PipelineError("--owner is required for failed verification")
        if args.owner in {"task", "e2e"} and not args.item_id:
            raise PipelineError("--item-id is required when failure owner is task or e2e")
        stage.update({
            "status": "verification_failed",
            "verification": {"result": "failed", "report": report, "at": now_iso(), "owner": args.owner, "item_id": args.item_id},
        })
        add_history(state, "verify-stage", stage_id=args.stage_id, result="failed", owner=args.owner,
                    item_id=args.item_id, report=report)
        if args.owner in {"task", "e2e"}:
            get_item(stage, args.owner, args.item_id)["status"] = "changes_requested"
            mark_impl_stale_from(state, args.stage_id)
            stage["status"] = "in_progress"
        elif args.owner in UPSTREAM_STAGES:
            reopen_upstream(state, args.owner)
        elif args.owner == "unknown":
            state["waiting_for_human"] = True
            state["human_gate_reason"] = f"Unknown verification failure in {args.stage_id}"
    save_state(feature_dir, state)


def cmd_reopen(args: argparse.Namespace) -> None:
    feature_dir = Path(args.feature_dir).resolve()
    state = load_state(feature_dir)
    require_no_human_gate(state)
    feedback = store_file(feature_dir, Path(args.feedback_file).resolve(), "reviews", f"reopen-{args.stage}")
    reopen_upstream(state, args.stage)
    state["artifacts"][args.stage]["feedback"].append({"kind": "reopen", "at": now_iso(), "feedback": feedback})
    add_history(state, "reopen", stage=args.stage, feedback=feedback)
    save_state(feature_dir, state)


def cmd_reopen_item(args: argparse.Namespace) -> None:
    feature_dir = Path(args.feature_dir).resolve()
    state = load_state(feature_dir)
    require_current_stage(state, "implementation")
    require_no_human_gate(state)
    stage = get_impl_stage(state, args.stage_id)
    item = get_item(stage, args.kind, args.item_id)
    item["status"] = "changes_requested"
    item["feedback"].append({"kind": "reopen", "at": now_iso(), "feedback": args.feedback})
    mark_impl_stale_from(state, args.stage_id)
    stage["status"] = "in_progress"
    add_history(state, "reopen-item", stage_id=args.stage_id, kind=args.kind, item_id=args.item_id, feedback=args.feedback)
    save_state(feature_dir, state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Feature Pipeline durable workflow state manager")
    sub = parser.add_subparsers(dest="command", required=True)

    command = sub.add_parser("init")
    command.add_argument("--repo", default=".")
    command.add_argument("--feature-id", required=True)
    command.add_argument("--title", required=True)
    command.add_argument("--business-request", required=True)
    command.set_defaults(func=cmd_init)

    command = sub.add_parser("status")
    command.add_argument("--feature-dir", required=True)
    command.set_defaults(func=cmd_status)

    command = sub.add_parser("sync-business-request")
    command.add_argument("--feature-dir", required=True)
    command.add_argument("--source", required=True)
    command.set_defaults(func=cmd_sync_business_request)

    command = sub.add_parser("submit")
    command.add_argument("--feature-dir", required=True)
    command.add_argument("--stage", choices=SUBMITTABLE_STAGES, required=True)
    command.add_argument("--source", required=True)
    command.set_defaults(func=cmd_submit)

    command = sub.add_parser("decide")
    command.add_argument("--feature-dir", required=True)
    command.add_argument("--stage", choices=SUBMITTABLE_STAGES, required=True)
    command.add_argument("--kind", choices=["ai", "human"], required=True)
    command.add_argument("--verdict", choices=["approved", "changes_requested"], required=True)
    command.add_argument("--feedback-file")
    command.set_defaults(func=cmd_decide)

    command = sub.add_parser("add-impl-stage")
    command.add_argument("--feature-dir", required=True)
    command.add_argument("--stage-id", required=True)
    command.add_argument("--title", required=True)
    command.add_argument("--depends-on", action="append")
    command.set_defaults(func=cmd_add_impl_stage)

    command = sub.add_parser("add-item")
    command.add_argument("--feature-dir", required=True)
    command.add_argument("--stage-id", required=True)
    command.add_argument("--kind", choices=["task", "e2e"], required=True)
    command.add_argument("--item-id", required=True)
    command.add_argument("--title", required=True)
    command.set_defaults(func=cmd_add_item)

    command = sub.add_parser("item-submit")
    command.add_argument("--feature-dir", required=True)
    command.add_argument("--stage-id", required=True)
    command.add_argument("--kind", choices=["task", "e2e"], required=True)
    command.add_argument("--item-id", required=True)
    command.add_argument("--artifact-ref", required=True)
    command.add_argument("--evidence", required=True)
    command.set_defaults(func=cmd_item_submit)

    command = sub.add_parser("item-decide")
    command.add_argument("--feature-dir", required=True)
    command.add_argument("--stage-id", required=True)
    command.add_argument("--kind", choices=["task", "e2e"], required=True)
    command.add_argument("--item-id", required=True)
    command.add_argument("--review-kind", choices=["ai", "human"], required=True)
    command.add_argument("--verdict", choices=["approved", "changes_requested"], required=True)
    command.add_argument("--feedback-file")
    command.set_defaults(func=cmd_item_decide)

    command = sub.add_parser("verify-stage")
    command.add_argument("--feature-dir", required=True)
    command.add_argument("--stage-id", required=True)
    command.add_argument("--result", choices=["passed", "failed"], required=True)
    command.add_argument("--owner", choices=sorted(VALID_VERIFY_OWNERS))
    command.add_argument("--item-id")
    command.add_argument("--report", required=True)
    command.set_defaults(func=cmd_verify_stage)

    command = sub.add_parser("reopen")
    command.add_argument("--feature-dir", required=True)
    command.add_argument("--stage", choices=UPSTREAM_STAGES, required=True)
    command.add_argument("--feedback-file", required=True)
    command.set_defaults(func=cmd_reopen)

    command = sub.add_parser("reopen-item")
    command.add_argument("--feature-dir", required=True)
    command.add_argument("--stage-id", required=True)
    command.add_argument("--kind", choices=["task", "e2e"], required=True)
    command.add_argument("--item-id", required=True)
    command.add_argument("--feedback", required=True)
    command.set_defaults(func=cmd_reopen_item)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.func(args)
        return 0
    except PipelineError as exc:
        print(f"pipeline error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
