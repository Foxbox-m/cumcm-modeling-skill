# -*- coding: utf-8 -*-
"""Unit tests for check_stage.py stage gate orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
STAGE_SCRIPT = ROOT / "cumcm-modeling" / "scripts" / "check_stage.py"


def _create_minimal_brief(
    path: Path,
    gate: str = "G1",
    evidence: str = "results/q1.json",
    questions: int = 1,
) -> None:
    project_root = path.parent
    if evidence:
        evidence_file = project_root / evidence.split("#")[0]
        evidence_file.parent.mkdir(parents=True, exist_ok=True)
        if not evidence_file.exists():
            evidence_file.write_text("{}", encoding="utf-8")
    task_blocks = []
    for q in range(1, questions + 1):
        task_blocks.append(f"""### Q{q}
deliverable: 可复核的任务交付物
model: 状态变量与约束模型
why: 该模型对应题面机制并可验证
validation:
  plan: 用独立情景和残差检查验证
  evidence: {evidence if gate in ("G2", "G3") else ""}
  finding: 误差在合理区间
answer: 得到最优解""")
    tasks_str = "\n\n".join(task_blocks)
    content = f"""brief_schema_version: 4
problem_source: CUMCM
current_gate: {gate}

## 题面与交付约束
记录题面约束和交付要求。

## 任务证据

{tasks_str}

## 事实、假设与风险
记录已确认事实、假设和风险。

## 当前门与下一步
记录当前门和下一步动作。
"""
    path.write_text(content, encoding="utf-8")


def _create_g1_h_report(
    path: Path,
    decision: str = "APPROVED",
    skip_evidence: str = "",
    skip_time: str = "",
    body_extra: str = "",
) -> None:
    content = f"""---
review_schema_version: 1
gate: G1-H
decision: {decision}
skip_evidence: "{skip_evidence}"
skip_recorded_at: "{skip_time}"
---

# G1-H 建模审查报告
## 审查结论
决策：{decision}
{body_extra}
"""
    path.write_text(content, encoding="utf-8")


def _create_g2_h_report(path: Path, decision: str = "APPROVED") -> None:
    content = f"""---
review_schema_version: 1
gate: G2-H
decision: {decision}
---

# G2-H 数据与结果审查报告
决策：{decision}
"""
    path.write_text(content, encoding="utf-8")


def test_stage_g1_blocked_when_g1_h_pending(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    _create_minimal_brief(project_root / "modeling-brief.md", gate="G1")
    _create_g1_h_report(project_root / "preliminary-modeling-report.md", decision="PENDING")

    cmd = [sys.executable, str(STAGE_SCRIPT), "--stage", "G1", "--project-root", str(project_root)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "未获批准或合法跳过前不得放行 G1" in res.stderr or "PENDING" in res.stderr


def test_stage_g1_passed_when_g1_h_approved(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    _create_minimal_brief(project_root / "modeling-brief.md", gate="G1")
    _create_g1_h_report(project_root / "preliminary-modeling-report.md", decision="APPROVED")

    cmd = [sys.executable, str(STAGE_SCRIPT), "--stage", "G1", "--project-root", str(project_root)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert "G1 放行" in res.stdout


def test_stage_g1_skipped_by_user_requires_evidence_and_time(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    _create_minimal_brief(project_root / "modeling-brief.md", gate="G1")

    # 缺少原话证据阻断
    _create_g1_h_report(
        project_root / "preliminary-modeling-report.md",
        decision="SKIPPED_BY_USER",
        skip_evidence="",
        skip_time="",
    )
    cmd = [sys.executable, str(STAGE_SCRIPT), "--stage", "G1", "--project-root", str(project_root)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "缺少用户原话证据或记录时间" in res.stderr

    # 包含证据与时间放行
    _create_g1_h_report(
        project_root / "preliminary-modeling-report.md",
        decision="SKIPPED_BY_USER",
        skip_evidence="用户明确要求跳过",
        skip_time="2026-08-25 10:00:00",
    )
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert "G1-H 审查已记录合法的用户显式跳过" in res.stdout


def _create_valid_reproducibility_manifest(project_root: Path) -> Path:
    results_dir = project_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_file = results_dir / "out.json"
    if not out_file.exists():
        out_file.write_text("{}", encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "project_name": "test-project",
        "canonical_entrypoint": "code/main.py",
        "entrypoint_command": ["python3", "code/main.py"],
        "runs": [
            {
                "id": "final",
                "working_directory": ".",
                "entry_command": ["python3", "code/main.py"],
                "inputs": [],
                "outputs": ["results/out.json"],
                "environment": {"python": "3.10"},
                "random_seeds": [],
                "checks": [{"name": "ok", "passed": True}],
                "status": "passed",
            }
        ],
    }
    manifest_path = results_dir / "reproducibility.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _outline_question_block(question: int) -> str:
    sections = (
        (1, "本问到底解决什么", "题面任务、输入输出、目标和直接答案。"),
        (2, "由现实问题到数学对象", "实体、状态、决策变量、假设、数据和硬约束。"),
        (3, "baseline 与建模 Gap", "baseline 的能力、关键 Gap 以及 selected model 的必要性。"),
        (4, "最终模型与核心推导路线", "核心定义、公式推导、目标函数和约束形成过程。"),
        (5, "算法与求解过程", "输入、步骤、可行性处理、停止条件和输出。"),
        (8, "正式结果", "canonical result、单位、口径、约束和事实源路径。"),
        (9, "结果为什么会这样", "主导变量、活跃约束和结果解释。"),
        (10, "验证与结论边界", "验证结果、能说明什么、不能说明什么和未关闭风险。"),
            )
    return "\n\n".join(
        f"### Q{question}.{number} {title}\n{body}"
        for number, title, body in sections
    )


def test_stage_g2_requires_g2_h_approved_and_verifies_g1_h_without_recursing(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    # brief is current_gate=G2
    _create_minimal_brief(project_root / "modeling-brief.md", gate="G2")
    _create_g1_h_report(project_root / "preliminary-modeling-report.md", decision="APPROVED")
    _create_valid_reproducibility_manifest(project_root)

    # G2-H is PENDING -> should fail
    _create_g2_h_report(project_root / "G2-H_data_review.md", decision="PENDING")
    cmd = [sys.executable, str(STAGE_SCRIPT), "--stage", "G2", "--project-root", str(project_root)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "G2-H 检查未通过" in res.stderr or "PENDING" in res.stderr

    # G2-H is APPROVED -> should pass
    _create_g2_h_report(project_root / "G2-H_data_review.md", decision="APPROVED")
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert "G2 放行" in res.stdout


def test_stage_g3_requires_historical_g1_and_g2_approved(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    _create_minimal_brief(project_root / "modeling-brief.md", gate="G3")
    _create_valid_reproducibility_manifest(project_root)

    # 1. 缺 G1-H 阻断
    cmd = [sys.executable, str(STAGE_SCRIPT), "--stage", "G3", "--project-root", str(project_root)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "G1 前置检查未通过" in res.stderr or "未找到 G1-H" in res.stderr

    # 2. G1-H 已批准但缺 G2-H 阻断
    _create_g1_h_report(project_root / "preliminary-modeling-report.md", decision="APPROVED")
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "G2 前置检查未通过" in res.stderr or "未找到 G2-H" in res.stderr


def test_stage_g3_outline_validation(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    _create_minimal_brief(project_root / "modeling-brief.md", gate="G3")
    _create_g1_h_report(project_root / "preliminary-modeling-report.md", decision="APPROVED")
    _create_g2_h_report(project_root / "G2-H_data_review.md", decision="APPROVED")
    _create_valid_reproducibility_manifest(project_root)

    cmd = [sys.executable, str(STAGE_SCRIPT), "--stage", "G3", "--project-root", str(project_root)]

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "建模交接大纲不存在" in res.stderr or "paper-outline.md" in res.stderr

    outline_path = project_root / "paper-outline.md"
    outline_path.write_text("   \n", encoding="utf-8")
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "建模交接大纲为空文件" in res.stderr

    outline_path.write_text("# G3 建模交接大纲\n## 全局问题链\n主线\n", encoding="utf-8")
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "建模交接大纲缺少必需结构" in res.stderr

    outline_missing_question_contract = """# G3 建模交接大纲
## 全局问题链
主线
## 分问建模交接
### Q1.1 本问到底解决什么
任务与答案
## 跨问关系
独立任务
## 结果与证据索引
证据
## 尚未解决的问题
无影响正式结论的未决事项
"""
    outline_path.write_text(outline_missing_question_contract, encoding="utf-8")
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "逐问信息契约" in res.stderr and "Q1.2" in res.stderr

    valid_outline = """# G3 建模交接大纲
## 全局问题链
核心目标与建模链条。
## 分问建模交接
{question_block}
## 跨问关系
本题仅一问，无跨问传递。
## 结果与证据索引
结果与事实源索引。
## 尚未解决的问题
无影响正式结论的未决事项
""".format(question_block=_outline_question_block(1))
    outline_path.write_text(valid_outline, encoding="utf-8")
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert "G3 放行" in res.stdout

def test_stage_g3_q11_q12_are_optional_but_nonempty_if_present(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    _create_minimal_brief(project_root / "modeling-brief.md", gate="G3")
    _create_g1_h_report(project_root / "preliminary-modeling-report.md", decision="APPROVED")
    _create_g2_h_report(project_root / "G2-H_data_review.md", decision="APPROVED")
    _create_valid_reproducibility_manifest(project_root)

    base = """# G3 建模交接大纲
## 全局问题链
主线
## 分问建模交接
{q1}
## 跨问关系
本题仅一问，无跨问传递。
## 结果与证据索引
证据
## 尚未解决的问题
无影响正式结论的未决事项
""".format(q1=_outline_question_block(1))
    outline = project_root / "paper-outline.md"
    outline.write_text(base, encoding="utf-8")
    cmd = [sys.executable, str(STAGE_SCRIPT), "--stage", "G3", "--project-root", str(project_root)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0, res.stderr

    outline.write_text(base.replace("## 跨问关系", "### Q1.11 可视化意图\n\n## 跨问关系"), encoding="utf-8")
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "Q1.11" in res.stderr

    outline.write_text(base.replace("## 跨问关系", "### Q1.12 与下一问的接口\n\n## 跨问关系"), encoding="utf-8")
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "Q1.12" in res.stderr

def test_stage_g3_expected_questions(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    _create_minimal_brief(project_root / "modeling-brief.md", gate="G3", questions=3)
    _create_g1_h_report(project_root / "preliminary-modeling-report.md", decision="APPROVED")
    _create_g2_h_report(project_root / "G2-H_data_review.md", decision="APPROVED")
    _create_valid_reproducibility_manifest(project_root)

    outline_path = project_root / "paper-outline.md"
    outline_text = """# G3 建模交接大纲
## 全局问题链
核心目标。
## 分问建模交接
{q1}

{q2}
## 跨问关系
逻辑
## 结果与证据索引
数据
## 尚未解决的问题
未决
""".format(q1=_outline_question_block(1), q2=_outline_question_block(2))
    outline_path.write_text(outline_text, encoding="utf-8")

    cmd = [
        sys.executable,
        str(STAGE_SCRIPT),
        "--stage",
        "G3",
        "--project-root",
        str(project_root),
        "--expected-questions",
        "3",
    ]
    auto_cmd = [sys.executable, str(STAGE_SCRIPT), "--stage", "G3", "--project-root", str(project_root)]
    auto_res = subprocess.run(auto_cmd, capture_output=True, text=True, check=False)
    assert auto_res.returncode != 0
    assert "未覆盖全部子问" in auto_res.stderr and "Q3" in auto_res.stderr

    # 缺 Q3 阻断
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "未覆盖全部子问" in res.stderr and "Q3" in res.stderr

    # 补齐 Q3 放行
    outline_path.write_text(
        outline_text + "\n" + _outline_question_block(3) + "\n",
        encoding="utf-8",
    )
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert "G3 放行" in res.stdout
