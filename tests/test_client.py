from __future__ import annotations

from pathlib import Path

import pytest
from conftest import FakeGitLab

from gitlab_mcp_lite import client


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("git@gitlab.com:grp/sub/proj.git", ("gitlab.com", "grp/sub/proj")),
        ("ssh://git@git.example.com:2222/grp/proj.git", ("git.example.com", "grp/proj")),
        ("https://gitlab.com/grp/proj.git", ("gitlab.com", "grp/proj")),
        ("https://oauth2:tok@gitlab.example.com:8443/grp/proj", ("gitlab.example.com:8443", "grp/proj")),
    ],
)
def test_parse_remote(url: str, expected: tuple[str, str]) -> None:
    assert client.parse_remote(url) == expected


def test_parse_remote_rejects_garbage() -> None:
    with pytest.raises(client.GitLabError, match="unsupported"):
        client.parse_remote("not a url")


def test_request_builds_scoped_url_and_sends_the_token(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /pipelines/5"] = {"id": 5}
    assert client.request("pipelines/5") == {"id": 5}
    sent = gitlab.last()
    assert sent.full_url == "https://gitlab.example.com/api/v4/projects/grp%2Fproj/pipelines/5"
    assert sent.get_header("Private-token") == "glpat-secret"


def test_get_params_go_in_the_query_and_lists_are_joined(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /issues"] = []
    client.request("issues", params={"labels": ["a", "b"], "state": "all", "skip": None})
    assert gitlab.last().full_url.endswith("/issues?labels=a%2Cb&state=all")


def test_post_params_are_form_encoded(gitlab: FakeGitLab) -> None:
    gitlab.routes["POST /issues/1/notes"] = {"id": 1}
    client.request("issues/1/notes", "POST", {"body": "a+b & c"})
    assert gitlab.body() == {"body": ["a+b & c"]}
    assert gitlab.last().get_header("Content-type") == "application/x-www-form-urlencoded"


def test_project_argument_overrides_environment(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /jobs/1"] = {}
    client.request("jobs/1", project="other/repo")
    assert "/projects/other%2Frepo/jobs/1" in gitlab.last().full_url


def test_http_errors_become_gitlab_errors_without_the_token(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /jobs/9"] = 403
    with pytest.raises(client.GitLabError, match="HTTP 403") as info:
        client.request("jobs/9")
    assert "glpat-secret" not in str(info.value)


def test_exists_distinguishes_404_from_other_failures(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /repository/branches/main"] = {"name": "main"}
    gitlab.routes["GET /repository/branches/boom"] = 500
    assert client.exists("repository/branches/main") is True
    assert client.exists("repository/branches/missing") is False
    with pytest.raises(client.GitLabError):
        client.exists("repository/branches/boom")


def test_token_precedence_and_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in client.TOKEN_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    assert client.token_source() is None
    (tmp_path / ".env").write_text('# comment\nexport GITLAB_TOKEN="from-dotenv"\nOTHER=1\n', encoding="utf-8")
    token, where = client.token_source() or ("", "")
    assert token == "from-dotenv" and "GITLAB_TOKEN" in where
    monkeypatch.setenv("GITLAB_API_KEY", "from-env")
    token, where = client.token_source() or ("", "")
    assert token == "from-env" and where == "environment variable GITLAB_API_KEY"


def test_dotenv_is_found_in_the_git_root_from_a_subdirectory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in client.TOKEN_KEYS:
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".env").write_text("GITLAB_API_KEY=root-token\n", encoding="utf-8")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert (client.token_source() or ("", ""))[0] == "root-token"


def test_missing_token_is_a_clear_error(gitlab: FakeGitLab, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITLAB_API_KEY")
    with pytest.raises(client.GitLabError, match="no GitLab token"):
        client.request("jobs/1")


def test_resolve_uses_origin_when_nothing_is_configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    for key in ("GITLAB_URL", "GITLAB_PROJECT"):
        monkeypatch.delenv(key, raising=False)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", "git@git.corp.example:team/app.git"], check=True)
    target = client.resolve(cwd=tmp_path)
    assert target == client.Target(api="https://git.corp.example/api/v4", project="team/app")


def test_resolve_fails_clearly_without_any_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("GITLAB_URL", "GITLAB_PROJECT"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(client.GitLabError, match="GITLAB_URL"):
        client.resolve(cwd=tmp_path)
