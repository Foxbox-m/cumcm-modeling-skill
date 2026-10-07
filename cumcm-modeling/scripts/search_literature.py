#!/usr/bin/env python3
"""Discover candidate literature metadata from Crossref and Semantic Scholar.

This tool is intentionally a discovery layer: every result is marked
``candidate_unverified`` and nothing is written to a citation ledger or fetched
as full text.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = "cumcm-modeling-skill/1.0 (literature discovery; metadata only)"
DEFAULT_CROSSREF_BASE = "https://api.crossref.org/works"
DEFAULT_S2_BASE = "https://api.semanticscholar.org/graph/v1/paper/search"


class ProviderError(RuntimeError):
    pass


def normalize_title(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", " ", value.casefold()).strip()


def parse_year(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, list) and value and isinstance(value[0], int):
        return value[0]
    if isinstance(value, str):
        match = re.search(r"\b(19|20)\d{2}\b", value)
        if match:
            return int(match.group(0))
    return None


def year_from_crossref(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        date = item.get(key, {})
        year = parse_year(date.get("date-parts") if isinstance(date, dict) else None)
        if year is not None:
            return year
    return None


def request_json(
    url: str,
    *,
    headers: dict[str, str],
    timeout: float = 5.0,
    retries: int = 0,
) -> Any:
    """Fetch one JSON response with a deliberately bounded retry budget."""
    for attempt in range(retries + 1):
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                try:
                    return json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ProviderError(f"返回内容不是有效 JSON：{exc}") from None
        except HTTPError as exc:
            retry_after = exc.headers.get("Retry-After", "")
            if (exc.code == 403 or exc.code == 429 or 500 <= exc.code < 600) and attempt < retries:
                try:
                    delay = float(retry_after) if retry_after else 0.5
                except ValueError:
                    delay = 0.5
                if not math.isfinite(delay):
                    delay = 0.5
                delay = min(max(delay, 0.0), 2.0)
                time.sleep(delay)
                continue
            if exc.code == 403:
                raise ProviderError("HTTP 403：Provider 拒绝请求") from None
            raise ProviderError(f"HTTP {exc.code}：Provider 请求失败") from None
        except (URLError, TimeoutError, OSError) as exc:
            if attempt < retries:
                time.sleep(0.5)
                continue
            raise ProviderError(f"网络或超时错误：{exc}") from None
    raise ProviderError("Provider 请求失败：重试预算耗尽")


def crossref(query: str, limit: int, from_year: int | None, until_year: int | None, base: str, mailto: str | None, *, timeout: float, retries: int) -> list[dict[str, Any]]:
    params: dict[str, str] = {"query": query, "rows": str(limit)}
    if from_year is not None:
        params["filter"] = f"from-pub-date:{from_year}-01-01"
    if until_year is not None:
        suffix = params.get("filter", "")
        params["filter"] = f"{suffix},until-pub-date:{until_year}-12-31" if suffix else f"until-pub-date:{until_year}-12-31"
    if mailto:
        params["mailto"] = mailto
    payload = request_json(base.rstrip("/") + "?" + urlencode(params), headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=timeout, retries=retries)
    items = payload.get("message", {}).get("items", []) if isinstance(payload, dict) else []
    results: list[dict[str, Any]] = []
    for item in items[:limit]:
        title = (item.get("title") or [""])[0]
        authors = []
        for author in item.get("author") or []:
            name = " ".join(part for part in (author.get("given"), author.get("family")) if part)
            if name:
                authors.append(name)
        doi = item.get("DOI") or None
        results.append({
            "provider": "crossref", "title": title, "authors": authors,
            "year": year_from_crossref(item), "venue": (item.get("container-title") or [None])[0],
            "doi": doi, "url": item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
            "type": item.get("type"), "citation_count": None,
            "discovery_status": "candidate_unverified",
        })
    return results


def semantic_scholar(query: str, limit: int, from_year: int | None, until_year: int | None, base: str, api_key: str | None, *, timeout: float, retries: int) -> list[dict[str, Any]]:
    params: dict[str, str] = {"query": query, "limit": str(limit), "fields": "title,authors,year,venue,externalIds,url,publicationTypes,citationCount"}
    if from_year is not None:
        params["year"] = str(from_year) + "-"
    if until_year is not None:
        params["year"] = f"{from_year or ''}-{until_year}"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    payload = request_json(base.rstrip("/") + "?" + urlencode(params), headers=headers, timeout=timeout, retries=retries)
    items = payload.get("data", []) if isinstance(payload, dict) else []
    results: list[dict[str, Any]] = []
    for item in items[:limit]:
        external = item.get("externalIds") or {}
        doi = external.get("DOI") or None
        results.append({
            "provider": "semantic-scholar", "title": item.get("title") or "",
            "authors": [author.get("name") for author in item.get("authors") or [] if author.get("name")],
            "year": item.get("year"), "venue": item.get("venue") or None,
            "doi": doi, "url": item.get("url") or (f"https://doi.org/{doi}" if doi else None),
            "type": (item.get("publicationTypes") or [None])[0],
            "citation_count": item.get("citationCount"), "discovery_status": "candidate_unverified",
        })
    return results


def deduplicate(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    by_doi: dict[str, int] = {}
    by_title: dict[str, int] = {}
    for result in results:
        doi = str(result.get("doi") or "").casefold().strip()
        title = normalize_title(str(result.get("title") or ""))
        index = by_doi.get(doi) if doi else by_title.get(title)
        if index is None:
            output.append(result)
            index = len(output) - 1
            if doi:
                by_doi[doi] = index
            if title:
                by_title[title] = index
            continue
        existing = output[index]
        # Prefer a DOI-bearing record, then retain non-empty metadata from either provider.
        if not existing.get("doi") and doi:
            existing["doi"] = result["doi"]
        for key in ("venue", "url", "year", "type", "citation_count"):
            if existing.get(key) is None and result.get(key) is not None:
                existing[key] = result[key]
        existing["provider"] = "+".join(sorted(set(str(existing["provider"]).split("+")) | {str(result["provider"])}))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="发现外部文献候选元数据（不代表内容已核验）")
    parser.add_argument("query")
    parser.add_argument("--provider", choices=("crossref", "semantic-scholar", "both"), default="crossref")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--retries", type=int, choices=(0, 1), default=0, help="失败时最多额外尝试一次")
    parser.add_argument("--from-year", "--start-year", dest="from_year", type=int)
    parser.add_argument("--until-year", "--end-year", dest="until_year", type=int)
    parser.add_argument("--mailto")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--crossref-base-url", default=DEFAULT_CROSSREF_BASE, help=argparse.SUPPRESS)
    parser.add_argument("--semantic-scholar-base-url", default=DEFAULT_S2_BASE, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit 必须大于 0")
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        parser.error("--timeout-seconds 必须大于 0")
    if args.from_year is not None and args.until_year is not None and args.from_year > args.until_year:
        parser.error("起始年份不能晚于结束年份")
    providers = ("crossref", "semantic-scholar") if args.provider == "both" else (args.provider,)
    results: list[dict[str, Any]] = []
    warnings: list[str] = []
    successes = 0
    for provider in providers:
        try:
            if provider == "crossref":
                found = crossref(args.query, args.limit, args.from_year, args.until_year, args.crossref_base_url, args.mailto, timeout=args.timeout_seconds, retries=args.retries)
            else:
                found = semantic_scholar(args.query, args.limit, args.from_year, args.until_year, args.semantic_scholar_base_url, os.environ.get("SEMANTIC_SCHOLAR_API_KEY"), timeout=args.timeout_seconds, retries=args.retries)
            results.extend(found)
            successes += 1
        except ProviderError as exc:
            warnings.append(f"{provider} 失败：{exc}")
    results = deduplicate(results) if args.provider == "both" else results
    network_status = "ok" if successes == len(providers) else ("partial" if successes else "unavailable")
    fallback_action = "stop_external_retries_and_use_verified_evidence" if network_status == "unavailable" else None
    payload = {
        "query": args.query, "provider": args.provider, "results": results,
        "warnings": warnings, "network_status": network_status,
        "fallback_action": fallback_action,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"候选 {len(results)} 条；discovery_status=candidate_unverified")
        for result in results:
            print(f"- {result['title']} | {result.get('year') or '年份未知'} | {result.get('doi') or result.get('url') or '无 DOI/URL'}")
        for warning in warnings:
            print(f"[警告] {warning}", file=sys.stderr)
        if network_status == "unavailable":
            print("[回退] 停止本轮联网重试，改用题面、Skill 内置蒸馏先验和已核验来源；新的外部主张标为待核验。", file=sys.stderr)
        elif network_status == "partial":
            print("[提示] 某 Provider 失败；保留成功 Provider 的候选，不自动重试，请人工核验。", file=sys.stderr)
    if successes == 0:
        if args.json:
            print("", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(2)
