"""CLI entrypoint: ``gitlab-mcp-lite`` starts the MCP server; ``check`` and ``config-snippet`` help set it up."""

from __future__ import annotations

import argparse
import sys
import urllib.parse

from . import __version__, client, clients, server


def _cmd_serve(args: argparse.Namespace) -> int:
    server.serve(server.read_only_requested(args.read_only))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    """Print what the server would use and test it against GitLab; never prints the token."""
    try:
        target = client.resolve(args.project)
        found = client.token_source()
        print(f"API:     {target.api}")
        print(f"project: {target.project}")
        print(f"token:   {found[1] if found else 'NOT FOUND (set GITLAB_API_KEY or GITLAB_TOKEN, or add it to .env)'}")
        print(f"mode:    {'read-only' if server.read_only_requested(args.read_only) else 'read-write'}")
        if found is None:
            return 1
        info = client.request("version", scoped=False)
        print(f"server:  GitLab {info.get('version')}")
        row = client.request(f"projects/{urllib.parse.quote(target.project, safe='')}", scoped=False, project=target.project)
        print(f"access:  {row.get('path_with_namespace')} (id {row.get('id')})")
    except client.GitLabError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_snippet(args: argparse.Namespace) -> int:
    try:
        print(
            clients.snippet(args.client, source=args.source, url=args.url, project=args.project, read_only=args.read_only),
            end="",
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("note: the token is not part of this block; see docs/clients.md", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Assemble the argparse tree; with no subcommand the MCP server starts."""
    parser = argparse.ArgumentParser(
        prog="gitlab-mcp-lite",
        description="MCP server for the GitLab REST API (pipelines, jobs, issues, merge requests).",
    )
    parser.add_argument("--version", action="version", version=f"gitlab-mcp-lite {__version__}")
    parser.add_argument(
        "--read-only", action="store_true", help="expose only tools that do not write (or GITLAB_MCP_READ_ONLY=1)"
    )
    parser.set_defaults(func=_cmd_serve)
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("check", help="show the resolved host, project and token source, and test the connection")
    p.add_argument("--project", help="group/name or id (default: GITLAB_PROJECT or the origin remote)")
    p.add_argument("--read-only", action="store_true", dest="read_only")
    p.set_defaults(func=_cmd_check)

    p = sub.add_parser("config-snippet", help="print MCP configuration for a client")
    p.add_argument("client", choices=list(clients.CLIENTS), help="; ".join(f"{k}: {v}" for k, v in clients.CLIENTS.items()))
    p.add_argument("--from", dest="source", help="uvx source (path, git URL or version spec); default: PyPI")
    p.add_argument("--url", help="GitLab URL, written as GITLAB_URL (self-hosted)")
    p.add_argument("--project", help="project, written as GITLAB_PROJECT")
    p.add_argument("--read-only", action="store_true", dest="read_only")
    p.set_defaults(func=_cmd_snippet)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Program entry: dispatch, return the exit code."""
    args = build_parser().parse_args(argv)
    code: int = args.func(args)
    return code


def run() -> None:
    """Console-script entry point."""
    sys.exit(main())
