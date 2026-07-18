"""Regression test: on-demand reports were silently excluded from the
Assets page's "Generate Assets" date-range filter whenever the range
included the report's own day.

Root cause: api_assets_generate() compared the *full* filename stem
against date_from/date_to. Regular reports' stem IS the plain date
(2026-05-14.md), but on-demand reports' stem also carries time/slug/
video-id (2026-07-18_0807_make-any-topic-addictive-social-media_
LvuoNlYRs7g.md) — since that's a longer string sharing the same 10-char
date prefix, it sorts *after* the plain date, so date_str > date_to
wrongly excluded it whenever date_to was set to that same day (exactly
what an HTML <input type="date"> defaulting to "today" would submit).
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.app import filter_reports_by_date_range


def _p(name: str) -> Path:
    return Path(f"/fake/reports/on_demand/research_job/{name}.md")


def test_on_demand_report_survives_date_to_set_to_its_own_day():
    # This is the exact real-world case reported: an on-demand report
    # created today must not be excluded when date_to == today.
    reports = [_p("2026-07-18_0807_make-any-topic-addictive-social-media_LvuoNlYRs7g")]
    result = filter_reports_by_date_range(reports, date_from=None, date_to="2026-07-18")
    assert result == reports


def test_on_demand_report_survives_date_from_and_date_to_both_set_to_its_day():
    reports = [_p("2026-07-18_0807_make-any-topic-addictive-social-media_LvuoNlYRs7g")]
    result = filter_reports_by_date_range(reports, date_from="2026-07-18", date_to="2026-07-18")
    assert result == reports


def test_regular_report_still_filtered_normally():
    reports = [Path("/fake/reports/ai_agents/2026-07-17.md"), Path("/fake/reports/ai_agents/2026-07-18.md")]
    result = filter_reports_by_date_range(reports, date_from="2026-07-18", date_to="2026-07-18")
    assert result == [Path("/fake/reports/ai_agents/2026-07-18.md")]


def test_on_demand_report_correctly_excluded_when_truly_outside_range():
    reports = [_p("2026-07-18_0807_make-any-topic-addictive-social-media_LvuoNlYRs7g")]
    result = filter_reports_by_date_range(reports, date_from="2026-07-19", date_to=None)
    assert result == []

    result2 = filter_reports_by_date_range(reports, date_from=None, date_to="2026-07-17")
    assert result2 == []


def test_no_range_given_returns_everything_unfiltered():
    reports = [_p("2026-07-18_0807_x_abc"), Path("/fake/reports/ai_agents/2026-05-01.md")]
    assert filter_reports_by_date_range(reports, None, None) == reports


def test_mixed_regular_and_on_demand_reports_in_same_day_range():
    on_demand = _p("2026-07-18_0807_make-any-topic-addictive-social-media_LvuoNlYRs7g")
    regular = Path("/fake/reports/ai_agents/2026-07-18.md")
    older = Path("/fake/reports/ai_agents/2026-07-10.md")
    result = filter_reports_by_date_range([on_demand, regular, older], date_from="2026-07-18", date_to="2026-07-18")
    assert set(result) == {on_demand, regular}
