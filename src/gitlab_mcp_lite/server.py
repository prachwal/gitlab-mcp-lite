"""MCP stdio server for the GitLab tools."""

from __future__ import annotations

import os
from typing import Any

from . import __version__, protocol, registry, tools

SERVER_INFO = {"name": "gitlab-mcp-lite", "version": __version__}


def read_only_requested(flag: bool = False) -> bool:
    """True when ``--read-only`` was passed or ``GITLAB_MCP_READ_ONLY`` is set to a truthy value."""
    return flag or os.environ.get("GITLAB_MCP_READ_ONLY", "").lower() in {"1", "true", "yes", "on"}


def tool_table(read_only: bool = False) -> dict[str, registry.ToolSpec]:
    """The tools to expose; read-only mode drops every tool that writes to GitLab."""
    return {n: s for n, s in registry.TOOLS.items() if not (read_only and n in tools.WRITE_TOOLS)}


def handle_request(request: dict[str, Any], *, read_only: bool = False) -> dict[str, Any] | None:
    """JSON-RPC dispatcher bound to this server's tools. Returns None for notifications."""
    return protocol.handle_request(request, tools=tool_table(read_only), server_info=SERVER_INFO)


def serve(read_only: bool = False) -> None:
    """Run the stdio loop until EOF."""
    protocol.serve(tools=tool_table(read_only), server_info=SERVER_INFO)
