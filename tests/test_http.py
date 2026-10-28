"""The real HTTP path (urllib) against a local stand-in for GitLab; no network, no real token."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
from conftest import call


class Handler(BaseHTTPRequestHandler):
    seen: list[dict[str, Any]] = []

    def _reply(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _record(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        entry = {"method": self.command, "path": self.path, "token": self.headers.get("PRIVATE-TOKEN"), "body": body.decode()}
        self.seen.append(entry)
        return body

    def do_GET(self) -> None:
        self._record()
        if self.path.startswith("/api/v4/projects/grp%2Fproj/repository/branches/main"):
            self._reply(200, {"name": "main"})
        elif self.path.startswith("/api/v4/projects/grp%2Fproj/pipelines/7"):
            self._reply(200, {"id": 7, "status": "running", "ref": "main", "sha": "abc", "web_url": "http://x/7"})
        else:
            self._reply(404, {"message": "404 Not Found"})

    def do_POST(self) -> None:
        self._record()
        self._reply(201, {"id": 99, "created_at": "now"})

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def server_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[str]:
    Handler.seen = []
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{httpd.server_port}"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITLAB_URL", url)
    monkeypatch.setenv("GITLAB_PROJECT", "grp/proj")
    monkeypatch.setenv("GITLAB_API_KEY", "glpat-local")
    yield url
    httpd.shutdown()
    httpd.server_close()


def test_get_over_real_http(server_url: str) -> None:
    text, is_error = call("gitlab_pipeline_get", {"pipeline_id": 7})
    assert not is_error and json.loads(text)["status"] == "running"
    assert Handler.seen[0]["token"] == "glpat-local"


def test_post_over_real_http_sends_a_form_body(server_url: str) -> None:
    text, is_error = call("gitlab_issue_comment", {"iid": 5, "body": "a & b=c"})
    assert not is_error and json.loads(text)["note_id"] == 99
    sent = Handler.seen[-1]
    assert sent["method"] == "POST" and sent["body"] == "body=a+%26+b%3Dc"


def test_404_maps_to_exists_false_over_real_http(server_url: str) -> None:
    text, _ = call("gitlab_mr_create", {"source_branch": "main", "target_branch": "gone", "title": "t"})
    assert json.loads(text)["missing_branches"] == ["gone"]


def test_connection_failure_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITLAB_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("GITLAB_PROJECT", "g/p")
    monkeypatch.setenv("GITLAB_API_KEY", "t")
    monkeypatch.setenv("GITLAB_TIMEOUT", "2")
    text, is_error = call("gitlab_pipeline_get", {"pipeline_id": 1})
    assert is_error and "GET pipelines/1" in text
