#!/usr/bin/env python3
"""Validate CUMCM reproducibility manifests without executing commands."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

SCHEMA_VERSIONS = {"1.0", "1.1"}
RUN_ROLES = {"candidate", "baseline", "final"}
RUN_STATUSES = {"planned", "running", "passed", "failed", "timed_out", "interrupted"}


def is_string_list(value: Any, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def resolve_inside(project_root: Path, relative: str) -> Path | None:
    path = Path(relative)
    if path.is_absolute():
        return None
    resolved = (project_root / path).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError:
        return None
    return resolved


def _load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def output_entries(run: dict[str, Any], schema_version: str) -> list[dict[str, Any]]:
    """Normalize legacy string outputs and 1.1 structured outputs."""
    values = run.get("outputs")
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    for value in values:
        if isinstance(value, str):
            result.append({"path": value})
        elif schema_version == "1.1" and isinstance(value, dict):
            result.append(value)
    return result


def _validate_model_decisions(
    manifest: dict[str, Any], runs_by_id: dict[str, dict[str, Any]], errors: list[str]
) -> None:
    decisions = manifest.get("model_decisions")
    if not isinstance(decisions, dict):
        errors.append("model_decisions 必须是按子问题编号组织的对象")
        return
    for question, decision in decisions.items():
        prefix = f"model_decisions[{question!r}]"
        if not isinstance(question, str) or not question.strip():
            errors.append("model_decisions 的子问题键必须是非空字符串")
        if not isinstance(decision, dict):
            errors.append(f"{prefix} 必须是对象")
            continue
        for field in ("selected_run", "baseline_run"):
            value = decision.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                errors.append(f"{prefix}.{field} 必须是非空字符串或省略")
            elif isinstance(value, str) and value not in runs_by_id:
                errors.append(f"{prefix}.{field} 引用了不存在的运行：{value}")
            elif isinstance(value, str) and field == "selected_run" and runs_by_id[value].get("role") != "final":
                errors.append(f"{prefix}.selected_run 必须引用 role=final 的运行：{value}")
            elif isinstance(value, str) and field == "baseline_run" and runs_by_id[value].get("role") != "baseline":
                errors.append(f"{prefix}.baseline_run 必须引用 role=baseline 的运行：{value}")
        for field in ("selection_evidence", "unresolved_risks"):
            value = decision.get(field)
            if value is not None and not is_string_list(value, allow_empty=True):
                errors.append(f"{prefix}.{field} 必须是字符串数组")


def audit(
    manifest_path: Path,
    project_root: Path,
    require_outputs: bool = False,
) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    manifest, load_error = _load_json(manifest_path)
    if load_error is not None:
        print(f"[错误] 无法读取复现清单：{load_error}", file=sys.stderr)
        return 2

    if not isinstance(manifest, dict):
        errors.append("顶层必须是 JSON 对象")
        schema_version = "1.0"
        runs: list[Any] = []
    else:
        schema_version = manifest.get("schema_version")
        if schema_version not in SCHEMA_VERSIONS:
            errors.append("schema_version 必须是字符串 1.0 或 1.1")
            schema_version = "1.0"
        runs = manifest.get("runs", [])
        if not isinstance(runs, list) or not runs:
            errors.append("runs 必须是非空数组")
            runs = []

    seen_ids: set[str] = set()
    runs_by_id: dict[str, dict[str, Any]] = {}
    for index, run in enumerate(runs, start=1):
        prefix = f"runs[{index}]"
        if not isinstance(run, dict):
            errors.append(f"{prefix} 必须是对象")
            continue
        run_id = run.get("id")
        if not isinstance(run_id, str) or not run_id.strip():
            errors.append(f"{prefix}.id 必须是非空字符串")
        elif run_id in seen_ids:
            errors.append(f"{prefix}.id 重复：{run_id}")
        else:
            seen_ids.add(run_id)
            runs_by_id[run_id] = run

        if schema_version == "1.1" and run.get("role") not in RUN_ROLES:
            errors.append(f"{prefix}.role 必须是 candidate/baseline/final 之一")

        command = run.get("entry_command")
        if not is_string_list(command):
            errors.append(f"{prefix}.entry_command 必须是非空字符串数组")
        working_directory = run.get("working_directory", ".")
        resolved_workdir = (
            resolve_inside(project_root, working_directory)
            if isinstance(working_directory, str)
            else None
        )
        if resolved_workdir is None:
            errors.append(f"{prefix}.working_directory 必须是 PROJECT_ROOT 内的相对路径")
        elif not resolved_workdir.is_dir():
            errors.append(f"{prefix}.working_directory 不存在或不是目录：{working_directory}")

        values = run.get("inputs")
        if not is_string_list(values, allow_empty=True):
            errors.append(f"{prefix}.inputs 必须是字符串数组")
        else:
            for value in values:
                resolved = resolve_inside(project_root, value)
                if resolved is None:
                    errors.append(f"{prefix}.inputs 含越界或绝对路径：{value}")
                elif not resolved.exists():
                    errors.append(f"{prefix}.inputs 文件不存在：{value}")

        outputs = run.get("outputs")
        is_candidate = schema_version == "1.1" and run.get("role") == "candidate"
        if schema_version == "1.1":
            if not isinstance(outputs, list) or not outputs:
                errors.append(f"{prefix}.outputs 必须是非空数组")
            elif any(not isinstance(item, dict) for item in outputs):
                errors.append(f"{prefix}.outputs 每项必须是结构化对象；字符串输出仅兼容 Schema 1.0")
        elif not is_string_list(outputs, allow_empty=False):
            errors.append(f"{prefix}.outputs 必须是非空字符串数组")
        for item in output_entries(run, schema_version):
            value = item.get("path")
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.outputs 每项必须含非空相对路径")
                continue
            resolved = resolve_inside(project_root, value)
            if resolved is None:
                errors.append(f"{prefix}.outputs 含越界或绝对路径：{value}")
            elif require_outputs and not resolved.is_file():
                message = f"{prefix}.outputs 文件不存在或不是普通文件：{value}"
                (warnings if is_candidate else errors).append(message)
            elif not require_outputs and not resolved.exists():
                warnings.append(f"{prefix}.outputs 尚未生成：{value}")
            if schema_version == "1.1":
                kind = item.get("kind")
                if not isinstance(kind, str) or not kind.strip():
                    errors.append(f"{prefix}.outputs 结构项必须含非空 kind")
                if kind == "figure_data":
                    if not isinstance(item.get("purpose"), str) or not item["purpose"].strip():
                        errors.append(f"{prefix}.outputs.figure_data 必须含非空 purpose")

        environment = run.get("environment")
        if schema_version == "1.0" and (not isinstance(environment, dict) or not environment):
            errors.append(f"{prefix}.environment 必须记录实际运行环境")
        elif environment is not None and not isinstance(environment, dict):
            errors.append(f"{prefix}.environment 必须是对象")
        if not isinstance(run.get("random_seeds"), list):
            errors.append(f"{prefix}.random_seeds 必须是数组；确定性任务使用空数组")
        checks = run.get("checks")
        if not isinstance(checks, list) or (schema_version == "1.0" and not checks):
            errors.append(f"{prefix}.checks 必须是数组" + ("并至少记录一项结果或约束检查" if schema_version == "1.0" else ""))
        elif any(not isinstance(item, dict) or not isinstance(item.get("passed"), bool) for item in checks):
            errors.append(f"{prefix}.checks 每项必须是对象并含布尔型 passed 字段")
        elif require_outputs and (not checks or any(not item["passed"] for item in checks)):
            message = f"{prefix}.checks 含未通过项或没有检查项"
            (warnings if is_candidate else errors).append(message)

        status = run.get("status")
        allowed = {"planned", "running", "passed", "failed"} if schema_version == "1.0" else RUN_STATUSES
        if status not in allowed:
            errors.append(f"{prefix}.status 不在允许集合中：{sorted(allowed)}")
        elif require_outputs and status != "passed":
            message = f"{prefix}.status 在终检时必须为 passed"
            (warnings if is_candidate else errors).append(message)
        if schema_version == "1.1" and "runtime_budget" in run:
            budget = run["runtime_budget"]
            if not isinstance(budget, dict):
                errors.append(f"{prefix}.runtime_budget 必须是对象")
            else:
                for field in ("timeout_seconds", "max_attempts"):
                    value = budget.get(field)
                    invalid = isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0
                    if isinstance(value, float) and not math.isfinite(value):
                        invalid = True
                    if field == "max_attempts":
                        invalid = invalid or not isinstance(value, int)
                    if value is not None and invalid:
                        expected = "正整数" if field == "max_attempts" else "正数"
                        errors.append(f"{prefix}.runtime_budget.{field} 必须是{expected}")

    if schema_version == "1.1":
        _validate_model_decisions(manifest, runs_by_id, errors)

    print(f"复现清单：{manifest_path}")
    print(f"项目根目录：{project_root}")
    print(f"Schema：{schema_version}")
    for message in errors:
        print(f"[阻断] {message}")
    for message in warnings:
        print(f"[提醒] {message}")
    if errors:
        print(f"结论：未通过（{len(errors)} 个阻断项）")
        return 1
    print(f"结论：结构与路径检查通过（{len(runs)} 个运行条目）；尚未执行 entry_command")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 CUMCM 复现清单的结构和文件路径")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--require-outputs", action="store_true", help="终检时要求全部输出文件存在")
    args = parser.parse_args()
    if not args.manifest.is_file():
        print(f"[错误] 清单不存在：{args.manifest}", file=sys.stderr)
        return 2
    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        print(f"[错误] 项目根目录不存在：{project_root}", file=sys.stderr)
        return 2
    return audit(
        args.manifest.resolve(),
        project_root,
        args.require_outputs,
    )


if __name__ == "__main__":
    raise SystemExit(main())
