from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_report_index import parse_report_file, build_index_records, search_records, write_indexes


def sample_report() -> str:
    return """# AI Trends Research - NATEHERK

**Date:** 2026-05-14 06:01 ICT
**Topic:** NATEHERK
**Mode:** Channel
**Videos Processed:** 1

---

## Video 1: Anthropic Just Dethroned OpenAI. Here's What Happens Next.

**Source:** https://www.youtube.com/watch?v=-nG-9vlSkho
**Video ID:** -nG-9vlSkho

### 📝 Full Summary (Thai)
### 1) ศึก Claude Code vs Codex และยุค AI โค้ดดิ้งราคาถูก

### 2) สรุปภาพรวม Full Summary
คลิปนี้พูดถึง Anthropic, Claude Code, OpenAI และ Codex ที่กำลังแข่งขันกันหนักมาก บริษัท AI ยอมลดราคาเพื่อเก็บ adoption และข้อมูลผู้ใช้

### 3) ประเด็นสำคัญ
* Claude Code แซง OpenAI ในภาคธุรกิจ
* บริษัท AI ใช้กลยุทธ์ land grab

### 4) Insight ที่น่าจำ
ความยืดหยุ่นในการใช้ AI coding tools สำคัญมาก

### 5) เอาไปใช้ยังไง
อย่าผูก workflow กับเครื่องมือเดียว

### 6) สรุปสั้น
ใช้ช่วงราคาถูกให้คุ้ม แต่ต้องออกแบบระบบให้ย้ายเครื่องมือได้

---

Report generated at: 2026-05-13T23:01:05+00:00
"""


def test_parse_report_file_extracts_video_metadata_and_keywords(tmp_path):
    report_path = tmp_path / "ai_trends_reports" / "reports" / "NATEHERK" / "2026-05-14.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(sample_report(), encoding="utf-8")

    records = parse_report_file(report_path, reports_root=tmp_path / "ai_trends_reports" / "reports")

    assert len(records) == 1
    record = records[0]
    assert record["date"] == "2026-05-14"
    assert record["topic"] == "NATEHERK"
    assert record["video_no"] == 1
    assert record["video_title"] == "Anthropic Just Dethroned OpenAI. Here's What Happens Next."
    assert record["source_url"] == "https://www.youtube.com/watch?v=-nG-9vlSkho"
    assert record["video_id"] == "-nG-9vlSkho"
    assert record["report_path"] == "NATEHERK/2026-05-14.md"
    assert "claude-code" in record["tags"]
    assert "codex" in record["keywords_normalized"]
    assert "คลิปนี้พูดถึง" in record["summary_short"]


def test_build_index_records_skips_unavailable_transcript_sections(tmp_path):
    reports_root = tmp_path / "reports"
    report = reports_root / "claude_code" / "claude_code_design" / "2026-05-14.md"
    report.parent.mkdir(parents=True)
    report.write_text(
        """# Claude Code - Claude Code Design

**Date:** 2026-05-14
**Topic:** claude code design

## Video 1: Good English Video
**Source:** https://youtube.com/watch?v=abc
**Video ID:** abc
### 📝 Full Summary (Thai)
### 1) Claude Design ใช้งานจริง
### 2) สรุปภาพรวม Full Summary
Claude Design ช่วยสร้าง design system และ template ได้

---
## Video 2: Thai Video Without English Transcript
**Source:** https://youtube.com/watch?v=def
**Video ID:** def
### 📝 Full Summary (Thai)
# ไม่สามารถสรุปวิดีโอนี้ได้
**เหตุผล:** วิดีโอนี้ไม่มี transcript ภาษาอังกฤษ
""",
        encoding="utf-8",
    )

    records = build_index_records(reports_root)

    assert len(records) == 1
    assert records[0]["video_title"] == "Good English Video"
    assert records[0]["topic"] == "claude code design"


def test_search_records_matches_topic_title_summary_keywords():
    records = [
        {
            "date": "2026-05-14",
            "topic": "NATEHERK",
            "video_title": "Anthropic and Claude Code pricing",
            "thai_title": "ศึก Claude Code vs Codex",
            "summary_short": "OpenAI Codex และ Anthropic แข่งกันเรื่อง AI coding",
            "keywords_normalized": ["claude-code", "codex", "openai"],
            "tags": ["ai-coding"],
        },
        {
            "date": "2026-05-14",
            "topic": "joanna_wiebe",
            "video_title": "Networking tips",
            "thai_title": "สูตร networking",
            "summary_short": "ทักคนใหม่และ follow up",
            "keywords_normalized": ["networking"],
            "tags": ["business"],
        },
    ]

    results = search_records(records, "NATEHERK claude code")

    assert [r["topic"] for r in results] == ["NATEHERK"]


def test_write_indexes_creates_jsonl_sqlite_and_mobile_markdown(tmp_path):
    out_dir = tmp_path / "index"
    records = [
        {
            "date": "2026-05-14",
            "topic": "NATEHERK",
            "video_no": 1,
            "video_title": "Anthropic and Claude Code pricing",
            "thai_title": "ศึก Claude Code vs Codex",
            "source_url": "https://youtube.com/watch?v=abc",
            "video_id": "abc",
            "report_path": "NATEHERK/2026-05-14.md",
            "summary_short": "สรุปเรื่อง AI coding tools",
            "keywords": ["Claude Code", "Codex"],
            "keywords_normalized": ["claude-code", "codex"],
            "tags": ["ai-coding", "claude-code"],
        }
    ]

    write_indexes(records, out_dir)

    jsonl = out_dir / "reports_index.jsonl"
    sqlite_path = out_dir / "reports_index.sqlite"
    by_topic = out_dir / "by-topic" / "NATEHERK.md"
    by_keyword = out_dir / "by-keyword" / "claude-code.md"

    assert jsonl.exists()
    assert sqlite_path.exists()
    assert by_topic.exists()
    assert by_keyword.exists()
    assert json.loads(jsonl.read_text(encoding="utf-8").splitlines()[0])["topic"] == "NATEHERK"
    assert "Anthropic and Claude Code pricing" in by_topic.read_text(encoding="utf-8")
