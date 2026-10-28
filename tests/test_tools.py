from __future__ import annotations

import json

from conftest import FakeGitLab, call


def test_all_tools_are_listed_with_annotations() -> None:
    from gitlab_mcp_lite import server

    response = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert response is not None
    tools = {t["name"]: t for t in response["result"]["tools"]}
    assert len(tools) == 9 and all(n.startswith("gitlab_") for n in tools)
    assert tools["gitlab_issues_list"]["annotations"]["readOnlyHint"] is True
    assert tools["gitlab_mr_create"]["annotations"]["readOnlyHint"] is False


def test_read_only_mode_hides_the_write_tools(gitlab: FakeGitLab) -> None:
    from gitlab_mcp_lite import server

    response = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, read_only=True)
    assert response is not None
    names = {t["name"] for t in response["result"]["tools"]}
    assert names == {"gitlab_pipeline_get", "gitlab_pipeline_jobs", "gitlab_issues_list", "gitlab_issue_get", "gitlab_mr_list"}


def test_read_only_call_is_refused_as_unknown_tool() -> None:
    from gitlab_mcp_lite import server

    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "gitlab_job_play", "arguments": {"job_id": 1}}},
        read_only=True,
    )
    assert response is not None and response["error"]["code"] == -32601


def test_pipeline_create_dry_run_checks_the_ref_without_writing(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /repository/branches/feat%2Fx"] = {"name": "feat/x"}
    text, is_error = call("gitlab_pipeline_create", {"ref": "feat/x"})
    assert not is_error and json.loads(text) == {"dry_run": True, "ok": True, "ref": "feat/x"}
    assert all(c.get_method() == "GET" for c in gitlab.calls)


def test_pipeline_dry_run_falls_back_to_tags(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /repository/tags/v1.0"] = {"name": "v1.0"}
    assert json.loads(call("gitlab_pipeline_create", {"ref": "v1.0"})[0])["ok"] is True
    assert json.loads(call("gitlab_pipeline_create", {"ref": "nope"})[0])["ok"] is False


def test_pipeline_create_posts_the_ref(gitlab: FakeGitLab) -> None:
    gitlab.routes["POST /pipeline"] = {"id": 7, "status": "created", "ref": "main", "sha": "abc", "web_url": "u", "extra": 1}
    text, is_error = call("gitlab_pipeline_create", {"ref": "main", "dry_run": False})
    assert not is_error and json.loads(text) == {"id": 7, "status": "created", "ref": "main", "sha": "abc", "web_url": "u"}
    assert gitlab.body() == {"ref": ["main"]}


def test_pipeline_get_and_jobs_are_compact(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /pipelines/3"] = {"id": 3, "status": "success", "ref": "main", "sha": "s", "web_url": "u", "junk": 1}
    job = {"id": 1, "name": "test", "status": "success", "stage": "t", "web_url": "u", "junk": 1}
    gitlab.routes["GET /pipelines/3/jobs"] = [job]
    assert "junk" not in call("gitlab_pipeline_get", {"pipeline_id": 3})[0]
    jobs = json.loads(call("gitlab_pipeline_jobs", {"pipeline_id": 3, "per_page": 5, "page": 2})[0])
    assert jobs == [{"id": 1, "name": "test", "status": "success", "stage": "t", "web_url": "u"}]
    assert "per_page=5" in gitlab.last().full_url and "page=2" in gitlab.last().full_url


def test_job_play_defaults_to_dry_run(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /jobs/4"] = {"id": 4, "name": "deploy", "status": "manual"}
    gitlab.routes["POST /jobs/4/play"] = {"id": 4, "name": "deploy", "status": "pending"}
    assert json.loads(call("gitlab_job_play", {"job_id": 4})[0])["dry_run"] is True
    assert {c.get_method() for c in gitlab.calls} == {"GET"}
    assert json.loads(call("gitlab_job_play", {"job_id": "4", "dry_run": False})[0])["status"] == "pending"


def test_issues_list_filters_labels_on_the_server(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /issues"] = [{"iid": 1, "title": "t", "state": "opened", "labels": ["a", "b"], "web_url": "u", "x": 1}]
    rows = json.loads(call("gitlab_issues_list", {"labels": ["a", "b"], "state": "all"})[0])
    assert rows[0]["iid"] == 1 and "x" not in rows[0]
    assert "labels=a%2Cb" in gitlab.last().full_url and "state=all" in gitlab.last().full_url


def test_state_is_validated_not_pasted_into_the_url(gitlab: FakeGitLab) -> None:
    text, is_error = call("gitlab_issues_list", {"state": "opened&assignee_id=1"})
    assert is_error and "state must be one of" in text and not gitlab.calls
    assert call("gitlab_mr_list", {"state": "bogus"})[1] is True


def test_paging_limits(gitlab: FakeGitLab) -> None:
    assert call("gitlab_issues_list", {"per_page": 500})[1] is True
    assert call("gitlab_mr_list", {"page": 0})[1] is True


def test_issue_get_returns_the_useful_fields(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /issues/9"] = {
        "iid": 9, "title": "T", "description": "D", "state": "opened", "labels": ["x"], "web_url": "u",
        "author": {"username": "ann"}, "assignees": [{"username": "bob"}], "milestone": {"title": "M1"},
        "created_at": "c", "updated_at": "u2", "noise": 1,
    }
    data = json.loads(call("gitlab_issue_get", {"iid": 9})[0])
    assert data["author"] == "ann" and data["assignees"] == ["bob"] and data["milestone"] == "M1" and "noise" not in data


def test_issue_comment_posts_a_note(gitlab: FakeGitLab) -> None:
    gitlab.routes["POST /issues/2/notes"] = {"id": 11, "created_at": "now"}
    text, is_error = call("gitlab_issue_comment", {"iid": 2, "body": "hello & bye"})
    assert not is_error and json.loads(text) == {"note_id": 11, "created_at": "now"}
    assert gitlab.body() == {"body": ["hello & bye"]}


def test_mr_create_dry_run_reports_missing_branches_exactly(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /repository/branches/feat"] = {"name": "feat"}
    text, _ = call("gitlab_mr_create", {"source_branch": "feat", "target_branch": "main", "title": "t"})
    assert json.loads(text) == {"dry_run": True, "ok": False, "missing_branches": ["main"]}
    assert {c.get_method() for c in gitlab.calls} == {"GET"}


def test_mr_create_posts_everything(gitlab: FakeGitLab) -> None:
    gitlab.routes["POST /merge_requests"] = {"iid": 3, "web_url": "u"}
    text, is_error = call("gitlab_mr_create", {
        "source_branch": "feat", "target_branch": "main", "title": "T", "description": "line1\nline2",
        "labels": ["l1", "l2"], "dry_run": False,
    })
    assert not is_error and json.loads(text) == {"iid": 3, "web_url": "u"}
    assert gitlab.body() == {"source_branch": ["feat"], "target_branch": ["main"], "title": ["T"],
                             "description": ["line1\nline2"], "labels": ["l1,l2"]}


def test_project_argument_reaches_the_url(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /issues/1"] = {"iid": 1}
    call("gitlab_issue_get", {"iid": 1, "project": "other/repo"})
    assert "/projects/other%2Frepo/issues/1" in gitlab.last().full_url


def test_api_failures_ride_in_the_envelope(gitlab: FakeGitLab) -> None:
    gitlab.routes["GET /pipelines/1"] = 401
    text, is_error = call("gitlab_pipeline_get", {"pipeline_id": 1})
    assert is_error and "HTTP 401" in text and "glpat-secret" not in text


def test_missing_configuration_is_an_error_not_a_crash(gitlab: FakeGitLab, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("GITLAB_API_KEY")
    text, is_error = call("gitlab_pipeline_get", {"pipeline_id": 1})
    assert is_error and "no GitLab token" in text
