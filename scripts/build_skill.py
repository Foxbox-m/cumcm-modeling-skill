#!/usr/bin/env python3
"""Validate the maintained CUMCM skill through one stable build entrypoint.

The ``cumcm-modeling/`` tree is the canonical runtime source.  Historical
``generate_*.py`` files remain available for reference, but are deliberately
not invoked here because their embedded text can overwrite maintained files.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = PROJECT_ROOT / "cumcm-modeling"
RESOURCE_VALIDATOR = PROJECT_ROOT / "scripts" / "build" / "generate_skill_scripts_and_assets.py"
RUNTIME_PYTHON_FILES = tuple(sorted((RUNTIME_ROOT / "scripts").glob("*.py")))
REQUIRED_CANONICAL = (
    RUNTIME_ROOT / "SKILL.md",
    RUNTIME_ROOT / "references",
    RUNTIME_ROOT / "scripts",
    RUNTIME_ROOT / "assets",
)
REQUIRED_EVALUATION = (
    PROJECT_ROOT / "evaluation" / "tests" / "test_audit_dataset.py",
    PROJECT_ROOT / "evaluation" / "tests" / "test_reproducibility.py",
    PROJECT_ROOT / "evaluation" / "tests" / "test_run_reproducible.py",
    PROJECT_ROOT / "evaluation" / "tests" / "test_skill_portability.py",
    PROJECT_ROOT / "evaluation" / "tests" / "test_search_literature.py",
    PROJECT_ROOT / "evaluation" / "tests" / "test_check_project_brief.py",
    PROJECT_ROOT / "evaluation" / "tests" / "test_project_brief_contract_consistency.py",
    PROJECT_ROOT / "evaluation" / "tests" / "test_check_stage.py",
    PROJECT_ROOT / "evaluation" / "tests" / "test_derivation_patterns_contract.py",
    PROJECT_ROOT / "evaluation" / "tests" / "test_workflow_contracts.py",
    PROJECT_ROOT / "evaluation" / "fixtures" / "data" / "README.md",
)


def validate_required_paths() -> list[str]:
    missing: list[str] = []
    for path in (*REQUIRED_CANONICAL, *REQUIRED_EVALUATION):
        if not path.exists():
            missing.append(str(path.relative_to(PROJECT_ROOT)))
    return missing


def validate_python_syntax() -> list[str]:
    errors: list[str] = []
    for path in RUNTIME_PYTHON_FILES:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append(f"{path.relative_to(PROJECT_ROOT)}：{exc}")
    return errors


def run_resource_validator() -> int:
    result = subprocess.run([sys.executable, str(RESOURCE_VALIDATOR)], cwd=PROJECT_ROOT, check=False)
    return result.returncode


def run_evaluation() -> int:
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "evaluation/tests"],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        print("[失败] evaluation/tests", file=sys.stderr)
    return result.returncode


def main() -> int:
    missing = validate_required_paths()
    if missing:
        for relative in missing:
            print(f"缺少：{relative}", file=sys.stderr)
        return 1

    syntax_errors = validate_python_syntax()
    if syntax_errors:
        for error in syntax_errors:
            print(f"语法错误：{error}", file=sys.stderr)
        return 1

    if run_resource_validator() != 0:
        return 1
    if run_evaluation() != 0:
        return 1

    print("Skill 构建检查完成：canonical 资源、脚本语法与 evaluation 测试均通过")
    print("说明：历史 generate_*.py 未执行，不会覆盖 canonical runtime 文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
