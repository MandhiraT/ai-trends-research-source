import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ai_trends_daily_summary_thai as daily_summary


def test_build_telegram_message_includes_publish_warnings():
    message = daily_summary.build_telegram_message(
        date_str="2026-06-24",
        time_str="09:30 ICT",
        lines=["✅ AI Agents — 3 videos\n   https://example.com/report.md"],
        total_videos=3,
        found=1,
        audio_status=[],
        group="morning",
        publish_warnings=[
            "GitHub upload ของ reports ล้มเหลว — สรุปนี้อ้างอิงไฟล์ local เป็นหลัก",
            "GitHub upload ของ audio ล้มเหลว — ลิงก์เสียงอาจยังไม่อัปเดตบน GitHub",
        ],
    )

    assert "Publish warnings" in message
    assert "GitHub upload ของ reports ล้มเหลว" in message
    assert "GitHub upload ของ audio ล้มเหลว" in message
    assert "AI Trends Research — Morning" in message


def test_generate_daily_summary_prints_publish_warnings(monkeypatch):
    monkeypatch.setattr(daily_summary, "build_status", lambda date_str, topics: (["✅ AI Agents — 1 video\n   https://example.com"], 1, 1, []))

    summary, *_ = daily_summary.generate_daily_summary(
        group="morning",
        publish_warnings=["GitHub upload ของ reports ล้มเหลว — สรุปนี้อ้างอิงไฟล์ local เป็นหลัก"],
    )

    assert "Publish warnings:" in summary
    assert "GitHub upload ของ reports ล้มเหลว" in summary
