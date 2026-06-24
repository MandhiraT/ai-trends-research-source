import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import upload_audio_to_github as audio_upload


def test_remove_matching_files_only_removes_current_date_outputs(tmp_path):
    target = tmp_path / "voice" / "topic"
    target.mkdir(parents=True)
    keep = target / "2026-06-23-v1.wav"
    remove1 = target / "2026-06-24-v1.wav"
    remove2 = target / "2026-06-24-v2.wav"
    for path in [keep, remove1, remove2]:
        path.write_text("x", encoding="utf-8")

    audio_upload._remove_matching_files(str(target), "2026-06-24.wav", "2026-06-24-*.wav")

    assert keep.exists()
    assert not remove1.exists()
    assert not remove2.exists()
