# Adding gitlab-mcp-lite to an MCP client

Every client runs the same stdio command: `uvx gitlab-mcp-lite`. `gitlab-mcp-lite config-snippet <client>` prints
the block; `--from <path|git-url>` runs from a checkout instead of PyPI, `--url` and `--project` write
`GITLAB_URL` / `GITLAB_PROJECT`, `--read-only` adds the read-only flag. The snippets never contain the token.

| Client | Where it goes | Command |
| --- | --- | --- |
| Claude Code | `.mcp.json` in the project, or `claude mcp add` | `gitlab-mcp-lite config-snippet claude` |
| VS Code (GitHub Copilot agent mode) | `.vscode/mcp.json` | `gitlab-mcp-lite config-snippet vscode` |
| OpenAI Codex CLI | `~/.codex/config.toml` | `gitlab-mcp-lite config-snippet codex` |
| Cursor | `.cursor/mcp.json` | `gitlab-mcp-lite config-snippet cursor` |
| Gemini CLI | `.gemini/settings.json` | `gitlab-mcp-lite config-snippet gemini` |

## The token

The server finds the token itself, in this order: `GITLAB_API_KEY`, `GITLAB_TOKEN`, then a `.env` file in the git
root or the current directory. The reliable setup is a `.env` in the repository root:

```
GITLAB_API_KEY=glpat-xxxxxxxxxxxxxxxxxxxx
```

Keep it out of version control (`echo .env >> .gitignore`). Clients often start servers with a minimal environment,
so a variable exported in your shell is not guaranteed to arrive; if you prefer the environment, use the client's
`env` setting with the syntax that client documents for referencing a variable.

## Working directory

The server resolves the project from the `origin` remote of its working directory. Claude Code and VS Code start
servers in the workspace, so nothing more is needed there. Clients that start servers elsewhere need `GITLAB_URL`
and `GITLAB_PROJECT` in the configuration (`config-snippet --url ... --project ...`).

## Examples

VS Code `.vscode/mcp.json`:

```json
{
  "servers": {
    "gitlab": { "type": "stdio", "command": "uvx", "args": ["gitlab-mcp-lite"] }
  }
}
```

Codex `~/.codex/config.toml`, self-hosted GitLab, read-only:

```toml
[mcp_servers.gitlab]
command = "uvx"
args = ["gitlab-mcp-lite", "--read-only"]

[mcp_servers.gitlab.env]
GITLAB_URL = "https://gitlab.example.com"
GITLAB_PROJECT = "team/app"
```

## Notes

- The file formats above are the ones the clients documented when this was written; check the client's current MCP
  documentation if a block is rejected.
- `uvx` must be on the `PATH` the client sees; otherwise use its absolute path (`command -v uvx`).
- Use `--read-only` for agents that should inspect pipelines and issues but never change anything.
