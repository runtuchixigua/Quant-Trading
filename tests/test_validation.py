import numpy as np
import pandas as pd

from ashare_quant.validation import (
    ExperimentLog,
    PurgedEmbargoSplit,
    cost_multiplier_stress,
    deflated_sharpe_ratio,
    market_regime_stress,
    parameter_neighborhood_stress,
    subsample_stress,
    train_validation_test_split,
)


def test_purged_embargo_split_keeps_dates_grouped_and_ordered() -> None:
    dates = pd.bdate_range("2023-01-02", periods=30)
    index = pd.MultiIndex.from_product([dates, ["A", "B"]], names=["date", "symbol"])
    frame = pd.DataFrame({"x": np.arange(len(index))}, index=index)
    splitter = PurgedEmbargoSplit(
        n_splits=3, min_train_dates=8, purge_dates=2, embargo_dates=1
    )

    for train_rows, validation_rows in splitter.split(frame):
        train_dates = index[train_rows].get_level_values("date").unique()
        validation_dates = index[validation_rows].get_level_values("date").unique()
        assert train_dates.max() < validation_dates.min()
        assert dates.get_loc(validation_dates.min()) - dates.get_loc(train_dates.max()) == 4
        assert len(train_rows) % 2 == 0
        assert len(validation_rows) % 2 == 0


def test_train_validation_final_test_protocol_is_disjoint() -> None:
    dates = pd.bdate_range("2020-01-01", periods=100)
    protocol = train_validation_test_split(
        dates,
        train_size=0.6,
        validation_size=0.2,
        purge_dates=2,
        embargo_dates=1,
    )
    assert protocol.train.max() < protocol.validation.min() < protocol.final_test.min()
    assert set(protocol.train).isdisjoint(protocol.validation)
    assert set(protocol.validation).isdisjoint(protocol.final_test)
    assert dates.get_loc(protocol.validation.min()) - dates.get_loc(protocol.train.max()) == 4


def test_deflated_sharpe_penalizes_more_trials_and_log_records_all_attempts() -> None:
    rng = np.random.default_rng(11)
    returns = pd.Series(rng.normal(0.0008, 0.01, 400))
    one_trial = deflated_sharpe_ratio(returns, n_trials=1)
    many_trials = deflated_sharpe_ratio(returns, n_trials=50)
    assert 0.0 <= many_trials <= one_trial <= 1.0

    log = ExperimentLog()
    log.record("ridge-a", returns=returns)
    log.record("ridge-b", returns=returns * 0.8)
    result = log.deflated_sharpe("ridge-a", returns)
    assert result.n_trials == 2
    assert list(log.to_frame()["name"]) == ["ridge-a", "ridge-b"]


def test_stress_apis_report_cost_parameter_subsample_and_regime_results() -> None:
    dates = pd.bdate_range("2022-01-03", periods=60)
    gross = pd.Series(0.001, index=dates)
    costs = pd.Series(0.0002, index=dates)
    cost_result = cost_multiplier_stress(gross, costs, [1.0, 3.0])
    assert cost_result.loc[3.0, "annualized_return"] < cost_result.loc[
        1.0, "annualized_return"
    ]

    parameter_result = parameter_neighborhood_stress(
        lambda params: {"score": -(params["alpha"] - 2.0) ** 2},
        {"alpha": 2.0, "window": 20},
        {"alpha": [1.0, 2.0, 3.0], "window": [20, 40]},
    )
    assert len(parameter_result) == 6
    assert parameter_result["score"].max() == 0.0

    varying = pd.Series(np.linspace(-0.01, 0.012, len(dates)), index=dates)
    subsamples = subsample_stress(varying, n_splits=3)
    assert len(subsamples) == 3
    regimes = pd.Series(np.where(np.arange(len(dates)) % 2, "bull", "bear"), index=dates)
    regime_result = market_regime_stress(varying, regimes)
    assert set(regime_result.index) == {"bull", "bear"}
