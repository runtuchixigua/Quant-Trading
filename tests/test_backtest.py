import numpy as np
import pandas as pd
import pytest

from ashare_quant.backtest import BacktestConfig, run_backtest


def zero_cost_config(**kwargs: object) -> BacktestConfig:
    return BacktestConfig(commission=0.0, stamp_duty=0.0, slippage=0.0, **kwargs)


def test_signal_is_executed_one_day_later() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = pd.DataFrame({"A": [100.0, 110.0, 121.0]}, index=dates)
    targets = pd.DataFrame({"A": [1.0, 1.0, 1.0]}, index=dates)
    result = run_backtest(prices, targets, config=zero_cost_config())
    assert np.isclose(result.returns.iloc[0], 0.0)
    assert np.isclose(result.returns.iloc[1], 0.0)
    assert np.isclose(result.returns.iloc[2], 0.10)


def test_limit_up_rejects_buy() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = pd.DataFrame({"A": [100.0, 110.0, 121.0]}, index=dates)
    targets = pd.DataFrame({"A": 1.0}, index=dates)
    limit_up = pd.DataFrame({"A": [False, True, False]}, index=dates)
    result = run_backtest(prices, targets, limit_up=limit_up, config=zero_cost_config())
    assert np.isclose(result.rejected_turnover.iloc[1], 1.0)
    assert np.isclose(result.returns.sum(), 0.0)


def test_same_day_execution_is_forbidden() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    prices = pd.DataFrame({"A": [100.0, 101.0]}, index=dates)
    targets = pd.DataFrame({"A": [1.0, 1.0]}, index=dates)
    with pytest.raises(ValueError, match="未来函数"):
        run_backtest(prices, targets, config=zero_cost_config(execution_lag=0))
