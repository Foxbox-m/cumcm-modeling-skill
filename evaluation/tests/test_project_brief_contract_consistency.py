from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "cumcm-modeling/scripts/check_project_brief.py"
TEMPLATE_PATH = ROOT / "cumcm-modeling/assets/project-brief/modeling-brief-template.md"


def _checker_module():
    spec = importlib.util.spec_from_file_location("project_brief_checker", CHECKER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _field_sets(checker, text: str) -> tuple[set[str], set[str], set[str]]:
    profile_text = text.split("## 任务证据", 1)[0]
    top = set(checker._top_level_fields(profile_text))
    task_id, task_body = checker._task_blocks(text)[0]
    assert task_id == "Q1"
    task = checker._parse_task(task_body)
    validation = task["validation"]
    assert isinstance(validation, dict)
    return top, set(task), set(validation)


def test_schema4_checker_version_and_template_share_only_declared_field_contract():
    checker = _checker_module()
    expected_profile = set(checker.PROFILE_FIELD_NAMES)
    expected_task = set(checker.TASK_FIELD_NAMES)
    expected_validation = set(checker.VALIDATION_FIELD_NAMES)

    template_sets = _field_sets(checker, TEMPLATE_PATH.read_text(encoding="utf-8"))

    assert checker.SCHEMA_VERSION == "4"
    assert template_sets == (expected_profile, expected_task, expected_validation)
