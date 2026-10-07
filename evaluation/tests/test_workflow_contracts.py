from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "cumcm-modeling"
SKILL = RUNTIME / "SKILL.md"
HUMAN_REVIEW = RUNTIME / "references/workflow/human-modeling-review.md"
G2_HUMAN_REVIEW = RUNTIME / "references/workflow/g2-human-review.md"
DETAILED_OUTLINE = RUNTIME / "references/workflow/detailed-paper-outline.md"
REPRO = RUNTIME / "references/workflow/reproducibility.md"
MODEL_SELECTION = RUNTIME / "references/workflow/model-selection.md"
PROBLEM_ANALYSIS = RUNTIME / "references/workflow/problem-analysis.md"
OPTIMIZATION_MODELS = RUNTIME / "references/models/optimization-models.md"
VALIDATION = RUNTIME / "references/workflow/validation-and-sensitivity.md"
DERIVATION_PATTERNS = RUNTIME / "references/models/derivation-patterns.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_new_workflow_references_are_routed_and_links_resolve():
    skill = read(SKILL)
    for path in (HUMAN_REVIEW, G2_HUMAN_REVIEW, DETAILED_OUTLINE):
        assert path.is_file()
        assert path.relative_to(RUNTIME).as_posix() in skill
    for document in (
        RUNTIME / "references/workflow/problem-analysis.md",
        RUNTIME / "references/workflow/model-selection.md",
        REPRO,
    ):
        assert document.is_file()


def test_human_review_contract_is_an_adaptive_g1_subgate():
    text = read(HUMAN_REVIEW)
    for phrase in (
        "PENDING",
        "APPROVED",
        "REVISE",
        "review_schema_version: 1",
        "gate: G1-H",
        "preliminary-modeling-report.md",
        "题目原始任务动词",
        "模型与算法",
        "核心项（每次 G1-H 都应可定位）",
        "条件触发项",
        "可检验 baseline",
        "Gap Check",
        "题意 Gap",
        "结构 Gap",
        "数据 Gap",
        "结果 Gap",
        "真实竞争方案",
        "参数/状态可辨识性",
        "决定性验证",
        "回退",
        "不打分",
        "不设固定候选数量",
        "题号字母",
        "diagnostic reference",
        "load-bearing risk probe",
    ):
        assert phrase in text, phrase
    assert "不新增顶层 Gate" in text
    assert "逐问模板" in text
    assert "### Q1" not in text
    assert "#### 3.1" not in text
    assert "未触发时直接省略" in text
    assert "无需逐项声明未触发项" in text
    assert "其余条件项不适用" not in text
    assert "题意修正" in text and "数据/信息处置" in text
    assert "求解/验证补强" in text and "保持 baseline" in text
    assert "真实的跨问传递" not in text
    assert "跨问接口/误差传播" in text
    assert "只写实际触发的条件项" in text
    assert "先判定属于题意修正" in text
    assert "只有最后一种触发时" in text
    assert "因此加入……机制" not in text


def test_baseline_gap_candidate_order_and_open_exploration():
    skill = read(SKILL)
    selection = read(MODEL_SELECTION)
    problem = read(PROBLEM_ANALYSIS)

    ordered_phrases = (
        (skill, "可检验 baseline", "Gap Check", "扩展候选"),
        (selection, "可检验的 baseline", "## 2. Gap Check", "开放候选空间"),
        (problem, "可检验 baseline", "Gap Check", "开放候选"),
    )
    for text, baseline_phrase, gap_phrase, candidate_phrase in ordered_phrases:
        baseline = text.find(baseline_phrase)
        gap = text.find(gap_phrase)
        candidate = text.find(candidate_phrase)
        assert baseline >= 0 and gap >= 0 and candidate >= 0
        assert baseline < gap < candidate

    assert "先发散：从问题结构生成候选" not in selection
    assert "候选形成后再补 baseline" not in selection
    for phrase in ("开放候选", "库外方法", "组合表示"):
        assert phrase in selection
    for phrase in (
        "Baseline comparability rule",
        "diagnostic reference",
        "完成真实任务",
        "fallback",
    ):
        assert phrase in selection


def test_gap_disposition_and_optimization_screening_are_non_mechanical():
    skill = read(SKILL)
    problem = read(PROBLEM_ANALYSIS)
    selection = read(MODEL_SELECTION)
    human = read(HUMAN_REVIEW)

    for text in (skill, problem, selection):
        assert "数据/信息不足" in text or "数据不足" in text
        assert "验证不足" in text
        assert "求解不足" in text
    assert "Gap 不自动等于模型扩展" in selection
    assert "题意映射错误" in selection and "题意映射" in problem
    assert "只有模型/表示缺口" in selection

    assert "所有显式优化任务先做轻量筛查" in selection
    assert "只有发现表示、搜索、交互或评价风险时" in selection
    optimization_section = selection.split("### Optimization Potential Check", 1)[1]
    screening = optimization_section.split("### 人工可审查输出", 1)[0]
    assert "原始决策变量" in screening
    assert "真正开放变量" in screening
    assert "评价误差" in screening
    assert "fast/full" not in screening

    assert "昂贵双保真" in human
    assert "seed/baseline" in human and "improvement gap" in human
    assert "未触发的条件项直接省略" in human


def test_outline_synthesis_contract_and_absence_of_paper_drafting():
    skill = read(SKILL)
    assert "references/workflow/detailed-paper-outline.md" in skill
    for forbidden in (
        "mandatory-" + "paper-template",
        "cumcm-" + "paper-playbook",
        "language-and-" + "argumentation",
        "award-paper-" + "writing-style",
        "award-paper-" + "layout",
        "word-" + "workflow",
        "award-paper-" + "visualization",
        "generate_" + "paper_scaffold",
        "generate_" + "word_template",
        "Paper " + "Authoring Boundary",
    ):
        assert forbidden not in skill, f"SKILL.md should not contain {forbidden}"

    stage_code = read(RUNTIME / "scripts/check_stage.py")
    assert "paper-outline.md" in stage_code
    assert ("final" + ".pdf") not in stage_code
    assert ("check_" + "paper.py") not in stage_code
    for section in (
        "全局问题链",
        "分问建模交接",
        "跨问关系",
        "结果与证据索引",
        "逐问信息契约",
        "Q{question}.{section}",
    ):
        assert section in stage_code, f"check_stage.py should enforce {section}"
    for removed_section in ("摘要内容蓝图", "独立写作章节映射", "图表与机制图 Storyboard"):
        assert removed_section not in stage_code

    outline_text = read(DETAILED_OUTLINE)
    for section in (
        "全局问题链",
        "分问建模交接",
        "优化思想",
        "实际遇到的问题与修正过程",
        "跨问关系",
        "结果与证据索引",
        "可视化意图",
    ):
        assert section in outline_text, f"detailed-paper-outline.md should contain {section}"
    for removed_heading in ("## B. 摘要内容蓝图", "## G. 独立写作章节映射", "## Part B — Narrative Bridges"):
        assert removed_heading not in outline_text

    for removed in (
        RUNTIME / "references/presentation",
        RUNTIME / "references/core/competition-rules.md",
        RUNTIME / "references/workflow/submission-and-ai-compliance.md",
        RUNTIME / "assets/paper-template",
        RUNTIME / "assets/figure-style",
        RUNTIME / "assets/submission-checklist",
        RUNTIME / "assets/ai-usage-template",
        RUNTIME / "scripts/render_figures.py",
        RUNTIME / "scripts/check_figures.py",
        RUNTIME / f"scripts/build/generate_{'paper'}_scaffold.py",
        RUNTIME / f"scripts/build/generate_{'word'}_template.py",
        RUNTIME / f"scripts/check_{'paper'}.py",
        RUNTIME / f"scripts/check_{'latex'}_tables.py",
        RUNTIME / f"scripts/render_{'paper'}_qa.py",
        RUNTIME / "references/workflow/pdf-qa-delegation.md",
    ):
        assert not removed.exists(), f"Path should be removed: {removed}"

def test_g2_human_review_is_explicit_data_result_subgate():
    text = read(G2_HUMAN_REVIEW)
    for phrase in (
        "G2-H", "不是 G4", "review_schema_version: 1", "gate: G2-H",
        "decision: PENDING", "PENDING", "APPROVED", "REVISE", "ROLLBACK",
        "数据与预处理", "最终模型与算法", "核心结果", "验证与稳健性",
        "G1→G2 偏差", "重大风险", "核心事实", "不能代替明确决定",
    ):
        assert phrase in text, phrase
    assert "不打分" in text
    assert "不复制运行日志" in text


def test_optimization_contracts_are_routed_and_cross_file_consistent():
    skill = read(SKILL)
    selection = read(MODEL_SELECTION)
    optimization = read(OPTIMIZATION_MODELS)
    derivation = read(DERIVATION_PATTERNS)
    human = read(HUMAN_REVIEW)

    assert "references/models/optimization-models.md" in skill
    for phrase in (
        "优化型任务额外原则",
        "R(theta)",
        "fast/search evaluation",
        "full/formal validation",
        "搜索空间",
        "原始目标与全部硬约束",
        "决策分辨率",
        "不为形式完整机械叠加验证",
    ):
        assert phrase in skill, phrase

    for phrase in (
        "Optimization Potential Check",
        "原始决策变量",
        "实际仍开放的变量",
        "人为结构约束",
        "题面硬约束",
        "表示偏差",
        "目标对动作的响应性",
        "相互作用",
        "评价成本",
        "松弛",
        "后问新增自由度",
        "更可搜索的替代表示",
        "接近可靠界",
        "不共享同一表示偏差",
        "耦合决策自由度",
    ):
        assert phrase in selection, phrase

    for phrase in (
        "Search-space before solver",
        "Least-sufficient solver principle",
        "Fast-search / Full-validation",
        "正式结论与 headline 数字必须由 full validation 支撑",
        "fast/代理诊断可作为明确标注的搜索证据",
        "Interaction-aware search",
        "Relaxed/nested subproblem feasible-set inheritance",
        "Improvement-gap decision",
        "seed/baseline",
        "必须作为 seed/baseline 进入候选集",
        "目标或正式约束口径变化",
        "incumbent",
        "add/delete/swap/block/region/local re-solve",
        "决策分辨率",
        "interaction probe",
        "正式解独立回算",
        "full/formal evaluator",
    ):
        assert phrase in optimization, phrase

    validation = read(VALIDATION)
    for phrase in (
        "上游预测进入下游决策时的闭环检查",
        "决策切换",
        "不把所有预测题强制改造成鲁棒优化",
    ):
        assert phrase in validation, phrase

    assert "Pattern 3 — Feasible Coordinates from Coupled Hard Constraints" in derivation
    assert "Search-family parameterization" in derivation
    assert "x=Psi(theta)" in derivation
    assert "而非等价变换" in derivation
    assert "不能据此声称原问题全局最优" in derivation

    for phrase in (
        "显式优化表示/搜索风险",
        "原始决策变量",
        "真正开放变量",
        "人为固定及理由",
        "搜索族/表示偏差",
        "fast/full",
        "seed/baseline",
        "improvement gap",
        "无改善后的扩展动作",
        "关键自由度过早冻结或评价/搜索失配",
        "低分辨率/代理粗搜",
        "不得作为正式最优结果",
    ):
        assert phrase in human, phrase
    assert "不新增顶层 Gate" in human
    assert "\n## Gate" not in human
    assert "\n## Schema" not in human
    representation = human.split("显式优化表示/搜索风险", 1)[1].split("昂贵双保真实际触发", 1)[0]
    assert "不把 fast/full 强加给普通显式优化" in representation
    dual = human.split("昂贵双保真实际触发", 1)[1]
    for phrase in ("fast/full", "seed/baseline", "improvement gap", "无改善后的扩展动作"):
        assert phrase in dual

    for text in (skill, selection, optimization, derivation, human):
        assert "heliostat" not in text.lower()
        assert "定日镜" not in text
        assert "镜场" not in text


def test_structural_depth_and_replace_over_stack_contract():
    skill = read(SKILL)
    selection = read(MODEL_SELECTION)
    problem = read(PROBLEM_ANALYSIS)
    human = read(HUMAN_REVIEW)

    for phrase in (
        "结构充分性",
        "replace-over-stack",
        "primary modeling mechanism",
    ):
        assert phrase in skill or phrase in selection

    for phrase in (
        "Baseline Structural Sufficiency Check",
        "Component Role Collapse",
        "Cross-question Shared Core + Delta",
        "Innovation Opportunity Check",
    ):
        assert phrase in selection

    for phrase in (
        "observed_pre_decision",
        "observed_post_decision",
        "区间删失",
        "重复测量",
    ):
        assert phrase in problem

    assert "同一中间目标" in selection
    assert "不设置“最多/至少 N 个模型”" in human


def test_result_semantic_review_contract():
    skill = read(SKILL)
    selection = read(MODEL_SELECTION)
    g2 = read(G2_HUMAN_REVIEW)

    assert "合适层级" in selection
    assert "只有当该结构确实改变核心状态关系或估计机制" in skill or \
           "只有结构确实改变核心状态关系或估计机制" in selection

    for phrase in (
        "优化退化",
        "边界锁定",
        "训练折内拟合",
        "真实独立采样单位",
    ):
        assert phrase in g2


def test_runtime_has_no_entity_paper_corpus_coupling():
    forbidden_paths = (
        RUNTIME / "references/evidence",
        RUNTIME / "references/core/source-governance.md",
        RUNTIME / "scripts/search_corpus.py",
        RUNTIME / "scripts/corpus",
    )
    for path in forbidden_paths:
        assert not path.exists(), path

    forbidden_terms = (
        "CORPUS_ROOT", "search_corpus.py", "method-evidence.md", "corpus-index.md",
        "A1R", "A1Q", "语料元数据.json", "CUMCM官方获奖论文库",
    )
    for path in RUNTIME.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".py", ".yaml", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for term in forbidden_terms:
            assert term not in text, f"{term} remains in {path.relative_to(RUNTIME)}"
