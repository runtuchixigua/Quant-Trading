"""无时间泄漏的横截面机器学习基线。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class WalkForwardConfig:
    min_train_dates: int = 252
    train_window_dates: int | None = 756
    label_horizon_dates: int = 20
    retrain_every: int = 20
    ridge_alpha: float = 10.0


def _model(alpha: float) -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("ridge", Ridge(alpha=alpha)),
        ]
    )


def walk_forward_predict(
    features: pd.DataFrame,
    labels: pd.Series,
    config: WalkForwardConfig | None = None,
) -> pd.Series:
    """按日期扩展/滚动训练并预测。

    features 索引必须是 (date, symbol)。训练截止日额外减去标签期限，确保训练标签在
    预测日已经完整实现。预处理器只在每个训练窗口拟合。
    """
    cfg = config or WalkForwardConfig()
    if list(features.index.names) != ["date", "symbol"]:
        raise ValueError("features 必须使用名为 (date, symbol) 的 MultiIndex")
    if not labels.index.equals(features.index):
        labels = labels.reindex(features.index)

    dates = pd.Index(features.index.get_level_values("date").unique()).sort_values()
    if cfg.min_train_dates + cfg.label_horizon_dates >= len(dates):
        raise ValueError("有效日期不足以进行 walk-forward")

    predictions = pd.Series(np.nan, index=features.index, name="prediction")
    fitted_model: Pipeline | None = None

    for i in range(cfg.min_train_dates + cfg.label_horizon_dates, len(dates)):
        prediction_date = dates[i]
        if fitted_model is None or (
            i - cfg.min_train_dates - cfg.label_horizon_dates
        ) % cfg.retrain_every == 0:
            train_end = i - cfg.label_horizon_dates
            train_start = 0
            if cfg.train_window_dates is not None:
                train_start = max(0, train_end - cfg.train_window_dates)
            train_dates = dates[train_start:train_end]
            train_mask = features.index.get_level_values("date").isin(train_dates)
            valid = train_mask & labels.notna()
            if not valid.any():
                continue
            fitted_model = _model(cfg.ridge_alpha)
            fitted_model.fit(features.loc[valid], labels.loc[valid])

        predict_mask = features.index.get_level_values("date") == prediction_date
        predictions.loc[predict_mask] = fitted_model.predict(features.loc[predict_mask])

    return predictions


def daily_rank_ic(predictions: pd.Series, labels: pd.Series) -> pd.Series:
    frame = pd.concat([predictions.rename("prediction"), labels.rename("label")], axis=1).dropna()
    values = {
        date: group["prediction"].corr(group["label"], method="spearman")
        for date, group in frame.groupby(level="date")
    }
    return pd.Series(values, name="ml_rank_ic")
