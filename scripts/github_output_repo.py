#!/usr/bin/env python3
"""Shared helpers for publishing to the ai-trends-research output repo.

Design goals:
- never trust a long-lived working tree after previous runs
- always start uploads from a fresh clone of the output repo
- keep authentication explicit instead of relying on stale remotes
- avoid persisting GitHub tokens inside `.git/config`
- give report/audio uploaders one hardening path instead of duplicating git logic
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable


class GitRepoError(RuntimeError):
    """Raised when the output repo cannot be prepared or updated."""


@contextmanager
def _git_auth_env(token: str | None):
    """Provide ephemeral GitHub auth without persisting credentials to git config."""
    if not token:
        yield None
        return

    askpass = tempfile.NamedTemporaryFile("w", delete=False, prefix="ats-git-askpass-", suffix=".sh")
    askpass.write(textwrap.dedent(
        """\
        #!/bin/sh
        case "$1" in
          *Username*) printf '%s\n' 'x-access-token' ;;
          *Password*) printf '%s\n' "$GITHUB_TOKEN_FOR_PUSH" ;;
          *) printf '\n' ;;
        esac
        """
    ))
    askpass.flush()
    askpass.close()
    os.chmod(askpass.name, 0o700)

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = askpass.name
    env["GITHUB_TOKEN_FOR_PUSH"] = token
    try:
        yield env
    finally:
        Path(askpass.name).unlink(missing_ok=True)


def run_git(
    args: list[str],
    cwd: str | Path,
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
    timeout: int | None = 180,
) -> subprocess.CompletedProcess:
    """Run a git command and optionally raise with stderr context."""
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitRepoError(
            f"git command timed out after {timeout}s: {' '.join(args)}"
        ) from exc
    if check and result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise GitRepoError(f"git command failed: {' '.join(args)}\n{stderr}")
    return result


def build_push_url(repo_url: str, token: str | None) -> str:
    if not token:
        return repo_url
    prefix = "https://github.com/"
    if repo_url.startswith(prefix):
        return repo_url.replace(prefix, "https://x-access-token@github.com/", 1)
    return repo_url


def _safe_rmtree(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def _default_allowed_checkout_roots() -> tuple[Path, ...]:
    return (
        Path.home() / ".cache" / "ai-trends-research",
        Path("/tmp/ai-trends-research"),
    )


def _validate_checkout_dir(
    checkout_dir: str | Path,
    allowed_roots: Iterable[str | Path] | None = None,
) -> Path:
    checkout = Path(checkout_dir).expanduser().resolve(strict=False)
    allowed = tuple(
        Path(root).expanduser().resolve(strict=False)
        for root in (allowed_roots or _default_allowed_checkout_roots())
    )

    if not checkout.name:
        raise GitRepoError(f"refusing unsafe checkout path: {checkout}")
    if checkout in {Path("/"), Path.home().resolve()}:
        raise GitRepoError(f"refusing unsafe checkout path: {checkout}")
    if not any(checkout == root or root in checkout.parents for root in allowed):
        allowed_text = ", ".join(str(root) for root in allowed)
        raise GitRepoError(
            f"refusing checkout path outside approved ATS cache roots: {checkout} (allowed: {allowed_text})"
        )
    return checkout


def prepare_fresh_checkout(
    repo_url: str,
    checkout_dir: str | Path,
    *,
    branch: str = "master",
    token: str | None = None,
    retries: int = 2,
    clone_timeout: int = 180,
    allowed_roots: Iterable[str | Path] | None = None,
) -> Path:
    """Create a fresh healthy checkout every run.

    This intentionally discards any previous clone at ``checkout_dir``. The
    ATS output repo is small enough that a clean clone per run is cheaper and
    safer than trying to heal an arbitrarily corrupted long-lived clone.
    """
    checkout = _validate_checkout_dir(checkout_dir, allowed_roots=allowed_roots)
    checkout.parent.mkdir(parents=True, exist_ok=True)
    last_error = ""

    for attempt in range(1, retries + 1):
        staging = checkout.parent / f".{checkout.name}.clone-{os.getpid()}-{attempt}"
        _safe_rmtree(staging)
        _safe_rmtree(checkout)

        with _git_auth_env(token) as env:
            try:
                clone = subprocess.run(
                    ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(staging)],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=clone_timeout,
                )
            except subprocess.TimeoutExpired:
                last_error = f"git clone timed out after {clone_timeout}s"
                _safe_rmtree(staging)
                if attempt < retries:
                    time.sleep(1)
                    continue
                raise GitRepoError(f"failed to clone output repo into {checkout}: {last_error}")
        if clone.returncode != 0:
            last_error = (clone.stderr or clone.stdout or "").strip()
            _safe_rmtree(staging)
            if attempt < retries:
                time.sleep(1)
                continue
            raise GitRepoError(f"failed to clone output repo into {checkout}: {last_error}")

        run_git(["git", "remote", "set-url", "origin", repo_url], staging)
        run_git(["git", "config", "user.email", "mandhira@thequietself.com"], staging)
        run_git(["git", "config", "user.name", "MandhiraT"], staging)
        run_git(["git", "status", "--short", "--branch"], staging)

        staging.rename(checkout)
        return checkout

    raise GitRepoError(f"failed to prepare output repo checkout: {last_error}")


def prepare_checkout(
    repo_url: str,
    checkout_dir: str | Path,
    *,
    branch: str = "master",
    token: str | None = None,
    fetch_timeout: int = 120,
    clone_timeout: int = 600,
    allowed_roots: Iterable[str | Path] | None = None,
) -> Path:
    """Prepare a checkout for publishing — reuse persistent clone if healthy, else clone fresh.

    On subsequent runs, does a fast fetch+reset instead of re-cloning the full repo.
    Uses --filter=blob:none so large audio/binary blobs are never downloaded —
    we replace those subtrees entirely from local content anyway.
    """
    checkout = _validate_checkout_dir(checkout_dir, allowed_roots=allowed_roots)
    checkout.parent.mkdir(parents=True, exist_ok=True)

    git_dir = checkout / ".git"
    if checkout.is_dir() and git_dir.is_dir():
        # Fast path: fetch latest commit + reset index (working tree left for replace_tree)
        with _git_auth_env(token) as env:
            try:
                run_git(["git", "remote", "set-url", "origin", repo_url], checkout)
                run_git(
                    ["git", "fetch", "--depth", "1", "--filter=blob:none", "origin", branch],
                    checkout,
                    env=env,
                    timeout=fetch_timeout,
                )
                run_git(["git", "reset", "--mixed", f"origin/{branch}"], checkout)
                run_git(["git", "config", "user.email", "mandhira@thequietself.com"], checkout)
                run_git(["git", "config", "user.name", "MandhiraT"], checkout)
                return checkout
            except GitRepoError:
                # Checkout corrupt — fall through to fresh clone
                _safe_rmtree(checkout)

    # First-time (or post-corruption) clone.
    # --filter=blob:none + --no-checkout: downloads only commit/tree objects (1-2s),
    # skipping all blobs (audio/report content we replace entirely anyway).
    # git reset --mixed HEAD then populates the index without touching working tree.
    staging = checkout.parent / f".{checkout.name}.clone-{os.getpid()}"
    _safe_rmtree(staging)
    with _git_auth_env(token) as env:
        try:
            clone = subprocess.run(
                [
                    "git", "clone",
                    "--depth", "1",
                    "--filter=blob:none",
                    "--no-checkout",
                    "--branch", branch,
                    repo_url, str(staging),
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=clone_timeout,
            )
        except subprocess.TimeoutExpired:
            _safe_rmtree(staging)
            raise GitRepoError(f"failed to clone output repo into {checkout}: git clone timed out after {clone_timeout}s")
    if clone.returncode != 0:
        _safe_rmtree(staging)
        stderr = (clone.stderr or clone.stdout or "").strip()
        raise GitRepoError(f"failed to clone output repo into {checkout}: {stderr}")

    run_git(["git", "remote", "set-url", "origin", repo_url], staging)
    run_git(["git", "config", "user.email", "mandhira@thequietself.com"], staging)
    run_git(["git", "config", "user.name", "MandhiraT"], staging)
    run_git(["git", "reset", "--mixed", "HEAD"], staging)
    staging.rename(checkout)
    return checkout


def replace_tree(src_dir: str | Path, dest_dir: str | Path) -> None:
    """Replace a destination subtree with a clean copy from source."""
    src = Path(src_dir)
    dest = Path(dest_dir)
    if not src.exists():
        raise GitRepoError(f"source tree does not exist: {src}")
    _safe_rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)



def stage_paths(repo_dir: str | Path, paths: Iterable[str | Path]) -> None:
    path_list = [str(p) for p in paths]
    if not path_list:
        return
    run_git(["git", "add", "--all", *path_list], repo_dir)


def has_staged_changes(repo_dir: str | Path) -> bool:
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(repo_dir))
    return result.returncode != 0


def commit_and_push(
    repo_dir: str | Path,
    message: str,
    *,
    token: str | None = None,
    push_timeout: int = 180,
) -> bool:
    if not has_staged_changes(repo_dir):
        return False
    run_git(["git", "commit", "-m", message], repo_dir)
    with _git_auth_env(token) as env:
        run_git(["git", "push", "origin", "master"], repo_dir, env=env, timeout=push_timeout)
    return True
