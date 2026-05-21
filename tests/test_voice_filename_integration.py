"""Source-level integration tests verifying all ATS callers use voice_filenames helper."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATE_AUDIO = ROOT / "scripts" / "generate_audio_report.py"
UPLOAD_AUDIO   = ROOT / "scripts" / "upload_audio_to_github.py"
DAILY_SUMMARY  = ROOT / "scripts" / "ai_trends_daily_summary_thai.py"
DASHBOARD_APP  = ROOT / "dashboard" / "app.py"


# ── Task 2: generate_audio_report.py ──────────────────────────────────────────

def test_generate_audio_report_uses_voice_filename_helper_for_wavs():
    source = GENERATE_AUDIO.read_text(encoding="utf-8")
    assert "from voice_filenames import" in source
    assert 'voice_filename(topic_key, date_str, variant="whole")' in source
    assert "voice_filename(topic_key, date_str, video_no=video_num)" in source
    assert "f'{date_str}-v{video_num}.wav'" not in source


# ── Task 3: upload_audio_to_github.py ─────────────────────────────────────────

def test_upload_audio_uses_legacy_aware_voice_file_finder():
    source = UPLOAD_AUDIO.read_text(encoding="utf-8")
    assert "find_voice_files" in source
    assert "f'{date_str}*.wav'" not in source


# ── Task 4: ai_trends_daily_summary_thai.py ───────────────────────────────────

def test_daily_summary_uses_legacy_aware_voice_file_finder():
    source = DAILY_SUMMARY.read_text(encoding="utf-8")
    assert "find_voice_files" in source
    assert "name.startswith(date_str)" not in source


# ── Task 5: dashboard/app.py — _voice_script_paths ───────────────────────────

def test_dashboard_voice_paths_use_topic_prefixed_helper():
    source = DASHBOARD_APP.read_text(encoding="utf-8")
    path_fn_start = source.index("def _voice_script_paths")
    path_fn_end   = source.index("def _extract_voice_text", path_fn_start)
    body = source[path_fn_start:path_fn_end]
    assert "voice_filename" in body
    assert 'f"{date}-v{vno}.wav"' not in body
    assert 'f"{date}-v{vno}-deep-dive.wav"' not in body


# ── Task 6: dashboard/app.py — api_audio_serve ───────────────────────────────

def test_dashboard_download_uses_legacy_aware_voice_file_finder():
    source = DASHBOARD_APP.read_text(encoding="utf-8")
    audio_serve_start = source.index("def api_audio_serve")
    social_start      = source.index("def api_social_view", audio_serve_start)
    body = source[audio_serve_start:social_start]
    assert "find_voice_files" in body
    assert 'glob(f"{date}-v*.wav")' not in body
    assert 'glob(f"{date}.wav")' not in body
