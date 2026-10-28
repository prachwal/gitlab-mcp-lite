from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from gitlab_mcp_lite import client, server


class FakeGitLab:
    """Records requests and answers from a route table.

    ``routes`` maps ``"METHOD path-suffix"`` (matched against the URL without the query) to a JSON-able
    payload, or to an int that is raised as an HTTP error with that code.
    """

    def __init__(self) -> None:
        self.routes: dict[str, Any] = {}
        self.calls: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request) -> bytes:
        self.calls.append(request)
        path = request.full_url.split("?")[0]
        for key, payload in self.routes.items():
            method, _, suffix = key.partition(" ")
            if method == request.get_method() and path.endswith(suffix):
                if isinstance(payload, int):
                    raise urllib.error.HTTPError(request.full_url, payload, "err", {}, io.BytesIO(b'{"message":"nope"}'))  # type: ignore[arg-type]
                return json.dumps(payload).encode()
        raise urllib.error.HTTPError(request.full_url, 404, "not found", {}, io.BytesIO(b"{}"))  # type: ignore[arg-type]

    def last(self) -> urllib.request.Request:
        return self.calls[-1]

    def body(self) -> dict[str, list[str]]:
        import urllib.parse

        data = self.last().data
        assert isinstance(data, bytes)
        return urllib.parse.parse_qs(data.decode())


@pytest.fixture
def gitlab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeGitLab:
    for key in ("GITLAB_API_KEY", "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_PROJECT", "GITLAB_MCP_READ_ONLY", "GITLAB_TIMEOUT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITLAB_URL", "https://gitlab.example.com")
    monkeypatch.setenv("GITLAB_PROJECT", "grp/proj")
    monkeypatch.setenv("GITLAB_API_KEY", "glpat-secret")
    fake = FakeGitLab()
    monkeypatch.setattr(client, "_send", fake)
    return fake


def call(name: str, arguments: dict[str, Any] | None = None, *, read_only: bool = False) -> tuple[str, bool]:
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments or {}}},
        read_only=read_only,
    )
    assert response is not None
    result = response["result"]
    return result["content"][0]["text"], result["isError"]
