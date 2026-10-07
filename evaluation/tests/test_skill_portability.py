from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "cumcm-modeling"
QUICK_VALIDATE = Path("/home/wuman/.codex/skills/.system/skill-creator/scripts/quick_validate.py")


def test_standalone_runtime_has_no_entity_corpus_dependency():
    with tempfile.TemporaryDirectory() as directory:
        sandbox = Path(directory)
        standalone = sandbox / "standalone-skill"
        shutil.copytree(RUNTIME, standalone)

        skill_text = (standalone / "SKILL.md").read_text(encoding="utf-8")
        direct_resources = [
            "references/workflow/problem-analysis.md",
            "references/workflow/model-selection.md",
            "references/models/derivation-patterns.md",
            "references/workflow/validation-and-sensitivity.md",
            "references/workflow/reproducibility.md",
            "references/workflow/detailed-paper-outline.md",
            "references/workflow/literature-verification.md",
        ]
        for relative in direct_resources:
            assert relative in skill_text
            assert (standalone / relative).is_file(), relative

        assert not (standalone / "references/evidence").exists()
        assert not (standalone / "scripts/search_corpus.py").exists()
        assert not (standalone / "scripts/corpus").exists()

        if QUICK_VALIDATE.is_file():
            validation = subprocess.run(
                [sys.executable, str(QUICK_VALIDATE), str(standalone)],
                text=True, capture_output=True, check=False,
            )
            assert validation.returncode == 0, validation.stdout + validation.stderr

        checker = subprocess.run(
            [sys.executable, str(standalone / "scripts/check_project_brief.py"), "--help"],
            text=True, capture_output=True, check=False,
        )
        assert checker.returncode == 0, checker.stdout + checker.stderr
