import numpy as np
import pandas as pd
import pytest

from ashare_quant.event_study import (
    abnormal_returns,
    align_event_windows,
    bootstrap_confidence_interval,
    event_window_car,
    generate_synthetic_events,
    placebo_dates,
)


def test_synthetic_events_are_reproducible_and_have_event_effect() -> None:
    first = generate_synthetic_events(
        n_events=500,
        window=(-1, 1),
        event_effect=0.03,
        idiosyncratic_volatility=0.005,
        seed=7,
    )
    second = generate_synthetic_events(
        n_events=500,
        window=(-1, 1),
        event_effect=0.03,
        idiosyncratic_volatility=0.005,
        seed=7,
    )
    pd.testing.assert_frame_equal(first, second)
    adjusted = first["asset_return"] - first["market_return"]
    event_mean = adjusted[first["relative_day"] == 0].mean()
    pre_mean = adjusted[first["relative_day"] == -1].mean()
    assert event_mean - pre_mean == pytest.approx(0.03, abs=0.002)


def test_event_alignment_market_adjustment_and_car() -> None:
    dates = pd.bdate_range("2024-01-02", periods=7)
    market = pd.Series([0.01, 0.0, -0.01, 0.01, 0.0, 0.0, 0.01], index=dates)
    asset = market + pd.Series([0.0, 0.0, 0.02, 0.03, 0.01, 0.0, 0.0], index=dates)
    abnormal = abnormal_returns(asset, market, model="market_adjusted")
    panel = align_event_windows(abnormal, [dates[3]], window=(-1, 1))
    assert event_window_car(panel).iloc[0] == pytest.approx(0.06)


def test_market_model_recovers_known_alpha_and_beta() -> None:
    index = pd.RangeIndex(20)
    market = pd.Series(np.linspace(-0.02, 0.02, len(index)), index=index)
    asset = 0.001 + 1.5 * market
    mask = pd.Series([True] * 15 + [False] * 5, index=index)
    result = abnormal_returns(asset, market, model="market_model", estimation_mask=mask)
    assert result.abs().max() < 1e-12
    assert result.attrs["alpha"] == pytest.approx(0.001)
    assert result.attrs["beta"] == pytest.approx(1.5)


def test_bootstrap_interval_and_placebos_are_reproducible() -> None:
    lower, upper = bootstrap_confidence_interval(
        np.arange(1.0, 11.0), n_bootstrap=500, seed=11
    )
    assert lower < 5.5 < upper

    index = pd.bdate_range("2024-01-02", periods=30)
    events = [index[5], index[20]]
    first = placebo_dates(index, events, exclusion=2, seed=4)
    second = placebo_dates(index, events, exclusion=2, seed=4)
    pd.testing.assert_index_equal(first, second)
    positions = index.get_indexer(first)
    event_positions = index.get_indexer(events)
    assert all(abs(placebo - event) > 2 for placebo in positions for event in event_positions)


def test_event_input_validation() -> None:
    returns = pd.Series([0.01, 0.02], index=[0, 1])
    with pytest.raises(ValueError):
        align_event_windows(returns, [3])
    with pytest.raises(ValueError):
        bootstrap_confidence_interval([1.0])
