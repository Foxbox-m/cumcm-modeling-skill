from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "cumcm-modeling"
PATTERNS = RUNTIME / "references/models/derivation-patterns.md"
MODEL_SELECTION = RUNTIME / "references/workflow/model-selection.md"
SKILL = RUNTIME / "SKILL.md"
PRIMITIVES = RUNTIME / "references/models/mathematical-derivation-primitives.md"

PATTERN_TITLES = (
    "Signed Feasibility Boundary from a Continuous Configuration",
    "Guarded Event from State Evolution",
    "Feasible Coordinates from Coupled Hard Constraints",
    "Inverse Formulation from a Generative Observation Map",
    "Decision Sensitivity from Upstream Uncertainty",
    "Reduced Representation from Scale Separation",
)


def _pattern_sections(text: str) -> list[str]:
    matches = list(re.finditer(r"^## Pattern \d+ — .+$", text, flags=re.MULTILINE))
    return [text[start.start() : (matches[i + 1].start() if i + 1 < len(matches) else len(text))]
            for i, start in enumerate(matches)]


def test_derivation_patterns_file_has_six_constructive_cards():
    text = PATTERNS.read_text(encoding="utf-8")
    assert "## Modeling Core" in text
    assert "Narrative Bridges" not in text
    assert "Figure trigger" not in text
    for phrase in (
        "具体的“现实结构 → 数学对象”缺口",
        "提出或重表示候选",
        "保留题面/数据来源的事实、硬约束、数据语义和因果顺序",
        "决定性的兼容性或证伪检查",
        "不要求 snapshot、schema、artifact",
    ):
        assert phrase in text, phrase

    sections = _pattern_sections(text)
    assert len(sections) == len(PATTERN_TITLES)
    for title, section in zip(PATTERN_TITLES, sections):
        assert title in section
        positions = [section.index(f"### {field}") for field in (
            "Use only if", "Reject / Abstain if", "Construct", "Output", "Validate"
        )]
        assert positions == sorted(positions), title
    assert "严格按" not in text
    assert "先证明适用" not in text


def test_derivation_assistance_is_gap_based_and_fact_preserving():
    model_selection = MODEL_SELECTION.read_text(encoding="utf-8")
    skill = SKILL.read_text(encoding="utf-8")
    patterns = PATTERNS.read_text(encoding="utf-8")
    primitives = PRIMITIVES.read_text(encoding="utf-8")
    combined = "\n".join((model_selection, skill, patterns, primitives))

    assert "推导援助" in model_selection
    assert "现实结构 → 数学对象" in model_selection
    assert "具体断点" in model_selection
    assert "可以帮助构造或重新表示" in model_selection
    assert "不能覆盖题面事实、硬约束、数据语义" in model_selection
    assert "不要求快照" in model_selection
    assert "artifact" in model_selection
    assert "决定性拒绝条件" in model_selection
    assert "回代" in model_selection or "一致性" in model_selection
    assert "退回原候选" in model_selection or "不采用" in model_selection
    assert "数学推理主线" in primitives
    assert "定义对象和边界" in primitives
    assert "推导关系" in primitives
    assert "特殊情形、反例、极限" in primitives
    assert "推广与边界" in primitives
    assert "严格命题" in primitives
    assert "经验结果外推" in primitives
    assert "测试域" in primitives
    assert "## Modeling Core" in patterns
    assert "Narrative Bridges" not in patterns
    assert "Figure trigger" not in patterns

    # The entrypoint routes the reference but does not reintroduce a topic-based
    # activation rule or the retired snapshot/audit protocol.
    assert "mathematical-derivation-primitives.md" in skill
    assert "blind structural snapshot" not in combined.lower()
    assert "audit-first" not in combined.lower()
