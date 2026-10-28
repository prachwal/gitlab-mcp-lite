"""GitLab REST v4 client: target resolution (host, project, token) and one request function.

Resolution order, first match wins:

- host:    ``GITLAB_URL``                       else the host of the git ``origin`` remote (https)
- project: the tool's ``project`` argument,     else ``GITLAB_PROJECT``, else the path of ``origin``
- token:   ``GITLAB_API_KEY``, ``GITLAB_TOKEN`` else the same keys in a ``.env`` file in the git root
           (or the current directory)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOKEN_KEYS = ("GITLAB_API_KEY", "GITLAB_TOKEN")
DEFAULT_TIMEOUT_S = 30.0


class GitLabError(RuntimeError):
    """A configuration problem or a failed GitLab API call (never contains the token)."""


def parse_remote(url: str) -> tuple[str, str]:
    """``(host, owner/path)`` from a git remote URL (scp-style, ssh:// or http(s)://)."""
    patterns = (
        r"^[\w.-]+@([^:/]+):(.+)$",  # git@host:group/project.git
        r"^ssh://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$",  # ssh://git@host[:22]/group/project.git
        r"^https?://(?:[^@/]+@)?([^/]+)/(.+)$",  # https://host[:port]/group/project.git
    )
    for pattern in patterns:
        match = re.match(pattern, url.strip())
        if match:
            return match.group(1), match.group(2).removesuffix(".git").strip("/")
    raise GitLabError(f"unsupported git remote URL {url!r}")


def origin(cwd: Path | None = None) -> tuple[str, str] | None:
    """``(host, project)`` of the ``origin`` remote, or ``None`` when there is none."""
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=cwd, capture_output=True, text=True, check=False, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return parse_remote(proc.stdout)


def _git_root(start: Path) -> Path | None:
    for parent in (start, *start.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _dotenv_value(path: Path, keys: tuple[str, ...]) -> tuple[str, str] | None:
    """The first of ``keys`` found in a dotenv file as ``(key, value)``."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    found: dict[str, str] = {}
    for line in lines:
        line = line.strip().removeprefix("export ").strip()
        key, sep, value = line.partition("=")
        if sep and key.strip() in keys:
            found[key.strip()] = value.strip().strip("'\"")
    for key in keys:
        if found.get(key):
            return key, found[key]
    return None


def token_source(cwd: Path | None = None) -> tuple[str, str] | None:
    """``(token, where)``: the token and a description of where it came from, never logged."""
    for key in TOKEN_KEYS:
        if os.environ.get(key):
            return os.environ[key], f"environment variable {key}"
    here = (cwd or Path.cwd()).resolve()
    root = _git_root(here)
    for candidate in dict.fromkeys(p / ".env" for p in (root, here) if p is not None):
        hit = _dotenv_value(candidate, TOKEN_KEYS)
        if hit:
            return hit[1], f"{hit[0]} in {candidate}"
    return None


@dataclass(frozen=True)
class Target:
    """Where requests go: API base URL and the project path or id."""

    api: str
    project: str


def resolve(project: str | None = None, cwd: Path | None = None) -> Target:
    """Work out the API base and project from arguments, environment and the origin remote."""
    remote = None
    url = os.environ.get("GITLAB_URL", "").strip().rstrip("/")
    project = project or os.environ.get("GITLAB_PROJECT") or None
    if not url or not project:
        remote = origin(cwd)
    if not url:
        if remote is None:
            raise GitLabError("cannot find the GitLab host: set GITLAB_URL or run inside a clone with an 'origin' remote")
        url = f"https://{remote[0]}"
    if not project:
        if remote is None:
            raise GitLabError(
                "cannot find the project: set GITLAB_PROJECT, pass 'project', or use a clone with an 'origin' remote"
            )
        project = remote[1]
    return Target(api=f"{url}/api/v4", project=project)


def _timeout() -> float:
    try:
        return float(os.environ.get("GITLAB_TIMEOUT", DEFAULT_TIMEOUT_S))
    except ValueError:
        return DEFAULT_TIMEOUT_S


def _send(request: urllib.request.Request) -> bytes:
    """Perform the HTTP call (replaced in tests)."""
    with urllib.request.urlopen(request, timeout=_timeout()) as resp:
        body: bytes = resp.read()
    return body


def request(
    path: str,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    *,
    project: str | None = None,
    scoped: bool = True,
) -> Any:
    """Call the API. ``path`` is relative to the project (``scoped``) or to ``/api/v4``.

    GET parameters go in the query string, other methods send a form body. Parameters whose value is
    ``None`` are dropped and lists are joined with commas.
    """
    target = resolve(project)
    found = token_source()
    if found is None:
        raise GitLabError(
            "no GitLab token: set GITLAB_API_KEY (or GITLAB_TOKEN) in the environment, "
            "or put it in a .env file in the repository root"
        )
    pairs = [
        (key, ",".join(map(str, value)) if isinstance(value, list) else str(value))
        for key, value in (params or {}).items()
        if value is not None
    ]
    base = f"{target.api}/projects/{urllib.parse.quote(target.project, safe='')}" if scoped else target.api
    url = f"{base}/{path}"
    data = None
    headers = {"PRIVATE-TOKEN": found[0], "Accept": "application/json"}
    if method == "GET":
        if pairs:
            url += "?" + urllib.parse.urlencode(pairs)
    else:
        data = urllib.parse.urlencode(pairs).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        body = _send(urllib.request.Request(url, data=data, method=method, headers=headers))
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode("utf-8", errors="replace").strip()
        raise GitLabError(f"{method} {path}: HTTP {exc.code} {detail}".strip()) from exc
    except urllib.error.URLError as exc:
        raise GitLabError(f"{method} {path}: {exc.reason}") from exc
    return json.loads(body) if body else None


def exists(path: str, *, project: str | None = None) -> bool:
    """True when a GET on ``path`` succeeds, False on HTTP 404; other failures propagate."""
    try:
        request(path, project=project)
    except GitLabError as exc:
        if "HTTP 404" in str(exc):
            return False
        raise
    return True
