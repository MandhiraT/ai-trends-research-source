#!/usr/bin/env python3
"""Build searchable indexes for AI Trends markdown reports.

No-AI-cost Phase 1:
- Parse existing report markdown files.
- Produce one record per successfully summarized video section.
- Write JSONL, SQLite, and mobile-friendly Markdown indexes.

Default input/output:
  ai_trends_reports/reports/**/*.md -> ai_trends_reports/index/
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_ROOT = PROJECT_ROOT / "ai_trends_reports" / "reports"
INDEX_DIR = PROJECT_ROOT / "ai_trends_reports" / "index"

_UNAVAILABLE_MARKERS = (
    "ไม่สามารถสรุปวิดีโอนี้ได้",
    "ไม่มี transcript ภาษาอังกฤษ",
    "transcript unavailable",
)

_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "your", "you", "how",
    "what", "why", "when", "where", "are", "was", "were", "has", "have", "had", "just",
    "here", "next", "like", "use", "using", "about", "actually", "really", "to", "of", "in",
    "a", "an", "is", "on", "it", "as", "at", "by", "or", "be", "ai",
}

_KNOWN_TERMS = {
    "claude code": "claude-code",
    "claude design": "claude-design",
    "claude": "claude",
    "codex": "codex",
    "openai": "openai",
    "anthropic": "anthropic",
    "gemini": "gemini",
    "notebooklm": "notebooklm",
    "notebook lm": "notebooklm",
    "obsidian": "obsidian",
    "seedance": "seedance",
    "higgsfield": "higgsfield",
    "shopify": "shopify",
    "remotion": "remotion",
    "kling": "kling",
    "wan": "wan",
    "ugc": "ugc",
    "tts": "tts",
    "podcast": "podcast",
    "networking": "networking",
    "copywriting": "copywriting",
    "facebook": "facebook",
    "youtube": "youtube",
    "automation": "automation",
    "agent": "agent",
    "agents": "agents",
    "ai coding": "ai-coding",
    "coding": "coding",
    "design system": "design-system",
    "template": "template",
    "templates": "templates",
    "pricing": "pricing",
    "land grab": "land-grab",
}

_TAG_RULES = {
    "ai-coding": {"claude-code", "codex", "coding"},
    "design": {"claude-design", "design-system", "template", "templates"},
    "pricing": {"pricing", "land-grab"},
    "copywriting": {"copywriting"},
    "business": {"networking"},
    "video-ai": {"seedance", "higgsfield", "kling", "wan", "ugc"},
    "automation": {"automation", "agent", "agents"},
}


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "untitled"


def safe_markdown_filename(value: str) -> str:
    """Safe filename for generated Markdown pages, preserving readable ASCII case."""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii") or value
    value = re.sub(r"[^A-Za-z0-9ก-๙_-]+", "-", value).strip("-")
    return value or "untitled"


def normalize_keyword(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9ก-๙]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def _extract_meta(text: str, key: str) -> str:
    m = re.search(rf"^\*\*{re.escape(key)}:\*\*\s*(.+?)\s*$", text, flags=re.MULTILINE)
    return m.group(1).strip() if m else ""


def _split_video_sections(text: str) -> list[tuple[int, str, str]]:
    pattern = re.compile(r"^## Video\s+(\d+):\s*(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections: list[tuple[int, str, str]] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections.append((int(match.group(1)), match.group(2).strip(), text[start:end].strip()))
    return sections


def _strip_markdown(text: str) -> str:
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}", "", text)
    text = re.sub(r"_{1,2}", "", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_thai_title(section: str, fallback: str) -> str:
    # Current detailed report uses "### 1) <thai title>" inside each section.
    m = re.search(r"^#{1,6}\s*1\)\s*(.+?)\s*$", section, flags=re.MULTILINE)
    if m:
        title = _strip_markdown(m.group(1))
        if title:
            return title
    return fallback


def _extract_summary_short(section: str, max_chars: int = 260) -> str:
    marker = re.search(r"^#{1,6}\s*2\)\s*สรุปภาพรวม.*$", section, flags=re.MULTILINE)
    if marker:
        start = marker.end()
        next_heading = re.search(r"^#{1,6}\s*[3-6]\)", section[start:], flags=re.MULTILINE)
        end = start + next_heading.start() if next_heading else len(section)
        candidate = section[start:end]
    else:
        marker = re.search(r"^#{1,6}\s*📝\s*Full Summary.*$", section, flags=re.MULTILINE)
        candidate = section[marker.end():] if marker else section
    summary = _strip_markdown(candidate)
    summary = re.sub(r"^(แน่นอน!?|นี่คือสรุป[^\s]*|สวัสดีครับ!?|สวัสดีค่ะ!?)\s*", "", summary).strip()
    if len(summary) > max_chars:
        return summary[:max_chars].rsplit(" ", 1)[0].strip() + "…"
    return summary


def _extract_keywords(*texts: str) -> tuple[list[str], list[str], list[str]]:
    combined = " ".join(t for t in texts if t)
    lowered = combined.lower()
    keywords: list[str] = []
    normalized: list[str] = []

    for term, norm in _KNOWN_TERMS.items():
        if term in lowered and norm not in normalized:
            keywords.append(term.title() if term.islower() else term)
            normalized.append(norm)

    # Add salient English tokens from titles/summaries.
    for token in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", combined):
        norm = normalize_keyword(token)
        if norm in _STOPWORDS or norm in normalized:
            continue
        if len(normalized) >= 18:
            break
        keywords.append(token)
        normalized.append(norm)

    tags = []
    norm_set = set(normalized)
    for tag, terms in _TAG_RULES.items():
        if norm_set & terms:
            tags.append(tag)
    # Preserve important tool/provider names as tags too, so mobile keyword pages and
    # CLI filters can target them directly (e.g. --tag claude-code).
    for norm in sorted(norm_set):
        if norm in {"claude-code", "claude-design", "codex", "openai", "anthropic", "gemini", "notebooklm", "obsidian", "seedance", "higgsfield", "shopify"}:
            tags.append(norm)
    return keywords[:20], normalized[:20], sorted(set(tags))


def parse_report_file(report_path: str | Path, reports_root: str | Path = REPORTS_ROOT) -> list[dict[str, Any]]:
    report_path = Path(report_path)
    reports_root = Path(reports_root)
    text = report_path.read_text(encoding="utf-8")
    date = _extract_meta(text, "Date") or report_path.stem
    date = date.split()[0]
    topic = _extract_meta(text, "Topic") or report_path.parent.name.replace("_", " ")
    mode = _extract_meta(text, "Mode")

    records: list[dict[str, Any]] = []
    for video_no, video_title, section in _split_video_sections(text):
        if any(marker.lower() in section.lower() for marker in _UNAVAILABLE_MARKERS):
            continue
        source_url = _extract_meta(section, "Source")
        video_id = _extract_meta(section, "Video ID")
        thai_title = _extract_thai_title(section, video_title)
        summary_short = _extract_summary_short(section)
        keywords, keywords_normalized, tags = _extract_keywords(topic, video_title, thai_title, summary_short)
        try:
            rel_path = report_path.relative_to(reports_root).as_posix()
        except ValueError:
            rel_path = report_path.name
        records.append({
            "date": date,
            "topic": topic,
            "mode": mode,
            "video_no": video_no,
            "video_title": video_title,
            "thai_title": thai_title,
            "source_url": source_url,
            "video_id": video_id,
            "report_path": rel_path,
            "section_anchor": f"video-{video_no}-{slugify(video_title)[:80]}",
            "summary_short": summary_short,
            "keywords": keywords,
            "keywords_normalized": keywords_normalized,
            "tags": tags,
        })
    return records


def build_index_records(reports_root: str | Path = REPORTS_ROOT) -> list[dict[str, Any]]:
    reports_root = Path(reports_root)
    records: list[dict[str, Any]] = []
    for report_path in sorted(reports_root.rglob("*.md")):
        if any(part.startswith(".") for part in report_path.parts):
            continue
        records.extend(parse_report_file(report_path, reports_root=reports_root))
    records.sort(key=lambda r: (r.get("date", ""), r.get("topic", ""), r.get("video_no", 0)), reverse=True)
    return records


def _record_search_text(record: dict[str, Any]) -> str:
    parts = [
        record.get("date", ""),
        record.get("topic", ""),
        record.get("video_title", ""),
        record.get("thai_title", ""),
        record.get("summary_short", ""),
        " ".join(record.get("keywords", [])),
        " ".join(record.get("keywords_normalized", [])),
        " ".join(record.get("tags", [])),
    ]
    return " ".join(parts).lower()


def search_records(records: Iterable[dict[str, Any]], query: str, topic: str | None = None,
                   keyword: str | None = None, tag: str | None = None) -> list[dict[str, Any]]:
    terms = [t.lower() for t in re.findall(r"[\wก-๙.-]+", query or "") if t.strip()]
    topic_l = topic.lower() if topic else None
    keyword_l = normalize_keyword(keyword) if keyword else None
    tag_l = normalize_keyword(tag) if tag else None

    results = []
    for record in records:
        if topic_l and topic_l not in record.get("topic", "").lower():
            continue
        if keyword_l and keyword_l not in record.get("keywords_normalized", []):
            continue
        if tag_l and tag_l not in record.get("tags", []):
            continue
        haystack = _record_search_text(record)
        if terms and not all(term in haystack for term in terms):
            continue
        score = sum(haystack.count(term) for term in terms) if terms else 1
        item = dict(record)
        item["score"] = score
        results.append(item)
    results.sort(key=lambda r: (r.get("score", 0), r.get("date", "")), reverse=True)
    return results


def _write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _write_sqlite(records: list[dict[str, Any]], path: Path) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                topic TEXT,
                mode TEXT,
                video_no INTEGER,
                video_title TEXT,
                thai_title TEXT,
                source_url TEXT,
                video_id TEXT,
                report_path TEXT,
                section_anchor TEXT,
                summary_short TEXT,
                keywords_json TEXT,
                keywords_normalized_json TEXT,
                tags_json TEXT,
                search_text TEXT
            )
            """
        )
        conn.execute("CREATE INDEX idx_reports_date ON reports(date)")
        conn.execute("CREATE INDEX idx_reports_topic ON reports(topic)")
        conn.execute("CREATE INDEX idx_reports_video_id ON reports(video_id)")
        conn.execute(
            "CREATE VIRTUAL TABLE reports_fts USING fts5(topic, video_title, thai_title, summary_short, keywords, tags, content='')"
        )
        for record in records:
            keywords_json = json.dumps(record.get("keywords", []), ensure_ascii=False)
            keywords_norm_json = json.dumps(record.get("keywords_normalized", []), ensure_ascii=False)
            tags_json = json.dumps(record.get("tags", []), ensure_ascii=False)
            cur = conn.execute(
                """
                INSERT INTO reports (
                    date, topic, mode, video_no, video_title, thai_title, source_url, video_id,
                    report_path, section_anchor, summary_short, keywords_json,
                    keywords_normalized_json, tags_json, search_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("date"), record.get("topic"), record.get("mode"), record.get("video_no"),
                    record.get("video_title"), record.get("thai_title"), record.get("source_url"), record.get("video_id"),
                    record.get("report_path"), record.get("section_anchor"), record.get("summary_short"),
                    keywords_json, keywords_norm_json, tags_json, _record_search_text(record),
                ),
            )
            rowid = cur.lastrowid
            conn.execute(
                "INSERT INTO reports_fts(rowid, topic, video_title, thai_title, summary_short, keywords, tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    rowid,
                    record.get("topic", ""),
                    record.get("video_title", ""),
                    record.get("thai_title", ""),
                    record.get("summary_short", ""),
                    " ".join(record.get("keywords_normalized", [])),
                    " ".join(record.get("tags", [])),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _record_md_line(record: dict[str, Any]) -> str:
    report_link = f"../reports/{record.get('report_path', '')}"
    source = record.get("source_url") or ""
    source_link = f" · [YouTube]({source})" if source else ""
    tags = ", ".join(f"`{t}`" for t in record.get("tags", []))
    tags_text = f" · {tags}" if tags else ""
    return (
        f"- **{record.get('date')}** — [{record.get('video_title')}]({report_link})"
        f"  \n  Topic: `{record.get('topic')}`{source_link}{tags_text}"
        f"  \n  {record.get('summary_short', '')}\n"
    )


def _write_markdown_indexes(records: list[dict[str, Any]], out_dir: Path) -> None:
    # Clean only generated subfolders to avoid stale pages.
    for sub in ("by-topic", "by-keyword", "by-tag", "by-date"):
        folder = out_dir / sub
        if folder.exists():
            for p in folder.glob("*.md"):
                p.unlink()
        folder.mkdir(parents=True, exist_ok=True)

    readme_lines = [
        "# AI Trends Report Index",
        "",
        "Generated from local report markdown files. One row = one summarized video section.",
        "",
        f"Total indexed videos: **{len(records)}**",
        "",
        "## Browse",
        "",
        "- [By topic](by-topic/)",
        "- [By keyword](by-keyword/)",
        "- [By tag](by-tag/)",
        "- [By month](by-date/)",
        "",
        "## Latest",
        "",
    ]
    for record in records[:50]:
        readme_lines.append(_record_md_line(record))
    (out_dir / "README.md").write_text("\n".join(readme_lines).rstrip() + "\n", encoding="utf-8")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        grouped[r.get("topic", "unknown")].append(r)
    for topic, items in grouped.items():
        path = out_dir / "by-topic" / f"{safe_markdown_filename(topic)}.md"
        lines = [f"# Topic: {topic}", "", f"Total: {len(items)}", ""]
        lines.extend(_record_md_line(r) for r in items)
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    keyword_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        for kw in r.get("keywords_normalized", []):
            keyword_groups[kw].append(r)
    for kw, items in keyword_groups.items():
        path = out_dir / "by-keyword" / f"{slugify(kw)}.md"
        lines = [f"# Keyword: {kw}", "", f"Total: {len(items)}", ""]
        lines.extend(_record_md_line(r) for r in items[:200])
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    tag_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        for tag in r.get("tags", []):
            tag_groups[tag].append(r)
    for tag, items in tag_groups.items():
        path = out_dir / "by-tag" / f"{slugify(tag)}.md"
        lines = [f"# Tag: {tag}", "", f"Total: {len(items)}", ""]
        lines.extend(_record_md_line(r) for r in items[:200])
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    month_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        month_groups[str(r.get("date", ""))[:7]].append(r)
    for month, items in month_groups.items():
        if not month:
            continue
        path = out_dir / "by-date" / f"{slugify(month)}.md"
        lines = [f"# Month: {month}", "", f"Total: {len(items)}", ""]
        lines.extend(_record_md_line(r) for r in items)
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_keywords_json(records: list[dict[str, Any]], path: Path) -> None:
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        for kw in record.get("keywords_normalized", []):
            counts[kw] += 1
    data = dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_indexes(records: list[dict[str, Any]], out_dir: str | Path = INDEX_DIR) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(records, out_dir / "reports_index.jsonl")
    _write_sqlite(records, out_dir / "reports_index.sqlite")
    _write_keywords_json(records, out_dir / "keywords.json")
    _write_markdown_indexes(records, out_dir)


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AI Trends searchable report indexes")
    parser.add_argument("--reports-root", default=str(REPORTS_ROOT), help="Reports root directory")
    parser.add_argument("--out-dir", default=str(INDEX_DIR), help="Index output directory")
    parser.add_argument("--pretty", action="store_true", help="Print indexed records summary")
    args = parser.parse_args()

    records = build_index_records(args.reports_root)
    write_indexes(records, args.out_dir)
    print(f"[index] Indexed {len(records)} video section(s)")
    print(f"[index] Output: {args.out_dir}")
    if args.pretty:
        for record in records[:20]:
            print(f"- {record['date']} | {record['topic']} | {record['video_title']}")


if __name__ == "__main__":
    main()
