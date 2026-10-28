"""MCP tools: pipelines, jobs, issues and merge requests of one GitLab project.

Tools that write default to ``dry_run`` where a preview makes sense. Every tool takes an optional
``project`` (``group/name`` or numeric id) that overrides ``GITLAB_PROJECT`` and the ``origin`` remote.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

from . import client
from .registry import arg, tool

PROJECT = {"type": "string", "description": "group/name or numeric id; default: GITLAB_PROJECT or the origin remote"}
PAGING = {
    "per_page": {"type": "integer", "minimum": 1, "maximum": 100, "default": 30},
    "page": {"type": "integer", "minimum": 1, "default": 1},
}
#: Tools that change GitLab state; ``--read-only`` / ``GITLAB_MCP_READ_ONLY=1`` leaves them out.
WRITE_TOOLS = frozenset({"gitlab_pipeline_create", "gitlab_job_play", "gitlab_issue_comment", "gitlab_mr_create"})


def _out(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1)


def _quote(value: Any) -> str:
    return urllib.parse.quote(str(value), safe="")


def _choice(args: dict[str, Any], key: str, allowed: tuple[str, ...], default: str) -> str:
    value = str(arg(args, key, default))
    if value not in allowed:
        raise ValueError(f"{key} must be one of {', '.join(allowed)} (got {value!r})")
    return value


def _paging(args: dict[str, Any]) -> dict[str, int]:
    per_page, page = int(arg(args, "per_page", 30)), int(arg(args, "page", 1))
    if not 1 <= per_page <= 100 or page < 1:
        raise ValueError("per_page must be 1-100 and page >= 1")
    return {"per_page": per_page, "page": page}


def _ref_exists(ref: str, project: str | None) -> bool:
    return client.exists(f"repository/branches/{_quote(ref)}", project=project) or client.exists(
        f"repository/tags/{_quote(ref)}", project=project
    )


def _pipeline(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row.get(k) for k in ("id", "status", "ref", "sha", "web_url")}


@tool(
    "gitlab_pipeline_create",
    "Create a pipeline for a branch or tag. dry_run (default true) only checks that the ref exists.",
    {"properties": {"ref": {"type": "string"}, "dry_run": {"type": "boolean", "default": True}, "project": PROJECT},
     "required": ["ref"]},
)
def gitlab_pipeline_create(args: dict[str, Any]) -> str:
    ref, project = str(arg(args, "ref")), arg(args, "project")
    if arg(args, "dry_run", True):
        return _out({"dry_run": True, "ok": _ref_exists(ref, project), "ref": ref})
    return _out(_pipeline(client.request("pipeline", "POST", {"ref": ref}, project=project)))


@tool(
    "gitlab_pipeline_get",
    "Fetch one pipeline by id (status, ref, sha, web_url).",
    {"properties": {"pipeline_id": {"type": "integer"}, "project": PROJECT}, "required": ["pipeline_id"]},
    read_only=True,
)
def gitlab_pipeline_get(args: dict[str, Any]) -> str:
    row = client.request(f"pipelines/{int(arg(args, 'pipeline_id'))}", project=arg(args, "project"))
    return _out(_pipeline(row))


@tool(
    "gitlab_pipeline_jobs",
    "List the jobs of a pipeline (id, name, status, stage, web_url).",
    {"properties": {"pipeline_id": {"type": "integer"}, **PAGING, "project": PROJECT}, "required": ["pipeline_id"]},
    read_only=True,
)
def gitlab_pipeline_jobs(args: dict[str, Any]) -> str:
    path = f"pipelines/{int(arg(args, 'pipeline_id'))}/jobs"
    rows = client.request(path, params=_paging(args), project=arg(args, "project")) or []
    return _out([{k: row.get(k) for k in ("id", "name", "status", "stage", "web_url")} for row in rows])


@tool(
    "gitlab_job_play",
    "Play a manual job. dry_run (default true) only reads the job's status.",
    {"properties": {"job_id": {"type": "integer"}, "dry_run": {"type": "boolean", "default": True}, "project": PROJECT},
     "required": ["job_id"]},
)
def gitlab_job_play(args: dict[str, Any]) -> str:
    job_id, project = int(arg(args, "job_id")), arg(args, "project")
    if arg(args, "dry_run", True):
        row = client.request(f"jobs/{job_id}", project=project)
        return _out({"dry_run": True, "id": row.get("id"), "name": row.get("name"), "status": row.get("status")})
    row = client.request(f"jobs/{job_id}/play", "POST", project=project)
    return _out({k: row.get(k) for k in ("id", "name", "status")})


@tool(
    "gitlab_issues_list",
    "List issues. state: opened (default), closed or all. labels: all must match. Paged with per_page and page.",
    {"properties": {
        "labels": {"type": "array", "items": {"type": "string"}},
        "state": {"type": "string", "enum": ["opened", "closed", "all"], "default": "opened"},
        **PAGING, "project": PROJECT,
    }},
    read_only=True,
)
def gitlab_issues_list(args: dict[str, Any]) -> str:
    params: dict[str, Any] = {"state": _choice(args, "state", ("opened", "closed", "all"), "opened"), **_paging(args)}
    if arg(args, "labels"):
        params["labels"] = arg(args, "labels")
    rows = client.request("issues", params=params, project=arg(args, "project")) or []
    keys = ("iid", "title", "state", "web_url")
    return _out([{**{k: row.get(k) for k in keys}, "labels": row.get("labels", [])} for row in rows])


@tool(
    "gitlab_issue_get",
    "Fetch one issue by iid: title, description, state, labels, assignees, milestone, dates.",
    {"properties": {"iid": {"type": "integer"}, "project": PROJECT}, "required": ["iid"]},
    read_only=True,
)
def gitlab_issue_get(args: dict[str, Any]) -> str:
    row = client.request(f"issues/{int(arg(args, 'iid'))}", project=arg(args, "project"))
    return _out({
        **{k: row.get(k) for k in ("iid", "title", "description", "state", "web_url", "created_at", "updated_at")},
        "labels": row.get("labels", []),
        "author": (row.get("author") or {}).get("username"),
        "assignees": [a.get("username") for a in row.get("assignees") or []],
        "milestone": (row.get("milestone") or {}).get("title"),
    })


@tool(
    "gitlab_issue_comment",
    "Post a comment (note) on an issue. Append-only.",
    {"properties": {"iid": {"type": "integer"}, "body": {"type": "string"}, "project": PROJECT}, "required": ["iid", "body"]},
)
def gitlab_issue_comment(args: dict[str, Any]) -> str:
    path = f"issues/{int(arg(args, 'iid'))}/notes"
    row = client.request(path, "POST", {"body": arg(args, "body")}, project=arg(args, "project"))
    return _out({"note_id": row["id"], "created_at": row["created_at"]})


@tool(
    "gitlab_mr_list",
    "List merge requests (state opened by default; opened, closed, merged or all). Paged with per_page and page.",
    {"properties": {"state": {"type": "string", "enum": ["opened", "closed", "merged", "all"], "default": "opened"},
                    **PAGING, "project": PROJECT}},
    read_only=True,
)
def gitlab_mr_list(args: dict[str, Any]) -> str:
    params: dict[str, Any] = {"state": _choice(args, "state", ("opened", "closed", "merged", "all"), "opened"), **_paging(args)}
    rows = client.request("merge_requests", params=params, project=arg(args, "project")) or []
    keys = ("iid", "title", "state", "source_branch", "target_branch", "web_url")
    return _out([{**{k: row.get(k) for k in keys}, "labels": row.get("labels", [])} for row in rows])


@tool(
    "gitlab_mr_create",
    "Create a merge request. dry_run (default true) only checks that both branches exist.",
    {"properties": {
        "source_branch": {"type": "string"},
        "target_branch": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "labels": {"type": "array", "items": {"type": "string"}},
        "dry_run": {"type": "boolean", "default": True},
        "project": PROJECT,
    }, "required": ["source_branch", "target_branch", "title"]},
)
def gitlab_mr_create(args: dict[str, Any]) -> str:
    source, target, project = str(arg(args, "source_branch")), str(arg(args, "target_branch")), arg(args, "project")
    if arg(args, "dry_run", True):
        missing = [b for b in (source, target) if not client.exists(f"repository/branches/{_quote(b)}", project=project)]
        return _out({"dry_run": True, "ok": not missing, "missing_branches": missing})
    params = {"source_branch": source, "target_branch": target, "title": arg(args, "title"),
              "description": arg(args, "description"), "labels": arg(args, "labels") or None}
    row = client.request("merge_requests", "POST", params, project=project)
    return _out({"iid": row["iid"], "web_url": row["web_url"]})
