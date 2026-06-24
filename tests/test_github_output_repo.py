import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from github_output_repo import GitRepoError, build_push_url, prepare_fresh_checkout


def _git(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _make_remote_repo(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    work = tmp_path / "seed"
    remote.mkdir()
    _git(["git", "init", "--bare", str(remote)], cwd=tmp_path)
    _git(["git", "clone", str(remote), str(work)], cwd=tmp_path)
    _git(["git", "config", "user.email", "test@example.com"], cwd=work)
    _git(["git", "config", "user.name", "Test User"], cwd=work)
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    _git(["git", "add", "README.md"], cwd=work)
    _git(["git", "commit", "-m", "seed"], cwd=work)
    _git(["git", "push", "origin", "master"], cwd=work)
    return remote


def test_build_push_url_injects_placeholder_username_only_for_github_https():
    url = "https://github.com/MandhiraT/ai-trends-research.git"
    assert build_push_url(url, "ghp_example") == "https://x-access-token@github.com/MandhiraT/ai-trends-research.git"
    assert build_push_url(url, "") == url
    assert build_push_url("git@github.com:MandhiraT/ai-trends-research.git", "ghp_example") == "git@github.com:MandhiraT/ai-trends-research.git"


def test_prepare_fresh_checkout_replaces_stale_directory_and_restores_repo(tmp_path):
    remote = _make_remote_repo(tmp_path)
    checkout = tmp_path / "checkout"

    # Simulate a stale/bad working directory from a previous run.
    checkout.mkdir()
    (checkout / "broken.txt").write_text("stale state", encoding="utf-8")

    prepared = prepare_fresh_checkout(str(remote), checkout, token=None, allowed_roots=[tmp_path])

    assert prepared == checkout
    assert (checkout / ".git").exists()
    assert (checkout / "README.md").read_text(encoding="utf-8") == "hello\n"
    assert not (checkout / "broken.txt").exists()

    status = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "## master" in status.stdout


def test_prepare_fresh_checkout_does_not_persist_token_in_git_config(tmp_path):
    remote = _make_remote_repo(tmp_path)
    checkout = tmp_path / "checkout-token"

    prepare_fresh_checkout(str(remote), checkout, token="ghp_secret_token", allowed_roots=[tmp_path])

    config_text = (checkout / ".git" / "config").read_text(encoding="utf-8")
    assert "ghp_secret_token" not in config_text
    assert "x-access-token" not in config_text


def test_prepare_fresh_checkout_rejects_paths_outside_approved_roots(tmp_path):
    remote = _make_remote_repo(tmp_path)
    checkout = tmp_path / "unsafe-checkout"

    try:
        prepare_fresh_checkout(str(remote), checkout, token=None)
    except GitRepoError as exc:
        assert "outside approved ATS cache roots" in str(exc)
    else:
        raise AssertionError("Expected GitRepoError for checkout path outside approved roots")
