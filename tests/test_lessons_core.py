import json

import pandas as pd
import pytest

from ashare_quant.lesson_io import read_manifest
from ashare_quant.lesson_registry import get_lesson
from ashare_quant.lessons import LessonResult
from ashare_quant.lessons_core import (
    run_week_06,
    run_week_07,
    run_week_08,
    run_week_09,
    run_week_10,
    run_week_11,
    run_week_12,
)


RUNNERS = {
    6: run_week_06,
    7: run_week_07,
    8: run_week_08,
    9: run_week_09,
    10: run_week_10,
    11: run_week_11,
    12: run_week_12,
}


@pytest.fixture(scope="module")
def lesson_outputs(tmp_path_factory):
    root = tmp_path_factory.mktemp("core_lessons")
    return {week: runner(root / f"week{week:02d}", quick=True) for week, runner in RUNNERS.items()}


def test_registry_resolves_all_core_lesson_runners() -> None:
    for week, runner in RUNNERS.items():
        assert get_lesson(week).resolve_runner() is runner


def test_each_core_lesson_is_self_contained(lesson_outputs) -> None:
    for week, result in lesson_outputs.items():
        assert isinstance(result, LessonResult)
        assert result.week == week
        assert not result.summary.empty
        assert (result.output / "manifest.json").exists()
        assert (result.output / "homework.md").exists()
        assert (result.output / "acceptance.json").exists()
        assert (result.output / "report.md").exists()
        manifest = read_manifest(result.output)
        assert manifest["week"] == week
        assert manifest["quick"] is True
        assert manifest["runner"].endswith(f":run_week_{week:02d}")
        for artifact in manifest["artifacts"]:
            assert (result.output / artifact).exists(), (week, artifact)
        acceptance = json.loads(
            (result.output / "acceptance.json").read_text(encoding="utf-8")
        )
        assert acceptance["status"] == "pending"
        assert acceptance["criteria"]


def test_week_06_preprocessing_is_finite(lesson_outputs) -> None:
    frame = pd.read_csv(lesson_outputs[6].output / "factor_preprocessing.csv")
    assert {
        "raw_factor",
        "winsorized",
        "neutralized",
        "processed_factor",
    }.issubset(frame.columns)
    assert frame["processed_factor"].notna().all()
    assert abs(frame["processed_factor"].mean()) < 1e-10


def test_week_07_has_ic_quantiles_and_decay(lesson_outputs) -> None:
    output = lesson_outputs[7].output
    quantiles = pd.read_csv(output / "quantile_returns.csv")
    decay = pd.read_csv(output / "ic_decay.csv")
    assert {"1", "2", "3", "4", "5"}.issubset(quantiles.columns)
    assert len(decay) == 6
    assert decay["mean_rank_ic"].notna().any()


def test_week_08_enforces_portfolio_constraints(lesson_outputs) -> None:
    weights = pd.read_csv(lesson_outputs[8].output / "portfolio_weights.csv")
    assert weights["weight"].max() <= 0.15 + 1e-12
    industry_weights = weights.groupby(["date", "industry"])["weight"].sum()
    assert industry_weights.max() <= 0.35 + 1e-12
    assert (weights.groupby("date")["weight"].sum() <= 1.0 + 1e-12).all()


def test_week_09_walk_forward_has_baseline_and_is_time_ordered(lesson_outputs) -> None:
    output = lesson_outputs[9].output
    predictions = pd.read_csv(output / "predictions.csv")
    folds = pd.read_csv(output / "folds.csv", parse_dates=["train_end", "prediction_start"])
    comparison = pd.read_csv(output / "model_comparison.csv")
    assert {"ridge_prediction", "baseline_prediction", "label"}.issubset(predictions.columns)
    assert set(comparison["model"]) == {"ridge", "equal_factor_baseline"}
    assert not folds.empty
    assert (folds["train_end"] < folds["prediction_start"]).all()


def test_week_10_records_models_and_fold_importance(lesson_outputs) -> None:
    output = lesson_outputs[10].output
    comparison = pd.read_csv(output / "model_comparison.csv")
    importance = pd.read_csv(output / "fold_importance.csv")
    experiments = pd.read_csv(output / "experiment_log.csv")
    assert set(comparison["model"]) == {"ridge", "hist_gbdt"}
    assert {"fold", "feature", "importance", "model"}.issubset(importance.columns)
    assert importance.groupby("model")["fold"].nunique().min() >= 1
    assert {"seed", "parameters", "quick"}.issubset(experiments.columns)


def test_week_11_runs_exactly_five_days_with_reconciliation(lesson_outputs) -> None:
    output = lesson_outputs[11].output
    nav = pd.read_csv(output / "daily_nav.csv")
    orders = pd.read_csv(output / "orders.csv")
    fills = pd.read_csv(output / "fills.csv")
    reconciliation = pd.read_csv(output / "reconciliation.csv")
    assert nav["date"].nunique() == 5
    assert set(orders["date"]) == set(fills["date"]) == set(reconciliation["date"])
    assert reconciliation["matched"].all()


def test_week_12_runs_fourteen_days_and_latches_stop(lesson_outputs) -> None:
    output = lesson_outputs[12].output
    monitoring = pd.read_csv(output / "daily_monitoring.csv")
    decisions = pd.read_csv(output / "stop_rules.csv")
    assert monitoring["date"].nunique() == 14
    assert decisions["should_stop"].any()
    first_halt = monitoring.index[monitoring["strategy_halted"]].min()
    assert monitoring.loc[first_halt:, "strategy_halted"].all()
    assert (output / "stage_report.md").exists()


def test_homework_is_never_overwritten(tmp_path) -> None:
    output = tmp_path / "week06"
    run_week_06(output, quick=True)
    homework = output / "homework.md"
    homework.write_text("# 我的答案\n", encoding="utf-8")

    run_week_06(output, force=True, quick=True)

    assert homework.read_text(encoding="utf-8") == "# 我的答案\n"
