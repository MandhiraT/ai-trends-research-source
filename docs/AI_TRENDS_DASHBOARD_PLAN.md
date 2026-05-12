# AI Trends Search Dashboard Plan

Last updated: 2026-05-12 ICT

## Goal

Build a simple local dashboard for AI Trends Research so a user can add or edit research jobs without editing crontab or shell commands manually.

The dashboard should support:

- Add a new topic search.
- Add a YouTube channel or playlist URL.
- Add a specific video URL.
- Set number of videos to summarize.
- Set report output folder.
- Run a job manually for verification.
- View recent report files and job logs.
- Use the same dashboard on localhost and through Cloudflare Tunnel.

The first version must not disrupt the existing production cron jobs or daily summary report.

## Current System Summary

The current AI Trends Research system is script based:

- Topic or channel jobs run through `scripts/run_ai_trends_with_creds.sh`.
- Claude Code subtopic jobs run through `scripts/run_claude_code_subtopics_with_creds.sh`.
- Full manual daily pipeline runs through `scripts/run_all_today.sh`.
- Daily summary, GitHub upload, audio generation, and Telegram delivery run through `scripts/run_daily_summary_cron.sh`.
- Output reports are written under `ai_trends_reports/reports/{topic_folder}/`.
- Logs are written under `logs/`.
- Current cron schedule runs research jobs from early morning and the consolidated summary at 07:55 Bangkok time.

The dashboard should reuse these scripts rather than replacing them.

## Current Implementation Status

Implemented on 2026-05-12:

- Added dashboard plan document: `docs/AI_TRENDS_DASHBOARD_PLAN.md`.
- Added dashboard-managed job config: `config/research_jobs.json`.
- Added local dashboard app: `dashboard/app.py`.
- Added manual run support from the dashboard.
- Added report browser for local markdown reports.
- Added dashboard log browser.
- Added read-only production cron view.
- Added `--video-url`, `--report-folder`, and `--config-job-id` support to `scripts/run_ai_trends_research_enhanced.py`.
- Verified dashboard pages on `http://127.0.0.1:8092`.
- Added Cloudflare Tunnel route for `ai-trends.thequietself.com`.
- Installed stable local `cloudflared` binary at `/home/mandhira/.cloudflared/cloudflared`.
- Updated Cloudflare helper files to avoid the old missing `/tmp/cloudflared-linux-amd64` binary.
- Verified public dashboard route at `https://ai-trends.thequietself.com`.

Not changed:

- Existing production crontab.
- Existing daily summary cron at 07:55 Bangkok time.
- Existing report upload/audio/Telegram summary flow.
- Existing FAW dashboard route `faw.thequietself.com -> localhost:8080`.

## Recommended Approach

Use the dashboard as a control panel over a job configuration file.

Do not make the dashboard directly rewrite the production crontab in the first version. Production cron should continue to run from the existing crontab until the dashboard has been tested.

Recommended implementation phases:

1. Add dashboard configuration storage.
2. Add a small local web dashboard.
3. Add manual job execution from the dashboard.
4. Add report and log browsing.
5. Add optional dashboard-managed cron export after verification.
6. Put the dashboard behind Cloudflare Tunnel after local testing.

## Data Model

Store dashboard-managed jobs in a simple JSON file:

`config/research_jobs.json`

Recommended shape:

```json
{
  "jobs": [
    {
      "id": "claude_code_seedance",
      "name": "Claude Code Seedance",
      "enabled": true,
      "source_type": "topic",
      "topic": "Claude Code Seedance",
      "source_url": "",
      "max_videos": 5,
      "detailed": true,
      "report_folder": "claude_code/claude_code_seedance",
      "schedule_time": "07:35",
      "include_in_daily_summary": true,
      "notes": ""
    }
  ]
}
```

Field meaning:

- `id`: stable internal job id.
- `name`: display name in the dashboard.
- `enabled`: whether the job should be included in dashboard-managed runs.
- `source_type`: `topic`, `channel`, `playlist`, `video`, or `claude_code_subtopic`.
- `topic`: topic name used for the report and AI summary context.
- `source_url`: optional YouTube channel, playlist, or video URL.
- `max_videos`: number of videos to fetch or process.
- `detailed`: whether to use the detailed Thai summary prompt.
- `report_folder`: output folder under `ai_trends_reports/reports/`.
- `schedule_time`: intended daily run time in Bangkok time.
- `include_in_daily_summary`: whether this job should be included in the consolidated summary workflow.
- `notes`: user notes for remembering why the job exists.

## Dashboard Features

Version 1 should stay small and practical:

- Dashboard home:
  - production cron status summary
  - latest daily summary status
  - recent job logs
  - recent generated reports

- Job list:
  - show active/inactive jobs
  - show topic/channel/video source
  - show max videos
  - show report folder
  - show last run status if available

- Add/edit job:
  - name
  - source type
  - topic
  - URL
  - number of videos
  - detailed summary on/off
  - report folder
  - enabled on/off

- Manual run:
  - run a single job now
  - show live or refreshed log output
  - show generated report path after completion

- Reports:
  - browse local markdown reports
  - open recent report text in browser
  - show file path for checking quality

## Backend Design

Recommended simple stack:

- Python standard library or Flask/FastAPI.
- Jinja templates or a minimal static frontend.
- No database for version 1.
- JSON config files for job definitions.
- Subprocess calls to the existing shell wrappers.

If keeping dependencies minimal is most important, use Python standard library `http.server` plus custom handlers.

If maintainability is more important, use Flask:

- Add `Flask` to `requirements.txt`.
- Create `dashboard/app.py`.
- Create `dashboard/templates/`.
- Create `dashboard/static/`.

Flask is recommended because the form handling, routing, and local UI will be simpler and easier to maintain than a custom HTTP server.

## Job Execution Mapping

For a normal topic search:

```bash
bash scripts/run_ai_trends_with_creds.sh --topic "AI Agents" --max-results 5 --detailed
```

For a YouTube channel or playlist:

```bash
bash scripts/run_ai_trends_with_creds.sh --topic "NATEHERK" --channel "https://youtube.com/@NATEHERK" --max-results 3 --detailed
```

For a specific video URL, add a new script mode:

```bash
bash scripts/run_ai_trends_with_creds.sh --topic "Topic Name" --video-url "https://youtube.com/watch?v=..." --detailed
```

This requires a small enhancement to `scripts/run_ai_trends_research_enhanced.py` because it currently supports topic search and channel/playlist URLs, but not one fixed video URL.

For Claude Code subtopics:

```bash
bash scripts/run_claude_code_subtopics_with_creds.sh --only "seedance" --max-results 5 --total-videos 5 --detailed
```

## Required Script Enhancements

To support the dashboard cleanly, add these low-risk enhancements:

1. `--video-url` support in `scripts/run_ai_trends_research_enhanced.py`.
   - Process exactly one given video URL.
   - Use the provided `--topic` for context and report folder.
   - Do not use YouTube search.

2. Optional `--report-folder` support.
   - Override the default sanitized topic folder.
   - Allows reports to be grouped under paths such as `claude_code/topic_name`.
   - Must validate that the folder stays inside `ai_trends_reports/reports/`.

3. Optional `--config-job-id` metadata.
   - Save the dashboard job id into the report header.
   - Useful for tracking which dashboard job created each report.

4. Job status file.
   - Write last status to `ai_trends_reports/dashboard/job_status.json`.
   - Track `last_started_at`, `last_finished_at`, `exit_code`, `latest_report`, and `latest_log`.

These changes should be backward compatible with current cron commands.

## Cron Safety

Do not let version 1 of the dashboard directly edit crontab.

Production cron should remain the source of truth until the dashboard is verified locally.

Safe first step:

- Dashboard can display current crontab by reading `crontab -l`.
- Dashboard can show which jobs exist in `config/research_jobs.json`.
- Dashboard can run jobs manually.
- Dashboard can generate a proposed cron block in a text preview.

Later optional step:

- Add a button to export dashboard-managed jobs to a separate shell script, for example:
  - `scripts/run_dashboard_jobs_today.sh`
- Cron can then call that one script after manual approval.

This avoids breaking the existing 07:55 daily summary while the dashboard is being tested.

## Localhost Deployment

Recommended local command:

```bash
cd /home/mandhira/Desktop/Projects/ai-trends-research-source
python3 dashboard/app.py --host 127.0.0.1 --port 8092
```

Local URL:

```text
http://127.0.0.1:8092
```

The dashboard should default to `127.0.0.1` for local safety.

## Cloudflare Tunnel Deployment

There are two possible Cloudflare Tunnel modes:

1. Temporary tunnel for testing:

```bash
cloudflared tunnel --url http://127.0.0.1:8092
```

2. Named tunnel for a stable domain:

```bash
cloudflared tunnel route dns <tunnel-name> <subdomain.yourdomain.com>
```

Access needed from user:

- Confirm the desired dashboard domain or subdomain.
- Confirm whether `cloudflared` is already installed on the machine.
- Confirm whether the existing Cloudflare account already has a named tunnel for FAW dashboard.
- If reusing the FAW tunnel, provide or confirm the tunnel config path.

Security recommendation:

- Do not expose the dashboard publicly without Cloudflare Access or another authentication layer.
- The dashboard can run scripts and read logs, so it should be protected.
- Use Cloudflare Access with a permitted email list before using a public domain.

## Production Risk Controls

The implementation should follow these controls:

- Existing crontab must not be modified in version 1.
- Existing scripts must keep all current arguments working.
- Dashboard manual runs should write separate dashboard logs under `logs/dashboard/`.
- Dashboard config should be committed, but secrets must stay in `~/.credentials.env`.
- No API keys or credentials should be displayed in the UI.
- Report folder inputs must be sanitized to prevent writing outside `ai_trends_reports/reports/`.
- Manual runs should be one job at a time in version 1 to avoid rate limits.

## Implementation Plan

### Phase 1: Documentation and Design

Status: completed

- Create this dashboard plan.
- Confirm port and Cloudflare domain.
- Confirm whether Flask dependency is acceptable.

### Phase 2: Non-invasive Dashboard MVP

Status: partially completed

- Add `config/research_jobs.json`.
- Add `dashboard/app.py`.
- Add dashboard HTML/CSS inside the standard-library app.
- Add job list page.
- Add add/edit/delete job forms.
- Add report/log browser.
- Add manual run endpoint.
- Write dashboard logs under `logs/dashboard/`.

### Phase 3: Runner Compatibility Enhancements

Status: partially completed

- Add `--video-url`.
- Add `--report-folder`.
- Add dashboard status JSON output.
- Keep existing cron commands unchanged.
- Test existing cron-equivalent commands still work.

### Phase 4: Local Verification

Status: in progress

- Start dashboard on `127.0.0.1:8092`.
- Add one test topic job.
- Add one test channel job.
- Add one specific video URL job.
- Run each manually with a low video limit.
- Confirm reports are generated in expected folders.
- Confirm existing daily summary script still runs.

### Phase 5: Cloudflare Tunnel

Status: completed for routing; Cloudflare Access still needs confirmation in Cloudflare

- Start local dashboard bound to localhost.
- Configure temporary or named Cloudflare Tunnel.
- Add Cloudflare Access policy before exposing domain.
- Verify dashboard loads through the domain.
- Verify manual runs still execute from the local machine.

### Phase 6: Optional Cron Integration

Status: future

- Generate dashboard-managed daily runner script.
- Keep existing production cron available as fallback.
- Migrate one low-risk job first.
- Migrate remaining jobs only after one successful daily cycle.

## Recommended First Implementation Scope

Build the dashboard MVP with manual runs only.

This gives the user the immediate ability to add topics, channels, video URLs, max video counts, and report folders without risking the daily production cron.

After the dashboard has generated reports correctly for a few manual tests, add optional cron export.

## Local Test Result

The dashboard server was started with:

```bash
python3 dashboard/app.py --host 127.0.0.1 --port 8092
```

Verified routes:

- `GET /`
- `GET /reports`
- `GET /cron`

Current local URL:

```text
http://127.0.0.1:8092
```

Current public URL:

```text
https://ai-trends.thequietself.com
```

Current tunnel route:

```yaml
- hostname: ai-trends.thequietself.com
  service: http://localhost:8092
```
