"""组合构建与只依赖 NumPy 的教学级优化器。"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd


class InfeasiblePortfolioError(ValueError):
    """组合约束没有可行解。"""


def portfolio_turnover(weights: pd.Series, previous_weights: pd.Series) -> float:
    """单边换手率：0.5 * sum(abs(新权重 - 旧权重))。"""
    current, previous = weights.align(previous_weights, join="outer", fill_value=0.0)
    return float(0.5 * (current - previous).abs().sum())


def _project_bounded_simplex(
    values: np.ndarray,
    total: float,
    lower: np.ndarray | float,
    upper: np.ndarray | float,
    tolerance: float = 1e-12,
) -> np.ndarray:
    """欧氏投影到带上下界的单纯形。"""
    values = np.asarray(values, dtype=float)
    lower_array = np.broadcast_to(np.asarray(lower, dtype=float), values.shape)
    upper_array = np.broadcast_to(np.asarray(upper, dtype=float), values.shape)
    if np.any(lower_array > upper_array):
        raise InfeasiblePortfolioError("约束不可行：存在下界高于上界")
    if total < lower_array.sum() - tolerance or total > upper_array.sum() + tolerance:
        raise InfeasiblePortfolioError(
            f"约束不可行：总暴露 {total:g} 不在可行区间 "
            f"[{lower_array.sum():g}, {upper_array.sum():g}]"
        )
    low = float(np.min(values - upper_array))
    high = float(np.max(values - lower_array))
    for _ in range(100):
        middle = (low + high) / 2.0
        projected = np.clip(values - middle, lower_array, upper_array)
        if projected.sum() > total:
            low = middle
        else:
            high = middle
    projected = np.clip(values - (low + high) / 2.0, lower_array, upper_array)
    residual = total - projected.sum()
    if abs(residual) > tolerance:
        room = upper_array - projected if residual > 0 else projected - lower_array
        available = np.flatnonzero(room > tolerance)
        if len(available):
            projected[available] += residual * room[available] / room[available].sum()
    return projected


def _score_target(scores: pd.Series, method: str) -> pd.Series:
    finite = scores.replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    if finite.empty:
        raise InfeasiblePortfolioError("约束不可行：没有有效分数")
    if method == "rank":
        raw = finite.rank(method="average", pct=True)
    elif method == "softmax":
        centered = finite - finite.max()
        raw = np.exp(centered.clip(lower=-700.0))
    elif method == "positive":
        raw = finite.clip(lower=0.0)
        if raw.sum() <= 0:
            raise InfeasiblePortfolioError("约束不可行：positive 模式没有正分数")
    else:
        raise ValueError("method 必须是 'rank'、'softmax' 或 'positive'")
    return raw / raw.sum()


def _as_industry_deviation(
    deviation: float | Mapping[object, float] | pd.Series,
    groups: pd.Index,
) -> pd.Series:
    if np.isscalar(deviation):
        result = pd.Series(float(deviation), index=groups)
    else:
        result = pd.Series(deviation, dtype=float).reindex(groups)
    if result.isna().any() or (result < 0).any():
        raise ValueError("行业偏离必须为覆盖全部行业的非负数")
    return result


def _check_static_constraints(
    weights: pd.Series,
    total_exposure: float,
    max_weight: float,
    industries: pd.Series | None,
    industry_lower: pd.Series | None,
    industry_upper: pd.Series | None,
    tolerance: float = 1e-8,
) -> None:
    if (weights < -tolerance).any() or (weights > max_weight + tolerance).any():
        raise InfeasiblePortfolioError("约束不可行：旧组合违反单票上限或多头约束")
    if abs(float(weights.sum()) - total_exposure) > tolerance:
        raise InfeasiblePortfolioError("约束不可行：旧组合不满足总暴露")
    if industries is not None and industry_lower is not None and industry_upper is not None:
        exposure = weights.groupby(industries).sum().reindex(industry_lower.index, fill_value=0.0)
        if (exposure < industry_lower - tolerance).any() or (
            exposure > industry_upper + tolerance
        ).any():
            raise InfeasiblePortfolioError("约束不可行：旧组合违反行业偏离约束")


def score_to_weights(
    scores: pd.Series,
    *,
    max_weight: float = 1.0,
    total_exposure: float = 1.0,
    industries: pd.Series | None = None,
    benchmark_weights: pd.Series | None = None,
    max_industry_deviation: float | Mapping[object, float] | pd.Series | None = None,
    previous_weights: pd.Series | None = None,
    max_turnover: float | None = None,
    method: str = "rank",
) -> pd.Series:
    """把横截面分数转为满足约束的多头权重。

    行业偏离相对基准行业权重计算；换手率采用单边定义。若指定换手
    约束，旧组合本身必须满足当前静态约束，从而保证插值得到的解可行。
    """
    scores = pd.Series(scores, dtype=float)
    if scores.index.has_duplicates:
        raise ValueError("scores 索引不能重复")
    if total_exposure < 0 or max_weight <= 0:
        raise ValueError("total_exposure 必须非负且 max_weight 必须为正")
    if max_turnover is not None and max_turnover < 0:
        raise ValueError("max_turnover 必须非负")
    valid = scores.replace([np.inf, -np.inf], np.nan).notna()
    if valid.sum() * max_weight < total_exposure - 1e-12:
        raise InfeasiblePortfolioError(
            "约束不可行：有效股票数量乘以单票上限小于总暴露"
        )

    target = _score_target(scores, method).reindex(scores.index, fill_value=0.0)
    industry = None
    lower = upper = None
    if max_industry_deviation is not None:
        if industries is None or benchmark_weights is None:
            raise ValueError("设置行业偏离时必须同时提供 industries 和 benchmark_weights")
        industry = pd.Series(industries).reindex(scores.index)
        if industry[valid].isna().any():
            raise ValueError("有效股票缺少行业标签")
        benchmark = pd.Series(benchmark_weights, dtype=float).reindex(scores.index, fill_value=0.0)
        groups = pd.Index(industry[valid].unique())
        benchmark_group = benchmark.groupby(industry).sum().reindex(groups, fill_value=0.0)
        deviation = _as_industry_deviation(max_industry_deviation, groups)
        capacity = valid.groupby(industry).sum().reindex(groups).astype(float) * max_weight
        lower = (benchmark_group - deviation).clip(lower=0.0)
        upper = pd.concat([benchmark_group + deviation, capacity], axis=1).min(axis=1)
        group_target = target.groupby(industry).sum().reindex(groups, fill_value=0.0)
        group_weights = _project_bounded_simplex(
            group_target.to_numpy(), total_exposure, lower.to_numpy(), upper.to_numpy()
        )
    else:
        industry = pd.Series("__all__", index=scores.index)
        groups = pd.Index(["__all__"])
        group_weights = np.array([total_exposure])

    result = pd.Series(0.0, index=scores.index, name="weight")
    for group, group_total in zip(groups, group_weights, strict=True):
        members = scores.index[valid & industry.eq(group)]
        base = target.reindex(members).to_numpy()
        result.loc[members] = _project_bounded_simplex(
            base, float(group_total), 0.0, max_weight
        )

    if previous_weights is not None or max_turnover is not None:
        if previous_weights is None or max_turnover is None:
            raise ValueError("previous_weights 与 max_turnover 必须同时提供")
        previous = pd.Series(previous_weights, dtype=float).reindex(scores.index, fill_value=0.0)
        _check_static_constraints(
            previous,
            total_exposure,
            max_weight,
            industry,
            lower,
            upper,
        )
        required = portfolio_turnover(result, previous)
        if required > max_turnover:
            fraction = 0.0 if required == 0 else max_turnover / required
            result = previous + fraction * (result - previous)
            result.name = "weight"
    return result


def _validate_covariance(covariance: pd.DataFrame) -> tuple[pd.Index, np.ndarray]:
    covariance = pd.DataFrame(covariance, dtype=float)
    if covariance.shape[0] != covariance.shape[1]:
        raise ValueError("协方差矩阵必须为方阵")
    if not covariance.index.equals(covariance.columns):
        covariance = covariance.reindex(index=covariance.index, columns=covariance.index)
    matrix = covariance.to_numpy()
    if not np.isfinite(matrix).all():
        raise ValueError("协方差矩阵不能包含缺失或无穷值")
    matrix = (matrix + matrix.T) / 2.0
    if np.linalg.eigvalsh(matrix).min() < -1e-10:
        raise ValueError("协方差矩阵必须半正定")
    return covariance.index, matrix


def _projected_optimizer(
    covariance: pd.DataFrame,
    expected_returns: pd.Series | None,
    risk_aversion: float,
    max_weight: float,
    total_exposure: float,
    max_iter: int,
    tolerance: float,
) -> pd.Series:
    assets, matrix = _validate_covariance(covariance)
    if len(assets) * max_weight < total_exposure - tolerance:
        raise InfeasiblePortfolioError("约束不可行：单票上限无法容纳总暴露")
    mu = (
        np.zeros(len(assets))
        if expected_returns is None
        else pd.Series(expected_returns, dtype=float).reindex(assets).to_numpy()
    )
    if not np.isfinite(mu).all():
        raise ValueError("预期收益必须覆盖协方差矩阵中的全部资产")
    largest = max(float(np.linalg.eigvalsh(matrix).max()), 1e-12)
    step = 1.0 / max(risk_aversion * largest, 1e-12)
    weights = _project_bounded_simplex(
        np.repeat(total_exposure / len(assets), len(assets)),
        total_exposure,
        0.0,
        max_weight,
    )
    for _ in range(max_iter):
        gradient = risk_aversion * matrix @ weights - mu
        updated = _project_bounded_simplex(
            weights - step * gradient, total_exposure, 0.0, max_weight
        )
        if np.max(np.abs(updated - weights)) < tolerance:
            weights = updated
            break
        weights = updated
    return pd.Series(weights, index=assets, name="weight")


def minimum_variance_weights(
    covariance: pd.DataFrame,
    *,
    max_weight: float = 1.0,
    total_exposure: float = 1.0,
    max_iter: int = 10_000,
    tolerance: float = 1e-10,
) -> pd.Series:
    """求多头、带单票上限的最小方差组合。"""
    return _projected_optimizer(
        covariance, None, 1.0, max_weight, total_exposure, max_iter, tolerance
    )


def mean_variance_weights(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    *,
    risk_aversion: float = 1.0,
    max_weight: float = 1.0,
    total_exposure: float = 1.0,
    max_iter: int = 10_000,
    tolerance: float = 1e-10,
) -> pd.Series:
    """最大化 mu'w - risk_aversion/2 * w'Σw。"""
    if risk_aversion <= 0:
        raise ValueError("risk_aversion 必须为正")
    return _projected_optimizer(
        covariance,
        expected_returns,
        risk_aversion,
        max_weight,
        total_exposure,
        max_iter,
        tolerance,
    )


def risk_budget_weights(
    covariance: pd.DataFrame,
    budgets: pd.Series | None = None,
    *,
    max_iter: int = 10_000,
    tolerance: float = 1e-10,
) -> pd.Series:
    """用循环坐标下降求风险预算组合；budgets 为方差贡献占比。"""
    assets, matrix = _validate_covariance(covariance)
    if np.any(np.diag(matrix) <= 0):
        raise ValueError("风险预算要求每个资产方差为正")
    budget = (
        np.repeat(1.0 / len(assets), len(assets))
        if budgets is None
        else pd.Series(budgets, dtype=float).reindex(assets).to_numpy()
    )
    if not np.isfinite(budget).all() or np.any(budget <= 0):
        raise ValueError("风险预算必须覆盖全部资产且严格为正")
    budget = budget / budget.sum()
    weights = np.sqrt(budget / np.diag(matrix))
    for _ in range(max_iter):
        previous = weights.copy()
        for index in range(len(weights)):
            cross = matrix[index] @ weights - matrix[index, index] * weights[index]
            discriminant = cross * cross + 4.0 * matrix[index, index] * budget[index]
            weights[index] = (-cross + np.sqrt(discriminant)) / (
                2.0 * matrix[index, index]
            )
        if np.max(np.abs(weights - previous)) < tolerance:
            break
    weights /= weights.sum()
    return pd.Series(weights, index=assets, name="weight")


min_variance_weights = minimum_variance_weights
risk_parity_weights = risk_budget_weights
