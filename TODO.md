# TODO

Ideas for the next editions, roughly by value. These are candidates, not commitments. Items marked **known gap**
describe something the current version does not do or has not verified.

## Next (0.2)

- [ ] **CI debugging tools.** `gitlab_job_trace` (the job log, tail by default), `gitlab_job_retry`,
      `gitlab_job_cancel`, `gitlab_pipeline_retry`, `gitlab_pipeline_cancel`. Reading a failed job's log is the
      most useful thing an agent can do with a pipeline, and today `gitlab_pipeline_jobs` stops at the status.
- [ ] **Merge request depth.** `gitlab_mr_get` (description, approvals, pipeline status), `gitlab_mr_changes` (diff,
      truncated), `gitlab_mr_comment`. Merging stays out until there is a guard (see Safety).
- [ ] **Issue writes.** `gitlab_issue_create` and `gitlab_issue_update` (title, description, labels, state).
- [ ] **Repository reads.** `gitlab_file_get` (a file at a ref), `gitlab_branches_list`, `gitlab_commits_list`,
      `gitlab_project_get`.
- [ ] **Paging metadata.** Lists return a page of rows but not whether there is a next page or a total, because the
      client does not expose response headers (`X-Next-Page`, `X-Total`). Return them so an agent knows it saw
      everything. **Known gap.**
- [ ] **Test against a real GitLab.** All tests use a stand-in transport and a local HTTP server, so response
      shapes, error codes and permissions are untested against the real API. Add opt-in integration tests
      (`GITLAB_IT_PROJECT`, a read-only token) and a documented test project. **Known gap.**
- [ ] **Verify the client config formats.** `config-snippet` output for Claude Code, VS Code, Codex, Cursor and
      Gemini CLI was written from memory of their documentation. Check each against the current docs and a real
      client; confirm how each passes the token through its `env` setting. **Known gap.**

## Safety

- [ ] **Project allow-list.** `GITLAB_ALLOWED_PROJECTS` so the per-call `project` argument cannot reach projects the
      token happens to see but the user never meant to expose.
- [ ] **Per-tool allow and deny.** `--tools a,b` / `--deny c`, finer than all-or-nothing `--read-only`.
- [ ] **Guarded merge.** `gitlab_mr_merge` only with an explicit `confirm` argument that must equal the MR's current
      head SHA, and never in dry-run-off mode by default.
- [ ] **Audit trail.** Optionally append every write call (tool, project, arguments without secrets, result id) to a
      local JSONL file.
- [ ] **Token hygiene.** `check` should report the token's scopes and expiry (`/personal_access_tokens/self`) and warn
      when it is broader than needed.

## Robustness

- [ ] **Retries.** Back off on HTTP 429 (honor `Retry-After`) and retry idempotent GETs on 5xx and connection resets.
- [ ] **TLS and proxies for self-hosted GitLab.** A custom CA bundle (`GITLAB_CA_BUNDLE`) and an explicit switch for
      internal certificates; confirm the standard proxy variables are honored by `urllib`. **Known gap.**
- [ ] **More token types.** CI job tokens (`JOB-TOKEN`) and OAuth bearer tokens in addition to private tokens.
- [ ] **Remote URL edge cases.** Sub-paths (`https://host/gitlab/group/project`) and `url.<base>.insteadOf` rewrites
      are not handled when resolving the host and project from `origin`.

## Integrations and docs

- [ ] **Task registry sync.** Publish a `taskgate` registry as GitLab issues (labels per status, milestones per
      phase). The Embersail version (`ghlab_sync`) was not carried over because it depends on that registry's
      format; rebuild it as an optional integration once `taskgate`'s schema is stable.
- [ ] **MCP resources and prompts.** Expose an issue or MR as a resource, and prompts such as "triage failed
      pipeline" that chain the tools.
- [ ] **Trusted publishing.** Releases currently use the `PYPI_API_TOKEN` secret. Switch to a trusted publisher
      (OIDC), drop the secret, and narrow any remaining token to this project.
- [ ] **Changelog-driven release notes** instead of `--generate-notes`.
