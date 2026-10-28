"""Ready-to-paste MCP server configuration for common clients (``gitlab-mcp-lite config-snippet``).

Snippets never contain the token: put it in the project's ``.env`` (read by the server itself) or pass it
through the client's own environment mechanism, whose syntax differs per client.
"""

from __future__ import annotations

import json

CLIENTS = {
    "claude": "Claude Code: .mcp.json in the project (or `claude mcp add`)",
    "vscode": "VS Code (GitHub Copilot agent mode): .vscode/mcp.json",
    "codex": "OpenAI Codex CLI: ~/.codex/config.toml",
    "cursor": "Cursor: .cursor/mcp.json",
    "gemini": "Gemini CLI: .gemini/settings.json",
    "generic": "any client that takes a command and arguments",
}
NAME = "gitlab"


def launch(source: str | None, read_only: bool) -> tuple[str, list[str]]:
    """Command and arguments that start the stdio server through ``uvx``."""
    args = ["--from", source, "gitlab-mcp-lite"] if source else ["gitlab-mcp-lite"]
    if read_only:
        args.append("--read-only")
    return "uvx", args


def snippet(
    client: str, *, source: str | None = None, url: str | None = None, project: str | None = None, read_only: bool = False
) -> str:
    """The configuration text for ``client``; raises ``ValueError`` for an unknown client."""
    if client not in CLIENTS:
        raise ValueError(f"unknown client {client!r}; choose one of {', '.join(CLIENTS)}")
    command, args = launch(source, read_only)
    env = {k: v for k, v in (("GITLAB_URL", url), ("GITLAB_PROJECT", project)) if v}
    if client == "codex":
        lines = [f"[mcp_servers.{NAME}]", f"command = {json.dumps(command)}", f"args = {json.dumps(args)}"]
        if env:
            lines += ["", f"[mcp_servers.{NAME}.env]", *(f"{k} = {json.dumps(v)}" for k, v in env.items())]
        return "\n".join(lines) + "\n"
    if client == "claude":
        add = ["claude", "mcp", "add", NAME]
        for key, value in env.items():
            add += ["-e", f"{key}={value}"]
        entry: dict[str, object] = {"type": "stdio", "command": command, "args": args}
        if env:
            entry["env"] = env
        text = json.dumps({"mcpServers": {NAME: entry}}, indent=2)
        return f"# one command:\n{' '.join([*add, '--', command, *args])}\n\n# or .mcp.json:\n{text}\n"
    entry = {"command": command, "args": args}
    if client == "vscode":
        entry = {"type": "stdio", **entry}
    if env:
        entry["env"] = env
    return json.dumps({("servers" if client == "vscode" else "mcpServers"): {NAME: entry}}, indent=2) + "\n"
