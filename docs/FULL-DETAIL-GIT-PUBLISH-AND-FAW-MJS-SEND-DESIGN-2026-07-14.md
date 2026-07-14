# ATS Full Detail — Git Publish Confirmation + Send-to-FAW/MJS Design

**Date:** 2026-07-14
**Status:** Analysis + design only — not implemented, awaiting Mandy's decisions below
**Trigger:** Mandy asked for Full Detail reports (generated from `/assets/manage`) to (1) get pushed to the git repo like a normal report, as a `.md` file, and (2) be sendable to FAW and MJS.

---

## 1. Git push — already happens today, no code needed

Traced the exact publish chain: `run_daily_summary_cron.sh` unconditionally runs `upload_reports_to_github_fixed.py` every morning, which hands the **entire** `ai_trends_reports/reports/` directory to `github_api_upload.py`'s `upload_subtrees()`. That function does `for f in sorted(local_dir.rglob("*")): if f.is_file(): ...` — a blanket recursive sweep with **no filename filtering at all**. A Full Detail file (`{date}-v{N}-full-detail.md`) lives as a direct sibling of the day's `{date}.md` inside that same tree, so it is already included in every push, with zero new code required.

Confirmed empirically: `ai_trends_reports/reports/nateherk/2026-07-13-v1-full-detail.md` and two under `reports/on_demand/research_job/` already exist in exactly the swept location.

**One documentation correction worth noting:** an older doc (`docs/ON-DEMAND-REPORT-GITHUB-PUSH-DESIGN.md`, 2026-06-04) claims on-demand reports are *not* auto-pushed and need a manual SOP — that's stale. The publisher was rewritten 2026-06-28 (`c73f795`) to the blanket-sweep approach above, which has no such exclusion. Recommend marking that doc superseded so it doesn't mislead anyone later.

**Nothing to build for item 1** — it already works. Worth a live confirmation on the next morning cron run (check the GitHub repo for a full-detail `.md` appearing under `reports/`), but that's verification, not implementation.

## 2. Send to MJS — the existing bridge is structurally wrong for Full Detail, and would silently gut it

MJS already has a brief-creation bridge (`ats_to_mjs_bridge.py`, triggered from MJS dashboard's `/ats` → "📝 Create Brief"). It is built entirely around the **regular multi-video report shape**:

- `_extract_video_section()` looks for `## Video N:` headings to slice out one video's content. A Full Detail file has no such heading — its real structure is `# Full Detail: {title}` header block, then Thai prose sections like `### เดินตามเนื้อหาทีละขั้นตอน`.
- When no `## Video N:` match is found, the code falls back to `report_text[:4000]` — for the real 21,442-character Full Detail file on disk, that's a ~80% silent truncation. This defeats the entire point of Full Detail (preserving every step), and it's not a loud failure — a brief would still get created, just gutted.
- Separately, the bridge treats whatever "date" string it's given as a literal filename component with no validation, so a full-detail "date" like `2026-07-13-v1-full-detail` ends up as the actual brief folder name (`mjs_briefs/{folder}/2026-07-13-v1-full-detail/`) instead of a real date — messy, though not itself destructive.

**A second, independent bug found during this investigation (not something Mandy asked about, flagging separately):** MJS's own `/ats` Source Browser (`_ats_list_sources`/`_ats_get_dates` in `micro-journey-studio/dashboard/app.py`) does `ATS_REPORTS.rglob("*.md")` with **zero filename filtering**, treating every file's stem as if it were a plain date. This means Full Detail files **already show up today** as their own bogus fake "source" cards on `/ats` (sorted above the real date since `"...-v1-full-detail"` string-sorts higher), and clicking "Create Brief" on one of them hits the exact truncation bug above — this can happen by accident today, with nobody having asked for a Full Detail → MJS integration yet. Recommend fixing this regardless of what's decided below (add the same `DATE_OR_REPORT_STEM_RE`-style guard ATS's own dashboard already uses for exactly this problem, filtering full-detail siblings out of the generic source list).

**Design for the real feature:** rather than trying to make the generic multi-video bridge also handle a fundamentally different single-video, uncapped-prose shape, add a **dedicated, explicit path**:
- A new action on `/assets/manage` itself (where Mandy already is when she has a Full Detail file open) — "📤 Send to MJS" — since a Full Detail file is already tied to one specific video (topic/date/video_no/title/source_url are all known at generation time, per its header), there's no need to route through the generic ATS Source Browser at all.
- Server-side: a small, new brief-builder specific to Full Detail files — reads the whole body (no `[:4000]` truncation, no `## Video N:` search), uses the file's own header metadata (Topic/Video/Source) directly instead of re-deriving it, and writes a brief exactly like today's (`mjs_briefs/{folder}/{date}/brief_{hash}.json`) so it lands in the existing Brief Review flow Mandy already knows (`/ats/brief/<id>`, editable, Approve & Seed).

## 3. Send to FAW — real integration exists, but for a different data shape; this needs new code, not a parameter tweak

FAW already has a working ATS integration (`ats_faw_bridge.py`, `ats_source_brief.py`, `ats_faw_generate.py`, `ats_analysis_selector.py`, a DB table `ats_faw_imports`) — this is not a "nothing exists" case. But every part of it is keyed to:
- A separate **asset JSON** file (`ai_trends_reports/assets/{topic}/{date}.json`), generated by ATS's asset pipeline — Full Detail generation never produces one of these.
- Report parsing that requires `## Video N:` headers **and** specific Thai section markers (`สรุปภาพรวม`, `ประเด็นสำคัญ`, `Insight ที่น่าจำ`, `เอาไปใช้ยังไง`, `สรุปสั้น`) — none of which exist in a Full Detail file's structure.

Pointing the existing bridge at a Full Detail file would either hard-fail (`[ERROR] Asset not found`, since no asset JSON exists) or produce a nearly-empty brief (all section-extraction returns blank, `context_quality` drops to "none").

**This needs genuinely new code** — a separate ingestion function in FAW that accepts a Full Detail file directly (header metadata + full prose body), bypassing the asset-JSON+multi-video-parsing machinery entirely. Before designing this further, I need to understand **what FAW would actually do with it** — see open question 1 below; the answer changes what "new code" means here (a draft post? raw content for something else? a different content type entirely?).

---

## 4. Open questions for Mandy

1. **What does "send to FAW" concretely produce?** FAW's existing ATS integration creates draft social/content posts from short video summaries. A Full Detail file is a long, uncapped, step-by-step walkthrough — quite different in shape/length from what FAW's current draft-post flow expects. What's the actual use case — a long-form post/article draft, source material for something else FAW does, or something new? I don't want to guess and build the wrong shape.
2. **Send to MJS — through the existing Brief Review flow, or more direct?** Since Full Detail content is already a single, curated, complete walkthrough (not a raw multi-video report needing selection), would you rather it still land in the familiar Brief Review page (edit fields, pick brand/style, Approve & Seed — same UI you already know), or skip straight to seeding an MJS project without an intermediate brief step? I'd default to reusing Brief Review (less new UI, consistent with how you already work), but wanted to confirm.
3. **Entry point — from `/assets/manage` directly, right?** Confirming the button lives on the Assets/manage page next to the Full Detail file itself (where you already are when this need comes up), not through the generic ATS Source Browser (which has the bug in §2 anyway).
4. **Fix the fake-source-card bug (§2) as part of this, or separately?** It's a real, independent bug (Full Detail files already masquerading as broken source cards today) — happy to bundle it into this same pass since I'm already touching the relevant code, unless you'd rather track it separately.

No implementation has started. This document + an MPD task card are the only changes made so far.
