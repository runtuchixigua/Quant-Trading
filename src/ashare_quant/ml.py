"""无时间泄漏的横截面机器学习与 walk-forward 诊断。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.base import RegressorMixin
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ModelName = Literal["ridge", "hist_gradient_boosting", "lightgbm"]
ModelFactory = Callable[["WalkForwardConfig"], RegressorMixin]


@dataclass(frozen=True)
class WalkForwardConfig:
    min_train_dates: int = 252
    train_window_dates: int | None = 756
    label_horizon_dates: int = 20
    retrain_every: int = 20
    ridge_alpha: float = 10.0
    model: ModelName | str = "ridge"
    model_params: Mapping[str, Any] = field(default_factory=dict)
    random_state: int = 42
    importance_repeats: int = 3


@dataclass(frozen=True)
class WalkForwardResult:
    """walk-forward 预测、每折元数据和特征解释。"""

    predictions: pd.Series
    folds: pd.DataFrame
    feature_importance: pd.DataFrame

    @property
    def fold_importance(self) -> pd.DataFrame:
        """兼容更直观的“按折重要性”命名。"""
        return self.feature_importance


def _ridge_model(cfg: WalkForwardConfig) -> Pipeline:
    params = {"alpha": cfg.ridge_alpha, **dict(cfg.model_params)}
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("estimator", Ridge(**params)),
        ]
    )


def _hist_gradient_boosting_model(cfg: WalkForwardConfig) -> Pipeline:
    params = {"random_state": cfg.random_state, **dict(cfg.model_params)}
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("estimator", HistGradientBoostingRegressor(**params)),
        ]
    )


def _lightgbm_model(cfg: WalkForwardConfig) -> Pipeline:
    try:
        from lightgbm import LGBMRegressor
    except ImportError as exc:  # pragma: no cover - 取决于可选依赖是否安装
        raise ImportError(
            "model='lightgbm' 需要可选依赖 lightgbm；请先安装 `pip install lightgbm`。"
        ) from exc
    params = {"random_state": cfg.random_state, "verbosity": -1, **dict(cfg.model_params)}
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("estimator", LGBMRegressor(**params)),
        ]
    )


def _model(cfg: WalkForwardConfig, model_factory: ModelFactory | None = None) -> RegressorMixin:
    if model_factory is not None:
        estimator = model_factory(cfg)
        if not hasattr(estimator, "fit") or not hasattr(estimator, "predict"):
            raise TypeError("model_factory 必须返回具有 fit/predict 的回归器")
        if isinstance(estimator, Pipeline):
            return estimator
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("estimator", estimator),
            ]
        )
    model_name = str(cfg.model).lower().replace("-", "_")
    if model_name == "ridge":
        return _ridge_model(cfg)
    if model_name in {"hist_gradient_boosting", "histgradientboosting", "hist_gbdt"}:
        return _hist_gradient_boosting_model(cfg)
    if model_name in {"lightgbm", "lgbm"}:
        return _lightgbm_model(cfg)
    raise ValueError(
        "未知模型；model 应为 'ridge'、'hist_gradient_boosting' 或 'lightgbm'"
    )


def _validate_inputs(
    features: pd.DataFrame, labels: pd.Series, cfg: WalkForwardConfig
) -> tuple[pd.Series, pd.Index]:
    if list(features.index.names) != ["date", "symbol"]:
        raise ValueError("features 必须使用名为 (date, symbol) 的 MultiIndex")
    if features.index.has_duplicates:
        raise ValueError("features 索引不能重复")
    if not features.index.is_monotonic_increasing:
        raise ValueError("features 必须按 date、symbol 递增排列")
    if features.empty or features.shape[1] == 0:
        raise ValueError("features 必须为非空数值表")
    if not all(pd.api.types.is_numeric_dtype(dtype) for dtype in features.dtypes):
        raise TypeError("features 只能包含数值列")
    if cfg.min_train_dates < 1 or cfg.label_horizon_dates < 0 or cfg.retrain_every < 1:
        raise ValueError("训练日期数和重训间隔须为正数，标签期限不能为负数")
    if cfg.train_window_dates is not None and cfg.train_window_dates < cfg.min_train_dates:
        raise ValueError("train_window_dates 不能小于 min_train_dates")
    if cfg.importance_repeats < 1:
        raise ValueError("importance_repeats 必须至少为 1")
    if not labels.index.equals(features.index):
        labels = labels.reindex(features.index)
    dates = pd.Index(features.index.get_level_values("date").unique()).sort_values()
    if cfg.min_train_dates + cfg.label_horizon_dates >= len(dates):
        raise ValueError("有效日期不足以进行 walk-forward")
    return labels, dates


def _final_estimator(model: RegressorMixin) -> Any:
    if isinstance(model, Pipeline):
        return model.steps[-1][1]
    return model


def _fold_explanation(
    model: RegressorMixin,
    train_features: pd.DataFrame,
    train_labels: pd.Series,
    cfg: WalkForwardConfig,
) -> tuple[np.ndarray, str]:
    estimator = _final_estimator(model)
    if hasattr(estimator, "coef_"):
        coefficients = np.asarray(estimator.coef_, dtype=float).reshape(-1)
        if len(coefficients) == train_features.shape[1]:
            return coefficients, "coefficient"
    if hasattr(estimator, "feature_importances_"):
        importances = np.asarray(estimator.feature_importances_, dtype=float).reshape(-1)
        if len(importances) == train_features.shape[1]:
            return importances, "native_importance"
    result = permutation_importance(
        model,
        train_features,
        train_labels,
        scoring="neg_mean_squared_error",
        n_repeats=cfg.importance_repeats,
        random_state=cfg.random_state,
    )
    return np.asarray(result.importances_mean, dtype=float), "permutation_importance"


def walk_forward_evaluate(
    features: pd.DataFrame,
    labels: pd.Series,
    config: WalkForwardConfig | None = None,
    *,
    model_factory: ModelFactory | None = None,
) -> WalkForwardResult:
    """逐折训练、预测并返回可审计的训练边界与特征解释。

    对预测日 ``t``，训练日期严格截止于 ``t - label_horizon_dates`` 之前；
    缺失值填充、缩放及模型都仅在该折训练窗口内拟合。
    """
    cfg = config or WalkForwardConfig()
    labels, dates = _validate_inputs(features, labels, cfg)
    predictions = pd.Series(np.nan, index=features.index, name="prediction")
    fitted_model: RegressorMixin | None = None
    fold_id = -1
    fold_rows: list[dict[str, Any]] = []
    importance_rows: list[dict[str, Any]] = []

    first_prediction = cfg.min_train_dates + cfg.label_horizon_dates
    for i in range(first_prediction, len(dates)):
        prediction_date = dates[i]
        should_retrain = fitted_model is None or (i - first_prediction) % cfg.retrain_every == 0
        if should_retrain:
            train_end = i - cfg.label_horizon_dates
            train_start = 0
            if cfg.train_window_dates is not None:
                train_start = max(0, train_end - cfg.train_window_dates)
            train_dates = dates[train_start:train_end]
            train_mask = features.index.get_level_values("date").isin(train_dates)
            valid = train_mask & labels.notna()
            if not valid.any():
                fitted_model = None
                continue

            fitted_model = _model(cfg, model_factory)
            x_train = features.loc[valid]
            y_train = labels.loc[valid]
            fitted_model.fit(x_train, y_train)
            fold_id += 1
            prediction_end_position = min(i + cfg.retrain_every - 1, len(dates) - 1)
            fold_rows.append(
                {
                    "fold": fold_id,
                    "train_start": train_dates[0],
                    "train_end": train_dates[-1],
                    "prediction_start": prediction_date,
                    "prediction_end": dates[prediction_end_position],
                    "n_train_dates": len(train_dates),
                    "n_train_samples": int(valid.sum()),
                    "model": str(cfg.model),
                }
            )
            values, kind = _fold_explanation(fitted_model, x_train, y_train, cfg)
            for feature, value in zip(features.columns, values, strict=True):
                importance_rows.append(
                    {
                        "fold": fold_id,
                        "feature": feature,
                        "importance": float(value),
                        "kind": kind,
                        "train_end": train_dates[-1],
                        "prediction_start": prediction_date,
                    }
                )

        if fitted_model is None:
            continue
        predict_mask = features.index.get_level_values("date") == prediction_date
        predictions.loc[predict_mask] = fitted_model.predict(features.loc[predict_mask])

    return WalkForwardResult(
        predictions=predictions,
        folds=pd.DataFrame(fold_rows),
        feature_importance=pd.DataFrame(importance_rows),
    )


def walk_forward_predict(
    features: pd.DataFrame,
    labels: pd.Series,
    config: WalkForwardConfig | None = None,
    *,
    model_factory: ModelFactory | None = None,
    return_diagnostics: bool = False,
) -> pd.Series | WalkForwardResult:
    """按日期扩展/滚动训练并预测。

    features 索引必须是 (date, symbol)。训练截止日额外减去标签期限，确保训练标签在
    预测日已经完整实现。设置 ``return_diagnostics=True`` 可同时取得逐折解释。
    """
    result = walk_forward_evaluate(
        features, labels, config=config, model_factory=model_factory
    )
    return result if return_diagnostics else result.predictions


def daily_rank_ic(predictions: pd.Series, labels: pd.Series) -> pd.Series:
    frame = pd.concat([predictions.rename("prediction"), labels.rename("label")], axis=1).dropna()
    values = {
        date: group["prediction"].corr(group["label"], method="spearman")
        for date, group in frame.groupby(level="date")
    }
    return pd.Series(values, name="ml_rank_ic")
