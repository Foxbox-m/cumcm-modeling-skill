#!/usr/bin/env python3
"""Orchestrate CUMCM workflow stage gates (G1, G2, G3).

This script provides an executable single-entrypoint stage orchestrator for
tasks under CUMCM modeling. It validates prerequisites, parses lightweight
frontmatter, verifies non-recursive historical evidence, and coordinates stage
requirements through G1 (modeling), G2 (computation/results), and G3 (structured modeling-handoff synthesis).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"

_G3_TOP_LEVEL_SECTIONS = (
    "全局问题链",
    "分问建模交接",
    "跨问关系",
    "结果与证据索引",
    "尚未解决的问题",
)
_G3_CORE_QUESTION_SECTIONS = (1, 2, 3, 4, 5, 8, 9, 10)
_G3_OPTIONAL_QUESTION_SECTIONS = (6, 7, 11, 12)
_G3_QUESTION_HEADING = re.compile(r"^###\s+Q(\d+)\.(\d+)\b.*$", re.MULTILINE)
_BRIEF_QUESTION_HEADING = re.compile(r"^###\s+Q(\d+)\b", re.MULTILINE)


def _parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    if not path.is_file():
        raise FileNotFoundError(f"文件不存在：{path}")
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end_idx = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx == -1:
        return {}, text
    frontmatter = {}
    for line in lines[1:end_idx]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            frontmatter[key.strip()] = val.strip().strip("\"'")
    body = "\n".join(lines[end_idx + 1:])
    return frontmatter, body


def _run_checker(cmd: list[str], *, cwd: Path | None = None) -> int:
    result = subprocess.run(cmd, cwd=cwd, check=False)
    return result.returncode


def _section_body(text: str, heading_pattern: re.Pattern[str], level: int) -> str | None:
    """Return a Markdown section body, stopping at the next same-or-higher heading."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not heading_pattern.match(line.strip()):
            continue
        end = index + 1
        boundary = re.compile(rf"^#{{1,{level}}}\s+")
        while end < len(lines) and not boundary.match(lines[end].strip()):
            end += 1
        return "\n".join(lines[index + 1:end]).strip()
    return None


def _has_outline_content(body: str | None) -> bool:
    """Reject empty sections while allowing ordinary Markdown lists and tables."""
    if body is None:
        return False
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or re.match(r"^#{1,6}\s+", stripped):
            continue
        if re.fullmatch(r"[|:\-\s]+", stripped):
            continue
        return True
    return False


def _has_top_level_section(text: str, phrase: str) -> bool:
    pattern = re.compile(rf"^##\s+.*{re.escape(phrase)}.*$")
    return _has_outline_content(_section_body(text, pattern, 2))


def _question_ids(text: str) -> set[int]:
    return {
        int(match.group(1))
        for match in _G3_QUESTION_HEADING.finditer(text)
        if match.group(2) == "1"
    }


def _brief_question_ids(path: Path) -> set[int]:
    text = path.read_text(encoding="utf-8")
    return {int(match.group(1)) for match in _BRIEF_QUESTION_HEADING.finditer(text)}


def _has_question_section(text: str, question: int, section: int) -> bool:
    pattern = re.compile(rf"^###\s+Q{question}\.{section}\b.*$")
    return _has_outline_content(_section_body(text, pattern, 3))


def _check_g1_h_evidence(project_root: Path) -> tuple[bool, str]:
    report_path = project_root / "preliminary-modeling-report.md"
    if not report_path.is_file():
        return False, f"未找到 G1-H 建模审查报告：{report_path}"
    try:
        frontmatter, body = _parse_frontmatter(report_path)
    except Exception as exc:
        return False, f"无法解析 G1-H 报告 frontmatter：{exc}"
    if frontmatter.get("gate") != "G1-H":
        return False, f"G1-H 报告 frontmatter 缺少 gate: G1-H (当前: {frontmatter.get('gate')})"
    decision = frontmatter.get("decision", "").upper()
    if decision == "APPROVED":
        return True, "G1-H 审查已明确 APPROVED"
    if decision == "SKIPPED_BY_USER":
        skip_evidence = frontmatter.get("skip_evidence", "").strip()
        skip_time = frontmatter.get("skip_recorded_at", "").strip()
        body_has_evidence = bool(re.search(r"explicit_user_skip|用户明确要求跳过|跳过人工建模审查", body))
        body_has_time = bool(re.search(r"\d{4}-\d{2}-\d{2}", body))
        has_evidence = bool(skip_evidence) or body_has_evidence
        has_time = bool(skip_time) or body_has_time
        if not (has_evidence and has_time):
            return False, "G1-H 状态为 SKIPPED_BY_USER，但缺少用户原话证据或记录时间"
        return True, "G1-H 审查已记录合法的用户显式跳过 (SKIPPED_BY_USER)"
    if decision in ("PENDING", "REVISE"):
        return False, f"G1-H 报告当前状态为 {decision}；未获批准或合法跳过前不得放行 G1"
    return False, f"G1-H 报告包含无效的 decision 状态：{decision}"


def _check_g2_h_evidence(project_root: Path) -> tuple[bool, str]:
    review_path = project_root / "G2-H_data_review.md"
    if not review_path.is_file():
        return False, f"未找到 G2-H 数据与结果审查报告：{review_path}"
    try:
        frontmatter, _ = _parse_frontmatter(review_path)
    except Exception as exc:
        return False, f"无法解析 G2-H 报告 frontmatter：{exc}"
    if frontmatter.get("gate") != "G2-H":
        return False, f"G2-H 报告 frontmatter 缺少 gate: G2-H (当前: {frontmatter.get('gate')})"
    decision = frontmatter.get("decision", "").upper()
    if decision == "APPROVED":
        return True, "G2-H 审查已明确 APPROVED"
    return False, f"G2-H 报告当前状态为 {decision}；未获明确 APPROVED 前不得放行 G2/G3"


def stage_g1(project_root: Path, *, expected_questions: int | None = None) -> int:
    print(f"=== [G1 建模门检查] {project_root} ===")
    brief_path = project_root / "modeling-brief.md"
    if not brief_path.is_file():
        print(f"[错误] 项目简报不存在：{brief_path}", file=sys.stderr)
        return 1

    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "check_project_brief.py"),
        str(brief_path),
        "--require-schema",
        "4",
        "--require-gate",
        "G1",
        "--project-root",
        str(project_root),
    ]
    if expected_questions is not None:
        cmd.extend(["--expected-questions", str(expected_questions)])

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print("[错误] check_project_brief.py 检查失败：", file=sys.stderr)
        if res.stdout:
            print(res.stdout.strip(), file=sys.stderr)
        if res.stderr:
            print(res.stderr.strip(), file=sys.stderr)
        return res.returncode

    ok, msg = _check_g1_h_evidence(project_root)
    if not ok:
        print(f"[错误] {msg}", file=sys.stderr)
        return 1
    print(f"[通过] {msg}")
    print("[G1 放行] 建模门检查全部通过。")
    return 0


def stage_g2(project_root: Path, *, expected_questions: int | None = None) -> int:
    print(f"=== [G2 计算与结果门检查] {project_root} ===")
    brief_path = project_root / "modeling-brief.md"
    if not brief_path.is_file():
        print(f"[错误] 项目简报不存在：{brief_path}", file=sys.stderr)
        return 1

    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "check_project_brief.py"),
        str(brief_path),
        "--require-schema",
        "4",
        "--require-gate",
        "G2",
        "--project-root",
        str(project_root),
    ]
    if expected_questions is not None:
        cmd.extend(["--expected-questions", str(expected_questions)])

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print("[错误] check_project_brief.py G2 校验失败：", file=sys.stderr)
        if res.stdout:
            print(res.stdout.strip(), file=sys.stderr)
        if res.stderr:
            print(res.stderr.strip(), file=sys.stderr)
        return res.returncode

    # 验证 G1 历史前置证据（非递归执行）
    ok, msg = _check_g1_h_evidence(project_root)
    if not ok:
        print(f"[错误] G1 前置检查未通过：{msg}", file=sys.stderr)
        return 1

    # 执行 G2-A 机器检查
    manifest_path = project_root / "results/reproducibility.json"
    if not manifest_path.is_file():
        print(f"[错误] 复现清单不存在：{manifest_path}", file=sys.stderr)
        return 1

    code = _run_checker([
        sys.executable,
        str(SCRIPTS_DIR / "check_reproducibility.py"),
        str(manifest_path),
        "--project-root",
        str(project_root),
        "--require-outputs",
    ])
    if code != 0:
        print("[错误] G2-A check_reproducibility.py 检查失败", file=sys.stderr)
        return code


    # 验证 G2-H 人工审查证据
    ok, msg = _check_g2_h_evidence(project_root)
    if not ok:
        print(f"[错误] G2-H 检查未通过：{msg}", file=sys.stderr)
        return 1
    print(f"[通过] {msg}")
    print("[G2 放行] 计算与结果门检查全部通过。")
    return 0


def stage_g3(project_root: Path, *, expected_questions: int | None = None) -> int:
    print(f"=== [G3 建模交接大纲门检查] {project_root} ===")
    brief_path = project_root / "modeling-brief.md"
    if not brief_path.is_file():
        print(f"[错误] 项目简报不存在：{brief_path}", file=sys.stderr)
        return 1

    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "check_project_brief.py"),
        str(brief_path),
        "--require-schema",
        "4",
        "--require-gate",
        "G3",
        "--project-root",
        str(project_root),
    ]
    if expected_questions is not None:
        cmd.extend(["--expected-questions", str(expected_questions)])

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print("[错误] check_project_brief.py G3 校验失败：", file=sys.stderr)
        if res.stdout:
            print(res.stdout.strip(), file=sys.stderr)
        if res.stderr:
            print(res.stderr.strip(), file=sys.stderr)
        return res.returncode

    # 验证历史前置证据（非递归执行）
    ok, msg = _check_g1_h_evidence(project_root)
    if not ok:
        print(f"[错误] G1 前置检查未通过：{msg}", file=sys.stderr)
        return 1
    ok, msg = _check_g2_h_evidence(project_root)
    if not ok:
        print(f"[错误] G2 前置检查未通过：{msg}", file=sys.stderr)
        return 1

    manifest_path = project_root / "results/reproducibility.json"
    if not manifest_path.is_file():
        print(f"[错误] 复现清单不存在：{manifest_path}", file=sys.stderr)
        return 1

    # 机器计算复现验证（要求输出齐全）
    code = _run_checker([
        sys.executable,
        str(SCRIPTS_DIR / "check_reproducibility.py"),
        str(manifest_path),
        "--project-root",
        str(project_root),
        "--require-outputs",
    ])
    if code != 0:
        print("[错误] G3 计算复现输出检查失败", file=sys.stderr)
        return code

    # G3 建模交接大纲检查
    outline_path = project_root / "paper-outline.md"
    if not outline_path.is_file():
        print(f"[错误] G3 建模交接大纲不存在：{outline_path}", file=sys.stderr)
        return 1

    text = outline_path.read_text(encoding="utf-8").strip()
    if not text:
        print(f"[错误] G3 建模交接大纲为空文件：{outline_path}", file=sys.stderr)
        return 1

    missing_sections = [
        section for section in _G3_TOP_LEVEL_SECTIONS
        if not _has_top_level_section(text, section)
    ]
    if missing_sections:
        print(f"[错误] G3 建模交接大纲缺少必需结构：{', '.join(missing_sections)}", file=sys.stderr)
        return 1

    detected_questions = _question_ids(text)
    if expected_questions is not None:
        expected_question_ids = set(range(1, expected_questions + 1))
        missing_questions = [
            f"Q{q}" for q in sorted(expected_question_ids - detected_questions)
        ]
        if missing_questions:
            print(f"[错误] G3 建模交接大纲未覆盖全部子问：缺少 {', '.join(missing_questions)}", file=sys.stderr)
            return 1
        question_ids = sorted(expected_question_ids)
    else:
        brief_question_ids = _brief_question_ids(brief_path)
        required_question_ids = brief_question_ids or detected_questions
        missing_questions = [
            f"Q{q}" for q in sorted(required_question_ids - detected_questions)
        ]
        if missing_questions:
            print(f"[错误] G3 建模交接大纲未覆盖全部子问：缺少 {', '.join(missing_questions)}", file=sys.stderr)
            return 1
        if not required_question_ids:
            print(
                "[错误] G3 建模交接大纲未找到实际子问区段：至少需要一个 `### Q1.1 ...` 形式的逐问大纲",
                file=sys.stderr,
            )
            return 1
        question_ids = sorted(required_question_ids)

    missing_question_sections = []
    for question in question_ids:
        for section in _G3_CORE_QUESTION_SECTIONS:
            if not _has_question_section(text, question, section):
                missing_question_sections.append(f"Q{question}.{section}")
        for section in _G3_OPTIONAL_QUESTION_SECTIONS:
            optional_heading = re.compile(
                rf"^###\s+Q{question}\.{section}\b.*$", re.MULTILINE
            )
            if optional_heading.search(text) and not _has_question_section(text, question, section):
                missing_question_sections.append(f"Q{question}.{section}")
    if missing_question_sections:
        print(
            "[错误] G3 建模交接大纲的逐问信息契约未满足（缺少区段或区段无内容）："
            + ", ".join(missing_question_sections),
            file=sys.stderr,
        )
        return 1

    print("[G3 放行] 建模交接大纲结构与事实前置检查通过")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CUMCM 工作流阶段门禁总控编排器 (G1, G2, G3)")
    parser.add_argument("--stage", choices=("G1", "G2", "G3"), required=True, help="要验证的阶段门")
    parser.add_argument("--project-root", type=Path, required=True, help="项目根目录")
    parser.add_argument("--expected-questions", type=int, help="显式问题数（若题面包含）")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        print(f"[错误] 项目根目录不存在：{project_root}", file=sys.stderr)
        return 2

    if args.stage == "G1":
        return stage_g1(project_root, expected_questions=args.expected_questions)
    elif args.stage == "G2":
        return stage_g2(project_root, expected_questions=args.expected_questions)
    elif args.stage == "G3":
        return stage_g3(project_root, expected_questions=args.expected_questions)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
