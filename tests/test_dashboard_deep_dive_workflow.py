from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_APP = ROOT / "dashboard" / "app.py"


def test_dashboard_exposes_deep_dive_script_generation_endpoint_and_button():
    source = DASHBOARD_APP.read_text(encoding="utf-8")

    assert '"/api/assets/generate-deep-dive-script"' in source
    assert "api_assets_generate_deep_dive_script" in source
    assert "generateDeepDiveScript" in source
    assert "Generate deep dive script" in source
    assert "fetch('/api/assets/generate-deep-dive-script'" in source


def test_dashboard_keeps_voice_generation_separate_from_deep_dive_script_generation():
    source = DASHBOARD_APP.read_text(encoding="utf-8")

    deep_dive_handler_start = source.index("def api_assets_generate_deep_dive_script")
    next_handler_start = source.index("def api_assets_generate_voice", deep_dive_handler_start)
    deep_dive_handler = source[deep_dive_handler_start:next_handler_start]

    assert "generate_deep_dive_script" in deep_dive_handler
    assert "save_deep_dive_script" in deep_dive_handler
    assert "generate_voice_from_text" not in deep_dive_handler
    assert "generate_voice_from_saved_script" not in deep_dive_handler
