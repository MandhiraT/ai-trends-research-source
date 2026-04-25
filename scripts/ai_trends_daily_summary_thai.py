#!/usr/bin/env python3

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "config"))
try:
    from paths import PROJECT_ROOT, CREDENTIALS_FILE, REPORTS_DIR, PROMPTS_DIR, GITHUB_TEMP_CLONE, THAI_SUMMARY_PROMPT, THAI_SUMMARY_PROMPT_DETAILED
except ImportError:
    PROJECT_ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
    CREDENTIALS_FILE = _os.path.join(PROJECT_ROOT, "credentials.env")
    REPORTS_DIR = _os.path.join(PROJECT_ROOT, "ai_trends_reports")
    PROMPTS_DIR = _os.path.join(PROJECT_ROOT, "prompts")
    GITHUB_TEMP_CLONE = GITHUB_TEMP_CLONE
    THAI_SUMMARY_PROMPT = _os.path.join(PROMPTS_DIR, "thai_summary_prompt.txt")
    THAI_SUMMARY_PROMPT_DETAILED = _os.path.join(PROMPTS_DIR, "thai_summary_prompt_detailed.txt")

"""
AI Trends Daily Summary in Thai
Generates a daily summary with links to all reports in Thai language
"""

import os
import glob
from datetime import datetime

def generate_daily_summary():
    """Generate daily summary in Thai with GitHub links"""
    date_str = datetime.now().strftime('%Y-%m-%d')
    report_topics = ['ai_agents', 'claude', 'ai_viral_niche', 'ai_trends']
    
    summary = f"""# สรุปงานวิจัยเทรนด์ AI - {date_str}

รายงานวิจัยเทรนด์ AI รายวันได้รับการอัปโหลดเรียบร้อยแล้วค่ะ! 📊

## 🔗 ลิงก์รายงานทั้งหมด

"""
    
    for topic in report_topics:
        github_url = f"https://github.com/MandhiraT/ai-trends-research/blob/master/reports/{topic}/{date_str}.md"
        # Thai topic names
        thai_names = {
            'ai_agents': 'เทรนด์ AI Agents',
            'claude': 'ระบบนิเวศ Claude', 
            'ai_viral_niche': 'เทรนด์ AI Viral Niche',
            'ai_trends': 'ช่อง NATEHERK'
        }
        topic_name = thai_names.get(topic, topic)
        summary += f"• [{topic_name}]({github_url})\n"
    
    summary += f"""

รายงานทั้งหมดอยู่ใน repository: [MandhiraT/ai-trends-research](https://github.com/MandhiraT/ai-trends-research)

---
สรุปโดย Atlas Research Agent • {datetime.now().strftime('%d %B %Y %H:%M ICT')}
"""
    
    return summary

if __name__ == "__main__":
    summary = generate_daily_summary()
    print(summary)