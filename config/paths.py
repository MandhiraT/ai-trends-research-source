"""
AI Trends Research — Path Configuration
Import at the top of every Python script:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config'))
    from paths import PROJECT_ROOT, CREDENTIALS_FILE, REPORTS_DIR, PROMPTS_DIR
"""
import os

PROJECT_ROOT = os.environ.get(
    'PROJECT_ROOT',
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

SCRIPTS_DIR       = os.path.join(PROJECT_ROOT, 'scripts')
PROMPTS_DIR       = os.path.join(PROJECT_ROOT, 'prompts')
REPORTS_DIR       = os.path.join(PROJECT_ROOT, 'ai_trends_reports')
LOGS_DIR          = os.path.join(PROJECT_ROOT, 'logs')
CREDENTIALS_FILE  = os.environ.get('CREDENTIALS_FILE',
                        os.path.join(PROJECT_ROOT, 'credentials.env'))

# GitHub upload working directory
GITHUB_TEMP_CLONE = os.environ.get('GITHUB_TEMP_CLONE', '/tmp/ai-trends-research')

# Prompt files
THAI_SUMMARY_PROMPT          = os.path.join(PROMPTS_DIR, 'thai_summary_prompt.txt')
THAI_SUMMARY_PROMPT_DETAILED = os.path.join(PROMPTS_DIR, 'thai_summary_prompt_detailed.txt')

# Ensure runtime dirs exist
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR,    exist_ok=True)


def load_credentials():
    """Load credentials.env into os.environ if not already set."""
    if not os.path.exists(CREDENTIALS_FILE):
        return
    with open(CREDENTIALS_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                os.environ.setdefault(key.strip(), val.strip())


load_credentials()
