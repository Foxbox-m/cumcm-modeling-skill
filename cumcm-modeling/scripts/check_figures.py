#!/usr/bin/env python3
"""Audit the required submission and QA files for final reproducibility figures."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from PIL import Image


VECTOR_EXTENSIONS = {".pdf", ".svg"}
GENERATED_RASTER_EXTENSIONS = {".png", ".tif", ".tiff"}
PAPER_VISUAL_RASTER_EXTENSIONS = GENERATED_RASTER_EXTENSIONS | {".jpeg", ".jpg"}
PAPER_VISUAL_TYPES = {"paper_native_schematic", "external_cited"}


def _load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(value, dict):
        return None, "顶层必须是 JSON 对象"
    return value, None


def _resolve_inside(project_root: Path, value: str) -> Path | None:
    candidate = Path(value)
    if candidate.is_absolute():
        return None
    resolved = (project_root / candidate).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError:
        return None
    return resolved


def _file_error(path: Path, relative: str) -> str | None:
    if not path.exists():
        return f"文件不存在：{relative}"
    if not path.is_file():
        return f"不是普通文件：{relative}"
    if path.stat().st_size <= 0:
        return f"文件为空：{relative}"
    return None


def _raster_error(path: Path, relative: str) -> tuple[str | None, str | None]:
    try:
        with Image.open(path) as image:
            image.load()
            dpi = image.info.get("dpi")
    except Exception as exc:
        return f"栅格图无法由 Pillow 打开：{relative}（{exc}）", None
    if not isinstance(dpi, (tuple, list)) or len(dpi) < 2:
        return None, "DPI 缺失"
    try:
        values = [float(dpi[0]), float(dpi[1])]
    except (TypeError, ValueError):
        return None, "DPI 无法解析"
    if any(not math.isfinite(value) for value in values):
        return None, "DPI 无法解析"
    if min(values) < 295:
        return None, f"DPI 低于 295（{values[0]:g}×{values[1]:g}）"
    return None, None


def _check_gray_preview(
    project_root: Path,
    path: Path,
    relative: str,
    errors: list[str],
    label: str,
) -> None:
    gray = path.parent / "_qa" / f"{path.stem}_gray.png"
    gray_relative = gray.relative_to(project_root).as_posix()
    gray_error = _file_error(gray, gray_relative)
    if gray_error is not None:
        errors.append(f"{label}缺少灰度预览：{gray_error}")
        return
    try:
        with Image.open(gray) as image:
            image.load()
    except Exception as exc:
        errors.append(f"{label}的灰度预览无法由 Pillow 打开：{exc}")


def audit(manifest_path: Path, project_root: Path, allow_missing_dpi: bool = False) -> int:
    manifest, load_error = _load(manifest_path)
    if load_error is not None:
        print(f"[错误] 无法读取复现清单：{load_error}", file=sys.stderr)
        return 2
    assert manifest is not None
    errors: list[str] = []
    warnings: list[str] = []
    groups: dict[str, list[tuple[str, Path]]] = {}
    runs = manifest.get("runs")
    if not isinstance(runs, list):
        errors.append("runs 必须是数组")
        runs = []
    for run_index, run in enumerate(runs, start=1):
        if not isinstance(run, dict) or run.get("role") != "final":
            continue
        outputs = run.get("outputs")
        if not isinstance(outputs, list):
            errors.append(f"runs[{run_index}].outputs 必须是数组")
            continue
        for output_index, item in enumerate(outputs, start=1):
            if not isinstance(item, dict) or item.get("kind") != "figure":
                continue
            value = item.get("path")
            if not isinstance(value, str) or not value.strip():
                errors.append(f"runs[{run_index}].outputs[{output_index}] figure 必须含非空 path")
                continue
            path = _resolve_inside(project_root, value)
            if path is None:
                errors.append(f"runs[{run_index}].outputs[{output_index}] figure 路径越界：{value}")
                continue
            # A generated gray preview is QA material, not another formal figure stem.
            if "_qa" in path.parts or path.stem.endswith("_gray"):
                continue
            relative_key = path.relative_to(project_root).with_suffix("").as_posix()
            groups.setdefault(relative_key, []).append((value, path))

    paper_visuals = manifest.get("paper_visuals")
    if paper_visuals is not None:
        if not isinstance(paper_visuals, list):
            errors.append("paper_visuals 必须是数组")
            paper_visuals = []
        seen_visual_paths: set[str] = set()
        for visual_index, visual in enumerate(paper_visuals, start=1):
            prefix = f"paper_visuals[{visual_index}]"
            if not isinstance(visual, dict):
                errors.append(f"{prefix} 必须是对象")
                continue
            for field in ("path", "type", "purpose"):
                if not isinstance(visual.get(field), str) or not visual[field].strip():
                    errors.append(f"{prefix}.{field} 必须是非空字符串")
            visual_type = visual.get("type")
            if isinstance(visual_type, str) and visual_type.strip() and visual_type not in PAPER_VISUAL_TYPES:
                errors.append(f"{prefix}.type 只支持 paper_native_schematic/external_cited")
            path_value = visual.get("path")
            path = _resolve_inside(project_root, path_value) if isinstance(path_value, str) and path_value.strip() else None
            if path is None:
                if isinstance(path_value, str) and path_value.strip():
                    errors.append(f"{prefix}.path 必须是 PROJECT_ROOT 内的相对路径：{path_value}")
                continue
            relative = path.relative_to(project_root).as_posix()
            if relative in seen_visual_paths:
                errors.append(f"{prefix}.path 含重复路径：{path_value}")
            else:
                seen_visual_paths.add(relative)
            file_error = _file_error(path, relative)
            if file_error is not None:
                errors.append(f"{prefix}：{file_error}")
            if visual_type == "paper_native_schematic":
                source_value = visual.get("source_path")
                source = _resolve_inside(project_root, source_value) if isinstance(source_value, str) and source_value.strip() else None
                if source is None:
                    if not isinstance(source_value, str) or not source_value.strip():
                        errors.append(f"{prefix}.source_path 必须是非空项目内相对路径")
                    else:
                        errors.append(f"{prefix}.source_path 必须是 PROJECT_ROOT 内的相对路径：{source_value}")
                else:
                    source_relative = source.relative_to(project_root).as_posix()
                    source_error = _file_error(source, source_relative)
                    if source_error is not None:
                        errors.append(f"{prefix}.source_path：{source_error}")
            elif visual_type == "external_cited":
                for field in ("citation_id", "usage_note"):
                    if not isinstance(visual.get(field), str) or not visual[field].strip():
                        errors.append(f"{prefix}.{field} 必须是非空字符串")
            if file_error is None and path.suffix.lower() in PAPER_VISUAL_RASTER_EXTENSIONS:
                raster_error, dpi_issue = _raster_error(path, relative)
                if raster_error is not None:
                    errors.append(f"{prefix}：{raster_error}")
                if dpi_issue is not None:
                    message = f"{prefix}：{relative} {dpi_issue}"
                    (warnings if allow_missing_dpi else errors).append(message)
                _check_gray_preview(project_root, path, relative, errors, f"{prefix} ")

    if not groups and not errors:
        warnings.append("未找到 role=final 的 kind=figure 输出")

    for figure_key, entries in sorted(groups.items()):
        stem = entries[0][1].stem
        extensions = {path.suffix.lower() for _, path in entries}
        if not extensions & VECTOR_EXTENSIONS:
            errors.append(f"正式图 {figure_key} 缺少 PDF/SVG 矢量容器")
        if not extensions & GENERATED_RASTER_EXTENSIONS:
            errors.append(f"正式图 {figure_key} 缺少 PNG/TIFF 预览")

        for relative, path in entries:
            file_error = _file_error(path, relative)
            if file_error is not None:
                errors.append(f"正式图 {figure_key}：{file_error}")
                continue
            if path.suffix.lower() in GENERATED_RASTER_EXTENSIONS:
                raster_error, dpi_issue = _raster_error(path, relative)
                if raster_error is not None:
                    errors.append(f"正式图 {figure_key}：{raster_error}")
                if dpi_issue is not None:
                    message = f"正式图 {figure_key}：{relative} {dpi_issue}"
                    (warnings if allow_missing_dpi else errors).append(message)

        raster_entries = [
            (relative, path) for relative, path in entries
            if path.suffix.lower() in GENERATED_RASTER_EXTENSIONS
        ]
        checked_parents: set[Path] = set()
        for relative, path in raster_entries:
            if path.parent in checked_parents:
                continue
            checked_parents.add(path.parent)
            _check_gray_preview(project_root, path, relative, errors, f"正式图 {figure_key} ")

    print(f"复现清单：{manifest_path}")
    print(f"项目根目录：{project_root}")
    print(f"正式图 stem 数：{len(groups)}")
    for message in errors:
        print(f"[阻断] {message}")
    for message in warnings:
        print(f"[提醒] {message}")
    if errors:
        print(f"结论：未通过（{len(errors)} 个阻断项）")
        return 1
    print("结论：正式图件成套检查通过；PDF/SVG 容器可能仍含热图栅格，不宣称纯矢量")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 CUMCM role=final 图件的矢量、预览和灰度成套输出")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument(
        "--allow-missing-dpi",
        action="store_true",
        help="将 PNG/TIFF 缺失或低于 295 的 DPI 从阻断降为提醒",
    )
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    project_root = args.project_root.resolve()
    if not manifest.is_file():
        print(f"[错误] 清单不存在：{manifest}", file=sys.stderr)
        return 2
    if not project_root.is_dir():
        print(f"[错误] 项目根目录不存在：{project_root}", file=sys.stderr)
        return 2
    return audit(manifest, project_root, args.allow_missing_dpi)


if __name__ == "__main__":
    raise SystemExit(main())
