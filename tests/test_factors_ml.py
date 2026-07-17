import numpy as np
import pandas as pd

from ashare_quant.factors import rank_ic, top_quantile_weights
from ashare_quant.ml import WalkForwardConfig, daily_rank_ic, walk_forward_predict


def test_rank_ic_and_top_quantile_weights() -> None:
    dates = pd.bdate_range("2024-01-02", periods=25)
    columns = ["A", "B", "C", "D", "E"]
    factor = pd.DataFrame(np.tile(np.arange(5), (25, 1)), index=dates, columns=columns)
    future = factor.copy()
    assert np.isclose(rank_ic(factor, future).mean(), 1.0)
    weights = top_quantile_weights(factor, quantile=0.2)
    invested = weights.sum(axis=1)
    assert (invested.isin([0.0, 1.0])).all()
    assert (weights["E"] == invested).all()


def test_walk_forward_predicts_only_after_training_window() -> None:
    rng = np.random.default_rng(3)
    dates = pd.bdate_range("2022-01-03", periods=45)
    symbols = ["A", "B", "C", "D"]
    index = pd.MultiIndex.from_product([dates, symbols], names=["date", "symbol"])
    signal = rng.normal(size=len(index))
    features = pd.DataFrame({"signal": signal, "noise": rng.normal(size=len(index))}, index=index)
    labels = pd.Series(signal + rng.normal(scale=0.05, size=len(index)), index=index)
    predictions = walk_forward_predict(
        features,
        labels,
        WalkForwardConfig(
            min_train_dates=10,
            train_window_dates=20,
            label_horizon_dates=2,
            retrain_every=3,
        ),
    )
    assert predictions.loc[(dates[:12], slice(None))].isna().all()
    assert predictions.notna().any()
    assert daily_rank_ic(predictions, labels).mean() > 0.8
