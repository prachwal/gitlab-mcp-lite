from __future__ import annotations

import io
import json
import tomllib

import pytest
from conftest import FakeGitLab

from gitlab_mcp_lite import cli, clients, protocol, server


def test_check_reports_without_printing_the_token(gitlab: FakeGitLab, capsys: pytest.CaptureFixture[str]) -> None:
    gitlab.routes["GET /api/v4/version"] = {"version": "17.0.0"}
    gitlab.routes["GET /api/v4/projects/grp%2Fproj"] = {"id": 42, "path_with_namespace": "grp/proj"}
    assert cli.main(["check"]) == 0
    out = capsys.readouterr().out
    assert "grp/proj" in out and "GitLab 17.0.0" in out and "environment variable GITLAB_API_KEY" in out
    assert "glpat-secret" not in out


def test_check_fails_when_the_token_is_missing(
    gitlab: FakeGitLab, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GITLAB_API_KEY")
    assert cli.main(["check"]) == 1
    assert "NOT FOUND" in capsys.readouterr().out


def test_check_reports_api_errors(gitlab: FakeGitLab, capsys: pytest.CaptureFixture[str]) -> None:
    gitlab.routes["GET /api/v4/version"] = 401
    assert cli.main(["check"]) == 1
    assert "HTTP 401" in capsys.readouterr().err


@pytest.mark.parametrize("name", ["vscode", "cursor", "gemini", "generic"])
def test_json_snippets(name: str) -> None:
    data = json.loads(clients.snippet(name, url="https://gl.example", project="g/p", read_only=True))
    entry = data["servers" if name == "vscode" else "mcpServers"]["gitlab"]
    assert entry["command"] == "uvx" and entry["args"] == ["gitlab-mcp-lite", "--read-only"]
    assert entry["env"] == {"GITLAB_URL": "https://gl.example", "GITLAB_PROJECT": "g/p"}
    assert (entry.get("type") == "stdio") == (name == "vscode")


def test_codex_snippet_is_valid_toml_and_has_no_token() -> None:
    text = clients.snippet("codex", source="/src/glm", url="https://gl.example")
    data = tomllib.loads(text)["mcp_servers"]["gitlab"]
    assert data["args"] == ["--from", "/src/glm", "gitlab-mcp-lite"] and data["env"] == {"GITLAB_URL": "https://gl.example"}
    assert "TOKEN" not in text and "API_KEY" not in text


def test_claude_snippet() -> None:
    text = clients.snippet("claude", project="g/p")
    assert "claude mcp add gitlab -e GITLAB_PROJECT=g/p -- uvx gitlab-mcp-lite" in text
    assert json.loads(text[text.index("{"):])["mcpServers"]["gitlab"]["env"] == {"GITLAB_PROJECT": "g/p"}


def test_snippet_command_prints_the_note_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["config-snippet", "vscode"]) == 0
    captured = capsys.readouterr()
    assert '"servers"' in captured.out and "token is not part" in captured.err


def test_read_only_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITLAB_MCP_READ_ONLY", raising=False)
    assert server.read_only_requested() is False
    monkeypatch.setenv("GITLAB_MCP_READ_ONLY", "yes")
    assert server.read_only_requested() is True
    assert server.read_only_requested(True) is True


def test_stdio_loop_roundtrip(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    lines = "garbage\n" + json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(lines))
    protocol.serve(tools=server.tool_table(), server_info=server.SERVER_INFO)
    replies = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert replies[0]["error"]["code"] == -32700
    assert replies[1]["result"]["serverInfo"]["name"] == "gitlab-mcp-lite"


def test_version_matches_pyproject() -> None:
    from pathlib import Path

    import gitlab_mcp_lite

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"] == gitlab_mcp_lite.__version__
