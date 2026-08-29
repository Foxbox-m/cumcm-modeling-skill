#!/usr/bin/env python3
"""Run one approved Schema 1.1 manifest entry with safe defaults.

Without ``--run`` this command is a read-only dry-run.  With ``--run`` it
executes the declared argument array (never through a shell) and atomically
updates the selected entry's lifecycle status in the same manifest.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from check_reproducibility import resolve_inside  # noqa: E402


def read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"[错误] 复现清单无法读取：{exc}\n"
            "未覆盖原文件；请使用 Git 恢复，或先手工修复 JSON 后再运行。",
            file=sys.stderr,
        )
        return None
    if not isinstance(value, dict):
        print("[错误] 复现清单顶层必须是 JSON 对象，未覆盖原文件。", file=sys.stderr)
        return None
    return value


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    """Replace one manifest only after the new JSON has been fully written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        if path.exists():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def update_status(manifest_path: Path, manifest: dict[str, Any], run: dict[str, Any], status: str) -> None:
    run["status"] = status
    atomic_write(manifest_path, manifest)


def path_inside_or_error(project_root: Path, relative: Any, label: str) -> Path | None:
    if not isinstance(relative, str) or not relative.strip():
        print(f"[阻断] {label} 必须是非空相对路径", file=sys.stderr)
        return None
    resolved = resolve_inside(project_root, relative)
    if resolved is None:
        print(f"[阻断] {label} 必须位于 PROJECT_ROOT 内：{relative}", file=sys.stderr)
    return resolved


def interpreter_and_script_check(command: list[str], workdir: Path, project_root: Path) -> list[str]:
    errors: list[str] = []
    first = command[0]
    first_path = Path(first)
    if first_path.is_absolute() or "/" in first or first.startswith("."):
        executable = first_path.resolve() if first_path.is_absolute() else (workdir / first_path).resolve()
        if not first_path.is_absolute():
            try:
                executable.relative_to(project_root)
            except ValueError:
                errors.append(f"入口脚本不得越出 PROJECT_ROOT：{first}")
                executable = None
        if executable is None or not executable.is_file() or not os.access(executable, os.X_OK):
            errors.append(f"入口脚本不存在或不可执行：{first}")
    elif shutil.which(first) is None:
        errors.append(f"解释器或可执行程序不在 PATH 中：{first}")

    interpreter = Path(first).name.lower()
    script_interpreters = {"python", "python3", "python3.10", "python3.11", "python3.12", "pypy", "pypy3", "bash", "sh", "zsh", "rscript"}
    candidate: str | None = None
    if interpreter in script_interpreters:
        option_takes_value = {"-W", "-X"} if interpreter not in {"bash", "sh", "zsh"} else {"-O", "-o"}
        index = 1
        while index < len(command):
            argument = command[index]
            if argument in {"-c", "-m", "--version", "-V"}:
                break
            if argument in option_takes_value:
                index += 2
                continue
            if argument == "--":
                index += 1
                if index < len(command):
                    candidate = command[index]
                break
            if not argument.startswith("-"):
                candidate = argument
                break
            index += 1
    if candidate is not None:
        candidate_path = Path(candidate)
        if candidate_path.is_absolute():
            script = candidate_path.resolve()
        else:
            script = (workdir / candidate_path).resolve()
        try:
            script.relative_to(project_root)
        except ValueError:
            errors.append(f"入口脚本不得越出 PROJECT_ROOT：{candidate}")
            script = None
        if script is not None and not script.is_file():
            errors.append(f"入口脚本不存在：{candidate}")
        elif script is not None and candidate_path.is_absolute():
            errors.append(f"入口脚本不得使用绝对路径：{candidate}")
    return errors


def output_paths(run: dict[str, Any]) -> list[str]:
    values = run.get("outputs", [])
    paths: list[str] = []
    if isinstance(values, list):
        for value in values:
            if isinstance(value, str):
                paths.append(value)
            elif isinstance(value, dict) and isinstance(value.get("path"), str):
                paths.append(value["path"])
    return paths


def output_snapshots(project_root: Path, run: dict[str, Any]) -> dict[str, tuple[bool, int | None, int | None]]:
    """Record existence, mtime and size without reading output contents."""
    snapshots: dict[str, tuple[bool, int | None, int | None]] = {}
    for path in output_paths(run):
        resolved = resolve_inside(project_root, path)
        if resolved is None:
            continue
        try:
            stat = resolved.stat()
        except FileNotFoundError:
            snapshots[path] = (False, None, None)
        except OSError:
            snapshots[path] = (resolved.exists(), None, None)
        else:
            snapshots[path] = (True, stat.st_mtime_ns, stat.st_size)
    return snapshots


def output_freshness(
    project_root: Path,
    run: dict[str, Any],
    before: dict[str, tuple[bool, int | None, int | None]],
) -> tuple[list[str], list[str]]:
    """Return (missing, stale) output paths after a successful command."""
    missing: list[str] = []
    stale: list[str] = []
    for path in output_paths(run):
        resolved = resolve_inside(project_root, path)
        if resolved is None or not resolved.is_file():
            missing.append(path)
            continue
        try:
            stat = resolved.stat()
        except OSError:
            missing.append(path)
            continue
        old_exists, old_mtime_ns, old_size = before.get(path, (False, None, None))
        if old_exists and old_mtime_ns == stat.st_mtime_ns and old_size == stat.st_size:
            stale.append(path)
    return missing, stale


def preflight(project_root: Path, run: dict[str, Any]) -> tuple[bool, Path | None, float, int]:
    errors: list[str] = []
    command = run.get("entry_command")
    if not isinstance(command, list) or not command or any(not isinstance(x, str) or not x.strip() for x in command):
        errors.append("entry_command 必须是非空字符串数组")
        command = []
    workdir = path_inside_or_error(project_root, run.get("working_directory", "."), "working_directory")
    if workdir is None or not workdir.is_dir():
        errors.append("working_directory 不存在或不是目录")
    if command and workdir is not None:
        errors.extend(interpreter_and_script_check(command, workdir, project_root))
    inputs = run.get("inputs", [])
    if not isinstance(inputs, list):
        errors.append("inputs 必须是数组")
    else:
        for index, item in enumerate(inputs, start=1):
            resolved = path_inside_or_error(project_root, item, f"inputs[{index}]")
            if resolved is not None and not resolved.exists():
                errors.append(f"输入文件不存在：{item}")
    outputs = run.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        errors.append("outputs 必须是非空数组")
    else:
        for index, item in enumerate(outputs, start=1):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"].strip():
                errors.append(f"outputs[{index}] 必须是含非空 path 的结构化对象")
                continue
            if not isinstance(item.get("kind"), str) or not item["kind"].strip():
                errors.append(f"outputs[{index}].kind 必须是非空字符串")
            if path_inside_or_error(project_root, item["path"], f"outputs[{index}]") is None:
                errors.append(f"输出路径越界：{item['path']}")
    budget = run.get("runtime_budget")
    timeout = budget.get("timeout_seconds") if isinstance(budget, dict) else None
    attempts = budget.get("max_attempts") if isinstance(budget, dict) else None
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0 or (isinstance(timeout, float) and not math.isfinite(timeout)):
        errors.append("runtime_budget.timeout_seconds 必须是正数")
        timeout = 0.0
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts <= 0:
        errors.append("runtime_budget.max_attempts 必须是正整数")
        attempts = 0
    for error in errors:
        print(f"[阻断] {error}", file=sys.stderr)
    return not errors, workdir, float(timeout), int(attempts)


def terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()


def execute(command: list[str], workdir: Path, timeout: float) -> tuple[str, int | None, str]:
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=workdir,
            shell=False,
            start_new_session=(os.name == "posix"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            output, _ = process.communicate(timeout=timeout)
            code = process.returncode
            return ("passed" if code == 0 else "failed", code, output[-4000:])
        except subprocess.TimeoutExpired as exc:
            terminate_process(process)
            output, _ = process.communicate()
            captured = exc.output or ""
            if isinstance(captured, bytes):
                captured = captured.decode(errors="replace")
            combined = captured + (output or "")
            return "timed_out", None, combined[-4000:]
    except KeyboardInterrupt:
        if process is not None:
            terminate_process(process)
        return "interrupted", None, "收到 KeyboardInterrupt，已终止进程组"
    except OSError as exc:
        return "failed", None, str(exc)


def dry_run(manifest: dict[str, Any], project_root: Path, selected: str | None) -> int:
    runs = manifest.get("runs", [])
    if not isinstance(runs, list) or not runs:
        print("[错误] runs 必须是非空数组", file=sys.stderr)
        return 1
    matched = [r for r in runs if isinstance(r, dict) and (selected is None or r.get("id") == selected)]
    if selected is not None and not matched:
        print(f"[错误] 未找到运行条目：{selected}", file=sys.stderr)
        return 1
    print("模式：dry-run（只读，不执行命令，不修改清单）")
    preflight_results: list[bool] = []
    for run in matched:
        ok, workdir, timeout, attempts = preflight(project_root, run)
        preflight_results.append(ok)
        print(f"运行：{run.get('id')} | status={run.get('status')} | preflight={'通过' if ok else '未通过'}")
        print(f"  命令：{run.get('entry_command')}")
        print(f"  工作目录：{workdir} | timeout={timeout} | max_attempts={attempts}")
    return 0 if all(preflight_results) else 1


def run_one(manifest_path: Path, manifest: dict[str, Any], project_root: Path, run_id: str, recover: bool) -> int:
    if manifest.get("schema_version") != "1.1":
        print("[阻断] 受控运行器只执行 Schema 1.1，Schema 1.0 请继续人工执行并检查。", file=sys.stderr)
        return 1
    runs = manifest.get("runs")
    matches = [item for item in runs if isinstance(item, dict) and item.get("id") == run_id] if isinstance(runs, list) else []
    if not matches:
        print(f"[错误] 未找到运行条目：{run_id}", file=sys.stderr)
        return 1
    if len(matches) > 1:
        print(f"[阻断] 运行 id 重复，无法确定执行目标：{run_id}", file=sys.stderr)
        return 1
    run = matches[0]
    if run.get("status") == "running":
        if not recover:
            print("[阻断] 运行状态为 running；请使用 --recover-running 明确恢复，避免重复执行。", file=sys.stderr)
            return 1
        update_status(manifest_path, manifest, run, "interrupted")
        print("[恢复] 已将遗留 running 状态标记为 interrupted，开始新的批准尝试。")
    ok, workdir, timeout, attempts = preflight(project_root, run)
    if not ok or workdir is None:
        return 1
    command = run["entry_command"]
    output_before = output_snapshots(project_root, run)
    update_status(manifest_path, manifest, run, "running")
    final_status = "failed"
    for attempt in range(1, attempts + 1):
        print(f"[执行] {run_id}：第 {attempt}/{attempts} 次")
        status, code, output = execute(command, workdir, timeout)
        if output:
            print(output)
        final_status = status
        if status in {"passed", "timed_out", "interrupted"}:
            break
    update_status(manifest_path, manifest, run, final_status)
    print(f"[结果] {run_id}: {final_status}")
    if final_status == "passed":
        missing, stale = output_freshness(project_root, run, output_before)
        if missing:
            print(f"[阻断] 程序成功退出，但声明输出缺失：{missing}", file=sys.stderr)
            update_status(manifest_path, manifest, run, "failed")
            return 1
        if stale:
            print(
                "[阻断] 程序成功退出，但旧输出未被本次正式运行刷新："
                f"{stale}（仅检查存在性、mtime_ns 和 size；不宣称防篡改）",
                file=sys.stderr,
            )
            update_status(manifest_path, manifest, run, "failed")
            return 1
        return 0
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="以受控方式执行 CUMCM Schema 1.1 复现清单")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run", dest="run_id", help="显式指定并执行一个运行条目；省略时只 dry-run")
    parser.add_argument("--recover-running", action="store_true", help="允许恢复遗留 running 状态")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        print(f"[错误] PROJECT_ROOT 不存在：{project_root}", file=sys.stderr)
        return 2
    try:
        manifest_path.relative_to(project_root)
    except ValueError:
        print("[错误] manifest 必须位于 PROJECT_ROOT 内", file=sys.stderr)
        return 2
    if not manifest_path.is_file():
        print(f"[错误] 清单不存在：{manifest_path}", file=sys.stderr)
        return 2
    manifest = read_manifest(manifest_path)
    if manifest is None:
        return 2
    if manifest.get("schema_version") != "1.1":
        print("[阻断] 受控运行器只支持 Schema 1.1。", file=sys.stderr)
        return 1
    if args.run_id is None:
        return dry_run(manifest, project_root, None)
    return run_one(manifest_path, manifest, project_root, args.run_id, args.recover_running)


if __name__ == "__main__":
    raise SystemExit(main())
