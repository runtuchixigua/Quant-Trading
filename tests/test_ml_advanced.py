import importlib.util

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor

from ashare_quant.ml import (
    WalkForwardConfig,
    WalkForwardResult,
    walk_forward_evaluate,
    walk_forward_predict,
)


def sample_data() -> tuple[pd.DataFrame, pd.Series, pd.DatetimeIndex]:
    rng = np.random.default_rng(17)
    dates = pd.bdate_range("2021-01-04", periods=36)
    index = pd.MultiIndex.from_product([dates, ["A", "B", "C"]], names=["date", "symbol"])
    signal = rng.normal(size=len(index))
    features = pd.DataFrame(
        {"signal": signal, "noise": rng.normal(size=len(index))},
        index=index,
    )
    labels = pd.Series(1.5 * signal + rng.normal(scale=0.05, size=len(index)), index=index)
    return features, labels, dates


def test_ridge_returns_per_fold_coefficients_and_auditable_boundaries() -> None:
    features, labels, dates = sample_data()
    config = WalkForwardConfig(
        min_train_dates=8,
        train_window_dates=12,
        label_horizon_dates=2,
        retrain_every=4,
        model="ridge",
    )
    result = walk_forward_predict(
        features, labels, config, return_diagnostics=True
    )
    assert isinstance(result, WalkForwardResult)
    assert result.predictions.loc[(dates[:10], slice(None))].isna().all()
    assert set(result.feature_importance["kind"]) == {"coefficient"}
    assert set(result.feature_importance["feature"]) == set(features.columns)
    assert (result.folds["train_end"] < result.folds["prediction_start"]).all()
    assert (result.folds["n_train_dates"] <= 12).all()


def test_hist_gradient_boosting_and_custom_factory_are_pluggable() -> None:
    features, labels, _ = sample_data()
    hist = walk_forward_evaluate(
        features,
        labels,
        WalkForwardConfig(
            min_train_dates=8,
            label_horizon_dates=2,
            retrain_every=8,
            model="hist_gradient_boosting",
            model_params={"max_iter": 10, "max_leaf_nodes": 7},
            importance_repeats=1,
        ),
    )
    assert hist.predictions.notna().any()
    assert set(hist.feature_importance["kind"]) == {"permutation_importance"}

    custom = walk_forward_predict(
        features,
        labels,
        WalkForwardConfig(min_train_dates=8, label_horizon_dates=2, retrain_every=8),
        model_factory=lambda _: DummyRegressor(strategy="mean"),
    )
    assert isinstance(custom, pd.Series)
    assert custom.notna().any()


def test_future_labels_cannot_change_earlier_predictions() -> None:
    features, labels, dates = sample_data()
    config = WalkForwardConfig(
        min_train_dates=8,
        train_window_dates=None,
        label_horizon_dates=3,
        retrain_every=1,
    )
    original = walk_forward_predict(features, labels, config)
    changed_labels = labels.copy()
    changed_labels.loc[(dates[15:], slice(None))] += 10_000.0
    changed = walk_forward_predict(features, changed_labels, config)
    pd.testing.assert_series_equal(
        original.loc[(dates[:18], slice(None))],
        changed.loc[(dates[:18], slice(None))],
    )


def test_lightgbm_has_clear_optional_dependency_error() -> None:
    if importlib.util.find_spec("lightgbm") is not None:
        pytest.skip("当前环境已安装 lightgbm")
    features, labels, _ = sample_data()
    config = WalkForwardConfig(
        min_train_dates=8,
        label_horizon_dates=2,
        retrain_every=8,
        model="lightgbm",
    )
    with pytest.raises(ImportError, match="pip install lightgbm"):
        walk_forward_predict(features, labels, config)
