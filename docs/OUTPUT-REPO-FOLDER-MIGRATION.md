# Output Repo Folder Migration Plan

Target repo: `MandhiraT/ai-trends-research`
Local clone: `/tmp/ai-trends-research`

## Goal

Normalize generated/publish artifacts before broader ATS voice automation.

Canonical top-level folders:

```text
reports/{topic}/{date}.md
assets/{topic}/{date}.json
audio_scripts/{topic}/{date}-vN.md
audio_scripts/{topic}/{date}-vN-deep-dive.md
voice/{topic}/{date}-vN.wav
voice/{topic}/{date}-vN-deep-dive.wav
social/{topic}/{date}.json
social/{topic}/{date}.md
```

## Current issues found

- `Voice/NateHerk/*.wav` uses legacy uppercase top-level folder and CamelCase topic.
- `voice/joanna_wiebe/*.wav` already uses the canonical top-level folder.
- `Content Marketing/Joanna-Wiebe/...` is legacy content folder outside canonical `reports/`.
- `/tmp/ai-trends-research` initially had stale deleted files in `git status`; fixed with `git restore reports` before migration.

## Migration map

### Voice files

```text
Voice/NateHerk/2026-05-04.wav → voice/nateherk/2026-05-04.wav
Voice/NateHerk/2026-05-05.wav → voice/nateherk/2026-05-05.wav
Voice/NateHerk/2026-05-06.wav → voice/nateherk/2026-05-06.wav
Voice/NateHerk/2026-05-07.wav → voice/nateherk/2026-05-07.wav
Voice/NateHerk/2026-05-08.wav → voice/nateherk/2026-05-08.wav
Voice/NateHerk/2026-05-09.wav → voice/nateherk/2026-05-09.wav
Voice/NateHerk/2026-05-10.wav → voice/nateherk/2026-05-10.wav
Voice/NateHerk/2026-05-11.wav → voice/nateherk/2026-05-11.wav
Voice/NateHerk/2026-05-12.wav → voice/nateherk/2026-05-12.wav
Voice/NateHerk/2026-05-13.wav → voice/nateherk/2026-05-13.wav
Voice/NateHerk/2026-05-14.wav → voice/nateherk/2026-05-14.wav
Voice/NateHerk/2026-05-16.wav → voice/nateherk/2026-05-16.wav
Voice/NateHerk/2026-05-17.wav → voice/nateherk/2026-05-17.wav
```

### Legacy content marketing files

These appear to be older Joanna reports/playlist files. Do not delete without reviewing links/history.

Proposed conservative migration:

```text
Content Marketing/Joanna-Wiebe/2026-04-22.md → reports/joanna_wiebe/2026-04-22.md (if not duplicate/conflict)
Content Marketing/Joanna-Wiebe/2026-04-23.md → reports/joanna_wiebe/2026-04-23.md (if not duplicate/conflict)
Content Marketing/Joanna-Wiebe/playlist_urls.md → reports/joanna_wiebe/playlist_urls.md or docs/source_urls/joanna_wiebe.md (needs decision)
Content Marketing/Joanna-Wiebe/joanna-wiebe/* → likely duplicate legacy nesting; compare before moving/deleting
```

Current Phase A scope: migrate `Voice/NateHerk` only and update upload scripts. Leave `Content Marketing/` untouched until duplicate comparison is complete.

## Scripts that must be updated

- `scripts/upload_audio_to_github.py` — currently publishes to legacy `Voice/NateHerk`; should publish to `voice/nateherk`.
- Any docs/config that mention `Voice/NateHerk` should be updated or noted as legacy.

## Verification checklist

- `git status --short --branch` clean before migration.
- After migration:
  - `Voice/` directory gone or empty.
  - `voice/nateherk/*.wav` count = previous `Voice/NateHerk/*.wav` count.
  - `voice/joanna_wiebe/*` preserved.
  - upload script points to `voice/nateherk`.
  - no `.ogg` files introduced.
  - `git diff --stat` shows renames, not delete+untracked mismatches if possible.

## Handoff notes

If interrupted:

1. Check source repo: `/home/mandhira/Desktop/Projects/ai-trends-research-source`.
2. Check output repo: `/tmp/ai-trends-research`.
3. Run `git status --short --branch` in both repos.
4. Read this file and `docs/TASKS.md` row: `ATS output repo folder cleanup — Phase A`.
