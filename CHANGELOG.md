# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-28

### Added
- MCP stdio server with 9 tools for one GitLab project: pipelines (create, get, jobs), manual jobs (play),
  issues (list, get, comment) and merge requests (list, create).
- Write tools default to `dry_run`; `--read-only` / `GITLAB_MCP_READ_ONLY=1` removes them from the tool list.
- Zero-config targeting: host and project come from the `origin` remote; `GITLAB_URL`, `GITLAB_PROJECT` and a
  per-call `project` argument override it, so self-hosted GitLab works.
- Token from `GITLAB_API_KEY` / `GITLAB_TOKEN` or a `.env` file in the repository root; never logged.
- `gitlab-mcp-lite check` shows the resolved host, project and token source and tests the connection.
- `gitlab-mcp-lite config-snippet` for Claude Code, VS Code (Copilot), Codex, Cursor and Gemini CLI.

### Changed (from the Embersail tooling this was generalized from)
- Lists are paged (`per_page`, `page`) instead of silently returning only the first 100 rows.
- Label filters run on the server; `state` values are validated before they reach the URL.
- Branch checks in dry runs ask for the exact branch instead of scanning the first page of branches.
- Remote URLs of the form `ssh://git@host:port/group/project.git` are understood.
- Tool names use the `gitlab_` prefix (was `ghlab_`).

### Not included
- Publishing task registries as issues (`ghlab_sync`); it depends on the task-registry format.
