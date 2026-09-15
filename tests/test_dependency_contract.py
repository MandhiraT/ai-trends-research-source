from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]


def _declared_packages() -> set[str]:
    packages: set[str] = set()
    for raw_line in (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        package = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip().lower()
        packages.add(package)
    return packages


def test_click_is_declared_for_ats_mjs_bridge() -> None:
    bridge = (REPO_ROOT / "scripts" / "ats_to_mjs_bridge.py").read_text(encoding="utf-8")
    assert "import click" in bridge
    assert "click" in _declared_packages(), (
        "scripts/ats_to_mjs_bridge.py imports click, but requirements.txt does not declare it"
    )
