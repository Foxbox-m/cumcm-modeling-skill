#!/usr/bin/env python3
"""Expand the canonical CUMCM paper template for an explicit question count.

The LaTeX route deliberately treats ``cumcm_template.tex`` as the source of
truth.  Only content between its question markers is expanded; text outside
those markers (preamble, package choices, and shared guidance) is preserved.
The Word route delegates to :mod:`generate_word_template` so the two routes
keep the same question-aware structure and styles.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[2]
TEX_TEMPLATE = RUNTIME_ROOT / "assets/paper-template/cumcm_template.tex"
WORD_GENERATOR = Path(__file__).with_name("generate_word_template.py")


def question_name(index: int) -> str:
    """Return the Chinese ordinal used by the maintained template."""

    digits = "一二三四五六七八九十"
    return digits[index - 1] if 1 <= index <= len(digits) else str(index)


def appendix_label(index: int) -> str:
    value = index
    label = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        label = chr(ord("A") + remainder) + label
    return label


def _replace_marker(source: str, marker: str, content: str) -> str:
    """Replace one marker body while retaining exactly one marker pair.

    Exact-line markers make this intentionally conservative: if a template is
    malformed or has been duplicated, fail instead of silently rewriting a
    larger part of the document.
    """

    start = f"% <CUMCM-QUESTIONS:{marker}>"
    end = f"% </CUMCM-QUESTIONS:{marker}>"
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError(f"模板标记 {marker} 必须各出现一次")
    start_at = source.index(start)
    end_at = source.index(end, start_at + len(start))
    if source.find(start, start_at + len(start)) != -1 or source.find(end, end_at + len(end)) != -1:
        raise ValueError(f"模板标记 {marker} 顺序无效")
    if end_at < start_at:
        raise ValueError(f"模板标记 {marker} 顺序无效")
    # Keep the original marker lines, including their comment syntax.
    return source[: start_at + len(start)] + "\n" + content.rstrip() + "\n" + source[end_at:]


def _abstract_body(questions: int) -> str:
    return "\n\n".join(
        f"\\placeholder{{针对问题{question_name(index)}：按困难→模型/关键求解→正式结果→一句现象/机制组织，只保留一项关键验证，并给出可核对的量化结果或结构性结论。}}\\par"
        for index in range(1, questions + 1)
    )


def _requirements_body(questions: int) -> str:
    return "\n".join(
        f"    \\item \\placeholder{{问题{question_name(index)}：只重述本问输入、输出、硬约束和交付量，不提前给出模型或答案。}}"
        for index in range(1, questions + 1)
    )


def _analysis_body(questions: int) -> str:
    blocks = []
    for index in range(1, questions + 1):
        question = question_name(index)
        blocks.append(
            "\n".join(
                (
                    f"\\subsection{{问题{question}的分析（按题面替换）}}",
                    f"\\placeholder{{第一自然句直接说明问题{question}的对象、动作或输出；先判断 Cascade/Parallel/Hybrid（级联/并列/混合），再按真实关系说明困难、数学表示、求解路线以及结果与验证出口，不能只列算法名。}}",
                )
            )
        )
    return "\n".join(blocks)


def _model_body(questions: int) -> str:
    blocks = []
    for index in range(1, questions + 1):
        question = question_name(index)
        blocks.append(
            "\n".join(
                (
                    f"\\subsection{{问题{question}的模型建立与求解（按题面替换）}}",
                    "\\placeholder{填写：最短充分直觉引线、目标/输入、模型、求解、正式结果、结果现象/机制、必要局部验证与直接作答。}",
                    "\\placeholder{复核：真实 Cascade/Parallel/Hybrid（级联/并列/混合）关系、基线缺口、活跃约束、局部简化依据与实现一致性。}",
                    "\\subsubsection{模型建立：请替换为当前题的数学对象、关系或约束标题}",
                    "\\placeholder{从现象或短直觉立即进入数学对象、关系或约束；纯解析、极短或真实级联任务可合并功能层，但模型/推导仍须可定位。}",
                    "\\subsubsection{求解与计算结果：请替换为当前题的求解动作或结果标题}",
                    "\\placeholder{交代求解设置与正式结果，并解释结果对应的题目现象或主导机制；算法名称不能替代模型和适配理由。}",
                    "\\subsubsection{结果分析与局部检验：请替换为当前题的证据或边界标题}",
                    "\\placeholder{仅在风险尚未关闭时保留足以关闭主要风险的必要局部验证；若不同主要风险需要不同证据，分别保留。局部简化依据放在首次依赖处，最后直接回答题面。}",
                )
            )
        )
    return "\n\n".join(blocks)


def _appendix_body(questions: int) -> str:
    entries = []
    for index in range(1, questions + 1):
        entries.append(
            "\n".join(
                (
                    f"\\subsection*{{附录 {appendix_label(index)}：问题{question_name(index)}求解程序及说明}}",
                    f"\\placeholder{{先说明本问特异核心函数/函数签名和主求解逻辑，并交代对应正文 5.{index} 节的输入、输出和功能；再纳入完整执行源文件，不得手抄、删行、简化或只放文件索引。}}",
                )
            )
        )
    return "\n\n".join(entries)


def _shared_appendix_body(questions: int) -> str:
    functions_label = appendix_label(questions + 1)
    materials_label = appendix_label(questions + 2)
    return "\n".join(
        (
            f"\\subsection*{{附录 {functions_label}：公共函数与共享模块}}",
            "\\placeholder{在各问特异核心逻辑之后只后置一次共享完整代码；列各问题实际调用的公共函数和共享模块，并说明题号到入口脚本的对应关系。}",
            "",
            f"\\subsection*{{附录 {materials_label}：提交支撑材料文件清单}}",
            "\\placeholder{只列真正提交的题目代码、共享函数、结果文件和必要数据；不列项目简报、内部账本、检查日志、QA 预览或内部清单。}",
        )
    )


def expand_tex(template: str, questions: int) -> str:
    if questions <= 0:
        raise ValueError("questions 必须是正整数")
    expanded = template
    expanded = _replace_marker(expanded, "ABSTRACT", _abstract_body(questions))
    expanded = _replace_marker(expanded, "REQUIREMENTS", _requirements_body(questions))
    expanded = _replace_marker(expanded, "ANALYSIS", _analysis_body(questions))
    expanded = _replace_marker(expanded, "MODELS", _model_body(questions))
    expanded = _replace_marker(expanded, "APPENDIX", _appendix_body(questions))
    expanded = _replace_marker(expanded, "APPENDIX-SHARED", _shared_appendix_body(questions))
    return expanded


def generate_tex(output: Path, *, questions: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    template = TEX_TEMPLATE.read_text(encoding="utf-8")
    output.write_text(expand_tex(template, questions), encoding="utf-8")


def _load_word_generator():
    spec = importlib.util.spec_from_file_location("cumcm_word_template_generator", WORD_GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 Word 生成器：{WORD_GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate_docx(output: Path, *, questions: int) -> None:
    module = _load_word_generator()
    module.build_document(output, questions=questions)


def main() -> int:
    parser = argparse.ArgumentParser(description="按显式问题数生成 CUMCM Word/LaTeX 论文 scaffold")
    parser.add_argument("--profile", choices=("cumcm",), default="cumcm")
    parser.add_argument("--questions", type=int, default=1, help="题面显式问题数，必须为正整数")
    parser.add_argument("--format", choices=("tex", "docx"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.questions <= 0:
        parser.error("--questions 必须是正整数")
    try:
        if args.format == "tex":
            generate_tex(args.output, questions=args.questions)
        else:
            generate_docx(args.output, questions=args.questions)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        parser.error(str(exc))
    print(f"已生成 {args.profile} {args.format} scaffold：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
