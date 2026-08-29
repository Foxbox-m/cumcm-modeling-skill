#!/usr/bin/env python3
"""Search the governed CUMCM corpus without loading the full Markdown index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
LEGACY_DEFAULT_METADATA = SKILL_ROOT.parent / "论文" / "00_目录与治理" / "语料元数据.json"
# A1R contains the most recent official display samples.  Their award-grade
# provenance is deliberately more cautious than confirmed A1, but they are
# the first style/method examples to inspect when recency is requested.
TAG_ORDER = {"A1R": 0, "A1": 1, "A1Q": 2, "M1": 3, "M3": 4, "A2": 5, "M2": 6, "E": 7, "G": 8}


def comma_values(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip().casefold() for item in value.split(",") if item.strip()}


def searchable_text(row: dict[str, Any]) -> str:
    fields = (
        "record_id",
        "source_tag",
        "subtype",
        "title",
        "year",
        "award_status",
        "verification_status",
        "topic",
        "format",
        "notes",
    )
    return " ".join(str(row.get(field, "")) for field in fields).casefold()


def matches(row: dict[str, Any], args: argparse.Namespace) -> bool:
    tags = comma_values(args.tag)
    years = comma_values(args.year)
    formats = comma_values(args.format)
    if tags and str(row.get("source_tag", "")).casefold() not in tags:
        return False
    if years and str(row.get("year", "")).casefold() not in years:
        return False
    if formats and str(row.get("format", "")).casefold() not in formats:
        return False
    if args.permission == "style" and not str(row.get("style_permission", "")).startswith("允许"):
        return False
    if args.permission == "method":
        permission = str(row.get("method_permission", ""))
        if permission.startswith("禁止") or permission.startswith("待转换"):
            return False
    terms = [term.casefold() for term in args.terms]
    if not terms:
        return True
    text = searchable_text(row)
    return any(term in text for term in terms) if args.any_term else all(term in text for term in terms)


def display_path(row: dict[str, Any]) -> str:
    return str(row.get("readable_derivative") or row.get("relative_path") or "")


def is_readable_pdf(row: dict[str, Any]) -> bool:
    return str(row.get("format", "")).casefold() == "pdf" or str(row.get("readable_derivative", "")).casefold().endswith(".pdf")


def coverage_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    layers: dict[str, dict[str, Any]] = {}
    for tag in ("A1", "A1Q", "A1R"):
        rows = [row for row in records if str(row.get("source_tag", "")) == tag]
        years: dict[str, int] = {}
        for row in rows:
            year = str(row.get("year", ""))
            years[year] = years.get(year, 0) + 1
        layer: dict[str, Any] = {"total": len(rows), "years": dict(sorted(years.items()))}
        if tag == "A1":
            layer["readable_pdf"] = sum(1 for row in rows if is_readable_pdf(row))
        layers[tag] = layer
    year_layers: dict[str, dict[str, int]] = {}
    for year in range(2018, 2026):
        year_layers[str(year)] = {
            tag: sum(1 for row in records if str(row.get("source_tag", "")) == tag and str(row.get("year", "")) == str(year))
            for tag in ("A1", "A1Q", "A1R")
        }
    gaps = [year for year, counts in year_layers.items() if sum(counts.values()) == 0]
    return {
        "A1": layers["A1"],
        "A1Q": {**layers["A1Q"], "label": "A1 调用层质量标签，奖级未核验"},
        "A1R": {**layers["A1R"], "label": "近年优先层，奖级未逐队匹配且内容质量未逐篇完成"},
        "year_layers_2018_2025": year_layers,
        "gap_years": [int(year) for year in gaps],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="按标签、年份、关键词检索 CUMCM 治理语料")
    parser.add_argument("terms", nargs="*", help="默认要求所有关键词均匹配")
    parser.add_argument("--any", dest="any_term", action="store_true", help="任一关键词匹配即可")
    parser.add_argument("--tag", help="逗号分隔，如 A1,M1,M3")
    parser.add_argument("--year", help="逗号分隔，如 2014,2015")
    parser.add_argument("--format", help="逗号分隔，如 pdf,doc")
    parser.add_argument(
        "--permission",
        choices=("style", "method"),
        help="按表现层或方法候选权限过滤；method 不代表内容质量已经审核",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--coverage", action="store_true", help="输出 A1/A1Q/A1R 覆盖审计，忽略关键词与 limit")
    metadata_group = parser.add_mutually_exclusive_group()
    metadata_group.add_argument("--metadata", type=Path, help="直接指定外部语料元数据 JSON")
    metadata_group.add_argument(
        "--corpus-root",
        type=Path,
        help="外部论文根目录；默认读取 PATH/00_目录与治理/语料元数据.json",
    )
    args = parser.parse_args()

    if args.corpus_root is not None:
        metadata_path = args.corpus_root / "00_目录与治理" / "语料元数据.json"
    elif args.metadata is not None:
        metadata_path = args.metadata
    else:
        metadata_path = LEGACY_DEFAULT_METADATA

    if not args.coverage:
        if args.limit < 1 or args.limit > 50:
            parser.error("--limit 必须在 1 到 50 之间")
        if not (args.terms or args.tag or args.year or args.format or args.permission):
            parser.error("普通检索至少需要一个关键词或显式筛选（--tag/--year/--format/--permission）；覆盖审计请使用 --coverage")
    if not metadata_path.is_file():
        print(
            f"[错误] 找不到可选外部语料元数据：{metadata_path}。"
            "外部论文库不是核心 Skill 的必需依赖；常规建模/写作无需它。"
            "若需要外部语料，请显式传 --corpus-root <CORPUS_ROOT> 或 --metadata <METADATA>。",
            file=sys.stderr,
        )
        return 2
    try:
        records = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[错误] 无法读取语料元数据：{exc}", file=sys.stderr)
        return 2
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        print("[错误] 语料元数据顶层必须是对象数组", file=sys.stderr)
        return 2

    if args.coverage:
        report = coverage_report(records)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"A1：{report['A1']['total']} 条，{report['A1']['readable_pdf']} 份可读 PDF；年份 {report['A1']['years']}")
            print(f"A1Q：{report['A1Q']['total']} 条；年份 {report['A1Q']['years']}；A1 调用层质量标签，奖级未核验")
            print(f"A1R：{report['A1R']['total']} 条；逐年 {report['A1R']['years']}；近年优先层，奖级未逐队匹配且内容质量未逐篇完成")
            for year, counts in report["year_layers_2018_2025"].items():
                print(f"{year}：A1={counts['A1']}，A1Q={counts['A1Q']}，A1R={counts['A1R']}")
            print(f"空缺年份：{report['gap_years']}")
        return 0

    selected = [row for row in records if matches(row, args)]
    selected.sort(
        key=lambda row: (
            TAG_ORDER.get(str(row.get("source_tag", "")), 99),
            -int(row["year"]) if str(row.get("year", "")).isdigit() else 0,
            str(row.get("record_id", "")),
        )
    )
    shown = selected[: args.limit]
    if args.json:
        payload = [
            {
                "id": row.get("record_id"),
                "tag": row.get("source_tag"),
                "year": row.get("year"),
                "topic": row.get("topic"),
                "title": row.get("title"),
                "status": row.get("verification_status"),
                "style_permission": row.get("style_permission"),
                "method_permission": row.get("method_permission"),
                "path": display_path(row),
            }
            for row in shown
        ]
        print(json.dumps({"matched": len(selected), "shown": payload}, ensure_ascii=False, indent=2))
    else:
        print(f"匹配 {len(selected)} 条；显示 {len(shown)} 条")
        for row in shown:
            print(
                f"{row.get('record_id')} | {row.get('year')} | {row.get('topic')} | "
                f"{row.get('title')}\n  {display_path(row)}"
            )
    return 0 if selected else 1


if __name__ == "__main__":
    raise SystemExit(main())
