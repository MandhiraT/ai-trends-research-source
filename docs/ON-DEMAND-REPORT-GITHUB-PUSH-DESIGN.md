# On Demand Report GitHub Push Design

> Status: Documented only — not implemented yet.

**Goal:** Record the safe future design for pushing ATS On Demand reports to the output GitHub repo without making auto-push the default behavior today.

**Decision:** Keep the current manual approval workflow for now. Mandy prefers asking Mali to push On Demand output reports because it is safer than automatic external publishing.

---

## Current Behavior

When Mandy clicks **Run** for an ATS Dashboard job:

1. ATS generates the report locally under:
   - `ai_trends_reports/reports/<report_folder>/<YYYY-MM-DD>.md`
2. The source repo ignores generated reports via `.gitignore`:
   - `ai_trends_reports/`
3. The report is **not pushed automatically** to GitHub.
4. If Mandy wants the report published, Mali manually pushes only the intended report file to the output repo:
   - Repo: `MandhiraT/ai-trends-research`
   - Branch: `master`
   - Destination path mirrors local path relative to `ai_trends_reports/reports/`

Example:

```text
Local:
ai_trends_reports/reports/on_demand/research_job/2026-06-04.md

Output repo:
reports/on_demand/research_job/2026-06-04.md
```

---

## Current Manual SOP

When Mandy asks Mali to push an On Demand report:

1. Confirm the latest successful Dashboard status for that job.
2. Identify the exact `latest_report` path from `ai_trends_reports/dashboard/job_status.json`.
3. Copy only that report into a fresh or updated clone of `MandhiraT/ai-trends-research`.
4. Stage only that one output report path.
5. Run a high-confidence secret scan on the staged diff.
6. Commit with a report-specific message.
7. Push to `master`.
8. Verify with GitHub API or `git ls-tree` that the file exists remotely.
9. Report the GitHub URL back to Mandy.

Do **not** use broad `git add .` for output reports.

---

## Future Feature Option: Opt-in Checkbox

If this becomes frequent enough to automate, add a checkbox in ATS Dashboard job settings:

```text
[ ] Push report to GitHub after successful run
```

Suggested config field:

```json
{
  "push_report_to_github": false
}
```

Recommended defaults:

- New jobs: `false`
- Existing jobs: `false`
- Mandy manually enables it per job when needed

This should be opt-in, not automatic for all On Demand jobs.

---

## Required Safety Rules Before Implementation

### 1. Push only the report from the finished job

Do not use the global newest `.md` file in `ai_trends_reports/reports/`.

Instead, resolve the report from the specific job:

- Prefer `latest_report` recorded for that job after the run completes.
- Verify the report path is inside that job’s configured `report_folder`.
- Reject paths outside `ai_trends_reports/reports/`.

### 2. Push only after successful research run

Only push when:

- process exit code is `0`
- report file exists
- report file is non-empty
- secret scan passes

If the research run fails, GitHub push must be skipped.

### 3. Secret scan before commit

Run a high-confidence scan for patterns such as:

- API keys
- GitHub tokens
- Bearer tokens
- passwords/secrets in assignment-like syntax

If scan fails:

- do not commit
- set Dashboard status to `github_push_failed`
- show the reason without printing the secret

### 4. Separate research status and GitHub status

Dashboard status should distinguish:

```json
{
  "state": "success",
  "github_push_state": "pushed|skipped|failed",
  "github_push_url": "https://github.com/...",
  "github_push_error": ""
}
```

This avoids making a successful research run look failed only because GitHub push failed.

### 5. Handle duplicate daily filenames safely

If the same report path already exists remotely:

- allow update commits
- clearly label status as `updated existing report`
- do not create random duplicate filenames unless explicitly designed later

### 6. Handle output repo conflicts safely

Before pushing:

- fetch/pull latest `master`
- stage only the target report file
- if pull or push conflicts, fail safely and show `github_push_failed`

Do not auto-resolve conflicts for report publishing.

---

## UX Recommendation

In the Dashboard job form:

```text
[ ] Push report to GitHub after successful run
    Publishes only this job’s generated report to MandhiraT/ai-trends-research.
    Keep off for drafts/private runs.
```

In job status:

```text
Research: success
GitHub: skipped
```

or:

```text
Research: success
GitHub: pushed
URL: https://github.com/MandhiraT/ai-trends-research/blob/master/reports/...
```

or:

```text
Research: success
GitHub: failed
Reason: secret scan failed / push conflict / auth error
```

---

## Why Not Implement Now

Mandy decided this is not necessary yet. Manual push by Mali is safer for now because:

- On Demand reports can be ad hoc or sensitive.
- Automatic publishing is an external side effect.
- Manual review keeps the risk of accidental publication lower.
- The current usage frequency does not yet justify added automation.

---

## Implementation Notes for Future Mali

If Mandy later asks to implement this, use TDD and add tests for:

1. Disabled checkbox leaves behavior unchanged.
2. Enabled checkbox pushes only the exact job report.
3. Failed research run skips GitHub push.
4. Secret scan failure blocks commit/push.
5. Missing report records `github_push_failed` without changing research success state.
6. Output repo update modifies the existing same-day report path safely.

Likely files to modify:

- `dashboard/app.py`
- `config/research_jobs.json`
- new helper, possibly `scripts/push_report_to_output_repo.py`
- tests under `tests/`

Do not implement until Mandy explicitly asks.
