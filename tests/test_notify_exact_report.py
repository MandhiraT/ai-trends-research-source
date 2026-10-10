import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "notify_topic.py"
spec = importlib.util.spec_from_file_location("notify_topic_exact_report", SCRIPT)
assert spec is not None and spec.loader is not None
notify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notify)


def _report(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# AI Trends Research - Marketing\n\n"
        "**Date:** 2026-10-09 12:34 ICT\n\n"
        "## Video 1: First\n\n### Full Summary\nเนื้อหารายงานฉบับเต็มหนึ่ง\n\n"
        "## Video 2: Second\n\n### Full Summary\nเนื้อหารายงานฉบับเต็มสอง\n\n"
        "## Video 3: Third\n\n### Full Summary\nเนื้อหารายงานฉบับเต็มสาม\n",
        encoding="utf-8",
    )
    return path


def test_exact_rerun_report_is_emailed_with_full_content_and_unique_url(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    report = _report(reports / "marketing" / "2026-10-09_1234_marketing-3-videos.md")
    captured = {}

    monkeypatch.setattr(notify, "REPORTS_BASE", reports)
    monkeypatch.setattr(notify, "TOPIC_MAP", {"marketing": ("Alex Hormozi", "marketing", "marketing")})
    monkeypatch.setattr(notify, "load_routing_config", lambda: ({}, {"marketing": {
        "email_enabled": True,
        "telegram_enabled": False,
        "recipient_emails": ["owner@example.com"],
        "telegram_chat_ids": [],
        "notification_mode": "per_topic",
    }}))

    def fake_send(recipients, subject, html_body, text_body, dry_run=False):
        captured.update(
            recipients=recipients,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            dry_run=dry_run,
        )
        return True

    monkeypatch.setattr(notify, "send_email", fake_send)

    assert notify.notify_topic(
        "marketing",
        "2026-10-09",
        email_only=True,
        report_path_override=str(report),
    ) is True

    assert "rerun 12:34" in captured["subject"]
    assert "Third" in captured["text_body"]
    assert "Full Summary" in captured["text_body"]
    assert "เนื้อหารายงานฉบับเต็มสาม" not in captured["text_body"]
    assert "Third" in captured["html_body"]
    assert "Full Summary" in captured["html_body"]
    assert "เนื้อหารายงานฉบับเต็มสาม" not in captured["html_body"]
    assert "View Report (browser)" in captured["html_body"]
    assert "date=2026-10-09_1234_marketing-3-videos" in captured["text_body"]


def test_exact_report_must_stay_inside_the_topic_report_folder(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    wrong = _report(reports / "other" / "2026-10-09_1234_other.md")
    monkeypatch.setattr(notify, "REPORTS_BASE", reports)
    monkeypatch.setattr(notify, "TOPIC_MAP", {"marketing": ("Alex Hormozi", "marketing", "marketing")})
    monkeypatch.setattr(notify, "load_routing_config", lambda: ({}, {"marketing": {
        "email_enabled": True,
        "telegram_enabled": False,
        "recipient_emails": ["owner@example.com"],
        "telegram_chat_ids": [],
        "notification_mode": "per_topic",
    }}))

    assert notify.notify_topic(
        "marketing",
        "2026-10-09",
        email_only=True,
        report_path_override=str(wrong),
    ) is False
