import numpy as np
import pandas as pd
import pytest

from ashare_quant.lesson_stats import (
    benjamini_hochberg,
    drawdown_recovery_periods,
    historical_var_es,
    moving_block_bootstrap_mean_interval,
    recovery_period,
    variance_inflation_factors,
)


def test_vif_identifies_collinearity() -> None:
    rng = np.random.default_rng(3)
    x = rng.normal(size=200)
    independent = rng.normal(size=200)
    features = pd.DataFrame({"x": x, "copy": 2.0 * x, "independent": independent})
    result = variance_inflation_factors(features)
    assert np.isinf(result["x"])
    assert np.isinf(result["copy"])
    assert result["independent"] == pytest.approx(1.0, abs=0.05)


def test_benjamini_hochberg_preserves_order_and_controls_rejections() -> None:
    p_values = pd.Series([0.01, 0.04, 0.03, 0.20], index=list("abcd"))
    result = benjamini_hochberg(p_values, alpha=0.05)
    assert result.index.tolist() == list("abcd")
    assert result["adjusted_p_value"].tolist() == pytest.approx(
        [0.04, 4.0 / 75.0, 4.0 / 75.0, 0.20]
    )
    assert result["reject"].tolist() == [True, False, False, False]


def test_moving_block_bootstrap_is_reproducible() -> None:
    values = pd.Series(np.sin(np.arange(100) / 8) + 0.1)
    first = moving_block_bootstrap_mean_interval(
        values, block_size=8, n_bootstrap=500, seed=9
    )
    second = moving_block_bootstrap_mean_interval(
        values, block_size=8, n_bootstrap=500, seed=9
    )
    assert first == second
    assert first[0] < values.mean() < first[1]


def test_historical_var_and_es_use_positive_loss_convention() -> None:
    risk = historical_var_es([-0.10, -0.04, -0.02, 0.01, 0.03], confidence=0.80)
    assert risk["var"] == pytest.approx(0.052)
    assert risk["es"] == pytest.approx(0.10)
    assert risk["es"] >= risk["var"]


def test_recovery_periods_include_completed_and_open_drawdowns() -> None:
    dates = pd.bdate_range("2024-01-02", periods=6)
    returns = pd.Series([0.10, -0.10, 0.12, 0.02, -0.20, 0.01], index=dates)
    periods = drawdown_recovery_periods(returns)
    assert periods["recovered"].tolist() == [True, False]
    assert periods["duration"].tolist() == [2, 2]
    assert recovery_period(returns) == 2


def test_statistical_input_validation() -> None:
    with pytest.raises(ValueError):
        benjamini_hochberg([0.1, np.nan])
    with pytest.raises(ValueError):
        moving_block_bootstrap_mean_interval([1.0, 2.0], block_size=3)
    with pytest.raises(ValueError):
        historical_var_es([], confidence=0.95)
