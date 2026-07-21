import json

import pandas as pd
import pytest

from ashare_quant.lesson_io import read_manifest
from ashare_quant.lesson_registry import get_lesson
from ashare_quant.lessons import LessonResult
from ashare_quant.lessons_intro import (
    run_week_02,
    run_week_03,
    run_week_04,
    run_week_05,
)


@pytest.mark.parametrize(
    ("week", "runner"),
    [
        (2, run_week_02),
        (3, run_week_03),
        (4, run_week_04),
        (5, run_week_05),
    ],
)
def test_intro_runners_write_shared_and_topic_artifacts(tmp_path, week, runner) -> None:
    output = tmp_path / f"week{week:02d}"
    result = runner(output, quick=True)

    assert isinstance(result, LessonResult)
    assert result.week == week
    assert result.output == output
    assert isinstance(result.summary, pd.Series)
    assert (output / "manifest.json").exists()
    assert (output / "homework.md").exists()
    assert (output / "acceptance.json").exists()
    assert list(output.glob("*.csv"))
    assert list(output.glob("*.png"))
    assert [path for path in output.glob("*.md") if path.name != "homework.md"]

    manifest = read_manifest(output)
    assert manifest["week"] == week
    assert manifest["quick"] is True
    assert manifest["runner"] == f"ashare_quant.lessons_intro:run_week_{week:02d}"
    assert all((output / artifact).exists() for artifact in manifest["artifacts"])
    acceptance = json.loads((output / "acceptance.json").read_text(encoding="utf-8"))
    assert acceptance["week"] == week
    assert acceptance["status"] == "pending"
    assert acceptance["criteria"]


@pytest.mark.parametrize(
    ("week", "runner"),
    [
        (2, run_week_02),
        (3, run_week_03),
        (4, run_week_04),
        (5, run_week_05),
    ],
)
def test_intro_runners_preserve_homework_and_are_deterministic(tmp_path, week, runner) -> None:
    output = tmp_path / f"week{week:02d}"
    first = runner(output, quick=True)
    (output / "homework.md").write_text("# 我的答案\n", encoding="utf-8")
    second = runner(output, force=True, quick=True)

    pd.testing.assert_series_equal(first.summary, second.summary)
    assert (output / "homework.md").read_text(encoding="utf-8") == "# 我的答案\n"
    assert get_lesson(week).resolve_runner() is runner


def test_week_02_has_field_dictionary_and_market_cases(tmp_path) -> None:
    output = run_week_02(tmp_path / "week02", quick=True).output
    fields = pd.read_csv(output / "field_dictionary.csv")
    cases = pd.read_csv(output / "mechanism_cases.csv")

    assert {
        "date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "adjust_factor",
        "suspended",
        "is_st",
        "limit_up",
        "limit_down",
        "list_date",
    }.issubset(set(fields["field"]))
    assert {"source", "available_at"}.issubset(fields.columns)
    assert {"T+1", "100股整数手", "涨停", "跌停", "停牌"}.issubset(
        set(cases["mechanism"])
    )


def test_week_03_reports_all_strategies_and_timeline(tmp_path) -> None:
    output = run_week_03(tmp_path / "week03", quick=True).output
    returns = pd.read_csv(output / "strategy_returns.csv")

    assert {
        "buy_and_hold",
        "ma_20_60",
        "momentum_60",
        "reversal_5",
        "equal_weight_benchmark",
    }.issubset(returns.columns)
    timeline = (output / "execution_timeline.md").read_text(encoding="utf-8")
    assert "T+1" in timeline
    assert "execution_lag" in timeline


def test_week_04_contains_full_cost_grid(tmp_path) -> None:
    output = run_week_04(tmp_path / "week04", quick=True).output
    grid = pd.read_csv(output / "cost_grid.csv")

    assert len(grid) == 27
    assert grid[["commission", "slippage", "stamp_duty"]].drop_duplicates().shape[0] == 27
    assert set(grid["commission_level"]) == {"zero", "base", "double"}


def test_week_05_rejects_orders_and_exposes_leakage_counterexample(tmp_path) -> None:
    output = run_week_05(tmp_path / "week05", quick=True).output
    orders = pd.read_csv(output / "rejected_orders.csv")
    comparison = pd.read_csv(output / "leakage_comparison.csv", index_col="experiment")

    event = orders.loc[orders["limit_up"] & orders["limit_down"] & orders["suspended"]]
    assert len(event) == 1
    assert event["rejected_turnover"].iloc[0] > 0
    assert comparison.loc["leaked_future_winner", "total_return"] > comparison.loc[
        "honest_past_momentum", "total_return"
    ]
