#!/usr/bin/env python3
"""Validate the maintained CUMCM skill scripts and assets.

These files are now edited as canonical resources instead of being overwritten from
large embedded strings. This command preserves them and reports missing resources.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOT = PROJECT_ROOT / "cumcm-modeling"
REQUIRED = (
    "scripts/audit_dataset.py",
    "scripts/check_reproducibility.py",
    "scripts/search_literature.py",
    "scripts/check_project_brief.py",
    "scripts/check_stage.py",
    "scripts/run_reproducible.py",
    "assets/project-brief/modeling-brief-template.md",
    "references/workflow/detailed-paper-outline.md",
)

EVALUATION_REQUIRED = (
    "evaluation/tests/test_audit_dataset.py",
    "evaluation/tests/test_reproducibility.py",
    "evaluation/tests/test_run_reproducible.py",
    "evaluation/tests/test_search_literature.py",
    "evaluation/tests/test_check_project_brief.py",
    "evaluation/tests/test_project_brief_contract_consistency.py",
    "evaluation/tests/test_check_stage.py",
    "evaluation/tests/test_derivation_patterns_contract.py",
    "evaluation/tests/test_workflow_contracts.py",
    "evaluation/tests/test_skill_portability.py",
    "evaluation/fixtures/data/README.md",
)


def main() -> int:
    missing = [relative for relative in REQUIRED if not (ROOT / relative).is_file()]
    missing.extend(relative for relative in EVALUATION_REQUIRED if not (PROJECT_ROOT / relative).is_file())
    if missing:
        for relative in missing:
            print(f"缺少：{relative}")
        return 1
    for relative in REQUIRED:
        if relative.startswith("scripts/"):
            (ROOT / relative).chmod(0o755)
    print(f"Skill 脚本与资产齐全：{len(REQUIRED)} 项；evaluation 入口齐全：{len(EVALUATION_REQUIRED)} 项")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
