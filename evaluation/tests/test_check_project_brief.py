from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "cumcm-modeling/scripts/check_project_brief.py"
TEMPLATE = ROOT / "cumcm-modeling/assets/project-brief/modeling-brief-template.md"


def schema4_brief(
    gate: str = "G1",
    *,
    deliverable: str = "可复核的任务交付物",
    model: str = "状态变量与约束模型",
    why: str = "该模型对应题面机制并可验证",
    plan: str = "用独立情景和残差检查验证",
    evidence: str = "",
    finding: str = "",
    answer: str = "",
    source: str = "CUMCM",
    extra_task_fields: str = "",
    task_ids: tuple[str, ...] = ("Q1",),
) -> str:
    task_blocks = "\n".join(
        f"""### {task_id}
deliverable: {deliverable}
model: {model}
why: {why}
validation:
  plan: {plan}
  evidence: {evidence}
  finding: {finding}
answer: {answer}
{extra_task_fields}"""
        for task_id in task_ids
    )
    return f"""brief_schema_version: 4
problem_source: {source}
current_gate: {gate}

## 题面与交付约束
记录题面约束和最终交付格式。

## 任务证据

{task_blocks}
## 事实、假设与风险
记录已确认事实、假设和风险。

## 当前门与下一步
记录当前门和下一步动作。
"""



def write_brief(tmp_path: Path, **kwargs: str) -> Path:
    path = tmp_path / "brief.md"
    path.write_text(schema4_brief(**kwargs), encoding="utf-8")
    return path


def run(path: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(CHECKER), str(path), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_valid_g1_passes_and_optional_slots_may_be_empty(tmp_path: Path):
    result = run(write_brief(tmp_path), "--require-gate", "G1", "--require-schema", "4")
    assert result.returncode == 0
    assert "项目简报通过" in result.stdout


@pytest.mark.parametrize("field", ["deliverable", "model", "why", "plan"])
def test_g1_requires_core_slots_and_validation_plan(tmp_path: Path, field: str):
    values = {field: ""}
    result = run(write_brief(tmp_path, **values))
    assert result.returncode == 1
    label = "validation.plan" if field == "plan" else field
    assert f"Q1.{label}" in result.stdout


def test_g1_does_not_require_evidence_finding_or_answer(tmp_path: Path):
    result = run(write_brief(tmp_path, evidence="", finding="", answer=""))
    assert result.returncode == 0


def test_g2_nested_and_dotted_evidence_paths_use_same_path_gate(tmp_path: Path):
    (tmp_path / "results").mkdir()
    (tmp_path / "results/q1.json").write_text("{}", encoding="utf-8")
    nested = write_brief(tmp_path, gate="G2", evidence="results/q1.json#q1", finding="误差在阈值内", answer="任务答案")
    assert run(nested, "--project-root", str(tmp_path)).returncode == 0

    dotted = tmp_path / "dotted.md"
    dotted.write_text(
        schema4_brief(gate="G2", evidence="", finding="误差在阈值内", answer="任务答案").replace(
            "  evidence: \n", "validation.evidence: results/q1.json#q1\n"
        ),
        encoding="utf-8",
    )
    assert run(dotted, "--project-root", str(tmp_path)).returncode == 0


@pytest.mark.parametrize("evidence", ["", "missing/result.json#row", "../outside.json", "/tmp/result.json", "~/result.json", "C:\\tmp\\result.json"])
def test_g2_rejects_missing_invalid_or_unsafe_evidence(tmp_path: Path, evidence: str):
    (tmp_path / "results").mkdir()
    path = write_brief(tmp_path, gate="G2", evidence=evidence, finding="验证发现", answer="任务答案")
    result = run(path, "--project-root", str(tmp_path))
    assert result.returncode == 1
    assert "Q1.validation.evidence" in result.stdout


def test_g2_requires_finding_and_answer(tmp_path: Path):
    (tmp_path / "results").mkdir()
    evidence = "results/q1.json"
    (tmp_path / evidence).write_text("{}", encoding="utf-8")
    path = write_brief(tmp_path, gate="G2", evidence=evidence, finding="", answer="")
    result = run(path, "--project-root", str(tmp_path))
    assert result.returncode == 1
    assert "Q1.validation.finding" in result.stdout
    assert "Q1.answer" in result.stdout


def test_g3_has_no_paper_section_page_or_legacy_logic_gate(tmp_path: Path):
    (tmp_path / "evidence.txt").write_text("validated", encoding="utf-8")
    path = write_brief(
        tmp_path,
        gate="G3",
        evidence="evidence.txt",
        finding="验证发现",
        answer="任务答案",
        extra_task_fields="paper_section: 不应参与 Schema 4 门禁\ncontent_budget: ignored\nlogic_checks: ignored\n",
    )
    assert run(path, "--project-root", str(tmp_path)).returncode == 0


def test_schema3_is_rejected(tmp_path: Path):
    path = write_brief(tmp_path).with_name("schema3.md")
    path.write_text(schema4_brief().replace("brief_schema_version: 4", "brief_schema_version: 3"), encoding="utf-8")
    result = run(path)
    assert result.returncode == 1
    assert "仅支持" in result.stdout and "4" in result.stdout


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("problem_source", "other"),
        ("current_gate", "G9"),
    ],
)
def test_profile_and_gate_values_are_checked(tmp_path: Path, field: str, value: str):
    content = schema4_brief().replace(f"{field}: {dict(problem_source='CUMCM', current_gate='G1')[field]}", f"{field}: {value}")
    path = tmp_path / "invalid.md"
    path.write_text(content, encoding="utf-8")
    result = run(path)
    assert result.returncode == 1
    assert field in result.stdout


def test_duplicate_top_level_field_is_rejected(tmp_path: Path):
    path = write_brief(tmp_path)
    path.write_text(path.read_text(encoding="utf-8").replace("problem_source: CUMCM\n", "problem_source: CUMCM\nproblem_source: MCM\n"), encoding="utf-8")
    result = run(path)
    assert result.returncode == 1
    assert "problem_source" in result.stdout and "只能出现一次" in result.stdout


def test_placeholder_and_normal_none_model_are_rejected(tmp_path: Path):
    path = write_brief(tmp_path, model="无")
    result = run(path)
    assert result.returncode == 1
    assert "Q1.model" in result.stdout
    path.write_text(schema4_brief(model="TODO"), encoding="utf-8")
    assert run(path).returncode == 1


def test_missing_heading_and_task_are_rejected(tmp_path: Path):
    path = write_brief(tmp_path)
    path.write_text(path.read_text(encoding="utf-8").replace("## 当前门与下一步\n记录当前门和下一步动作。\n", ""), encoding="utf-8")
    result = run(path)
    assert result.returncode == 1
    assert "缺少必需二级标题" in result.stdout

    no_task = tmp_path / "no-task.md"
    no_task.write_text(schema4_brief().replace("### Q1\n", ""), encoding="utf-8")
    result = run(no_task)
    assert result.returncode == 1
    assert "至少需要一个" in result.stdout


def test_expected_questions_rejects_missing_task_and_accepts_complete_set_in_any_order(tmp_path: Path):
    missing = write_brief(tmp_path, task_ids=("Q1", "Q3"))
    result = run(missing, "--expected-questions", "3")
    assert result.returncode == 1
    assert "恰为 Q1..Q3" in result.stdout and "Q2" in result.stdout

    complete = write_brief(tmp_path, task_ids=("Q3", "Q1", "Q2"))
    assert run(complete, "--expected-questions", "3").returncode == 0


def test_omitted_expected_questions_does_not_infer_task_set(tmp_path: Path):
    path = write_brief(tmp_path, task_ids=("Q2", "Q7"))
    result = run(path)
    assert result.returncode == 0


def test_duplicate_task_id_is_always_rejected(tmp_path: Path):
    path = write_brief(tmp_path, task_ids=("Q1", "Q1"))
    result = run(path)
    assert result.returncode == 1
    assert "任务 ID 不得重复" in result.stdout and "Q1" in result.stdout


@pytest.mark.parametrize("heading", ["题面与交付约束", "事实、假设与风险", "当前门与下一步"])
def test_required_non_task_sections_must_have_content(tmp_path: Path, heading: str):
    path = write_brief(tmp_path)
    content = path.read_text(encoding="utf-8")
    content = content.replace(
        f"## {heading}\n" + {
            "题面与交付约束": "记录题面约束和最终交付格式。",
            "事实、假设与风险": "记录已确认事实、假设和风险。",
            "当前门与下一步": "记录当前门和下一步动作。",
        }[heading],
        f"## {heading}\n",
    )
    path.write_text(content, encoding="utf-8")
    result = run(path)
    assert result.returncode == 1
    assert heading in result.stdout


def test_comment_only_required_sections_are_rejected(tmp_path: Path):
    path = write_brief(tmp_path)
    content = path.read_text(encoding="utf-8")
    for heading, body in (
        ("题面与交付约束", "记录题面约束和最终交付格式。"),
        ("事实、假设与风险", "记录已确认事实、假设和风险。"),
        ("当前门与下一步", "记录当前门和下一步动作。"),
    ):
        content = content.replace(f"## {heading}\n{body}", f"## {heading}\n<!-- comment-only -->")
    path.write_text(content, encoding="utf-8")
    result = run(path)
    assert result.returncode == 1
    assert result.stdout.count("去除 HTML 注释后不能为空") == 3


@pytest.mark.parametrize("count", ["0", "-1"])
def test_expected_questions_must_be_positive(tmp_path: Path, count: str):
    result = run(write_brief(tmp_path), "--expected-questions", count)
    assert result.returncode == 2
    assert "正整数" in result.stderr


def test_json_is_machine_readable(tmp_path: Path):
    path = write_brief(tmp_path)
    result = run(path, "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["errors"] == []
    assert "项目简报通过" not in result.stdout

    bad = tmp_path / "bad.md"
    bad.write_text(schema4_brief(deliverable="TODO"), encoding="utf-8")
    result = run(bad, "--json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False and payload["errors"]
    assert "[错误]" not in result.stdout


def test_require_schema_accepts_only_four(tmp_path: Path):
    path = write_brief(tmp_path)
    assert run(path, "--require-schema", "4").returncode == 0
    result = run(path, "--require-schema", "3")
    assert result.returncode != 0
    assert "4" in result.stderr


def test_repository_template_is_rejected_until_filled():
    result = run(TEMPLATE)
    assert result.returncode == 1
    assert "占位标记" in result.stdout
    template = TEMPLATE.read_text(encoding="utf-8")
    assert "brief_schema_version: 4" in template
    assert "content_budget" not in template
    assert "paper_section" not in template
    assert "logic_checks" not in template
    assert "  evidence:\n  finding:\nanswer:\n" in template
    assert "evidence: <填写" not in template
    assert "finding: <填写" not in template
    assert "answer: <填写" not in template
    assert "G2/G3 再填写" in template
