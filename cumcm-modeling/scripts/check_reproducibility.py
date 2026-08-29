#!/usr/bin/env python3
"""Validate CUMCM reproducibility manifests without executing commands."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

SCHEMA_VERSIONS = {"1.0", "1.1"}
RUN_ROLES = {"candidate", "baseline", "final"}
RUN_STATUSES = {"planned", "running", "passed", "failed", "timed_out", "interrupted"}
PAPER_VISUAL_TYPES = {"paper_native_schematic", "external_cited"}


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


def json_pointer_get(document: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON Pointer."""
    if pointer == "":
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("JSON Pointer 必须为空字符串或以 / 开头")
    current = document
    for raw_token in pointer[1:].split("/"):
        token = ""
        index = 0
        while index < len(raw_token):
            if raw_token[index] != "~":
                token += raw_token[index]
                index += 1
            elif index + 1 >= len(raw_token) or raw_token[index + 1] not in "01":
                raise ValueError("JSON Pointer 含无效转义")
            else:
                token += "~" if raw_token[index + 1] == "0" else "/"
                index += 2
        if isinstance(current, dict):
            if token not in current:
                raise KeyError(token)
            current = current[token]
        elif isinstance(current, list):
            valid_index = token == "0" or (token.isdigit() and not token.startswith("0"))
            if token == "-" or not valid_index or int(token) >= len(current):
                raise KeyError(token)
            current = current[int(token)]
        else:
            raise KeyError(token)
    return current


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


def _validate_claim_bindings(
    manifest: dict[str, Any],
    project_root: Path,
    runs_by_id: dict[str, dict[str, Any]],
    schema_version: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    bindings = manifest.get("claim_bindings")
    if bindings is None:
        return
    if not isinstance(bindings, list):
        errors.append("claim_bindings 必须是数组")
        return
    seen_claim_ids: set[str] = set()
    for index, binding in enumerate(bindings, start=1):
        prefix = f"claim_bindings[{index}]"
        if not isinstance(binding, dict):
            errors.append(f"{prefix} 必须是对象")
            continue
        for field in ("id", "paper_location", "source_run", "output_path", "output_pointer"):
            if not isinstance(binding.get(field), str) or not binding[field].strip():
                errors.append(f"{prefix}.{field} 必须是非空字符串")
        claim_id = binding.get("id")
        if isinstance(claim_id, str) and claim_id.strip():
            if claim_id in seen_claim_ids:
                errors.append(f"{prefix}.id 重复：{claim_id}")
            else:
                seen_claim_ids.add(claim_id)
        source_run = binding.get("source_run")
        output_path = binding.get("output_path")
        pointer = binding.get("output_pointer")
        run = runs_by_id.get(source_run) if isinstance(source_run, str) else None
        if run is None:
            if isinstance(source_run, str):
                errors.append(f"{prefix}.source_run 引用了不存在的运行：{source_run}")
            continue
        entries = output_entries(run, schema_version)
        declared = [
            item for item in entries
            if item.get("path") == output_path and item.get("kind") == "metrics"
        ]
        if not declared:
            errors.append(f"{prefix}.output_path 必须对应 source_run 声明的 metrics 输出：{output_path}")
            continue
        resolved = resolve_inside(project_root, output_path) if isinstance(output_path, str) else None
        if resolved is None:
            errors.append(f"{prefix}.output_path 必须是 PROJECT_ROOT 内的相对路径")
            continue
        if not resolved.is_file():
            warnings.append(f"{prefix}.output_path 尚未生成，暂不解析 output_pointer：{output_path}")
            continue
        metrics, error = _load_json(resolved)
        if error is not None:
            errors.append(f"{prefix}.metrics 输出不是可读取的 JSON：{error}")
            continue
        try:
            json_pointer_get(metrics, pointer)
        except (KeyError, ValueError, TypeError) as exc:
            errors.append(f"{prefix}.output_pointer 无法解析：{pointer}（{exc}）")


def _validate_figure_claim_references(
    manifest: dict[str, Any],
    runs: list[Any],
    require_claims: bool,
    errors: list[str],
    warnings: list[str],
) -> None:
    bindings = manifest.get("claim_bindings")
    defined_ids = {
        item["id"]
        for item in bindings
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
    } if isinstance(bindings, list) else set()
    for run_index, run in enumerate(runs, start=1):
        if not isinstance(run, dict):
            continue
        for output_index, item in enumerate(output_entries(run, "1.1"), start=1):
            if item.get("kind") != "figure":
                continue
            claims = item.get("supports_claims")
            if not is_string_list(claims, allow_empty=True):
                continue
            for claim_id in claims:
                if claim_id not in defined_ids:
                    message = (
                        f"runs[{run_index}].outputs[{output_index}].supports_claims "
                        f"引用了未定义的 claim id：{claim_id}"
                    )
                    (errors if require_claims else warnings).append(message)


def _validate_paper_visuals(
    manifest: dict[str, Any],
    project_root: Path,
    strict: bool,
    errors: list[str],
    warnings: list[str],
) -> dict[str, dict[str, Any]]:
    """Validate optional non-running paper visuals and return normalized entries."""
    value = manifest.get("paper_visuals")
    if value is None:
        return {}
    if not isinstance(value, list):
        errors.append("paper_visuals 必须是数组")
        return {}

    entries: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(value, start=1):
        prefix = f"paper_visuals[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} 必须是对象")
            continue
        for field in ("path", "type", "purpose"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field} 必须是非空字符串")
        visual_type = item.get("type")
        if isinstance(visual_type, str) and visual_type.strip() and visual_type not in PAPER_VISUAL_TYPES:
            errors.append(f"{prefix}.type 只支持 paper_native_schematic/external_cited")

        path_value = item.get("path")
        normalized: str | None = None
        if isinstance(path_value, str) and path_value.strip():
            normalized = _normalised_project_path(project_root, path_value)
            if normalized is None:
                errors.append(f"{prefix}.path 必须是 PROJECT_ROOT 内的相对路径：{path_value}")
            elif normalized in entries:
                errors.append(f"{prefix}.path 含重复路径：{path_value}")
            else:
                entries[normalized] = item
                resolved = project_root / normalized
                if not resolved.is_file() or resolved.stat().st_size <= 0:
                    message = f"{prefix}.path 文件不存在、为空或不是普通文件：{path_value}"
                    (errors if strict else warnings).append(message)

        if visual_type == "paper_native_schematic":
            source_value = item.get("source_path")
            if not isinstance(source_value, str) or not source_value.strip():
                errors.append(f"{prefix}.source_path 必须是非空项目内相对路径")
            else:
                source_normalized = _normalised_project_path(project_root, source_value)
                if source_normalized is None:
                    errors.append(f"{prefix}.source_path 必须是 PROJECT_ROOT 内的相对路径：{source_value}")
                elif not (project_root / source_normalized).is_file() or (project_root / source_normalized).stat().st_size <= 0:
                    message = f"{prefix}.source_path 文件不存在、为空或不是普通文件：{source_value}"
                    (errors if strict else warnings).append(message)
        elif visual_type == "external_cited":
            for field in ("citation_id", "usage_note"):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    errors.append(f"{prefix}.{field} 必须是非空字符串")
    return entries


_TEX_FIGURE_EXTENSIONS = (".pdf", ".svg", ".png", ".tiff", ".tif", ".jpeg", ".jpg")
_SCRIPT_INTERPRETERS = {
    "python", "python3", "python3.10", "python3.11", "python3.12",
    "pypy", "pypy3", "bash", "sh", "zsh", "rscript", "ruby", "node",
    "julia", "perl", "php",
}


def _is_script_interpreter(name: str) -> bool:
    if name in _SCRIPT_INTERPRETERS:
        return True
    return bool(re.fullmatch(r"(?:python|python3|pypy|pypy3)\d+(?:\.\d+)*", name))


def _normalised_project_path(project_root: Path, value: str) -> str | None:
    resolved = resolve_inside(project_root, value)
    if resolved is None:
        return None
    return resolved.relative_to(project_root).as_posix()


def _entry_script_path(project_root: Path, run: dict[str, Any]) -> str | None:
    """Return a recognizable, existing project-relative script in entry_command."""
    command = run.get("entry_command")
    working_directory = run.get("working_directory", ".")
    if not is_string_list(command) or not isinstance(working_directory, str):
        return None
    workdir = resolve_inside(project_root, working_directory)
    if workdir is None or not workdir.is_dir():
        return None

    first = command[0]
    first_name = Path(first).name.lower()
    candidate: str | None = None
    first_path = Path(first)
    if _is_script_interpreter(first_name):
        takes_value = {"-W", "-X", "-e", "--eval"} if first_name.startswith(("python", "pypy")) else set()
        index = 1
        while index < len(command):
            argument = command[index]
            if argument in {"-c", "-m", "--version", "-V", "--eval"}:
                break
            if argument in takes_value:
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
    elif first_path.is_absolute() or "/" in first or first.startswith("."):
        candidate = first
    if candidate is None:
        return None
    candidate_path = Path(candidate)
    resolved = candidate_path.resolve() if candidate_path.is_absolute() else (workdir / candidate_path).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError:
        return None
    if not resolved.is_file():
        return None
    return resolved.relative_to(project_root).as_posix()


def _strip_tex_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%[^\n\r]*", "", text)


def _tex_appendix_references(text: str) -> tuple[list[tuple[str, str]], bool]:
    """Return (path, options) references and whether a line-range option was used."""
    cleaned = _strip_tex_comments(text)
    boundaries = [match.start() for match in re.finditer(r"\\appendix\b", cleaned)]
    title_pattern = re.compile(
        r"\\(?:section|chapter)\*?(?:\s*\[[^\]]*\])?\s*\{([^{}]*(?:附录|appendix)[^{}]*)\}",
        re.IGNORECASE,
    )
    boundaries.extend(match.start() for match in title_pattern.finditer(cleaned))
    if not boundaries:
        return [], False
    cleaned = cleaned[min(boundaries):]
    references: list[tuple[str, str]] = []
    partial = False
    listing = re.compile(r"\\lstinputlisting\s*(?:\[([^\]]*)\])?\s*\{([^{}]+)\}")
    minted = re.compile(r"\\inputminted\s*(?:\[([^\]]*)\])?\s*\{[^{}]+\}\s*\{([^{}]+)\}")
    for match in list(listing.finditer(cleaned)) + list(minted.finditer(cleaned)):
        options = match.group(1) or ""
        path = match.group(2).strip()
        references.append((path, options))
        if re.search(r"(?:^|,)\s*(?:firstline|lastline)\s*=", options):
            partial = True
    return references, partial


def _resolve_tex_relative(project_root: Path, tex_path: Path, reference: str) -> Path | None:
    reference_path = Path(reference)
    if reference_path.is_absolute():
        return None
    resolved = (tex_path.parent / reference_path).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError:
        return None
    return resolved


def _tex_graphic_paths(text: str) -> list[str]:
    cleaned = _strip_tex_comments(text)
    paths: list[str] = []
    for match in re.finditer(r"\\graphicspath\s*\{((?:\s*\{[^{}]*\})+)\}", cleaned):
        paths.extend(item.strip() for item in re.findall(r"\{([^{}]*)\}", match.group(1)) if item.strip())
    return paths


def _tex_graphic_references(text: str) -> list[str]:
    cleaned = _strip_tex_comments(text)
    return [match.group(1).strip() for match in re.finditer(
        r"\\includegraphics\*?\s*(?:\[[^\]]*\])?\s*\{([^{}]+)\}", cleaned
    )]


def _resolve_tex_graphic(project_root: Path, tex_path: Path, graphic_paths: list[str], reference: str) -> Path | None:
    reference_path = Path(reference)
    if reference_path.is_absolute():
        return None
    bases = [tex_path.parent / item for item in graphic_paths] if graphic_paths else [tex_path.parent]
    candidates: list[Path] = []
    for base in bases:
        direct = (base / reference_path).resolve()
        if reference_path.suffix:
            candidates.append(direct)
        else:
            candidates.append(direct)
            candidates.extend(direct.with_suffix(ext) for ext in _TEX_FIGURE_EXTENSIONS)
        for candidate in candidates:
            try:
                candidate.relative_to(project_root)
            except ValueError:
                continue
            if candidate.is_file():
                return candidate
        candidates.clear()
    return None


def _validate_top_artifact_fields(
    manifest: dict[str, Any],
    project_root: Path,
    runs: list[Any],
    schema_version: str,
    require_appendix_sources: bool,
    require_paper_artifacts: bool,
    paper_visuals: dict[str, dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> None:
    if schema_version != "1.1":
        return

    paper_value = manifest.get("paper_source")
    paper_path: Path | None = None
    if paper_value is not None:
        if not isinstance(paper_value, str) or not paper_value.strip():
            errors.append("paper_source 必须是非空项目内相对路径")
        else:
            paper_path = resolve_inside(project_root, paper_value)
            if paper_path is None:
                errors.append("paper_source 必须是 PROJECT_ROOT 内的相对路径")
            elif not paper_path.is_file():
                errors.append(f"paper_source 文件不存在或不是普通文件：{paper_value}")
    if require_appendix_sources and paper_value is None:
        errors.append("--require-appendix-sources 要求 paper_source")
    if require_paper_artifacts:
        if paper_value is None:
            errors.append("--require-paper-artifacts 要求 paper_source")
        elif paper_path is not None and paper_path.suffix.lower() != ".tex":
            errors.append("--require-paper-artifacts 要求 paper_source 为 .tex")

    appendix_value = manifest.get("appendix_sources")
    appendix_paths: dict[str, Path] = {}
    if appendix_value is not None:
        if not is_string_list(appendix_value):
            errors.append("appendix_sources 必须是非空字符串数组")
        else:
            for item in appendix_value:
                normalised = _normalised_project_path(project_root, item)
                if normalised is None:
                    errors.append(f"appendix_sources 含越界或绝对路径：{item}")
                    continue
                if normalised in appendix_paths:
                    errors.append(f"appendix_sources 含重复路径：{item}")
                    continue
                resolved = project_root / normalised
                appendix_paths[normalised] = resolved
                if not resolved.is_file():
                    errors.append(f"appendix_sources 文件不存在或不是普通文件：{item}")
    if require_appendix_sources and not is_string_list(appendix_value):
        errors.append("--require-appendix-sources 要求非空 appendix_sources")

    archive_value = manifest.get("supporting_archive")
    archive_path: Path | None = None
    if archive_value is not None:
        if not isinstance(archive_value, str) or not archive_value.strip():
            errors.append("supporting_archive 必须是非空项目内相对路径")
        else:
            archive_path = resolve_inside(project_root, archive_value)
            if archive_path is None:
                errors.append("supporting_archive 必须是 PROJECT_ROOT 内的相对路径")
            elif archive_path.suffix.lower() not in {".zip", ".rar"}:
                errors.append("supporting_archive 只支持 .zip 或 .rar")
            elif not archive_path.is_file():
                errors.append(f"supporting_archive 文件不存在或不是普通文件：{archive_value}")

    if not require_appendix_sources and not require_paper_artifacts:
        return

    if require_appendix_sources:
        final_scripts = {
            script for run in runs
            if isinstance(run, dict) and run.get("role") == "final"
            for script in [_entry_script_path(project_root, run)]
            if script is not None
        }
        missing_scripts = sorted(final_scripts - set(appendix_paths))
        for script in missing_scripts:
            errors.append(f"role=final 的入口脚本未列入 appendix_sources：{script}")

        if paper_path is not None and paper_path.is_file() and paper_path.suffix.lower() == ".tex":
            try:
                tex_text = paper_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                errors.append(f"paper_source 无法读取：{exc}")
            else:
                references, partial = _tex_appendix_references(tex_text)
                if partial:
                    errors.append("paper_source 的代码引入使用了 firstline/lastline，无法证明附录完整包含")
                reference_paths: set[str] = set()
                for reference, _options in references:
                    resolved = _resolve_tex_relative(project_root, paper_path, reference)
                    if resolved is None:
                        errors.append(f"paper_source 代码引入越出 PROJECT_ROOT：{reference}")
                        continue
                    if not resolved.is_file():
                        errors.append(f"paper_source 引用的附录源文件不存在：{reference}")
                        continue
                    reference_paths.add(resolved.relative_to(project_root).as_posix())
                for source in sorted(set(appendix_paths) - reference_paths):
                    errors.append(f"appendix_sources 未被 paper_source 完整引入：{source}")
                for reference in sorted(reference_paths - set(appendix_paths)):
                    errors.append(f"paper_source 引入的源文件未列入 appendix_sources：{reference}")
        elif paper_path is not None:
            warnings.append("paper_source 不是 TeX；附录内容是否完整包含需人工复核")

        if archive_path is not None and archive_path.is_file() and archive_path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(archive_path) as archive:
                    names = set(archive.namelist())
                for source in sorted(set(appendix_paths) - names):
                    errors.append(f"supporting_archive 未精确包含 appendix source：{source}")
            except (OSError, zipfile.BadZipFile) as exc:
                errors.append(f"supporting_archive 不是可读取的 ZIP：{exc}")
        elif archive_path is not None and archive_path.is_file() and archive_path.suffix.lower() == ".rar":
            warnings.append("RAR supporting_archive 的成员路径未由标准库核对，需人工精确核对")

    if require_paper_artifacts:
        if paper_path is None or not paper_path.is_file() or paper_path.suffix.lower() != ".tex":
            return
        try:
            tex_text = paper_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"paper_source 无法读取：{exc}")
            return
        figure_outputs: dict[str, list[dict[str, Any]]] = {}
        for run in runs:
            if not isinstance(run, dict) or run.get("role") != "final":
                continue
            for item in output_entries(run, "1.1"):
                if item.get("kind") != "figure" or not isinstance(item.get("path"), str):
                    continue
                normalised = _normalised_project_path(project_root, item["path"])
                if normalised is not None:
                    figure_outputs.setdefault(normalised, []).append(item)
        for reference in _tex_graphic_references(tex_text):
            resolved = _resolve_tex_graphic(project_root, paper_path, _tex_graphic_paths(tex_text), reference)
            if resolved is None:
                errors.append(f"正文 includegraphics 文件不存在：{reference}")
                continue
            normalised = resolved.relative_to(project_root).as_posix()
            declarations = figure_outputs.get(normalised, [])
            if not declarations and normalised not in paper_visuals:
                errors.append(f"正文插图未由 role=final 的 kind=figure 输出声明，也未由 paper_visuals 声明：{normalised}")
        consumed_paths = set()
        for reference in _tex_graphic_references(tex_text):
            resolved = _resolve_tex_graphic(project_root, paper_path, _tex_graphic_paths(tex_text), reference)
            if resolved is not None:
                consumed_paths.add(resolved.relative_to(project_root).as_posix())
        for visual_path, visual in paper_visuals.items():
            if visual.get("type") == "paper_native_schematic" and visual_path not in consumed_paths:
                errors.append(
                    f"paper_visuals 注册的 paper_native_schematic 未被 paper_source includegraphics 消费：{visual_path}"
                )


def audit(
    manifest_path: Path,
    project_root: Path,
    require_outputs: bool,
    require_claims: bool = False,
    require_paper_artifacts: bool = False,
    require_appendix_sources: bool = False,
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

    paper_visuals = (
        _validate_paper_visuals(
            manifest, project_root, require_outputs or require_paper_artifacts, errors, warnings
        )
        if isinstance(manifest, dict) and schema_version == "1.1"
        else {}
    )

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
                if kind == "figure":
                    if not isinstance(item.get("purpose"), str) or not item["purpose"].strip():
                        errors.append(f"{prefix}.outputs.figure 必须含非空 purpose")
                    if "supports_claims" in item and not is_string_list(item.get("supports_claims"), allow_empty=True):
                        errors.append(f"{prefix}.outputs.figure.supports_claims 必须是字符串数组")

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
        _validate_claim_bindings(manifest, project_root, runs_by_id, schema_version, errors, warnings)
        _validate_figure_claim_references(manifest, runs, require_claims, errors, warnings)
        _validate_top_artifact_fields(
            manifest,
            project_root,
            runs,
            schema_version,
            require_appendix_sources,
            require_paper_artifacts,
            paper_visuals,
            errors,
            warnings,
        )
        if require_claims and (not isinstance(manifest.get("claim_bindings"), list) or not manifest["claim_bindings"]):
            errors.append("--require-claims 要求存在非空 headline claim_bindings 数组")

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
    parser.add_argument("--require-claims", action="store_true", help="G3 终检时要求非空 headline 数值主张 claim_bindings")
    parser.add_argument(
        "--require-paper-artifacts",
        action="store_true",
        help="G3 严格核对 TeX 正文插图与 role=final figure/paper_visuals 声明",
    )
    parser.add_argument(
        "--require-appendix-sources",
        action="store_true",
        help="G3 严格核对附录源文件、TeX 代码引入和 supporting_archive",
    )
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
        args.require_claims,
        args.require_paper_artifacts,
        args.require_appendix_sources,
    )


if __name__ == "__main__":
    raise SystemExit(main())
