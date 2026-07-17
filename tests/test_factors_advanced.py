import numpy as np
import pandas as pd

from ashare_quant.factors import (
    accruals,
    amihud_from_prices,
    book_to_price,
    earnings_yield,
    equal_weight_composite,
    factor_correlation,
    ic_decay,
    ic_ir,
    return_on_equity,
    rolling_ic_composite,
    yearly_ic,
)


def test_fundamental_factors_and_amihud() -> None:
    index = pd.Index(["A", "B"])
    profit = pd.Series([10.0, 20.0], index=index)
    equity = pd.Series([50.0, 80.0], index=index)
    market_cap = pd.Series([100.0, 200.0], index=index)
    cash_flow = pd.Series([8.0, 25.0], index=index)
    assets = pd.Series([200.0, 400.0], index=index)
    assert earnings_yield(profit, market_cap).tolist() == [0.1, 0.1]
    assert book_to_price(equity, market_cap).tolist() == [0.5, 0.4]
    assert return_on_equity(profit, equity).tolist() == [0.2, 0.25]
    assert np.allclose(accruals(profit, cash_flow, assets), [0.01, -0.0125])

    dates = pd.bdate_range("2024-01-02", periods=4)
    prices = pd.DataFrame({"A": [100.0, 101.0, 99.0, 102.0]}, index=dates)
    amount = pd.DataFrame(1_000_000.0, index=dates, columns=["A"])
    result = amihud_from_prices(prices, amount, window=2)
    expected = prices.pct_change(fill_method=None).abs().div(amount).rolling(2).mean()
    pd.testing.assert_frame_equal(result, expected)


def test_ic_statistics_decay_and_correlation() -> None:
    dates = pd.to_datetime(["2023-01-02", "2023-01-03", "2024-01-02", "2024-01-03"])
    ic = pd.Series([0.1, 0.2, -0.1, 0.1], index=dates)
    assert np.isfinite(ic_ir(ic))
    annual = yearly_ic(ic)
    assert np.isclose(annual.loc[2023, "mean"], 0.15)
    assert annual.loc[2024, "count"] == 2

    columns = ["A", "B", "C"]
    factor = pd.DataFrame(np.tile([1.0, 2.0, 3.0], (4, 1)), index=dates, columns=columns)
    future = factor.copy()
    decay = ic_decay(factor, future, max_lag=2)
    assert decay.loc[0] == 1.0
    correlation = factor_correlation({"quality": factor, "value": -factor})
    assert np.isclose(correlation.loc["quality", "value"], -1.0)


def test_equal_and_rolling_ic_composites() -> None:
    dates = pd.bdate_range("2024-01-02", periods=8)
    columns = ["A", "B", "C"]
    good = pd.DataFrame(np.tile([1.0, 2.0, 3.0], (8, 1)), index=dates, columns=columns)
    bad = -good
    equal = equal_weight_composite({"good": good, "bad": bad})
    assert np.allclose(equal, 0.0)

    future = good.copy()
    composite = rolling_ic_composite(
        {"good": good, "bad": bad},
        future,
        window=3,
        min_periods=2,
    )
    assert composite.iloc[:2].isna().all().all()
    assert composite.iloc[3:].notna().all().all()
    assert (composite.iloc[3:, 2] > composite.iloc[3:, 0]).all()
