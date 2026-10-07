import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "cumcm-modeling/scripts/check_reproducibility.py"


class ReproducibilityCheckerTests(unittest.TestCase):
    def run_checker(self, manifest: Path, project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), str(manifest), "--project-root", str(project), *extra],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_schema_10_legacy_manifest_remains_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "input.csv").write_text("x\n1\n", encoding="utf-8")
            (project / "result.json").write_text("{}", encoding="utf-8")
            manifest = project / "reproducibility.json"
            manifest.write_text(json.dumps({
                "schema_version": "1.0",
                "runs": [{
                    "id": "legacy",
                    "working_directory": ".",
                    "entry_command": ["python3", "script.py"],
                    "inputs": ["input.csv"],
                    "outputs": ["result.json"],
                    "environment": {"python": "3"},
                    "random_seeds": [],
                    "checks": [{"name": "ok", "passed": True}],
                    "status": "passed",
                }],
            }), encoding="utf-8")
            result = self.run_checker(manifest, project, "--require-outputs")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_schema_11_structured_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "input.csv").write_text("x\n1\n", encoding="utf-8")
            (project / "metrics.json").write_text(json.dumps({"metrics": {"burn_time": 382}}), encoding="utf-8")
            (project / "trajectory.csv").write_text("t,x\n0,1\n", encoding="utf-8")
            manifest = project / "reproducibility.json"
            manifest.write_text(json.dumps({
                "schema_version": "1.1",
                "model_decisions": {"Q1": {"selected_run": "final", "baseline_run": "base"}},
                "runs": [
                    {
                        "id": "base", "question": "Q1", "role": "baseline", "working_directory": ".",
                        "entry_command": ["python3", "base.py"], "inputs": ["input.csv"],
                        "outputs": [{"path": "metrics.json", "kind": "metrics"}],
                        "environment": {"python": "3"}, "random_seeds": [],
                        "checks": [{"name": "ok", "passed": True}], "status": "passed",
                    },
                    {
                        "id": "final", "question": "Q1", "role": "final", "working_directory": ".",
                        "entry_command": ["python3", "final.py"], "inputs": ["input.csv"],
                        "outputs": [
                            {"path": "metrics.json", "kind": "metrics"},
                            {"path": "trajectory.csv", "kind": "figure_data", "purpose": "状态轨迹"},
                        ],
                        "environment": {"python": "3"}, "random_seeds": [],
                        "checks": [{"name": "ok", "passed": True}], "status": "passed",
                    },
                ],
            }), encoding="utf-8")
            result = self.run_checker(manifest, project, "--require-outputs")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_schema_11_rejects_legacy_string_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = project / "reproducibility.json"
            manifest.write_text(json.dumps({
                "schema_version": "1.1", "model_decisions": {}, "runs": [{
                    "id": "final", "role": "final", "working_directory": ".", "entry_command": ["python3", "x.py"],
                    "inputs": [], "outputs": ["result.json"], "environment": {},
                    "random_seeds": [], "checks": [], "status": "planned",
                }],
            }), encoding="utf-8")
            result = self.run_checker(manifest, project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("字符串输出仅兼容 Schema 1.0", result.stdout)

    def test_model_decision_references_match_run_roles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = project / "reproducibility.json"
            manifest.write_text(json.dumps({
                "schema_version": "1.1",
                "model_decisions": {"Q1": {"selected_run": "candidate", "baseline_run": "final"}},
                "runs": [
                    {"id": "candidate", "role": "candidate", "working_directory": ".", "entry_command": ["python3", "x.py"], "inputs": [], "outputs": [{"path": "x.json", "kind": "metrics"}], "environment": {}, "random_seeds": [], "checks": [], "status": "planned"},
                    {"id": "final", "role": "final", "working_directory": ".", "entry_command": ["python3", "x.py"], "inputs": [], "outputs": [{"path": "x.json", "kind": "metrics"}], "environment": {}, "random_seeds": [], "checks": [], "status": "planned"},
                ],
            }), encoding="utf-8")
            result = self.run_checker(manifest, project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("role=final", result.stdout)

    def test_runtime_budget_attempts_must_be_positive_integer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = project / "reproducibility.json"
            manifest.write_text(json.dumps({
                "schema_version": "1.1", "model_decisions": {}, "runs": [{
                    "id": "r", "role": "final", "working_directory": ".", "entry_command": ["python3", "x.py"],
                    "runtime_budget": {"timeout_seconds": 1, "max_attempts": 1.5}, "inputs": [],
                    "outputs": [{"path": "x.json", "kind": "metrics"}], "environment": {},
                    "random_seeds": [], "checks": [], "status": "planned",
                }],
            }), encoding="utf-8")
            result = self.run_checker(manifest, project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("max_attempts", result.stdout)

    def test_candidate_failure_is_warning_at_g3_but_final_failure_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = project / "reproducibility.json"
            manifest.write_text(json.dumps({
                "schema_version": "1.1", "model_decisions": {}, "runs": [
                    {"id": "candidate", "role": "candidate", "working_directory": ".", "entry_command": ["python3", "x.py"], "inputs": [], "outputs": [{"path": "candidate.json", "kind": "metrics"}], "environment": {}, "random_seeds": [], "checks": [], "status": "failed"},
                    {"id": "final", "role": "final", "working_directory": ".", "entry_command": ["python3", "x.py"], "inputs": [], "outputs": [{"path": "final.json", "kind": "metrics"}], "environment": {}, "random_seeds": [], "checks": [], "status": "failed"},
                ],
            }), encoding="utf-8")
            result = self.run_checker(manifest, project, "--require-outputs")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("runs[1].status", result.stdout)
            self.assertIn("[提醒] runs[1].status", result.stdout)

    def test_require_outputs_rejects_directory_declared_as_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "not-a-file.json").mkdir()
            manifest = project / "reproducibility.json"
            manifest.write_text(json.dumps({
                "schema_version": "1.1", "model_decisions": {}, "runs": [{
                    "id": "final", "role": "final", "working_directory": ".", "entry_command": ["python3", "x.py"],
                    "inputs": [], "outputs": [{"path": "not-a-file.json", "kind": "metrics"}],
                    "environment": {}, "random_seeds": [], "checks": [{"name": "ok", "passed": True}], "status": "passed",
                }],
            }), encoding="utf-8")
            result = self.run_checker(manifest, project, "--require-outputs")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("不是普通文件", result.stdout)

    def test_checker_does_not_change_files_or_mtimes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "metrics.json").write_text('{"value": 1}', encoding="utf-8")
            manifest = project / "reproducibility.json"
            manifest.write_text(json.dumps({
                "schema_version": "1.1", "model_decisions": {}, "runs": [{
                    "id": "final", "role": "final", "working_directory": ".", "entry_command": ["python3", "run.py"], "inputs": [],
                    "outputs": [{"path": "metrics.json", "kind": "metrics"}], "environment": {}, "random_seeds": [], "checks": [{"name": "c", "passed": True}], "status": "passed",
                }],
            }), encoding="utf-8")
            before = {path: (path.stat().st_mtime_ns, path.stat().st_size) for path in project.iterdir()}
            result = self.run_checker(manifest, project, "--require-outputs")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            after = {path: (path.stat().st_mtime_ns, path.stat().st_size) for path in project.iterdir()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
