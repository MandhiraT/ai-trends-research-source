#!/usr/bin/env python3
"""
GitHub API-based file uploader for AI Trends Research reports.

Replaces git-clone-based uploads entirely. No local git repo needed.
Scales to any repo size — only uploads files that actually changed.

How it works:
1. GET current tree from GitHub (1 API call, gets all blob SHAs)
2. Compute expected git blob SHA for each local file (local, no network)
3. Upload blobs only for new/changed files (parallelised)
4. POST new tree (base_tree preserves all unchanged files/audio)
5. POST commit + PATCH ref

GitHub blob SHA formula: sha1("blob {len}\0{content}")
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple
from urllib import request as _urllib_request
from urllib.error import HTTPError


GITHUB_API = "https://api.github.com"
GITHUB_OWNER = "MandhiraT"
GITHUB_REPO = "ai-trends-research"
GIT_AUTHOR = {"name": "MandhiraT", "email": "mandhira@thequietself.com"}


class ApiError(RuntimeError):
    pass


def _req(
    method: str,
    path: str,
    token: str,
    body: dict | None = None,
    timeout: int = 60,
) -> dict:
    url = f"{GITHUB_API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = _urllib_request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "ats-github-upload/2.0",
        },
    )
    try:
        with _urllib_request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise ApiError(f"GitHub API {method} {path} → {exc.code}: {body_text}") from exc


def _git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


def _get_current_tree(token: str, branch: str = "master") -> tuple[str, str, dict[str, str]]:
    """Returns (commit_sha, tree_sha, {path: blob_sha}) for current branch HEAD."""
    ref = _req("GET", f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/ref/heads/{branch}", token)
    commit_sha = ref["object"]["sha"]

    commit = _req("GET", f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/commits/{commit_sha}", token)
    tree_sha = commit["tree"]["sha"]

    tree = _req(
        "GET",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/trees/{tree_sha}?recursive=1",
        token,
        timeout=120,
    )
    if tree.get("truncated"):
        print("⚠️  GitHub tree response truncated — repo has >100k files, treating all local files as changed")
        return commit_sha, tree_sha, {}

    path_to_sha = {
        item["path"]: item["sha"]
        for item in tree.get("tree", [])
        if item["type"] == "blob"
    }
    return commit_sha, tree_sha, path_to_sha


def _create_blob(token: str, content: bytes) -> str:
    resp = _req(
        "POST",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/blobs",
        token,
        body={"content": base64.b64encode(content).decode(), "encoding": "base64"},
        timeout=120,
    )
    return resp["sha"]


def upload_subtrees(
    token: str,
    subtrees: list[tuple[Path, str]],
    commit_message: str,
    branch: str = "master",
    max_workers: int = 8,
) -> bool:
    """
    Upload one or more local directories to GitHub subtree paths.

    subtrees: list of (local_dir, github_prefix) pairs
      e.g. [(Path("reports"), "reports"), (Path("joanna-wiebe"), "Content Marketing/Joanna-Wiebe")]

    Returns True if a commit was made, False if nothing changed.
    """
    print("📡 Fetching current GitHub tree…")
    commit_sha, tree_sha, existing = _get_current_tree(token, branch)
    print(f"   Current HEAD: {commit_sha[:8]}  ({len(existing)} blobs indexed)")

    # Build map of all local files: github_path → local_path
    local_files: dict[str, Path] = {}
    for local_dir, prefix in subtrees:
        if not local_dir.exists():
            print(f"   ⚠️  Local dir not found, skipping: {local_dir}")
            continue
        for f in sorted(local_dir.rglob("*")):
            if f.is_file():
                rel = f.relative_to(local_dir)
                github_path = f"{prefix}/{rel}".replace("\\", "/")
                local_files[github_path] = f

    # Determine what changed
    local_shas: dict[str, str] = {}
    for gpath, lpath in local_files.items():
        data = lpath.read_bytes()
        local_shas[gpath] = _git_blob_sha(data)

    to_upload = {
        gpath: local_files[gpath]
        for gpath, sha in local_shas.items()
        if existing.get(gpath) != sha
    }

    # Detect deletions within managed subtrees
    managed_prefixes = tuple(f"{prefix}/" for _, prefix in subtrees)
    deleted = [
        gpath for gpath in existing
        if gpath.startswith(managed_prefixes) and gpath not in local_files
    ]

    if not to_upload and not deleted:
        print("✅ Nothing changed — GitHub already up to date")
        return False

    print(f"   ↑ {len(to_upload)} file(s) to upload, ✗ {len(deleted)} to delete")

    # Upload changed blobs in parallel
    new_blob_shas: dict[str, str] = {}
    if to_upload:
        print(f"   Uploading {len(to_upload)} blob(s)…")
        failed = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_create_blob, token, lpath.read_bytes()): gpath
                for gpath, lpath in to_upload.items()
            }
            done = 0
            for fut in as_completed(futures):
                gpath = futures[fut]
                try:
                    new_blob_shas[gpath] = fut.result()
                    done += 1
                    if done % 10 == 0 or done == len(to_upload):
                        print(f"   … {done}/{len(to_upload)}")
                except ApiError as exc:
                    print(f"   ❌ Failed to upload {gpath}: {exc}")
                    failed.append(gpath)
        if failed:
            raise ApiError(f"Blob upload failed for {len(failed)} file(s): {failed[:3]}")

    # Build tree entries
    tree_entries = []
    for gpath, sha in new_blob_shas.items():
        tree_entries.append({"path": gpath, "mode": "100644", "type": "blob", "sha": sha})
    for gpath in deleted:
        tree_entries.append({"path": gpath, "mode": "100644", "type": "blob", "sha": None})

    # Create new tree (base_tree preserves all unchanged files)
    print("   Creating tree…")
    new_tree = _req(
        "POST",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/trees",
        token,
        body={"base_tree": tree_sha, "tree": tree_entries},
        timeout=120,
    )
    new_tree_sha = new_tree["sha"]

    # Create commit
    print("   Creating commit…")
    new_commit = _req(
        "POST",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/commits",
        token,
        body={
            "message": commit_message,
            "tree": new_tree_sha,
            "parents": [commit_sha],
            "author": GIT_AUTHOR,
        },
    )
    new_commit_sha = new_commit["sha"]

    # Update branch ref
    print("   Updating ref…")
    _req(
        "PATCH",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/refs/heads/{branch}",
        token,
        body={"sha": new_commit_sha, "force": False},
    )

    print(f"✅ Committed {new_commit_sha[:8]}: {commit_message}")
    return True


def upload_files(
    token: str,
    additions: list[tuple[Path, str]],
    deletions: list[str],
    commit_message: str,
    branch: str = "master",
    max_workers: int = 8,
) -> bool:
    """
    Add/update/delete specific files without touching the rest of the repo.

    additions: list of (local_path, github_path) — files to create or update
    deletions: list of github_path strings — files to remove
    Returns True if a commit was made.
    """
    if not additions and not deletions:
        print("✅ Nothing to upload")
        return False

    print("📡 Fetching current GitHub tree…")
    commit_sha, tree_sha, existing = _get_current_tree(token, branch)

    # Filter: skip additions where file is identical to what's already on GitHub
    to_upload: list[tuple[Path, str]] = []
    for local_path, github_path in additions:
        data = local_path.read_bytes()
        if existing.get(github_path) != _git_blob_sha(data):
            to_upload.append((local_path, github_path))

    # Filter: skip deletions for files that don't exist on GitHub
    to_delete = [p for p in deletions if p in existing]

    if not to_upload and not to_delete:
        print("✅ Nothing changed — GitHub already up to date")
        return False

    print(f"   ↑ {len(to_upload)} file(s) to upload, ✗ {len(to_delete)} to delete")

    new_blob_shas: dict[str, str] = {}
    if to_upload:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_create_blob, token, lpath.read_bytes()): gpath
                for lpath, gpath in to_upload
            }
            for fut in as_completed(futures):
                gpath = futures[fut]
                new_blob_shas[gpath] = fut.result()

    tree_entries = []
    for gpath, sha in new_blob_shas.items():
        tree_entries.append({"path": gpath, "mode": "100644", "type": "blob", "sha": sha})
    for gpath in to_delete:
        tree_entries.append({"path": gpath, "mode": "100644", "type": "blob", "sha": None})

    new_tree = _req(
        "POST",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/trees",
        token,
        body={"base_tree": tree_sha, "tree": tree_entries},
        timeout=120,
    )
    new_commit = _req(
        "POST",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/commits",
        token,
        body={
            "message": commit_message,
            "tree": new_tree["sha"],
            "parents": [commit_sha],
            "author": GIT_AUTHOR,
        },
    )
    _req(
        "PATCH",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/refs/heads/{branch}",
        token,
        body={"sha": new_commit["sha"], "force": False},
    )
    print(f"✅ Committed {new_commit['sha'][:8]}: {commit_message}")
    return True
