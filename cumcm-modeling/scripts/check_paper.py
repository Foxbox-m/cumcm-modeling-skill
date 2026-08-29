#!/usr/bin/env python3
"""Audit a CUMCM electronic paper against machine-checkable 2026 rules."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
import statistics
import re
import subprocess
import sys
from pathlib import Path


APPENDIX_HEADING_PATTERN = (
    r"^\s*(?:(?:\d+(?:\.\d+)*|[一二三四五六七八九十]+|[A-Z])"
    r"\s*[、.．:：-]?\s*)?(?:附\s*录|appendix)"
    r"(?:\s*[（(]?(?:[A-Z]|\d+|[一二三四五六七八九十]+)[)）]?)?"
    r"(?:\s*[-—:：]\s*[^\n]{1,80})?\s*$"
)

# General semantic patterns are retained for page accounting.  The stricter
# The explicit strict seven-chapter template audit below additionally checks
# the visible numbering convention used by the maintained CUMCM template.
STRUCTURE_HEADING_PATTERNS = {
    "问题重述": r"^\s*(?:(?:\d+|[一二三四五六七八九十]+)\s*[、.)．:：-]\s*)?(?:问题\s*(?:重述|提出|背景\s*[与及和]\s*重述|的\s*重述(?:\s*[与及和]\s*提出)?)|问题\s*重述\s*[与及和]\s*提出)(?:\s*[：:—-]?[^\n]{0,60})?$",
    "问题分析": r"^\s*(?:(?:\d+|[一二三四五六七八九十]+)\s*[、.)．:：-]\s*)?(?:问题\s*分析(?:\s*[与及和][^\n]{0,40})?|赛题\s*分析\s*[与及和]\s*技术路线)(?:\s*[：:—-]?[^\n]{0,60})?$",
    "模型假设": r"^\s*(?:(?:\d+|[一二三四五六七八九十]+)\s*[、.)．:：-]\s*)?(?:模型\s*假设|基本\s*假设)(?:\s*[：:—-]?[^\n]{0,60})?$",
    "符号说明": r"^\s*(?:(?:\d+|[一二三四五六七八九十]+)\s*[、.)．:：-]\s*)?(?:符号\s*说明|变量\s*说明\s*[与及和]\s*符号\s*约定)(?:\s*[：:—-]?[^\n]{0,60})?$",
    "模型准备": r"^\s*(?:(?:\d+|[一二三四五六七八九十]+)\s*[、.)．:：-]\s*)?模型\s*准备(?:\s*[：:—-]?[^\n]{0,60})?$",
    "模型检验": r"^\s*(?:(?:\d+|[一二三四五六七八九十]+)\s*[、.)．:：-]\s*)?模型\s*(?:检验|验证)(?:与|及|和)?[^\n]{0,60}$",
    "模型评价": r"^\s*(?:(?:\d+|[一二三四五六七八九十]+)\s*[、.)．:：-]\s*)?模型\s*(?:的\s*)?(?:评价|优缺点|局限|边界)(?:与|及|和)?[^\n]{0,60}$|^\s*(?:(?:\d+|[一二三四五六七八九十]+)\s*[、.)．:：-]\s*)?(?:模型)?(?:合理性分析|适用边界|局限性)(?:与|及|和)?[^\n]{0,60}$",
    "参考文献": r"^\s*(?:(?:\d+|[一二三四五六七八九十]+)\s*[、.)．:：-]\s*)?(?:参考文献|references)\s*$",
}
EVALUATION_SEMANTIC_PATTERN = (
    r"模型\s*(?:的\s*)?(?:评价|优缺点|局限|检验|验证|推广)"
    r"|合理性分析|适用(?:边界|范围)|局限性|误差(?:分析|评估|范围)?"
    r"|敏感性(?:分析)?|稳健性|不确定性"
)
QUESTION_HEADING_PATTERN = (
    r"^\s*(?:(?:\d+(?:\.\d+)*|[一二三四五六七八九十]+)\s*[、.)．:：-]\s*)?"
    r"问题\s*(?P<number>[一二三四五六七八九十]+|\d+)"
    r"(?:\s*(?:的)?(?:求解|建模|分析|模型|算法|计算|结果|解答))?"
    r"(?:\s*[：:—-]?[^\n]{0,80})?\s*$"
)

CUMCM_AWARD_TOP_LEVEL = (
    ("问题重述", r"^\s*一\s*[、.．]\s*问题\s*重述\s*$"),
    ("问题分析", r"^\s*二\s*[、.．]\s*问题\s*分析\s*$"),
    ("模型假设", r"^\s*三\s*[、.．]\s*模型\s*假设\s*$"),
    ("符号说明", r"^\s*四\s*[、.．]\s*符号\s*说明\s*$"),
    ("模型的建立与求解", r"^\s*五\s*[、.．]\s*模型\s*的?\s*建立\s*与\s*求解\s*$"),
    ("模型的分析与检验", r"^\s*六\s*[、.．]\s*模型\s*的?\s*分析\s*与\s*检验\s*$"),
    ("模型的评价", r"^\s*七\s*[、.．]\s*模型\s*的?\s*评价\s*$"),
)

FUNCTIONAL_COVERAGE_PATTERNS = (
    ("题目理解与任务映射", r"问题\s*(?:重述|背景|分析|要求)|任务|第\s*[一二三四五六七八九十\d]+\s*问"),
    ("模型推导与求解", r"模型|方程|目标函数|约束|推导|求解|计算|算法"),
    ("正式结果与现象/机理解释", r"结果|结论|方案|答案|现象|机理|机制|几何|解释|显示|表明"),
    ("决定性验证", r"验证|检验|误差|敏感性|稳健性|边界|对照|守恒|收敛"),
    ("局限与评价", r"局限|缺点|评价|适用(?:范围|边界)|改进|不足"),
)

INTERNAL_PAPER_TERMS = (
    ("Schema 4", r"\bSchema\s*4\b"),
    ("G1/G2/G3", r"(?<![A-Za-z0-9])G[123](?![A-Za-z0-9])"),
    ("modeling-brief", r"modeling[-_ ]brief(?:\.md)?"),
    ("reproducibility.json", r"reproducibility\.json"),
    ("claim binding", r"claim\s*binding|主张绑定"),
    ("JSON Pointer", r"JSON\s*Pointer"),
    ("run role", r"run\s*role"),
    ("selected_run", r"selected[_ -]?run"),
    ("candidate run", r"candidate\s*run"),
    ("事实源", r"事实源"),
    ("运行清单", r"运行清单"),
    ("可复现性与交付一致性审计", r"可复现性与交付一致性审计"),
    ("checker", r"(?<![A-Za-z])checker(?![A-Za-z])"),
    ("paper artifact", r"paper\s*artifact"),
    ("视觉审计", r"视觉审计"),
    ("构建流程", r"构建流程"),
    ("结果宏", r"结果宏"),
    ("manifest", r"(?<![A-Za-z])manifest(?![A-Za-z])"),
)

# Conservative, non-blocking paper-voice locators.  These phrases are more
# specific than single words such as “结构/模块/接口/基线/复用”, which can be
# legitimate mathematical or physical language and must never be banned.
PAPER_VOICE_ARCHITECTURE_PATTERNS = (
    ("混合路由", r"混合路由"),
    ("共同接口", r"共同接口"),
    ("计算接口", r"计算接口"),
    ("结论接口", r"结论接口"),
    ("正式入口", r"正式入口"),
    ("程序映射", r"程序映射"),
    ("结构化判定逻辑", r"结构化判定逻辑"),
    ("真值源", r"真值源"),
    ("门状态", r"门状态"),
    ("机器结构审计", r"机器结构审计"),
    ("读回审计", r"读回审计"),
    ("交付动作", r"交付动作"),
)

STRONG_CODE_LINE_PATTERNS = (
    r"^\s*(?:from\s+[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s+import\b|import\s+[A-Za-z_]\w*)",
    r"^\s*(?:async\s+)?def\s+[A-Za-z_]\w*\s*[(].*[:]?\s*$",
    r"^\s*class\s+[A-Za-z_]\w*\s*(?:[(].*[)]\s*)?:\s*$",
    r"^\s*if\s+__name__\s*==\s*[\"']__main__[\"']\s*:",
    r"^\s*print\s*[(]",
    r"^\s*(?:plt\.|pd\.|np\.)[A-Za-z_]\w*\s*[(]",
    r"^\s*#include\s*[<\"]",
    r"^\s*public\s+static\s+void\s+main\s*[(]",
    r"^\s*function\s+[A-Za-z_]\w*\s*[(]",
    r"^\s*[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*<-\s*.+$",
)

# These are intentionally conservative lexical signals.  They only locate
# content that deserves human review; they do not attempt semantic scoring.
CHAPTER_RESPONSIBILITY_PATTERNS = {
    "符号说明": re.compile(
        r"(?m)^\s*(?:公式|推导|坐标|索引|方程|递推|定义)(?:定义)?\s*(?:为|如下|：|:|是)"
        r"|^\s*[A-Za-zα-ωΑ-Ω][^\n]{0,40}=[^\n。]{1,80}$",
        re.IGNORECASE | re.MULTILINE,
    ),
    "模型假设": re.compile(
        r"Excel|Python|MATLAB|双精度|随机种子|迭代次数|容差|输出格式|软件版本",
        re.IGNORECASE,
    ),
}

APPENDIX_CORE_EVIDENCE_PATTERN = re.compile(
    r"(?m)^\s*(?:from\s+\w[\w.]*\s+import\b|import\s+\w|"
    r"(?:async\s+)?def\s+\w+\s*\(|function\s+\w+\s*\(|"
    r"class\s+\w+\s*(?:\(|:)|(?:if|for|while|switch|case)\b|"
    r"\w+\s*\([^\n]{1,100}\)\s*(?:\{|:|=))",
    re.IGNORECASE,
)

A4_WIDTH_PT = 595.275590551
A4_HEIGHT_PT = 841.88976378
A4_SIZE_TOLERANCE_PT = 5.0
PAGE_FLOW_COVERAGE_THRESHOLD = 0.60
PAGE_FLOW_INTERNAL_GAP_THRESHOLD = 0.25
PAGE_FLOW_CONTENT_BOTTOM = 0.94
PAGE_FLOW_GAP_TOLERANCE_FRACTION = 0.025
PAGE_FLOW_VISUAL_TEXT_LIMIT = 240
PAGE_FLOW_DRAWING_LIMIT = 20


def _structure_matches(pages: list[str], pattern: str) -> list[tuple[int, str]]:
    """Return (page index, matched heading) pairs for a line-anchored pattern."""
    compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    matches: list[tuple[int, str]] = []
    for page_index, text in enumerate(pages):
        matches.extend((page_index, match.group(0).strip()) for match in compiled.finditer(text))
    return matches


def find_internal_paper_terms(text: str) -> list[str]:
    """Return internal workflow vocabulary that must not leak into CUMCM prose."""
    return [
        label for label, pattern in INTERNAL_PAPER_TERMS
        if re.search(pattern, text, re.IGNORECASE)
    ]


def audit_competition_paper_voice(
    text: str, *, expected_questions: int | None = None
) -> dict[str, list[str]]:
    """Locate likely engineering meta-narrative without judging mathematics.

    The caller supplies front-matter/core prose only; appendix code is excluded.
    Findings are deliberately non-blocking and use compound phrases to avoid a
    global ban on words that may describe real mathematical or physical objects.
    """
    quality_warnings: list[str] = []
    manual_checks: list[str] = []
    hits = [
        label for label, pattern in PAPER_VOICE_ARCHITECTURE_PATTERNS
        if re.search(pattern, text, re.IGNORECASE)
    ]
    shared_core_count = len(re.findall(r"共享核心", text, re.IGNORECASE))
    if shared_core_count >= 2:
        hits.append(f"共享核心×{shared_core_count}")
    if hits:
        quality_warnings.append(
            "Competition Paper Voice 写作定位提示：核心论证出现可能的软件架构式复合短语："
            + "、".join(hits)
            + "；请按语境改写为实际数学对象、方程、约束或现象。"
            "这不是官方规则、数学质量判断或阻断项"
        )

    if expected_questions is not None:
        direct_answer_count = len(re.findall(r"直接\s*回答\s*[：:]", text))
        if direct_answer_count >= expected_questions:
            manual_checks.append(
                f"Competition Paper Voice 非机械同构提示：识别到 {direct_answer_count} 次“直接回答：”，"
                f"已覆盖显式问题数 {expected_questions}；请保持答案可定位，同时按各问证据自然变化收束措辞。"
                "这不是官方规则、数学质量判断或阻断项"
            )
    return {"quality_warn": quality_warnings, "manual_check": manual_checks}


def _question_number(raw: str) -> int | None:
    """Convert the small set of visible Chinese/Arabic question labels."""
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    return {character: index for index, character in enumerate("一二三四五六七八九十", start=1)}.get(raw)


def _question_labels(text: str) -> set[int]:
    """Find visible question labels, including template list prefixes."""
    label_pattern = re.compile(
        r"(?:^|[\s\[：:（(、；;])问题\s*(?P<number>[一二三四五六七八九十]|\d+)"
        r"(?=\s*(?:[：:、.．)）-]|\s|$))"
        r"|(?:^|[\s\[：:（(、；;])第\s*(?P<ordinal>[一二三四五六七八九十]|\d+)\s*问"
        r"(?=\s*(?:[：:、.．)）-]|\s|$))"
        r"|(?:^|[\s\[：:（(、；;])[（(]\s*(?P<enumerated>\d+)\s*[）)]\s*问题"
        r"(?=\s*(?:[：:、.．-]|\s|$))",
        re.IGNORECASE,
    )
    labels: set[int] = set()
    for line in text.splitlines():
        # A common numbered-list prefix is either ``1. 问题一`` or
        # ``（1）问题一``.  Keep the prefix out of the semantic label itself;
        # the question number after ``问题`` is the value used for coverage.
        line = re.sub(r"^\s*(?:[-*•]\s*)?(?:\d+\s*[.．、)]|[（(]\s*\d+\s*[）)])\s*", "", line)
        for match in label_pattern.finditer(line):
            raw = match.group("number") or match.group("ordinal") or match.group("enumerated")
            number = _question_number(raw)
            if number is not None:
                labels.add(number)
    return labels


def _problem_requirements_block(pages: list[str]) -> str | None:
    """Return a visible 1.2/problem/task-requirements block."""
    joined = "\n\f".join(pages)
    match = re.search(
        r"(?m)^\s*(?:1\.2\s+)?(?:问题|任务)\s*要求\s*$", joined
    )
    if match is None:
        return None
    remainder = joined[match.end():]
    next_chapter = re.search(r"(?m)^\s*(?:二|三|四|五|六|七)\s*[、.．]\s*", remainder)
    return remainder[: next_chapter.start()] if next_chapter else remainder


def audit_question_requirement_labels(
    pages: list[str], expected_questions: int
) -> list[str]:
    """Warn only when an identifiable 1.2 region has too few question labels."""
    block = _problem_requirements_block(pages)
    if block is None:
        return []
    labels = _question_labels(block)
    expected = set(range(1, expected_questions + 1))
    missing = sorted(expected - labels)
    if missing:
        return [
            f"1.2 问题要求区域识别到问题标签集合 {sorted(labels)}，"
            f"缺失题号：{missing}（题面要求覆盖 1—{expected_questions}）；请人工核对逐问重述"
        ]
    return []


PROGRAM_ENTRY_PATTERN = re.compile(
    r"(?:[A-Za-z0-9_./\\-]+\.(?:py|m|r|java|cpp|c|h|jl|ipynb|sh|sql|tex|R)\b)"
    r"|(?:程序|代码|源码|源程序|脚本)\s*.{0,24}(?:入口|文件|路径)"
    r"|(?:入口|文件|路径)\s*.{0,24}(?:程序|代码|源码|脚本)",
    re.IGNORECASE,
)


def audit_appendix_question_mappings(
    pages: list[str], expected_questions: int
) -> list[str]:
    """Require each question number to have a visible source/program entry.

    The check intentionally accepts a shared path for multiple questions.  It
    only requires each question label to be locally associated with an entry,
    so it does not infer that the code is complete or executable.
    """
    appendix_page = section_page(pages, APPENDIX_HEADING_PATTERN)
    if appendix_page is None:
        return []
    appendix = "\n".join(pages[appendix_page:])
    missing: list[int] = []
    chinese_numbers = "一二三四五六七八九十"
    mapped_on_entry_line: set[int] = set()
    marker_pattern = re.compile(
        r"问题\s*(?P<number>[一二三四五六七八九十]|\d+)"
        r"|Q\s*(?P<q_number>\d+)"
        r"|第\s*(?P<ordinal>[一二三四五六七八九十]|\d+)\s*问",
        re.IGNORECASE,
    )
    for line in appendix.splitlines():
        if not PROGRAM_ENTRY_PATTERN.search(line):
            continue
        for marker in marker_pattern.finditer(line):
            raw = marker.group("number") or marker.group("q_number") or marker.group("ordinal")
            number = _question_number(raw)
            if number is not None:
                mapped_on_entry_line.add(number)
    # Window boundaries use the next marker for any question, rather than the
    # next occurrence of the same number.  Otherwise a bare 问题一 heading
    # could borrow 问题二's later source path.  Explicit same-line mappings
    # were recorded above, so they remain valid for shared scripts.
    all_markers = sorted(marker_pattern.finditer(appendix), key=lambda match: match.start())
    for number in range(1, expected_questions + 1):
        chinese = chinese_numbers[number - 1] if number <= len(chinese_numbers) else ""
        number_variants = "|".join(
            variant for variant in (str(number), re.escape(chinese)) if variant
        )
        label = re.compile(
            rf"(?:问题\s*(?:{number_variants})|Q\s*{number}|第\s*(?:{number_variants})\s*问)",
            re.IGNORECASE,
        )
        matches = list(label.finditer(appendix))
        mapped = number in mapped_on_entry_line
        for match in matches:
            # Include the heading and its short explanatory/code-entry block;
            # stop before the next *different or same* question marker to avoid
            # borrowing another question's path.
            end = next(
                (marker.start() for marker in all_markers if marker.start() > match.start()),
                len(appendix),
            )
            window = appendix[match.start():end]
            if len(window) > 800:
                window = window[:800]
            if PROGRAM_ENTRY_PATTERN.search(window):
                mapped = True
                break
        if not mapped:
            missing.append(number)
    if missing:
        labels = "、".join(str(number) for number in missing)
        return [
            f"附录缺少题号到程序/代码/源码入口的可见映射：问题 {labels}；"
            "允许多个问题共用同一脚本，但每个题号都须在附录中明确对应入口"
        ]
    return []


def audit_appendix_question_content(
    pages: list[str], expected_questions: int
) -> list[str]:
    """Warn when a mapped appendix block has no visible core-code signal.

    A filename or path is enough for the hard question-to-entry contract, but
    it is not evidence that the question's specific solver logic is shown.
    Keep this check deliberately lexical and bounded to the question block;
    shared code is checked once in its later shared section by a human.
    """
    appendix_page = section_page(pages, APPENDIX_HEADING_PATTERN)
    if appendix_page is None:
        return []
    appendix = "\n".join(pages[appendix_page:])
    marker_pattern = re.compile(
        r"问题\s*(?P<number>[一二三四五六七八九十]|\d+)"
        r"|Q\s*(?P<q_number>\d+)"
        r"|第\s*(?P<ordinal>[一二三四五六七八九十]|\d+)\s*问",
        re.IGNORECASE,
    )
    all_markers = sorted(marker_pattern.finditer(appendix), key=lambda match: match.start())
    warnings: list[str] = []
    chinese_numbers = "一二三四五六七八九十"
    for number in range(1, expected_questions + 1):
        chinese = chinese_numbers[number - 1] if number <= len(chinese_numbers) else ""
        variants = [str(number)] + ([re.escape(chinese)] if chinese else [])
        label = re.compile(
            rf"(?:问题\s*(?:{'|'.join(variants)})|Q\s*{number}|第\s*(?:{'|'.join(variants)})\s*问)",
            re.IGNORECASE,
        )
        matches = list(label.finditer(appendix))
        if not matches:
            continue
        # Use the first local block.  Mapping remains a separate hard check and
        # may find a shared path on the same line; this warning only concerns
        # the visible core-function/control/signature evidence.
        match = matches[0]
        end = next(
            (marker.start() for marker in all_markers if marker.start() > match.start()),
            len(appendix),
        )
        block = appendix[match.start():min(end, match.start() + 1600)]
        if PROGRAM_ENTRY_PATTERN.search(block) and not APPENDIX_CORE_EVIDENCE_PATTERN.search(block):
            warnings.append(
                f"附录问题 {number} 仅识别到文件映射，未识别本问特异核心求解逻辑或函数签名；"
                "请人工核对 PDF 中的 def/function/class/import 或控制/函数签名证据"
            )
    return warnings


def audit_summary_geometry(
    path: Path, summary_index: int = 0
) -> tuple[int | None, bool, str]:
    """Return (paragraph count, reliable, reason).

    PyMuPDF coordinates are used only as a conservative layout signal.  A
    missing heading/keyword/body block is deliberately reported as unreliable,
    never as an official or Skill failure.
    """
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            return None, False, "未找到 PyMuPDF"
    try:
        document = fitz.open(path)
    except Exception as exc:
        return None, False, f"无法打开 PDF 几何：{exc}"
    try:
        if summary_index < 0 or summary_index >= len(document):
            return None, False, "摘要页索引越界"
        page = document[summary_index]
        blocks = []
        for block in page.get_text("blocks"):
            if len(block) < 5:
                continue
            x0, y0, x1, y1, raw_text = block[:5]
            text = str(raw_text or "").strip()
            if not text or float(y1) >= float(page.rect.height) * 0.84:
                continue
            blocks.append((float(x0), float(y0), float(x1), float(y1), text))
        blocks.sort(key=lambda block: (block[1], block[0]))
        heading = next((block for block in blocks if re.search(r"^摘要(?:\s|$|[:：])", block[4])), None)
        keyword = next((block for block in blocks if re.search(r"^关键词(?:\s|$|[:：])", block[4])), None)
        if heading is None or keyword is None or keyword[1] <= heading[1]:
            return None, False, "无法可靠定位摘要标题或关键词"
        body = [block for block in blocks if block[1] >= heading[3] - 1 and block[3] <= keyword[1] + 1]
        body = [block for block in body if not re.search(r"^摘要(?:\s|$|[:：])", block[4]) and not re.search(r"^关键词", block[4])]
        if not body:
            return None, False, "摘要标题与关键词之间没有可识别正文块"

        # A normal wrapped paragraph is commonly one PyMuPDF block.  ReportLab
        # fixtures may emit one block per line; join only tight vertical lines,
        # while materially separated/indented lines start a new paragraph.
        heights = [max(block[3] - block[1], 1.0) for block in body]
        # Allow ordinary 1.25-line spacing (roughly 20 pt for a 12 pt font)
        # while still separating the larger blank-line gap used between prose
        # paragraphs in the ReportLab/PyMuPDF fixtures.
        line_gap_limit = max(5.0, statistics.median(heights) * 1.2)
        paragraphs = 1
        previous = body[0]
        for current in body[1:]:
            gap = current[1] - previous[3]
            indent_change = abs(current[0] - previous[0]) >= max(8.0, statistics.median(heights))
            if gap > line_gap_limit or (indent_change and gap >= 0):
                paragraphs += 1
            previous = current
        return paragraphs, True, ""
    except Exception as exc:
        return None, False, f"读取摘要文本块几何失败：{exc}"
    finally:
        document.close()


def audit_summary_question_anchors(text: str, expected_questions: int) -> list[str]:
    """Return soft warnings for missing normalized paragraph-start anchors."""
    chinese_numbers = "一二三四五六七八九十"
    anchor_pattern = re.compile(
        r"(?m)^\s*针对\s*问题\s*(?P<number>[一二三四五六七八九十]|\d+)\s*[，,]"
    )
    found: set[int] = set()
    for match in anchor_pattern.finditer(text):
        number = _question_number(match.group("number"))
        if number is not None:
            found.add(number)
    missing = [
        number for number in range(1, expected_questions + 1) if number not in found
    ]
    if not missing:
        return []
    labels = "、".join(
        f"针对问题{chinese_numbers[number - 1]}"
        if number <= len(chinese_numbers)
        else f"针对问题{number}"
        for number in missing
    )
    return [
        f"摘要缺少问题段首归一化锚点：{labels}；请人工核对段首是否使用对应的“针对问题x，”"
        "（可用匹配的阿拉伯数字与中英文逗号）；这是跨样本 Skill 默认，不是官方规则或阻断项"
    ]


def audit_structure_details(
    pages: list[str], *, expected_questions: int | None = None, min_questions: int | None = None,
    allow_placeholders: bool = False, check_appendix_content: bool = False,
    require_seven_chapter: bool = False,
) -> dict[str, list[str]]:
    """Audit functional coverage, optionally enforcing the default seven-chapter template."""
    skill_failures: list[str] = []
    quality_warnings: list[str] = []
    closure_manual_checks: list[str] = []
    first_pages: dict[str, int] = {}
    for name, pattern in STRUCTURE_HEADING_PATTERNS.items():
        matches = _structure_matches(pages, pattern)
        if matches:
            first_pages[name] = matches[0][0]

    whole_text = "\n".join(pages)
    if require_seven_chapter:
        top_level_positions: list[int] = []
        for name, pattern in CUMCM_AWARD_TOP_LEVEL:
            match = re.search(pattern, whole_text, re.IGNORECASE | re.MULTILINE)
            if match is None:
                skill_failures.append(f"CUMCM 七章模板缺少一级标题：{name}")
            else:
                top_level_positions.append(match.start())
        if len(top_level_positions) == len(CUMCM_AWARD_TOP_LEVEL) and top_level_positions != sorted(top_level_positions):
            skill_failures.append("CUMCM 七章模板一级标题顺序不满足：问题重述→问题分析→模型假设→符号说明→模型的建立与求解→模型的分析与检验→模型的评价")

    if require_seven_chapter and "参考文献" not in first_pages:
        skill_failures.append("CUMCM 七章模板缺少未编号标题：参考文献")
    appendix_page = section_page(pages, APPENDIX_HEADING_PATTERN)
    if require_seven_chapter and appendix_page is None:
        skill_failures.append("CUMCM 七章模板缺少未编号标题：附录")
    if require_seven_chapter and appendix_page is not None and "参考文献" in first_pages and appendix_page < first_pages["参考文献"]:
        skill_failures.append("CUMCM 骨架中附录位于参考文献之前")

    if require_seven_chapter and re.search(r"(?m)^\s*(?:八|九|十|\d+)\s*[、.．]\s*(?:参考文献|附\s*录)\s*$", whole_text):
        skill_failures.append("参考文献与附录必须使用未编号标题，不得作为正文编号章节")
    if require_seven_chapter:
        for label, pattern in (
            ("1.1 问题背景", r"^\s*1\.1\s+问题\s*背景\s*$"),
            ("1.2 问题要求", r"^\s*1\.2\s+问题\s*要求\s*$"),
            ("7.1 模型的优点", r"^\s*7\.1\s+模型\s*的?\s*优点\s*$"),
            ("7.2 模型的缺点与改进", r"^\s*7\.2\s+模型\s*的?\s*缺点\s*与\s*改进\s*$"),
        ):
            if not _structure_matches(pages, pattern):
                skill_failures.append(f"CUMCM 七章模板缺少二级标题：{label}")

    symbol_matches = _structure_matches(pages, CUMCM_AWARD_TOP_LEVEL[3][1])
    model_matches = _structure_matches(pages, CUMCM_AWARD_TOP_LEVEL[4][1])
    if symbol_matches and model_matches:
        symbol_start = symbol_matches[0][0]
        model_start = model_matches[0][0]
        symbol_block = "\n".join(pages[symbol_start : model_start + 1])
        missing_headers = [header for header in ("符号", "含义", "单位") if header not in symbol_block]
        if require_seven_chapter and missing_headers:
            skill_failures.append("符号说明表缺少表头：" + "、".join(missing_headers))
        symbol_heading = re.search(CUMCM_AWARD_TOP_LEVEL[3][1], whole_text, re.IGNORECASE | re.MULTILINE)
        model_heading = re.search(CUMCM_AWARD_TOP_LEVEL[4][1], whole_text, re.IGNORECASE | re.MULTILINE)
        symbol_content = whole_text[symbol_heading.end():model_heading.start()] if symbol_heading and model_heading else ""
        if CHAPTER_RESPONSIBILITY_PATTERNS["符号说明"].search(symbol_content):
            quality_warnings.append(
                "符号说明章节出现独立公式/推导/坐标或索引定义等建模内容；"
                "请人工确认建模论证是否应移至第五章"
            )

    assumption_matches = _structure_matches(pages, CUMCM_AWARD_TOP_LEVEL[2][1])
    if assumption_matches and symbol_matches:
        assumption_start = assumption_matches[0][0]
        symbol_start = symbol_matches[0][0]
        assumption_heading = re.search(CUMCM_AWARD_TOP_LEVEL[2][1], whole_text, re.IGNORECASE | re.MULTILINE)
        symbol_heading = re.search(CUMCM_AWARD_TOP_LEVEL[3][1], whole_text, re.IGNORECASE | re.MULTILINE)
        assumption_content = whole_text[assumption_heading.end():symbol_heading.start()] if assumption_heading and symbol_heading else ""
        if CHAPTER_RESPONSIBILITY_PATTERNS["模型假设"].search(assumption_content):
            quality_warnings.append(
                "模型假设章节出现 Excel/Python/MATLAB/双精度/随机种子/迭代次数/容差/"
                "输出格式/软件版本等工程实现内容；请人工确认章节职责"
            )

    def numbered_question_subsections(chapter: int) -> list[int]:
        pattern = re.compile(
            rf"(?m)^\s*{chapter}\.(\d+)\s+[^\n]+$"
        )
        return [int(match.group(1)) for match in pattern.finditer(whole_text)]

    analysis_numbers = numbered_question_subsections(2)
    model_numbers = numbered_question_subsections(5)
    if expected_questions is not None:
        expected = list(range(1, expected_questions + 1))
        # Equations and prose can contain strings such as ``5.267``.  Only
        # the exact 5.1--5.N question interval participates in strict closure;
        # out-of-range numeric lines are not task headings.
        model_numbers = [number for number in model_numbers if number in expected]
        if require_seven_chapter and (analysis_numbers[:expected_questions] != expected or len(set(analysis_numbers)) < expected_questions):
            skill_failures.append(f"问题分析必须按 2.1—2.{expected_questions} 逐问映射；识别到 {analysis_numbers}")
        if require_seven_chapter and (model_numbers[:expected_questions] != expected or len(set(model_numbers)) < expected_questions):
            skill_failures.append(f"模型建立与求解必须按 5.1—5.{expected_questions} 逐问映射；识别到 {model_numbers}")
        quality_warnings.extend(audit_question_requirement_labels(pages, expected_questions))
        appendix_mapping_failures = audit_appendix_question_mappings(pages, expected_questions)
        if allow_placeholders:
            quality_warnings.extend(appendix_mapping_failures)
        else:
            skill_failures.extend(appendix_mapping_failures)

    question_pattern = re.compile(QUESTION_HEADING_PATTERN, re.IGNORECASE | re.MULTILINE)
    joined = "\n\f".join(pages)
    # Abstract prose may start a line with “问题一：……”. It is not a task
    # chapter, so count explicit task headings only after the summary page.
    question_matches = [
        match for match in question_pattern.finditer(joined) if "\f" in joined[: match.start()]
    ]
    if expected_questions is not None and require_seven_chapter:
        # In strict explicit-question mode, only exact 5.i section titles are
        # task boundaries.  Prose such as “问题一” in 1.2, the abstract, or a
        # result paragraph must never create phantom question blocks.
        exact_model_pattern = re.compile(
            r"(?m)^\s*5\.(?P<section>\d+)\s+[^\n]+$"
        )
        question_matches = [
            match for match in exact_model_pattern.finditer(joined)
            if 1 <= int(match.group("section")) <= expected_questions
        ]
        question_matches.sort(key=lambda match: match.start())
        if len(question_matches) > expected_questions:
            question_matches = question_matches[:expected_questions]
    elif expected_questions is not None:
        semantic_pattern = re.compile(
            r"(?m)^\s*(?:\d+(?:\.\d+)*\s+)?(?:问题\s*(?P<number>[一二三四五六七八九十]|\d+)"
            r"|第\s*(?P<ordinal>[一二三四五六七八九十]|\d+)\s*问)"
            r"(?:\s*[：:—-]?[^\n]{0,100})?\s*$",
            re.IGNORECASE,
        )
        semantic_end = len("\n\f".join(pages[:appendix_page])) if appendix_page is not None else len(joined)
        by_number: dict[int, re.Match[str]] = {}
        for match in semantic_pattern.finditer(joined[:semantic_end]):
            raw = match.group("number") or match.group("ordinal")
            number = _question_number(raw)
            if number is not None and 1 <= number <= expected_questions:
                by_number[number] = match
        question_matches = sorted(by_number.values(), key=lambda match: match.start())
        missing_semantic = sorted(set(range(1, expected_questions + 1)) - set(by_number))
        if missing_semantic:
            closure_manual_checks.append(
                f"功能覆盖模式无法按语义问题标题定位题号 {missing_semantic} 的正文论证区间；"
                "请人工核对任务映射、模型、结果、验证和作答，不应为通过审计而补关键词"
            )
    # An unnumbered/semantic paper is valid when no question count is supplied.
    # Keep ``min_questions`` only as an explicit compatibility/testing override;
    # never impose a default “问题一/问题二” quota.
    effective_min_questions = (
        min_questions if expected_questions is None else min_questions
    )
    if require_seven_chapter and effective_min_questions is not None and len(question_matches) < effective_min_questions:
        skill_failures.append(
            f"严格结构至少需要 {effective_min_questions} 个显式问题小节，当前识别到 {len(question_matches)} 个"
        )
    elif not require_seven_chapter and effective_min_questions is not None and len(question_matches) < effective_min_questions:
        closure_manual_checks.append(
            f"功能覆盖模式仅定位到 {len(question_matches)} 个语义问题区间，少于显式要求 {effective_min_questions}；"
            "请人工核对，不应为通过审计而补关键词"
        )
    if require_seven_chapter and expected_questions is not None and len(question_matches) != expected_questions:
        if len(model_numbers) < expected_questions:
            quality_warnings.append(f"精确 5.i 标题区间识别到 {len(question_matches)} 个，请人工核对 5.1—5.{expected_questions} 的题意映射")
    if require_seven_chapter and expected_questions is not None and question_matches:
        numbers: list[int] = []
        for match in question_matches:
            numbers.append(int(match.group("section")))
        if set(numbers) != set(range(1, expected_questions + 1)):
            quality_warnings.append(
                f"问题小节编号未覆盖 1—{expected_questions} 且各出现一次：识别到 {numbers}"
            )
    if expected_questions is not None and pages:
        chinese_numbers = "一二三四五六七八九十"
        abstract = pages[0]
        for number in range(1, expected_questions + 1):
            chinese = chinese_numbers[number - 1] if number <= len(chinese_numbers) else ""
            variants = [rf"问题\s*{number}", rf"Q\s*{number}"]
            if chinese:
                variants.append(rf"问题\s*{chinese}")
            if not any(re.search(variant, abstract, re.IGNORECASE) for variant in variants):
                quality_warnings.append(f"摘要未识别到问题 {number} 的对应信息")

    question_checks_requested = expected_questions is not None or min_questions is not None

    # Each question must leave a local evidence trail. The check is deliberately
    # lexical and conservative: it catches empty/template sections, while
    # substantive mathematical correctness remains a human and reproducibility check.
    closure_terms = (
        ("目标", "输出", "要求"),
        ("模型", "关系", "方程", "目标函数", "约束"),
        ("求解", "推导", "计算", "算法", "解析"),
        ("结果", "结论", "方案", "答案"),
        ("验证", "检验", "误差", "敏感性", "边界", "对照"),
    )
    if question_checks_requested:
        for index, match in enumerate(question_matches, start=1):
            end = question_matches[index].start() if index < len(question_matches) else len(joined)
            block = joined[match.end():end]
            if require_seven_chapter:
                cross_question_heading = re.search(
                    CUMCM_AWARD_TOP_LEVEL[5][1], block, re.IGNORECASE | re.MULTILINE
                )
                if cross_question_heading is not None:
                    block = block[:cross_question_heading.start()]
            missing = []
            for term_index, options in enumerate(closure_terms):
                # The explicit question heading itself identifies the requested
                # output/target; the remaining terms must be present in its local
                # evidence block.  This remains a conservative lexical check, not
                # a claim about mathematical correctness.
                if term_index == 0 and "问题" in match.group(0):
                    continue
                if not any(option in block for option in options):
                    missing.append("/".join(options))
            if missing:
                section_label = (
                    f"5.{match.group('section')}"
                    if expected_questions is not None and match.groupdict().get("section")
                    else f"问题小节 {index}"
                )
                closure_manual_checks.append(
                    f"{section_label} 的闭环词汇仅供人工定位，缺少：{', '.join(missing)}；"
                    "不应为通过审计而补关键词，请人工核对目标、模型、求解、结果和局部验证"
                )
                # Keep lexical closure out of QUALITY_WARN: it is a locator
                # for a human review, not a requirement to seed keywords.
    if expected_questions is not None and check_appendix_content:
        quality_warnings.extend(audit_appendix_question_content(pages, expected_questions))
    if not require_seven_chapter:
        for label, pattern in FUNCTIONAL_COVERAGE_PATTERNS:
            if not re.search(pattern, whole_text, re.IGNORECASE):
                closure_manual_checks.append(
                    f"功能覆盖审计无法从文本层确认：{label}；仅供人工定位，不代表内容缺失，"
                    "不应为通过审计而补关键词"
                )
    if not re.search(EVALUATION_SEMANTIC_PATTERN, "\n".join(pages), re.IGNORECASE):
        closure_manual_checks.append(
            "未识别到局限/适用边界/误差/评价语义；仅供人工定位，不代表缺少该内容，"
            "也不应为通过审计而补关键词，请人工核对模型结论边界"
        )
    return {
        "official_fail": [],
        "skill_fail": skill_failures,
        "quality_warn": quality_warnings,
        "manual_check": closure_manual_checks,
    }


def audit_structure(
    pages: list[str], *, expected_questions: int | None = None, min_questions: int | None = None,
    require_seven_chapter: bool = False,
) -> list[str]:
    """Backward-compatible list API returning blocking and warning findings."""
    details = audit_structure_details(
        pages, expected_questions=expected_questions, min_questions=min_questions,
        require_seven_chapter=require_seven_chapter,
    )
    return details["skill_fail"] + details["quality_warn"]


def extract_with_pymupdf(path: Path) -> tuple[list[str], list[str], dict[str, str]]:
    try:
        import pymupdf as fitz
    except ImportError as first_error:
        try:
            import fitz
        except ImportError as second_error:
            raise RuntimeError(
                "PyMuPDF 路径不可用：未找到 pymupdf 或 fitz；请安装 PyMuPDF，或确保 Poppler 可用"
            ) from second_error
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise RuntimeError(f"PyMuPDF 路径打开 PDF 失败：{exc}") from exc
    pages: list[str] = []
    footers: list[str] = []
    try:
        for page in document:
            pages.append(page.get_text("text"))
            footer_parts = []
            for block in page.get_text("blocks"):
                if block[1] >= page.rect.height * 0.84:
                    footer_parts.append(str(block[4]))
            footers.append(" ".join(footer_parts))
        metadata = {key: str(value or "") for key, value in (document.metadata or {}).items()}
    except Exception as exc:
        raise RuntimeError(f"PyMuPDF 路径提取文本失败：{exc}") from exc
    finally:
        document.close()
    return pages, footers, metadata


def extract_with_poppler(path: Path) -> tuple[list[str], list[str], dict[str, str]]:
    try:
        info = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("Poppler 路径不可用：未找到 pdfinfo；请安装 poppler-utils 或安装 PyMuPDF") from exc
    if info.returncode != 0:
        detail = info.stderr.strip() or info.stdout.strip() or "无额外错误信息"
        raise RuntimeError(f"Poppler 的 pdfinfo 无法读取文件（退出码 {info.returncode}）：{detail}")
    match = re.search(r"^Pages:\s*(\d+)", info.stdout, re.MULTILINE)
    if not match:
        raise RuntimeError("无法取得 PDF 页数")
    pages = []
    for page_number in range(1, int(match.group(1)) + 1):
        try:
            result = subprocess.run(
                ["pdftotext", "-f", str(page_number), "-l", str(page_number), str(path), "-"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Poppler 路径不可用：未找到 pdftotext；请安装 poppler-utils 或安装 PyMuPDF") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "无额外错误信息"
            raise RuntimeError(f"Poppler 的 pdftotext 提取第 {page_number} 页失败（退出码 {result.returncode}）：{detail}")
        pages.append(result.stdout)
    return pages, [""] * len(pages), {}


def extract_pdf(path: Path) -> tuple[list[str], list[str], dict[str, str]]:
    errors: list[str] = []
    try:
        return extract_with_pymupdf(path)
    except Exception as exc:
        errors.append(str(exc))
    try:
        return extract_with_poppler(path)
    except Exception as exc:
        errors.append(str(exc))
    raise RuntimeError("PDF 文本提取失败；PyMuPDF：{}；Poppler：{}".format(errors[0], errors[1]))


def audit_page_geometry(path: Path) -> tuple[list[int], list[int], bool]:
    """Check page rectangles against A4 without inspecting text bounding boxes."""
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            return [], [], False
    try:
        document = fitz.open(path)
    except Exception:
        return [], [], False
    non_a4_pages: list[int] = []
    landscape_pages: list[int] = []
    try:
        for page_index, page in enumerate(document):
            width = float(page.rect.width)
            height = float(page.rect.height)
            portrait = abs(width - A4_WIDTH_PT) <= A4_SIZE_TOLERANCE_PT and abs(
                height - A4_HEIGHT_PT
            ) <= A4_SIZE_TOLERANCE_PT
            landscape = abs(width - A4_HEIGHT_PT) <= A4_SIZE_TOLERANCE_PT and abs(
                height - A4_WIDTH_PT
            ) <= A4_SIZE_TOLERANCE_PT
            if not portrait and not landscape:
                non_a4_pages.append(page_index)
            elif landscape:
                landscape_pages.append(page_index)
    except Exception:
        return [], [], False
    finally:
        document.close()
    return non_a4_pages, landscape_pages, True


def audit_page_flow(
    path: Path, page_indices: Iterable[int]
) -> tuple[list[dict[str, object]], bool]:
    """Measure visible vertical coverage and internal gaps for a QA hint.

    ``page_indices`` is zero-based and should be limited by the caller to the
    core argument pages.  Text, image, and vector-drawing bounding boxes are
    combined while the bottom 6% of each page is ignored as a footer/page
    number zone.  The result is only a locator for human page-flow review; it
    is deliberately not a structure or official-format gate.
    """
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            return [], False
    try:
        document = fitz.open(path)
    except Exception:
        return [], False

    records: list[dict[str, object]] = []
    try:
        for page_index in list(page_indices):
            if page_index < 0 or page_index >= len(document):
                continue
            page = document[page_index]
            page_height = float(page.rect.height)
            content_bottom = page_height * PAGE_FLOW_CONTENT_BOTTOM
            boxes: list[tuple[float, float]] = []
            text_chars = 0
            text_blocks = 0

            for block in page.get_text("blocks"):
                if len(block) < 5:
                    continue
                _x0, y0, _x1, y1, raw_text = block[:5]
                text = str(raw_text or "").strip()
                compact_text = re.sub(r"\s+", "", text)
                is_page_number = re.fullmatch(r"(?:第\d+页|Page\d+)", compact_text, re.IGNORECASE)
                if not text or is_page_number or float(y0) >= content_bottom:
                    continue
                top = max(0.0, float(y0))
                bottom = min(content_bottom, float(y1))
                if bottom > top:
                    boxes.append((top, bottom))
                    text_chars += len(re.sub(r"\s+", "", text))
                    text_blocks += 1

            image_count = 0
            try:
                image_info = page.get_image_info()
            except Exception:
                image_info = []
            for image in image_info:
                bbox = image.get("bbox") if isinstance(image, dict) else None
                if not bbox or len(bbox) < 4:
                    continue
                _x0, y0, _x1, y1 = bbox[:4]
                if float(y0) >= content_bottom:
                    continue
                top = max(0.0, float(y0))
                bottom = min(content_bottom, float(y1))
                if bottom > top:
                    boxes.append((top, bottom))
                    image_count += 1

            drawing_count = 0
            try:
                drawings = page.get_drawings()
            except Exception:
                drawings = []
            for drawing in drawings:
                rect = drawing.get("rect") if isinstance(drawing, dict) else None
                if rect is None:
                    continue
                y0 = float(rect.y0)
                y1 = float(rect.y1)
                if y0 >= content_bottom:
                    continue
                top = max(0.0, y0)
                bottom = min(content_bottom, y1)
                if bottom > top:
                    boxes.append((top, bottom))
                    drawing_count += 1

            if boxes:
                boxes.sort(key=lambda box: (box[0], box[1]))
                gap_tolerance = min(
                    24.0,
                    max(12.0, page_height * PAGE_FLOW_GAP_TOLERANCE_FRACTION),
                )
                merged: list[tuple[float, float]] = []
                for current_top, current_bottom in boxes:
                    if not merged or current_top - merged[-1][1] > gap_tolerance:
                        merged.append((current_top, current_bottom))
                    else:
                        merged[-1] = (merged[-1][0], max(merged[-1][1], current_bottom))
                coverage = (
                    sum(bottom - top for top, bottom in merged) / content_bottom
                    if content_bottom
                    else 0.0
                )
                largest_internal_gap = (
                    max(
                        next_top - previous_bottom
                        for (_previous_top, previous_bottom), (next_top, _next_bottom)
                        in zip(merged, merged[1:])
                    )
                    / content_bottom
                    if len(merged) > 1 and content_bottom
                    else 0.0
                )
            else:
                coverage = largest_internal_gap = 0.0
            visual_dominant = (
                text_chars < PAGE_FLOW_VISUAL_TEXT_LIMIT
                and (image_count > 0 or drawing_count >= PAGE_FLOW_DRAWING_LIMIT)
            )
            records.append(
                {
                    "page_index": page_index,
                    "coverage": coverage,
                    "largest_internal_gap": largest_internal_gap,
                    "text_chars": text_chars,
                    "text_blocks": text_blocks,
                    "image_count": image_count,
                    "drawing_count": drawing_count,
                    "visual_dominant": visual_dominant,
                    "low_coverage": coverage < PAGE_FLOW_COVERAGE_THRESHOLD,
                    "large_internal_gap": largest_internal_gap > PAGE_FLOW_INTERNAL_GAP_THRESHOLD,
                }
            )
    except Exception:
        return [], False
    finally:
        document.close()
    return records, True


def audit_body_layout(path: Path, body_page_indices: range) -> tuple[set[int], bool]:
    """Return conservative double-column hits for body pages.

    This is intentionally only a layout/text heuristic.  If PyMuPDF geometry is
    unavailable, callers must warn rather than infer a pass or failure.
    """
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            return set(), False
    try:
        document = fitz.open(path)
    except Exception:
        return set(), False
    column_hits: set[int] = set()
    try:
        for page_index in body_page_indices:
            if page_index < 0 or page_index >= len(document):
                continue
            page = document[page_index]
            blocks = page.get_text("blocks")
            left_chars = right_chars = 0
            left_blocks = right_blocks = 0
            for block in blocks:
                if len(block) < 5:
                    continue
                x0, y0, x1, y1, raw_text = block[:5]
                text = str(raw_text or "")
                if not text.strip():
                    continue
                # Ignore wide blocks and non-text blocks; a single table/figure
                # should not be mistaken for a second column.
                block_width = max(float(x1) - float(x0), 0.0)
                page_width = float(page.rect.width)
                center = page_width / 2.0
                if block_width < page_width * 0.58:
                    compact = re.sub(r"\s+", "", text)
                    if float(x1) <= center + page_width * 0.02:
                        left_chars += len(compact)
                        left_blocks += 1
                    elif float(x0) >= center - page_width * 0.02:
                        right_chars += len(compact)
                        right_blocks += 1
            # Require substantial text on both sides.  This deliberately does
            # not classify one-page figure/table layouts as double-column text.
            if (
                left_chars >= 60
                and right_chars >= 60
                and (left_blocks >= 2 or left_chars >= 120)
                and (right_blocks >= 2 or right_chars >= 120)
            ):
                column_hits.add(page_index)
    except Exception:
        return set(), False
    finally:
        document.close()
    return column_hits, True


def audit_body_code(pages: list[str], body_page_indices: range) -> tuple[set[int], int]:
    """Count strong code-looking lines from already extracted body text."""
    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in STRONG_CODE_LINE_PATTERNS]
    hits: set[int] = set()
    count = 0
    for page_index in body_page_indices:
        if page_index < 0 or page_index >= len(pages):
            continue
        page_count = sum(
            1 for line in pages[page_index].splitlines() if any(pattern.match(line) for pattern in compiled)
        )
        if page_count:
            hits.add(page_index)
            count += page_count
    return hits, count


def section_page(pages: list[str], pattern: str) -> int | None:
    compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    for index, text in enumerate(pages):
        if compiled.search(text):
            return index
    return None


def chapter_page_spans(pages: list[str], core_end: int) -> list[str]:
    """Return printable page spans for the seven CUMCM top-level chapters."""
    spans: list[str] = []
    starts: dict[str, int] = {}
    for name, pattern in CUMCM_AWARD_TOP_LEVEL:
        matches = _structure_matches(pages, pattern)
        if matches:
            starts[name] = matches[0][0]
    for index, (name, _pattern) in enumerate(CUMCM_AWARD_TOP_LEVEL):
        chapter_start = starts.get(name)
        if chapter_start is None:
            spans.append(f"{name}=无法识别")
            continue
        next_starts = [
            starts[later_name]
            for later_name, _ in CUMCM_AWARD_TOP_LEVEL[index + 1:]
            if later_name in starts
        ]
        if next_starts:
            chapter_end = max(chapter_start, min(next_starts) - 1)
        else:
            chapter_end = max(chapter_start, core_end - 1)
        spans.append(f"{name}={chapter_start + 1}–{chapter_end + 1}")
    return spans


def audit(
    path: Path,
    allow_placeholders: bool = False,
    max_pre_appendix_pages: int | None = None,
    strict_structure: bool = False,
    expected_questions: int | None = None,
    *,
    award_style_audit: bool = False,
    min_main_matter_pages: int | None = None,
    max_main_matter_pages: int | None = None,
    profile: str | None = None,
    min_body_pages: int | None = None,
    max_body_pages: int | None = None,
) -> int:
    official_failures: list[str] = []
    skill_failures: list[str] = []
    quality_warnings: list[str] = []
    manual_checks: list[str] = []

    def input_error(message: str) -> int:
        print(f"[错误] {message}", file=sys.stderr)
        return 2

    if not path.is_file():
        return input_error(f"文件不存在：{path}")
    if path.suffix.lower() != ".pdf":
        return input_error("电子论文审计只接受 PDF")

    if expected_questions is not None and (
        isinstance(expected_questions, bool) or expected_questions <= 0
    ):
        return input_error("expected_questions 必须是正整数")
    for name, value in (
        ("min_main_matter_pages", min_main_matter_pages),
        ("max_main_matter_pages", max_main_matter_pages),
        ("max_pre_appendix_pages", max_pre_appendix_pages),
        ("min_body_pages", min_body_pages),
        ("max_body_pages", max_body_pages),
    ):
        if value is not None and (isinstance(value, bool) or value <= 0):
            return input_error(f"{name} 必须是正整数")
    if (
        max_main_matter_pages is not None
        and max_pre_appendix_pages is not None
        and max_main_matter_pages != max_pre_appendix_pages
    ):
        return input_error("max_main_matter_pages 与兼容参数 max_pre_appendix_pages 不一致")
    effective_max_main_matter_pages = (
        max_main_matter_pages
        if max_main_matter_pages is not None
        else max_pre_appendix_pages
    )
    if (
        min_main_matter_pages is not None
        and effective_max_main_matter_pages is not None
        and min_main_matter_pages > effective_max_main_matter_pages
    ):
        return input_error("min_main_matter_pages 不能大于 max_main_matter_pages")
    if max_pre_appendix_pages is not None:
        quality_warnings.append("--max-pre-appendix-pages 已弃用；请改用 --max-main-matter-pages")
    if profile not in {None, "cumcm"}:
        return input_error(f"不支持的 profile：{profile!r}；当前仅支持 cumcm")
    formal_structure_audit = profile == "cumcm" and (strict_structure or award_style_audit)
    min_body_pages_explicit = min_body_pages is not None
    max_body_pages_explicit = max_body_pages is not None
    if profile == "cumcm":
        if min_body_pages is None:
            min_body_pages = 26
        if max_body_pages is None:
            max_body_pages = 30
        if min_body_pages_explicit and max_body_pages_explicit and min_body_pages > max_body_pages:
            return input_error("min_body_pages 不能大于 max_body_pages")
    size_mib = path.stat().st_size / 1024 / 1024
    if size_mib > 20:
        official_failures.append(f"电子论文 {size_mib:.2f} MiB，超过 20 MiB")

    pages, footers, metadata = extract_pdf(path)
    if not pages:
        return input_error("PDF 未返回任何页面；请确认文件完整且可由 PDF 阅读器打开")
    text_available = any(text.strip() for text in pages)
    if not text_available:
        manual_checks.append("PDF 文本层缺失，摘要、附录、身份字段和页码无法可靠机器识别；请人工逐页核对")
        page_one = ""
    else:
        page_one = pages[0]

    compact_page_one = re.sub(r"\s+", "", page_one)
    if text_available and ("摘要" not in compact_page_one or "关键词" not in compact_page_one):
        official_failures.append("电子论文第一页未同时识别到摘要和关键词")

    first_pages = "\n".join(pages)
    if text_available and re.search(r"(?m)^\s*目\s*录\s*$", first_pages):
        official_failures.append("检测到目录；2026 格式规范要求正文不要目录")

    summary_index = section_page(pages, r"^\s*摘\s*要(?:\s*[:：]|\s|$)")
    problem_matches = _structure_matches(pages, STRUCTURE_HEADING_PATTERNS["问题重述"])
    problem_index = min((page_index for page_index, _ in problem_matches), default=None)
    appendix_index = section_page(pages, APPENDIX_HEADING_PATTERN)
    if problem_index is not None:
        body_start_index = problem_index
    elif summary_index is not None:
        body_start_index = summary_index + 1
    else:
        body_start_index = 0
    if appendix_index is None:
        if text_available:
            official_failures.append("未识别到附录")
        body_pages = max(len(pages) - body_start_index, 0)
        appendix_text = ""
    else:
        body_pages = max(appendix_index - body_start_index, 0)
        appendix_text = "\n".join(pages[appendix_index:])
        if not re.search(r"支撑材料.*文件|文件.*清单", appendix_text):
            official_failures.append("附录中未识别到支撑材料文件列表")
        if not re.search(r"源程序|程序代码|代码清单|本论文没有用到程序", appendix_text):
            message = "附录中未识别到完整源程序代码或无程序说明"
            if allow_placeholders:
                quality_warnings.append(message + "（模板结构 QA；正式审计仍需补齐）")
            else:
                official_failures.append(message)
    if text_available and body_pages > 30:
        official_failures.append(f"正文推定为 {body_pages} 页，超过 30 页")
    end_index = appendix_index if appendix_index is not None else len(pages)
    main_matter_pages = None if summary_index is None else max(end_index - summary_index, 0)
    summary_pages = (
        max(problem_index - summary_index, 0)
        if summary_index is not None and problem_index is not None and problem_index > summary_index
        else None
    )
    appendix_pages = max(len(pages) - appendix_index, 0) if appendix_index is not None else None
    profile_body_indices = (
        range(body_start_index, appendix_index)
        if profile == "cumcm" and appendix_index is not None and body_start_index < appendix_index
        else range(0)
    )
    profile_body_pages = len(profile_body_indices)
    if summary_index is None:
        if min_main_matter_pages is not None or effective_max_main_matter_pages is not None:
            manual_checks.append("未识别到摘要标题，无法精确计算主体稿（摘要至附录前，含参考文献）页数")
    elif text_available:
        if min_main_matter_pages is not None and main_matter_pages < min_main_matter_pages:
            quality_warnings.append(
                f"主体稿（摘要至附录前，含参考文献）推定页数为 {main_matter_pages} 页，"
                f"低于 {min_main_matter_pages} 页的软提示；请按证据闭环人工复核"
            )
        if effective_max_main_matter_pages is not None and main_matter_pages > effective_max_main_matter_pages:
            quality_warnings.append(
                f"主体稿（摘要至附录前，含参考文献）推定页数为 {main_matter_pages} 页，"
                f"超过 {effective_max_main_matter_pages} 页的软提示；请删减重复内容并人工复核"
            )
    if profile == "cumcm":
        non_a4_pages, landscape_pages, geometry_available = audit_page_geometry(path)
        if not geometry_available:
            manual_checks.append("CUMCM profile 无法取得 PyMuPDF 页面几何，A4 页面尺寸无法判断；请人工核对")
        else:
            if non_a4_pages:
                official_failures.append(
                    "CUMCM profile 检测到非 A4 页面（页 "
                    + ", ".join(str(index + 1) for index in non_a4_pages)
                    + "）；页面尺寸必须为 A4"
                )
            if landscape_pages:
                manual_checks.append(
                    "CUMCM profile 检测到 A4 横向页面（页 "
                    + ", ".join(str(index + 1) for index in landscape_pages)
                    + "）；请人工确认视觉版式"
                )
        if summary_index is None:
            if text_available:
                official_failures.append("CUMCM profile 未识别到摘要标题；摘要必须位于首页且原则上为一页")
            else:
                manual_checks.append("CUMCM profile 无法识别摘要，无法判断摘要首页和页数；请人工核对")
        else:
            if summary_index != 0:
                official_failures.append("CUMCM profile 摘要不是电子版第 1 页；摘要首页是官方硬项")
            if problem_index is None:
                manual_checks.append("CUMCM profile 未识别到‘问题重述’，正文页数回退为摘要后一页至附录前；无法精确分隔摘要")
            elif summary_pages is not None and summary_pages > 1:
                official_failures.append(
                    f"CUMCM profile 摘要推定为 {summary_pages} 页，超过原则上 1 页；摘要一页是官方格式硬项"
                )
            if expected_questions is not None and expected_questions > 0:
                paragraph_count, reliable, reason = audit_summary_geometry(path, summary_index)
                if not reliable:
                    manual_checks.append(
                        "CUMCM profile 无法可靠识别摘要自然段"
                        + (f"（{reason}）" if reason else "")
                        + "；请人工核对，不得据此判定官方不合格"
                    )
                else:
                    lower = expected_questions + 1
                    upper = expected_questions + 2
                    if paragraph_count is not None and not lower <= paragraph_count <= upper:
                        quality_warnings.append(
                            f"摘要几何审计识别到约 {paragraph_count} 个论证自然段，"
                            f"不在跨样本 Skill 默认范围 [{lower}, {upper}]（Q+1 至 Q+2）；"
                            "这不是官方规则或阻断项，请人工复核"
                        )
                if text_available:
                    quality_warnings.extend(
                        audit_summary_question_anchors(pages[summary_index], expected_questions)
                    )
        if appendix_index is None:
            manual_checks.append("CUMCM profile 无法识别附录，无法验证问题重述至附录之前的正文页数")
        elif not profile_body_indices:
            manual_checks.append("CUMCM profile 正文起始页晚于附录，无法精确推定正文页数")
        if appendix_index is None or not profile_body_indices:
            pass
        else:
            if profile_body_pages < min_body_pages:
                if profile_body_pages >= 24:
                    quality_warnings.append(
                        f"CUMCM profile 正文为 {profile_body_pages} 页，低于推荐的 26–29 页区间；短篇提醒不阻断"
                    )
                elif profile_body_pages >= 20:
                    quality_warnings.append(
                        f"强质量提醒：CUMCM profile 正文为 {profile_body_pages} 页，低于 24 页；请重点复核论证完整性"
                    )
                else:
                    quality_warnings.append(
                        f"严重质量风险：CUMCM profile 正文为 {profile_body_pages} 页，低于 20 页；请重点复核论证完整性"
                    )
            if profile_body_pages > max_body_pages and max_body_pages_explicit:
                quality_warnings.append(
                    f"CUMCM profile 正文（问题重述至附录之前（无法识别时回退摘要后一页））为 {profile_body_pages} 页，"
                    f"超过显式最高页数 {max_body_pages} 页的软提示；请人工复核"
                )
            elif profile_body_pages == 30:
                quality_warnings.append("CUMCM profile 正文为 30 页，处于官方正文上限附近；请人工复核篇幅")
            code_hits, code_line_count = audit_body_code(pages, profile_body_indices)
            column_hits, geometry_available = audit_body_layout(path, profile_body_indices)
            if not geometry_available:
                manual_checks.append("CUMCM profile 无法取得 PyMuPDF 文本块几何，双栏布局无法判断；请人工核对")
            else:
                column_threshold = max(2, (profile_body_pages + 1) // 2)
                if len(column_hits) >= column_threshold:
                    skill_failures.append(
                        "CUMCM profile 检测到正文双栏文字布局，命中页 "
                        + ", ".join(str(index + 1) for index in sorted(column_hits))
                        + f"（{len(column_hits)} 页；达到大面积双栏阻断阈值 max(2, ceil(body_pages/2))={column_threshold}）"
                    )
                elif column_hits:
                    quality_warnings.append(
                        "CUMCM profile 发现疑似双栏正文页 "
                        + ", ".join(str(index + 1) for index in sorted(column_hits))
                        + "，未达到大面积阈值；请人工复核版式"
                    )
            if code_line_count >= 6:
                skill_failures.append(
                    "CUMCM profile 正文检测到至少 6 行强代码行（命中页 "
                    + ", ".join(str(index + 1) for index in sorted(code_hits))
                    + "）；正文长代码违反 Skill 内部代码隔离门"
                )
            elif code_line_count:
                quality_warnings.append(
                    f"CUMCM profile 正文发现 {code_line_count} 行疑似强代码行，未达到 6 行阻断阈值；"
                    "普通公式和伪代码不计入"
                )
    manual_checks.append(
        "正文分账按‘问题重述至附录前’的保守机器范围；无法识别问题重述时回退为摘要后一页至附录前，"
        "标题识别和分页仍须按最终 PDF 人工核对。官方正文硬项仍以当届规则为准"
    )

    ai_index = section_page(
        pages, r"^\s*(?:\d+(?:\.\d+)*\s*)?AI\s*工具使用声明(?:\s*[:：])?(?:\s|$)"
    )
    references_index = section_page(pages, r"^\s*(?:参考文献|references)(?:\s*[:：])?(?:\s|$)")
    core_end_candidates = [index for index in (ai_index, references_index, appendix_index) if index is not None]
    core_end = min(core_end_candidates) if core_end_candidates else len(pages)
    core_start = problem_index if problem_index is not None else body_start_index
    core_argument_pages = max(core_end - core_start, 0)
    if profile == "cumcm" and text_available:
        voice_text = "\n".join(pages[core_start:core_end])
        voice_findings = audit_competition_paper_voice(
            voice_text, expected_questions=expected_questions
        )
        quality_warnings.extend(voice_findings["quality_warn"])
        manual_checks.extend(voice_findings["manual_check"])
    if profile == "cumcm":
        flow_records, flow_available = audit_page_flow(path, range(core_start, core_end))
        if not flow_available:
            manual_checks.append(
                "CUMCM profile 无法取得 PyMuPDF 页面文字/图像/绘图几何，"
                "Page-Flow/Whitespace Pass 未运行；请结合联系表人工复核"
            )
        else:
            sparse = [
                record for record in flow_records
                if record["low_coverage"] or record["large_internal_gap"]
            ]
            if sparse:
                locations = "；".join(
                    f"第{int(record['page_index']) + 1}页（内容区间并集覆盖率约 {float(record['coverage']):.0%}，"
                    f"最大内部连续空白约 {float(record['largest_internal_gap']):.0%}）"
                    for record in sparse
                )
                quality_warnings.append(
                    "Page-Flow/Whitespace Pass 启发式候选："
                    + locations
                    + "；内容区间并集覆盖率低于约 60%或最大内部连续空白高于约 25%，仅是经验定位，"
                    "请结合约 6 页联系表和异常页原尺寸复核；该提示不是官方规则或阻断项"
                )
            visual_candidates = [record for record in flow_records if record["visual_dominant"]]
            if visual_candidates:
                locations = "；".join(
                    f"第{int(record['page_index']) + 1}页（内容区间并集覆盖率约 {float(record['coverage']):.0%}，"
                    f"文本 {int(record['text_chars'])} 字符，图像 {int(record['image_count'])}，"
                    f"矢量绘图 {int(record['drawing_count'])}）"
                    for record in visual_candidates
                )
                quality_warnings.append(
                    "Page-Flow/Whitespace 图表主导/正文叙事稀少候选："
                    + locations
                    + "；即使覆盖率高也请检查图表孤页、图文相邻关系与固定浮动；"
                    "该提示是 QUALITY_WARN 启发式定位，不是官方规则或阻断项"
                )
    if formal_structure_audit:
        manual_checks.append(
            "Semantic Emphasis 需人工核对：中文黑体与图像型 PDF 字体层可能不可靠；"
            "请检查标题样式、摘要任务锚点、正文短语义锚点，并避免整段或孤立数字过粗"
        )
    if text_available:
        if references_index is None:
            official_failures.append("未识别到参考文献；论文应包含参考文献部分")
        if ai_index is None:
            official_failures.append("未识别到 AI 工具使用声明；当前 2026 规则要求所有参赛队在参考文献之前声明")
        elif references_index is not None and ai_index > references_index:
            official_failures.append("AI 工具使用声明位于参考文献之后；当前 2026 规则要求置于参考文献之前")
        if re.search(r"(?m)^\s*(?:[一二三四五六七八九十]+|\d+)\s*[、.．]\s*AI\s*工具使用声明\s*$", first_pages):
            skill_failures.append("AI 工具使用声明不得作为编号的模型论文叙事章节；仅按当届规则在指定位置加入")
    else:
        manual_checks.append("AI 工具使用声明和参考文献无法由文本层确认；请人工核对")
    if (strict_structure or award_style_audit) and text_available:
        structure_details = audit_structure_details(
            pages,
            expected_questions=expected_questions,
            allow_placeholders=allow_placeholders,
            check_appendix_content=True,
            require_seven_chapter=strict_structure,
        )
        skill_failures.extend(structure_details["skill_fail"])
        quality_warnings.extend(structure_details["quality_warn"])
        manual_checks.extend(structure_details["manual_check"])
    elif expected_questions is not None and text_available:
        # The two explicit expected-question checks are useful even when the
        # caller does not request the complete seven-chapter shell audit.
        quality_warnings.extend(audit_question_requirement_labels(pages, expected_questions))
        mapping_failures = audit_appendix_question_mappings(pages, expected_questions)
        if allow_placeholders:
            quality_warnings.extend(mapping_failures)
        else:
            skill_failures.extend(mapping_failures)
        quality_warnings.extend(audit_appendix_question_content(pages, expected_questions))

    full_text = "\n".join(pages)
    if profile == "cumcm" and text_available:
        paper_end = references_index if references_index is not None else appendix_index
        paper_body = "\n".join(pages[:paper_end]) if paper_end is not None else full_text
        internal_hits = find_internal_paper_terms(paper_body)
        if internal_hits:
            skill_failures.append(
                "正文泄露内部工作流术语：" + "、".join(internal_hits)
                + "；必须改写为数学对象、证据或结论语言"
            )
    placeholder_pattern = (
        r"\[\s*请\s*替换\s*[:：][^\]\n]*\]"
        r"|请\s*替换(?:\s*[:：]|为)"
        r"|XXX|XX\.XX|X\.X%|关键词\s*1|……|按实际填写|\b(?:TODO|TBD)\b"
    )
    if re.search(placeholder_pattern, full_text, re.IGNORECASE):
        message = "检测到模板占位内容，必须替换为本题真实模型、结果和材料"
        if allow_placeholders:
            quality_warnings.append(message + "（本次仅验证模板结构）")
        elif formal_structure_audit:
            skill_failures.append(message + "；正式 CUMCM 结构审计不得保留占位内容")
        else:
            quality_warnings.append(message)
    identity_patterns = {
        "参赛队员": r"参赛队员\s*[:：]",
        "指导教师": r"指导教师\s*[:：]",
        "学校或学院字段": r"(?:学校|学院|院系)\s*[:：]\s*\S+",
        "赛区字段": r"赛区\s*[:：]\s*\S+",
        "队号字段": r"(?:队号|参赛密码)\s*[:：]\s*\S+",
    }
    leaks = [label for label, pattern in identity_patterns.items() if text_available and re.search(pattern, full_text)]
    author = metadata.get("author", "").strip()
    if author and author.lower() not in {"anonymous", "none", "unknown"}:
        leaks.append(f"PDF 作者元数据={author}")
    if leaks:
        official_failures.append("疑似身份泄露：" + "、".join(leaks))
    else:
        manual_checks.append("匿名扫描只覆盖显式身份字段和 PDF 作者元数据，仍需人工检查图像、文件名与支撑材料")

    for index, footer in enumerate(footers[:2], start=1):
        numbers = re.findall(r"(?<!\d)(\d{1,3})(?!\d)", footer)
        if numbers and str(index) not in numbers:
            manual_checks.append(f"第 {index} 页页脚未识别到连续页码 {index}；请人工核对页码与视觉位置")
        elif not numbers:
            manual_checks.append(f"第 {index} 页页码无法由文本层确认，请人工核对页脚")

    print(f"论文：{path}")
    main_matter_label = (
        f"主体稿（摘要至附录前，含参考文献）推定页数：{main_matter_pages}"
        if main_matter_pages is not None
        else "主体稿（摘要至附录前，含参考文献）推定页数：无法识别摘要"
    )
    chapter_spans = chapter_page_spans(pages, core_end)
    ledger = (
        f"摘要：{summary_pages if summary_pages is not None else '无法识别'}；"
        f"正文（问题重述至附录之前（无法识别时回退摘要后一页））：{profile_body_pages if profile == 'cumcm' and appendix_index is not None else body_pages if problem_index is not None else '回退/无法精确'}；"
        f"附录：{appendix_pages if appendix_pages is not None else '无法识别'}；总页数：{len(pages)}"
    )
    print(
        f"{ledger}；官方正文基线推定页数：{body_pages}；"
        f"{main_matter_label}；文件大小：{size_mib:.2f} MiB"
    )
    print(
        f"核心论证页（问题重述起至 AI 声明/参考文献/附录中最早者之前）：{core_argument_pages}；"
        f"主体稿/附录/总页数：{main_matter_pages if main_matter_pages is not None else '无法识别'}/"
        f"{appendix_pages if appendix_pages is not None else '无法识别'}/{len(pages)}"
    )
    if strict_structure:
        print("七章模板页码跨度：" + "；".join(chapter_spans))
    else:
        semantic_locations = []
        for name, pattern in STRUCTURE_HEADING_PATTERNS.items():
            matches = _structure_matches(pages, pattern)
            if matches:
                semantic_locations.append(f"{name}=第{matches[0][0] + 1}页")
        print(
            "可识别语义章节/功能覆盖定位："
            + ("；".join(semantic_locations) if semantic_locations else "未可靠识别，见人工检查")
        )
    for message in official_failures:
        print(f"[OFFICIAL_FAIL] {message}")
    for message in skill_failures:
        print(f"[SKILL_FAIL] {message}")
    for message in quality_warnings:
        print(f"[QUALITY_WARN] {message}")
    for message in manual_checks:
        print(f"[MANUAL_CHECK] {message}")
    blocking_count = len(official_failures) + len(skill_failures)
    if blocking_count:
        print(f"结论：未通过（{blocking_count} 个官方/Skill 阻断项）")
        return 1
    print("结论：无官方或 Skill 阻断项；仍须完成人工检查")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="审计 CUMCM 2026 电子论文 PDF；输出 OFFICIAL_FAIL/SKILL_FAIL/QUALITY_WARN/MANUAL_CHECK 四级结果"
    )
    parser.add_argument("paper", type=Path)
    parser.add_argument("--allow-placeholders", action="store_true", help="仅用于模板结构测试")
    parser.add_argument(
        "--min-main-matter-pages",
        type=int,
        help="主体稿最低页数：显式指定时作为 Skill 内部硬门；从摘要页至附录前一页，含摘要、正文和参考文献",
    )
    parser.add_argument(
        "--max-main-matter-pages",
        type=int,
        help="主体稿最高页数：显式指定时作为 Skill 内部硬门；从摘要页至附录前一页，含摘要、正文和参考文献",
    )
    parser.add_argument(
        "--max-pre-appendix-pages",
        type=int,
        help="兼容旧参数：等同 --max-main-matter-pages（已弃用）",
    )
    parser.add_argument(
        "--award-style-audit",
        action="store_true",
        help="推荐：启用 CUMCM 功能覆盖、表现与官方硬项审计，不固定正文一级章数；传入 --expected-questions 时检查任务覆盖与附录映射",
    )
    parser.add_argument(
        "--strict-structure",
        action="store_true",
        help="仅在用户、题面或模板明确要求时启用精确七章默认模板内部门；不是官方章节规则",
    )
    parser.add_argument(
        "--expected-questions",
        type=int,
        help="功能覆盖或严格七章审计下核对的实际问题数；应按本题题面填写",
    )
    parser.add_argument(
        "--profile",
        choices=("cumcm",),
        help="可选投稿 profile；显式 cumcm 时启用官方 A4/摘要/页数检查及 Skill 单栏、正文代码隔离审计",
    )
    parser.add_argument(
        "--min-body-pages",
        type=int,
        help="profile=cumcm 时显式指定为 Skill 内部最低页数硬门（无法识别时人工检查）；未指定时 26–29 页仅为质量建议",
    )
    parser.add_argument(
        "--max-body-pages",
        type=int,
        help="profile=cumcm 时显式指定为 Skill 内部最高页数硬门（官方正文 >30 页仍为 OFFICIAL_FAIL）；未指定则不增加内部硬门",
    )
    args = parser.parse_args()
    if not args.paper.is_file():
        print(f"[错误] 文件不存在：{args.paper}", file=sys.stderr)
        return 2
    if args.paper.suffix.lower() != ".pdf":
        print("[错误] 电子论文审计只接受 PDF", file=sys.stderr)
        return 2
    try:
        return audit(
            args.paper,
            allow_placeholders=args.allow_placeholders,
            min_main_matter_pages=args.min_main_matter_pages,
            max_main_matter_pages=args.max_main_matter_pages,
            max_pre_appendix_pages=args.max_pre_appendix_pages,
            strict_structure=args.strict_structure,
            expected_questions=args.expected_questions,
            award_style_audit=args.award_style_audit,
            profile=args.profile,
            min_body_pages=args.min_body_pages,
            max_body_pages=args.max_body_pages,
        )
    except Exception as exc:
        print(f"[错误] PDF 审计失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
