#!/usr/bin/env python3
"""Check the Markdown-native Schema 4 project-brief contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PureWindowsPath


REQUIRED_HEADINGS = (
    "题面与交付约束",
    "任务证据",
    "事实、假设与风险",
    "当前门与下一步",
)
SCHEMA_VERSION = "4"
ALLOWED_SOURCES = {"CUMCM", "MCM", "custom"}
ALLOWED_GATES = {"G1", "G2", "G3"}
PLACEHOLDER_MARKERS = ("<填写", "TODO", "TBD", "待填写", "请填写", "按实际填写")
TOP_FIELD_PATTERN = re.compile(
    r"^(?P<indent>[ \t]*)(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<value>.*)$"
)
TASK_HEADING_PATTERN = re.compile(r"(?m)^###\s+(Q\d+)(?:\s*[:：\-—]\s*[^\n]*)?\s*$")
TASK_FIELD_NAMES = ("deliverable", "model", "why", "validation", "answer")
VALIDATION_FIELD_NAMES = ("plan", "evidence", "finding")
PROFILE_FIELD_NAMES = (
    "brief_schema_version",
    "problem_source",
    "current_gate",
)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?(?:-->|$)", re.DOTALL)


def _clean_value(value: str | None) -> str:
    if value is None:
        return ""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "`\"'":
        return value[1:-1].strip()
    return value


def _without_html_comments(value: str) -> str:
    return HTML_COMMENT_PATTERN.sub("", value)


def _is_placeholder(value: str | None) -> bool:
    value = _clean_value(value)
    if not value:
        return False
    folded = value.casefold()
    if any(marker.casefold() in folded for marker in PLACEHOLDER_MARKERS):
        return True
    if folded in {"pending", "待定", "待核验", "未确认", "none", "n/a", "na", "无"}:
        return True
    return bool(re.fullmatch(r"<[^>]+>", value))


def _nonempty_value(value: str | None, label: str, errors: list[str]) -> bool:
    cleaned = _clean_value(value)
    if not cleaned:
        errors.append(f"{label} 不能为空")
        return False
    if _is_placeholder(cleaned):
        errors.append(f"{label} 不能是占位内容")
        return False
    return True


def _top_level_fields(text: str) -> dict[str, list[str]]:
    """Collect unindented ``key: value`` declarations, retaining duplicates."""

    fields: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = TOP_FIELD_PATTERN.match(line)
        if match and not match.group("indent"):
            fields.setdefault(match.group("key"), []).append(_clean_value(match.group("value")))
    return fields


def _heading_bodies(text: str, heading: str) -> list[str]:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\n?(.*?)(?=^##\s+|\Z)"
    )
    return [match.group(1) for match in pattern.finditer(text)]


def _parse_inline_mapping(value: str) -> dict[str, str]:
    inner = value.strip().strip("{}").strip()
    result: dict[str, str] = {}
    if not inner:
        return result
    for item in re.split(r"[,;]", inner):
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$", item)
        if match:
            result[match.group(1)] = _clean_value(match.group(2))
    return result


def _task_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(TASK_HEADING_PATTERN.finditer(text))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        next_section = re.search(r"(?m)^##\s+", text[match.end() :])
        if next_section:
            end = min(end, match.end() + next_section.start())
        blocks.append((match.group(1), text[match.end() : end]))
    return blocks


def _parse_task(block: str) -> dict[str, object]:
    """Parse only the five Schema 4 task slots and validation's three children."""

    lines = block.splitlines()
    field_pattern = re.compile(
        r"^(?P<indent>[ \t]*)(?:[-*]\s+)?(?P<key>"
        + "|".join(TASK_FIELD_NAMES)
        + r")\s*:\s*(?P<value>.*)$"
    )
    candidates = [(index, match) for index, line in enumerate(lines) if (match := field_pattern.match(line))]
    if not candidates:
        return {}

    base_indent = min(len(match.group("indent")) for _, match in candidates)
    top_fields = [(index, match) for index, match in candidates if len(match.group("indent")) == base_indent]
    parsed: dict[str, object] = {}
    for position, (line_index, match) in enumerate(top_fields):
        key = match.group("key")
        next_line = top_fields[position + 1][0] if position + 1 < len(top_fields) else len(lines)
        inline = match.group("value").strip()
        continuation = lines[line_index + 1 : next_line]
        if key == "validation":
            mapping: dict[str, str] = _parse_inline_mapping(inline) if inline else {}
            child_pattern = re.compile(
                r"^[ \t]+(?:[-*]\s+)?(?P<key>"
                + "|".join(VALIDATION_FIELD_NAMES)
                + r")\s*:\s*(?P<value>.*)$"
            )
            for child_line in continuation:
                child = child_pattern.match(child_line)
                if child:
                    mapping[child.group("key")] = _clean_value(child.group("value"))
            parsed[key] = mapping
        else:
            value_lines = [inline] if inline else []
            value_lines.extend(line.strip() for line in continuation if line.strip())
            parsed[key] = _clean_value(" ".join(value_lines))

    # Dotted validation keys are useful in editors that flatten indentation.
    for line in lines:
        dotted = re.match(
            r"^\s*(?:[-*]\s+)?validation\.([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$", line
        )
        if dotted and dotted.group(1) in VALIDATION_FIELD_NAMES:
            mapping = parsed.setdefault("validation", {})
            if isinstance(mapping, dict):
                mapping[dotted.group(1)] = _clean_value(dotted.group(2))
    return parsed


def _path_error(
    raw_value: str | None,
    label: str,
    project_root: Path,
    errors: list[str],
) -> bool:
    value = _clean_value(raw_value)
    if not value:
        errors.append(f"{label} 不能为空")
        return False
    path_text = value.split("#", 1)[0]
    if not path_text:
        errors.append(f"{label} 的路径不能为空")
        return False
    if path_text.startswith("~") or PureWindowsPath(path_text).is_absolute() or PureWindowsPath(path_text).drive:
        errors.append(f"{label} 必须是项目根下的相对路径")
        return False
    candidate = Path(path_text)
    if candidate.is_absolute():
        errors.append(f"{label} 必须是项目根下的相对路径")
        return False
    root = project_root.resolve()
    resolved = (root / candidate).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        errors.append(f"{label} 路径不得越界项目根")
        return False
    if not resolved.exists():
        errors.append(f"{label} 路径不存在：{path_text}")
        return False
    return True


def _validate_profile(
    top_fields: dict[str, list[str]],
    required_gate: str | None,
    errors: list[str],
) -> tuple[str | None, str | None]:
    for field in PROFILE_FIELD_NAMES:
        values = top_fields.get(field, [])
        if len(values) != 1:
            errors.append(f"Schema4 要求顶层字段 {field} 且只能出现一次（当前 {len(values)} 次）")

    schema = top_fields.get("brief_schema_version", [None])[0]
    source = top_fields.get("problem_source", [None])[0]
    gate = top_fields.get("current_gate", [None])[0]
    if schema is not None and schema != "4":
        errors.append(f"字段 brief_schema_version 的值无效：{schema!r}；要求为 4")
    if source is not None and source not in ALLOWED_SOURCES:
        errors.append(f"字段 problem_source 的值无效：{source!r}；允许值为 CUMCM|MCM|custom")
    if gate is not None and gate not in ALLOWED_GATES:
        errors.append(f"字段 current_gate 的值无效：{gate!r}；允许值为 G1|G2|G3")
    if required_gate and gate in ALLOWED_GATES and gate != required_gate:
        errors.append(f"current_gate={gate} 与要求的 {required_gate} 不一致")
    return _clean_value(source) or None, _clean_value(gate) or None


def _validate_tasks(
    text: str,
    gate: str | None,
    project_root: Path,
    errors: list[str],
    expected_questions: int | None = None,
) -> None:
    blocks = _task_blocks(text)
    if not blocks:
        errors.append("Schema4 至少需要一个 ### Q1 等任务")
    task_ids = [task_id for task_id, _ in blocks]
    counts: dict[str, int] = {}
    for task_id in task_ids:
        counts[task_id] = counts.get(task_id, 0) + 1
    duplicates = sorted(task_id for task_id, count in counts.items() if count > 1)
    for task_id in duplicates:
        errors.append(f"Schema4 任务 ID 不得重复：{task_id}（当前 {counts[task_id]} 次）")

    if expected_questions is not None:
        if isinstance(expected_questions, bool) or not isinstance(expected_questions, int) or expected_questions <= 0:
            errors.append("expected_questions 必须是正整数")
        else:
            expected_ids = {f"Q{number}" for number in range(1, expected_questions + 1)}
            actual_ids = set(task_ids)
            if actual_ids != expected_ids or len(task_ids) != expected_questions:
                missing = sorted(expected_ids - actual_ids, key=lambda value: int(value[1:]))
                extra = sorted(actual_ids - expected_ids, key=lambda value: int(value[1:]))
                details: list[str] = []
                if missing:
                    details.append(f"缺少 {','.join(missing)}")
                if extra:
                    details.append(f"多出 {','.join(extra)}")
                if not details:
                    details.append(f"当前识别到 {len(task_ids)} 个任务")
                errors.append(
                    f"任务集合必须恰为 Q1..Q{expected_questions}（不要求顺序）；" + "，".join(details)
                )

    if not blocks:
        return

    for task_id, block in blocks:
        task = _parse_task(block)
        for field in ("deliverable", "model", "why"):
            _nonempty_value(task.get(field), f"{task_id}.{field}", errors)

        validation = task.get("validation")
        if not isinstance(validation, dict):
            errors.append(f"{task_id}.validation 必须包含 plan/evidence/finding 子项")
            validation = {}
        _nonempty_value(validation.get("plan"), f"{task_id}.validation.plan", errors)
        if gate in {"G2", "G3"}:
            _path_error(
                validation.get("evidence"),
                f"{task_id}.validation.evidence",
                project_root,
                errors,
            )
            _nonempty_value(validation.get("finding"), f"{task_id}.validation.finding", errors)
            _nonempty_value(task.get("answer"), f"{task_id}.answer", errors)


def _check_detailed(
    path: Path,
    required_gate: str | None = None,
    *,
    require_schema: str | None = None,
    project_root: Path | None = None,
    expected_questions: int | None = None,
) -> tuple[list[str], list[str], dict[str, object]]:
    errors: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, object] = {}
    if require_schema is not None:
        require_schema = str(require_schema)
        if require_schema != "4":
            errors.append(f"不支持的 schema 要求：{require_schema}；只接受 4")
    if not path.is_file():
        return [f"找不到简报：{path}"], warnings, metadata
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ["简报不是有效 UTF-8 文本"], warnings, metadata
    except OSError as exc:
        return [f"读取简报失败：{exc}"], warnings, metadata

    root = (project_root if project_root is not None else path.parent).resolve()
    top_fields = _top_level_fields(text)
    schema_values = top_fields.get("brief_schema_version", [])
    declared_schema = schema_values[0] if schema_values else None
    metadata["schema"] = declared_schema
    metadata["project_root"] = str(root)
    if declared_schema != SCHEMA_VERSION:
        errors.append(f"本 checker 仅支持 brief_schema_version: {SCHEMA_VERSION}；当前为 {declared_schema!r}")
    if require_schema == SCHEMA_VERSION and (len(schema_values) != 1 or schema_values[0] != SCHEMA_VERSION):
        errors.append(f"要求 brief_schema_version:{SCHEMA_VERSION}，当前为 {schema_values!r}")

    source, gate = _validate_profile(top_fields, required_gate, errors)
    metadata["problem_source"] = source
    metadata["current_gate"] = gate

    for heading in REQUIRED_HEADINGS:
        bodies = _heading_bodies(text, heading)
        if not bodies:
            errors.append(f"Schema4 缺少必需二级标题：{heading}")
        elif len(bodies) != 1:
            errors.append(f"Schema4 二级标题 {heading} 只能出现一次（当前 {len(bodies)} 次）")
        elif heading != "任务证据" and not _without_html_comments(bodies[0]).strip():
            errors.append(f"Schema4 二级标题 {heading} 去除 HTML 注释后不能为空")

    _validate_tasks(text, gate, root, errors, expected_questions=expected_questions)
    if any(marker.casefold() in text.casefold() for marker in PLACEHOLDER_MARKERS):
        errors.append("检测到模板占位标记；正式简报需替换为已确认内容")
    return errors, warnings, metadata


def check(
    path: Path,
    required_gate: str | None = None,
    *,
    require_schema: str | None = None,
    project_root: Path | None = None,
    expected_questions: int | None = None,
) -> list[str]:
    """Return Schema 4 validation errors for callers that do not need metadata."""

    errors, _, _ = _check_detailed(
        path,
        required_gate,
        require_schema=require_schema,
        project_root=project_root,
        expected_questions=expected_questions,
    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="检查持久化 CUMCM 项目简报")
    parser.add_argument("brief", type=Path)
    parser.add_argument("--require-gate", choices=("G1", "G2", "G3"))
    parser.add_argument("--require-schema", choices=("4",), help="要求简报使用 Schema 4")
    parser.add_argument("--project-root", type=Path, help="证据路径的项目根目录（默认使用简报所在目录）")
    def positive_integer(value: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("必须是正整数") from exc
        if parsed <= 0:
            raise argparse.ArgumentTypeError("必须是正整数")
        return parsed

    parser.add_argument(
        "--expected-questions",
        type=positive_integer,
        help="仅显式传入时要求任务集合恰为 Q1..QN；N 必须为正整数，任务顺序不限",
    )
    parser.add_argument("--json", action="store_true", help="只输出结构化 JSON 结果")
    args = parser.parse_args()
    errors, warnings, metadata = _check_detailed(
        args.brief,
        args.require_gate,
        require_schema=args.require_schema,
        project_root=args.project_root,
        expected_questions=args.expected_questions,
    )
    passed = not errors
    if args.json:
        payload = {
            "ok": passed,
            "passed": passed,
            "path": str(args.brief),
            "errors": errors,
            "warnings": warnings,
            **metadata,
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if passed else 1
    for error in errors:
        print(f"[错误] {error}")
    for warning in warnings:
        print(f"[警告] {warning}")
    if errors:
        return 1
    print(f"项目简报通过：{args.brief}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
