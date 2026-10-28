# gitlab-mcp-lite

A small MCP server for the GitLab REST API: pipelines, manual jobs, issues and merge requests of one project.
No runtime dependencies (Python 3.11+ standard library), no setup beyond a token, works with self-hosted GitLab.
Write tools default to dry runs and can be removed entirely with `--read-only`.

## Quick start

```sh
export GITLAB_API_KEY=glpat-...      # a personal or project access token with the `api` scope
cd your-clone-of-a-gitlab-project
uvx gitlab-mcp-lite check            # shows what it resolved and tests the connection
uvx gitlab-mcp-lite config-snippet claude
```

`check` prints the API URL, the project, where the token came from (never the token) and whether GitLab
accepts it. Run it first when something does not work.

## Configuration

Everything is resolved from the environment, a `.env` file and the git `origin` remote. First match wins.

| Value | Sources, in order | Default |
| --- | --- | --- |
| Token | `GITLAB_API_KEY`, `GITLAB_TOKEN`, then the same keys in `.env` in the git root or the current directory | none (required) |
| GitLab URL | `GITLAB_URL` (e.g. `https://gitlab.example.com`, no `/api/v4`) | host of the `origin` remote, over https |
| Project | the tool's `project` argument, `GITLAB_PROJECT` (`group/name` or numeric id) | path of the `origin` remote |
| Request timeout | `GITLAB_TIMEOUT` (seconds) | `30` |
| Read-only mode | `--read-only` or `GITLAB_MCP_READ_ONLY=1` | off |

In a clone of the project you want to manage, only the token is needed. Outside a clone, set `GITLAB_URL` and
`GITLAB_PROJECT`, or pass `project` per call.

**Where to keep the token.** Prefer a `.env` file in the repository root (`GITLAB_API_KEY=glpat-...`, listed in
`.gitignore`): the server reads it itself, so it works the same in every client. MCP clients usually start servers
with a trimmed environment, so a variable exported in your shell may not reach the server; if you rely on the
environment, pass it through the client's own `env` setting. The token is sent only in the `PRIVATE-TOKEN` header
and is never included in tool results or error messages.

## Tools

| Tool | Does | Writes |
| --- | --- | --- |
| `gitlab_pipeline_get` | status, ref, sha and URL of a pipeline | no |
| `gitlab_pipeline_jobs` | jobs of a pipeline (paged) | no |
| `gitlab_issues_list` | issues by `state` and `labels` (paged) | no |
| `gitlab_issue_get` | one issue with description, assignees, milestone | no |
| `gitlab_mr_list` | merge requests by `state` (paged) | no |
| `gitlab_pipeline_create` | create a pipeline for a branch or tag; `dry_run` (default) only checks the ref | yes |
| `gitlab_job_play` | play a manual job; `dry_run` (default) only reads its status | yes |
| `gitlab_issue_comment` | add a comment to an issue | yes |
| `gitlab_mr_create` | create a merge request; `dry_run` (default) only checks both branches | yes |

Every tool takes an optional `project`. Lists return compact rows; `per_page` is 1-100 (default 30) and `page`
starts at 1. Failures come back as `isError` results with the reason, so an agent can see what went wrong.
Read-only tools carry `readOnlyHint`, so clients can skip the approval prompt for them.

## Adding it to a client

`gitlab-mcp-lite config-snippet <client>` prints the block (clients: `claude`, `vscode`, `codex`, `cursor`,
`gemini`, `generic`; options `--url`, `--project`, `--read-only`, `--from <path|git-url>`). See
[docs/clients.md](docs/clients.md).

```sh
claude mcp add gitlab -- uvx gitlab-mcp-lite
```

## Development

```sh
python -m pip install -e ".[dev]"
ruff check . && mypy && pytest
```

Tests use a stand-in transport and a local HTTP server; they need no network and no token.

## Releasing

Pushing to `main` runs the tests on Linux, macOS and Windows and builds the package. If `version` in
`pyproject.toml` has no `v<version>` tag yet, the workflow publishes to PyPI and creates the tag and GitHub release.
Bump `version` in `pyproject.toml` and `src/gitlab_mcp_lite/__init__.py` (a test keeps them equal), add a changelog
entry, merge to `main`. One-time setup: a GitHub environment named `pypi`, and either the repository secret
`PYPI_API_TOKEN` or a trusted publisher on PyPI for this repository (workflow `ci.yml`, environment `pypi`).

## Status

Alpha. Covers one project per call and the most common read/write operations; it is not a full GitLab client.
It originated in the Embersail project's GitLab tooling.

## License

MIT
