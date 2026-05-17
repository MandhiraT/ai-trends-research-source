from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_content_assets import generate_deep_dive_script, save_deep_dive_script


class FakeAI:
    def __init__(self):
        self.prompts = []

    def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "นี่คือสคริปต์ Deep Dive ภาษาไทยที่เล่าแบบพอดแคสต์ ครอบคลุมทุกประเด็นและตัวอย่างจากรายงานค่ะ"


class GreetingThenHookAI:
    def __init__(self):
        self.prompts = []
        self.responses = [
            "สวัสดีครับ วันนี้เราจะมาเจาะลึกเรื่อง AI agent กันค่ะ",
            "ใครจะคิดว่า AI agent หนึ่งตัวสามารถเปลี่ยน workflow ทั้งระบบได้ ถ้าเราออกแบบจากโจทย์เล็กให้ถูกก่อนค่ะ",
        ]

    def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0)


def sample_asset():
    long_section = "\n".join([
        "### 📝 Full Summary (Thai)",
        "### 1) Hook ของเนื้อหา",
        "ประเด็นนี้พูดถึงการใช้ AI agent ในการสร้าง workflow ธุรกิจแบบ end-to-end " * 8,
        "### 2) ตัวอย่างสำคัญ",
        "มีตัวอย่างบริษัท ทีมงาน และขั้นตอนที่ต้องเล่าครบ เพื่อให้คนฟังไม่ต้องกลับไปดูคลิปต้นฉบับ " * 8,
        "### 5) เอาไปใช้ยังไง",
        "เริ่มจากเลือก use case เล็ก วัดผล แล้วค่อยขยายเป็นระบบอัตโนมัติ " * 8,
    ])
    return {
        "date": "2026-05-17",
        "topic": "AI Agents",
        "videos": [
            {
                "video_no": 1,
                "video_title": "Building AI Agents",
                "thai_title": "สร้าง AI Agent ให้ใช้ได้จริง",
                "source_url": "https://youtube.com/watch?v=abc",
                "section_text": long_section,
            },
            {
                "video_no": 2,
                "video_title": "Other Video",
                "thai_title": "วิดีโออื่น",
                "source_url": "https://youtube.com/watch?v=def",
                "section_text": long_section,
            },
        ],
    }


def test_generate_deep_dive_script_targets_one_video_and_uses_full_episode_formula():
    asset = sample_asset()
    fake = FakeAI()

    result = generate_deep_dive_script(asset, video_no=1, module=fake)

    assert result["deep_dive_scripts_generated"] == 1
    assert len(fake.prompts) == 1
    prompt = fake.prompts[0]
    assert "Hook & Promise" in prompt
    assert "Core Problem" in prompt
    assert "Deep Dive" in prompt
    assert "Master Insights" in prompt
    assert "How-to Blueprint" in prompt
    assert "8–12" in prompt or "8-12" in prompt
    assert "Building AI Agents" in prompt
    assert asset["videos"][0]["audio_script_deep_dive"].startswith("นี่คือสคริปต์ Deep Dive")
    assert "audio_script_deep_dive" not in asset["videos"][1]


def test_generate_deep_dive_script_retries_when_ai_uses_forbidden_greeting_opening():
    asset = sample_asset()
    fake = GreetingThenHookAI()

    result = generate_deep_dive_script(asset, video_no=1, module=fake)

    assert result["deep_dive_scripts_generated"] == 1
    assert result["quality_retry_count"] == 1
    assert len(fake.prompts) == 2
    assert "ห้ามขึ้นต้นด้วยคำทักทาย" in fake.prompts[1]
    script = asset["videos"][0]["audio_script_deep_dive"]
    assert script.startswith("ใครจะคิด")
    assert not script.startswith("สวัสดี")


def test_save_deep_dive_script_writes_separate_reviewable_file_without_normal_script_sections(tmp_path):
    asset = sample_asset()
    asset["videos"][0]["audio_script_deep_dive"] = "เนื้อหา deep dive ที่ผ่านการ review แล้วค่ะ"

    path = save_deep_dive_script(asset, video_no=1, output_dir=tmp_path)

    assert path == tmp_path / "ai_agents" / "2026-05-17-v1-deep-dive.md"
    text = path.read_text(encoding="utf-8")
    assert "# Deep Dive Audio Script:" in text
    assert "Date: 2026-05-17" in text
    assert "Topic: AI Agents" in text
    assert "Video: Building AI Agents" in text
    assert "## Deep Dive Script" in text
    assert "เนื้อหา deep dive ที่ผ่านการ review แล้วค่ะ" in text
    assert "## Full Script" not in text
    assert "## Short Script" not in text
