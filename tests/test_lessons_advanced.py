import json

import numpy as np
import pandas as pd
import pytest

from ashare_quant.lessons import LessonResult
from ashare_quant.lessons_advanced import (
    run_week_13,
    run_week_14,
    run_week_15,
    run_week_16,
    run_week_17,
    run_week_18,
)


RUNNERS = [
    run_week_13,
    run_week_14,
    run_week_15,
    run_week_16,
    run_week_17,
    run_week_18,
]


@pytest.mark.parametrize(("week", "runner"), enumerate(RUNNERS, start=13))
def test_advanced_lesson_contract_and_manifest(tmp_path, week, runner) -> None:
    result = runner(tmp_path / f"week{week:02d}", quick=True)

    assert isinstance(result, LessonResult)
    assert result.week == week
    assert result.summary.notna().all()
    for common in ("manifest.json", "homework.md", "acceptance.json"):
        assert (result.output / common).exists()

    manifest = json.loads((result.output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["week"] == week
    assert manifest["quick"] is True
    assert manifest["runner"].endswith(f":run_week_{week:02d}")
    assert all((result.output / artifact).exists() for artifact in manifest["artifacts"])


def test_week_13_snapshot_is_point_in_time_and_hashed(tmp_path) -> None:
    result = run_week_13(tmp_path / "week13", quick=True)
    snapshot = pd.read_csv(result.output / "pit_snapshot.csv", parse_dates=["announcement_date"])
    lineage = json.loads((result.output / "lineage.json").read_text(encoding="utf-8"))

    assert snapshot["announcement_date"].le(pd.Timestamp(lineage["as_of"])).all()
    assert len(lineage["source_sha256"]) == 64
    assert len(lineage["snapshot_sha256"]) == 64


def test_week_14_exposes_survivorship_bias(tmp_path) -> None:
    result = run_week_14(tmp_path / "week14", quick=True)
    comparison = pd.read_csv(result.output / "bias_comparison.csv")
    master = pd.read_csv(result.output / "security_master.csv")

    assert (~master["survived_to_end"]).any()
    assert comparison["survivor_only_wealth"].iloc[-1] > comparison[
        "historical_wealth"
    ].iloc[-1]


def test_week_15_event_effect_beats_placebo(tmp_path) -> None:
    result = run_week_15(tmp_path / "week15", quick=True)
    summary = pd.read_csv(result.output / "event_summary.csv", index_col=0).iloc[:, 0]

    assert summary["mean_car"] > 0
    assert summary["event_minus_placebo"] > 0.01
    assert summary["bootstrap_lower"] < summary["mean_car"] < summary["bootstrap_upper"]


def test_week_16_reports_redundancy_fdr_and_marginal_value(tmp_path) -> None:
    result = run_week_16(tmp_path / "week16", quick=True)
    diagnostics = pd.read_csv(result.output / "factor_diagnostics.csv", index_col=0)

    assert diagnostics.loc["value_clone", "vif"] > 5
    assert {"adjusted_p_value", "reject", "marginal_oos_mse_reduction"}.issubset(
        diagnostics.columns
    )


def test_week_17_covariances_and_attribution_are_valid(tmp_path) -> None:
    result = run_week_17(tmp_path / "week17", quick=True)
    sample = pd.read_csv(result.output / "sample_covariance.csv", index_col=0)
    shrunk = pd.read_csv(result.output / "ledoit_wolf_covariance.csv", index_col=0)
    attribution = pd.read_csv(result.output / "asset_risk_attribution.csv", index_col=0)

    assert sample.shape == shrunk.shape
    assert np.linalg.eigvalsh(shrunk).min() >= -1e-10
    volatility = np.sqrt(
        float(attribution["weight"] @ shrunk @ attribution["weight"])
    )
    assert np.isclose(attribution["volatility_contribution"].sum(), volatility)


def test_week_18_compares_four_normalized_portfolios_and_perturbations(tmp_path) -> None:
    result = run_week_18(tmp_path / "week18", quick=True)
    weights = pd.read_csv(result.output / "portfolio_weights.csv", index_col=0)
    perturbation = pd.read_csv(result.output / "input_perturbation.csv", index_col=0)

    assert set(weights) == {
        "equal_weight",
        "minimum_variance",
        "mean_variance",
        "risk_budget",
    }
    assert np.allclose(weights.sum(), 1.0)
    assert (perturbation["l1_weight_change"] >= 0).all()


def test_rerun_never_overwrites_homework(tmp_path) -> None:
    output = tmp_path / "week18"
    run_week_18(output, quick=True)
    homework = output / "homework.md"
    homework.write_text("我的答案", encoding="utf-8")

    run_week_18(output, force=True, quick=True)

    assert homework.read_text(encoding="utf-8") == "我的答案"
