import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1] / "scripts" / "pipeline.py"


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / ".ai-sdlc").mkdir()
        self.business = self.repo / "business.md"
        self.business.write_text("# Business request\n\nMVP\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, ok=True):
        proc = subprocess.run(
            [sys.executable, str(PIPELINE), *map(str, args)],
            cwd=self.repo,
            text=True,
            capture_output=True,
        )
        if ok and proc.returncode != 0:
            self.fail(f"CLI failed: {proc.stderr}\n{proc.stdout}")
        return proc

    def init(self):
        proc = self.run_cli(
            "init", "--repo", self.repo,
            "--feature-id", "FEATURE-001",
            "--title", "Example",
            "--business-request", self.business,
        )
        return Path(proc.stdout.strip())

    def submit_and_approve(self, feature, stage):
        source = self.repo / f"{stage}.md"
        source.write_text(f"# {stage}\n", encoding="utf-8")
        self.run_cli("submit", "--feature-dir", feature, "--stage", stage, "--source", source)
        self.run_cli("decide", "--feature-dir", feature, "--stage", stage, "--kind", "ai", "--verdict", "approved")
        status = json.loads(self.run_cli("status", "--feature-dir", feature).stdout)
        self.assertTrue(status["waiting_for_human"])
        self.assertEqual("artifact", status["pending_gate"]["type"])
        self.run_cli("decide", "--feature-dir", feature, "--stage", stage, "--kind", "human", "--verdict", "approved")

    def advance_to_implementation(self, feature):
        for stage in ("requirements", "design", "architecture", "test_plan"):
            self.submit_and_approve(feature, stage)

    def approve_item(self, feature, stage_id, kind, item_id):
        evidence = self.repo / f"{item_id}.txt"
        evidence.write_text("reviewable evidence\n", encoding="utf-8")
        self.run_cli(
            "item-submit", "--feature-dir", feature,
            "--stage-id", stage_id, "--kind", kind, "--item-id", item_id,
            "--artifact-ref", f"branch/{item_id.lower()}", "--evidence", evidence,
        )
        self.run_cli(
            "item-decide", "--feature-dir", feature,
            "--stage-id", stage_id, "--kind", kind, "--item-id", item_id,
            "--review-kind", "ai", "--verdict", "approved",
        )
        status = json.loads(self.run_cli("status", "--feature-dir", feature).stdout)
        self.assertEqual("item", status["pending_gate"]["type"])
        self.run_cli(
            "item-decide", "--feature-dir", feature,
            "--stage-id", stage_id, "--kind", kind, "--item-id", item_id,
            "--review-kind", "human", "--verdict", "approved",
        )

    def test_upstream_gates_advance_to_implementation(self):
        feature = self.init()
        self.advance_to_implementation(feature)
        state = json.loads((feature / "state.json").read_text(encoding="utf-8"))
        self.assertEqual("implementation", state["current_stage"])

    def test_human_gate_blocks_other_mutations(self):
        feature = self.init()
        req = self.repo / "requirements.md"
        req.write_text("# requirements\n", encoding="utf-8")
        self.run_cli("submit", "--feature-dir", feature, "--stage", "requirements", "--source", req)
        self.run_cli("decide", "--feature-dir", feature, "--stage", "requirements", "--kind", "ai", "--verdict", "approved")
        proc = self.run_cli(
            "sync-business-request", "--feature-dir", feature, "--source", self.business,
            ok=False,
        )
        self.assertEqual(2, proc.returncode)
        self.assertIn("waiting for human", proc.stderr.lower())

    def test_verification_requires_task_and_e2e(self):
        feature = self.init()
        self.advance_to_implementation(feature)
        self.run_cli("add-impl-stage", "--feature-dir", feature, "--stage-id", "STAGE-001", "--title", "Vertical slice")
        self.run_cli("add-item", "--feature-dir", feature, "--stage-id", "STAGE-001", "--kind", "task", "--item-id", "TASK-001", "--title", "Code")
        self.approve_item(feature, "STAGE-001", "task", "TASK-001")
        report = self.repo / "verification.md"
        report.write_text("passed\n", encoding="utf-8")
        proc = self.run_cli(
            "verify-stage", "--feature-dir", feature, "--stage-id", "STAGE-001",
            "--result", "passed", "--report", report, ok=False,
        )
        self.assertEqual(2, proc.returncode)
        self.assertIn("one task and one E2E", proc.stderr)

    def test_verified_stage_reaches_acceptance(self):
        feature = self.init()
        self.advance_to_implementation(feature)
        self.run_cli("add-impl-stage", "--feature-dir", feature, "--stage-id", "STAGE-001", "--title", "Vertical slice")
        for kind, item_id in (("task", "TASK-001"), ("e2e", "E2E-001")):
            self.run_cli("add-item", "--feature-dir", feature, "--stage-id", "STAGE-001", "--kind", kind, "--item-id", item_id, "--title", item_id)
            self.approve_item(feature, "STAGE-001", kind, item_id)
        report = self.repo / "verification.md"
        report.write_text("passed\n", encoding="utf-8")
        self.run_cli(
            "verify-stage", "--feature-dir", feature, "--stage-id", "STAGE-001",
            "--result", "passed", "--report", report,
        )
        state = json.loads((feature / "state.json").read_text(encoding="utf-8"))
        self.assertEqual("acceptance", state["current_stage"])
        self.assertEqual("verified", state["implementation"]["stages"][0]["status"])

    def test_reopen_architecture_invalidates_downstream(self):
        feature = self.init()
        self.advance_to_implementation(feature)
        feedback = self.repo / "feedback.md"
        feedback.write_text("Architecture issue\n", encoding="utf-8")
        self.run_cli("reopen", "--feature-dir", feature, "--stage", "architecture", "--feedback-file", feedback)
        state = json.loads((feature / "state.json").read_text(encoding="utf-8"))
        self.assertEqual("architecture", state["current_stage"])
        self.assertEqual("changes_requested", state["artifacts"]["architecture"]["status"])
        self.assertEqual("stale", state["artifacts"]["test_plan"]["status"])

    def test_unknown_verification_failure_opens_human_triage_gate(self):
        feature = self.init()
        self.advance_to_implementation(feature)
        self.run_cli("add-impl-stage", "--feature-dir", feature, "--stage-id", "STAGE-001", "--title", "Vertical slice")
        report = self.repo / "failure.md"
        report.write_text("unknown failure\n", encoding="utf-8")
        self.run_cli(
            "verify-stage", "--feature-dir", feature, "--stage-id", "STAGE-001",
            "--result", "failed", "--owner", "unknown", "--report", report,
        )
        status = json.loads(self.run_cli("status", "--feature-dir", feature).stdout)
        self.assertTrue(status["waiting_for_human"])
        self.assertEqual("triage", status["pending_gate"]["type"])


if __name__ == "__main__":
    unittest.main()
