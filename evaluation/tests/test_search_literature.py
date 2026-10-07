from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "cumcm-modeling/scripts/search_literature.py"


class FixtureHandler(BaseHTTPRequestHandler):
    mode = "ok"
    counts: dict[str, int] = {}

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        self.counts[path] = self.counts.get(path, 0) + 1
        if self.mode == "429" or (self.mode == "crossref-429" and path.endswith("/works")):
            self.send_response(429)
            self.send_header("Retry-After", "0")
            self.end_headers()
            return
        if self.mode == "nonjson":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"not json")
            return
        if path.endswith("/works"):
            payload = {"message": {"items": [{
                "title": ["A Candidate Paper"], "author": [{"given": "Ada", "family": "Lovelace"}],
                "published": {"date-parts": [[2022]]}, "container-title": ["Test Journal"],
                "DOI": "10.1000/test", "URL": "https://doi.org/10.1000/test", "type": "journal-article",
            }]}}
        else:
            payload = {"data": [{
                "title": "A Candidate Paper", "authors": [{"name": "Ada Lovelace"}], "year": 2022,
                "venue": "Test Journal", "externalIds": {"DOI": "10.1000/test"},
                "url": "https://doi.org/10.1000/test", "publicationTypes": ["JournalArticle"],
                "citationCount": 4,
            }]}
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


def run_server(mode: str = "ok"):
    FixtureHandler.mode = mode
    FixtureHandler.counts = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def run(server, *args: str):
    base = f"http://127.0.0.1:{server.server_port}"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--crossref-base-url", base + "/works", "--semantic-scholar-base-url", base + "/paper/search"],
        text=True,
        capture_output=True,
        check=False,
    )


def stop_server(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()


def test_crossref_json_is_candidate_metadata_only():
    server, _ = run_server()
    try:
        result = run(server, "candidate", "--provider", "crossref", "--limit", "1", "--json")
    finally:
        stop_server(server)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["results"][0]["provider"] == "crossref"
    assert payload["results"][0]["discovery_status"] == "candidate_unverified"
    assert payload["results"][0]["citation_count"] is None
    assert payload["network_status"] == "ok"
    assert payload["fallback_action"] is None


def test_both_deduplicates_by_doi_and_keeps_metadata():
    server, _ = run_server()
    try:
        result = run(server, "candidate", "--provider", "both", "--limit", "1", "--json")
    finally:
        stop_server(server)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert len(payload["results"]) == 1
    assert payload["results"][0]["provider"] == "crossref+semantic-scholar"
    assert payload["results"][0]["citation_count"] == 4


def test_provider_errors_are_clear_and_do_not_print_traceback():
    server, _ = run_server("429")
    try:
        result = run(server, "candidate", "--provider", "crossref", "--limit", "1", "--json")
    finally:
        stop_server(server)
    assert result.returncode != 0
    assert "HTTP 429" in result.stdout or "HTTP 429" in result.stderr
    assert "Traceback" not in result.stdout + result.stderr
    assert FixtureHandler.counts["/works"] == 1
    payload = json.loads(result.stdout)
    assert payload["network_status"] == "unavailable"
    assert payload["fallback_action"] == "stop_external_retries_and_use_verified_evidence"


def test_explicit_retry_attempts_exactly_twice():
    server, _ = run_server("429")
    try:
        result = run(server, "candidate", "--provider", "crossref", "--limit", "1", "--retries", "1", "--json")
    finally:
        stop_server(server)
    assert result.returncode != 0
    assert FixtureHandler.counts["/works"] == 2


def test_both_one_provider_failure_is_partial():
    server, _ = run_server("crossref-429")
    try:
        result = run(server, "candidate", "--provider", "both", "--limit", "1", "--json")
    finally:
        stop_server(server)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["network_status"] == "partial"
    assert payload["fallback_action"] is None
    assert len(payload["results"]) == 1


def test_partial_text_keeps_candidates_without_full_fallback():
    server, _ = run_server("crossref-429")
    try:
        result = run(server, "candidate", "--provider", "both", "--limit", "1")
    finally:
        stop_server(server)
    assert result.returncode == 0
    assert "某 Provider 失败" in result.stderr
    assert "不自动重试" in result.stderr
    assert "停止本轮联网重试" not in result.stderr
