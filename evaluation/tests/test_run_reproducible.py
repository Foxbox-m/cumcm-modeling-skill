import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "cumcm-modeling/scripts/run_reproducible.py"
SPEC = importlib.util.spec_from_file_location("run_reproducible_under_test", RUNNER)
assert SPEC and SPEC.loader
run_reproducible = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_reproducible)


def write_manifest(project: Path, command: list[str], *, status: str = "planned", timeout: float = 2, attempts: int = 1, working_directory: str = ".") -> Path:
    (project / "input.txt").write_text("input", encoding="utf-8")
    manifest = project / "reproducibility.json"
    manifest.write_text(json.dumps({
        "schema_version": "1.1",
        "model_decisions": {},
        "runs": [{
            "id": "run-1", "role": "final", "working_directory": working_directory, "entry_command": command,
            "runtime_budget": {"timeout_seconds": timeout, "max_attempts": attempts},
            "inputs": ["input.txt"], "outputs": [{"path": "output.txt", "kind": "metrics"}],
            "environment": {}, "random_seeds": [], "checks": [], "status": status,
        }],
    }), encoding="utf-8")
    return manifest


class ReproducibleRunnerTests(unittest.TestCase):
    def invoke(self, manifest: Path, project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RUNNER), str(manifest), "--project-root", str(project), *extra],
            text=True, capture_output=True, check=False,
        )

    def test_default_is_read_only_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = write_manifest(project, [sys.executable, "-c", "open('output.txt','w').write('ok')"])
            result = self.invoke(manifest, project)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((project / "output.txt").exists())
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["runs"][0]["status"], "planned")

    def test_explicit_run_updates_same_manifest_and_checks_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = write_manifest(project, [sys.executable, "-c", "open('output.txt','w').write('ok')"])
            result = self.invoke(manifest, project, "--run", "run-1")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["runs"][0]["status"], "passed")
            self.assertEqual((project / "output.txt").read_text(encoding="utf-8"), "ok")

    def test_success_without_refreshing_old_output_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "output.txt").write_text("old", encoding="utf-8")
            manifest = write_manifest(project, [sys.executable, "-c", "pass"])
            result = self.invoke(manifest, project, "--run", "run-1")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("旧输出未被本次正式运行刷新", result.stderr)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["runs"][0]["status"], "failed")

    def test_relative_script_is_resolved_from_declared_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / "src"
            source.mkdir()
            (source / "q1.py").write_text("from pathlib import Path; Path('../output.txt').write_text('ok')", encoding="utf-8")
            manifest = write_manifest(project, [sys.executable, "q1.py"], working_directory="src")
            result = self.invoke(manifest, project, "--run", "run-1")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((project / "output.txt").read_text(encoding="utf-8"), "ok")

    def test_direct_relative_executable_is_resolved_from_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / "src"
            source.mkdir()
            script = source / "run.py"
            script.write_text(
                f"#!{sys.executable}\nfrom pathlib import Path\nPath('../output.txt').write_text('ok')\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            manifest = write_manifest(project, ["./run.py"], working_directory="src")
            result = self.invoke(manifest, project, "--run", "run-1")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((project / "output.txt").read_text(encoding="utf-8"), "ok")

    def test_relative_script_that_leaves_project_root_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "src").mkdir()
            manifest = write_manifest(project, [sys.executable, "../../outside.py"], working_directory="src")
            result = self.invoke(manifest, project, "--run", "run-1")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("不得越出 PROJECT_ROOT", result.stderr)

    def test_interpreter_options_do_not_hide_out_of_root_script(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = write_manifest(project, [sys.executable, "-u", "../outside.py"])
            result = self.invoke(manifest, project, "--run", "run-1")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("不得越出 PROJECT_ROOT", result.stderr)

    def test_timeout_terminates_and_records_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = write_manifest(project, [sys.executable, "-c", "import time; time.sleep(2)"], timeout=0.1)
            result = self.invoke(manifest, project, "--run", "run-1")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["runs"][0]["status"], "timed_out")

    def test_running_requires_explicit_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = write_manifest(project, [sys.executable, "-c", "open('output.txt','w').write('ok')"], status="running")
            result = self.invoke(manifest, project, "--run", "run-1")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["runs"][0]["status"], "running")
            result = self.invoke(manifest, project, "--run", "run-1", "--recover-running")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["runs"][0]["status"], "passed")

    def test_corrupt_manifest_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = project / "reproducibility.json"
            original = "{ invalid"
            manifest.write_text(original, encoding="utf-8")
            result = self.invoke(manifest, project, "--run", "run-1")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(manifest.read_text(encoding="utf-8"), original)

    def test_dry_run_rejects_unsupported_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = write_manifest(project, [sys.executable, "-c", "pass"])
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["schema_version"] = "1.0"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            result = self.invoke(manifest, project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("只支持 Schema 1.1", result.stderr)

    def test_malformed_output_is_blocked_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = write_manifest(project, [sys.executable, "-c", "open('side-effect','w').write('ran')"])
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["runs"][0]["outputs"] = [{"kind": "metrics"}]
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            result = self.invoke(manifest, project, "--run", "run-1")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((project / "side-effect").exists())

    def test_duplicate_run_id_is_not_executed_ambiguously(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = write_manifest(project, [sys.executable, "-c", "open('side-effect','w').write('ran')"])
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["runs"].append(dict(payload["runs"][0]))
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            result = self.invoke(manifest, project, "--run", "run-1")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("运行 id 重复", result.stderr)
            self.assertFalse((project / "side-effect").exists())

    def test_declared_output_directory_does_not_count_as_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = write_manifest(
                project,
                [sys.executable, "-c", "from pathlib import Path; Path('output.txt').mkdir()"],
            )
            result = self.invoke(manifest, project, "--run", "run-1")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["runs"][0]["status"], "failed")

    def test_windows_termination_waits_only_once_before_kill(self) -> None:
        class FakeProcess:
            def __init__(self) -> None:
                self.wait_calls = 0
                self.terminate_calls = 0
                self.kill_calls = 0

            def poll(self):
                return None

            def terminate(self) -> None:
                self.terminate_calls += 1

            def wait(self, timeout: float) -> None:
                self.wait_calls += 1
                raise subprocess.TimeoutExpired("fixture", timeout)

            def kill(self) -> None:
                self.kill_calls += 1

        process = FakeProcess()
        with mock.patch.object(run_reproducible.os, "name", "nt"):
            run_reproducible.terminate_process(process)
        self.assertEqual(process.terminate_calls, 1)
        self.assertEqual(process.wait_calls, 1)
        self.assertEqual(process.kill_calls, 1)


if __name__ == "__main__":
    unittest.main()
