"""后续课程使用的独立统计工具。"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def variance_inflation_factors(features: pd.DataFrame) -> pd.Series:
    """计算各特征的 VIF；完全共线或常量列返回无穷大。"""

    if not isinstance(features, pd.DataFrame):
        raise TypeError("features 必须是 pandas DataFrame")
    if features.shape[1] < 2:
        raise ValueError("VIF 至少需要 2 个特征")
    if not features.columns.is_unique:
        raise ValueError("features 列名必须唯一")
    numeric = features.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    clean = numeric.dropna()
    if len(clean) < 3:
        raise ValueError("VIF 至少需要 3 行完整的有限观测")

    result: dict[object, float] = {}
    for column in clean.columns:
        target = clean[column].to_numpy(dtype=float)
        predictors = clean.drop(columns=column).to_numpy(dtype=float)
        if np.ptp(target) == 0:
            result[column] = float("inf")
            continue
        score = LinearRegression().fit(predictors, target).score(predictors, target)
        result[column] = float("inf") if score >= 1.0 - 1e-12 else float(1.0 / (1.0 - score))
    return pd.Series(result, name="vif", dtype=float)


def benjamini_hochberg(
    p_values: pd.Series | Sequence[float] | np.ndarray,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """Benjamini-Hochberg FDR 修正。

    返回原顺序的 ``p_value``、单调校正后的 ``adjusted_p_value`` 和 ``reject``。
    Series 输入会保留其索引。
    """

    if not 0 < alpha < 1:
        raise ValueError("alpha 必须在 (0, 1) 内")
    if isinstance(p_values, pd.Series):
        index = p_values.index
        values = pd.to_numeric(p_values, errors="coerce").to_numpy(dtype=float)
    else:
        values = np.asarray(p_values, dtype=float)
        if values.ndim != 1:
            raise ValueError("p_values 必须是一维")
        index = pd.RangeIndex(len(values))
    if values.size == 0:
        raise ValueError("p_values 不能为空")
    if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
        raise ValueError("p_values 必须全部是 [0, 1] 内的有限数")

    order = np.argsort(values, kind="stable")
    ranked = values[order]
    ranks = np.arange(1, len(values) + 1)
    adjusted_sorted = np.minimum.accumulate((ranked * len(values) / ranks)[::-1])[::-1]
    adjusted_sorted = np.minimum(adjusted_sorted, 1.0)
    adjusted = np.empty_like(adjusted_sorted)
    adjusted[order] = adjusted_sorted
    return pd.DataFrame(
        {
            "p_value": values,
            "adjusted_p_value": adjusted,
            "reject": adjusted <= alpha,
        },
        index=index,
    )


def moving_block_bootstrap_mean_interval(
    values: pd.Series | Sequence[float] | np.ndarray,
    block_size: int,
    confidence: float = 0.95,
    n_bootstrap: int = 2_000,
    seed: int | None = None,
) -> tuple[float, float]:
    """移动块 bootstrap 的样本均值 percentile 区间。

    每次拼接随机抽取的连续非环形块，达到原样本长度后截断。
    """

    if block_size < 1:
        raise ValueError("block_size 必须为正")
    if not 0 < confidence < 1:
        raise ValueError("confidence 必须在 (0, 1) 内")
    if n_bootstrap < 1:
        raise ValueError("n_bootstrap 必须为正")
    sample = np.asarray(values, dtype=float).reshape(-1)
    sample = sample[np.isfinite(sample)]
    if sample.size < 2:
        raise ValueError("至少需要 2 个有限观测")
    if block_size > sample.size:
        raise ValueError("block_size 不能超过有效样本数")

    block_starts = np.arange(sample.size - block_size + 1)
    blocks_needed = int(np.ceil(sample.size / block_size))
    rng = np.random.default_rng(seed)
    estimates = np.empty(n_bootstrap)
    for index in range(n_bootstrap):
        starts = rng.choice(block_starts, size=blocks_needed, replace=True)
        draw = np.concatenate([sample[start : start + block_size] for start in starts])
        estimates[index] = draw[: sample.size].mean()
    tail = (1.0 - confidence) / 2.0
    lower, upper = np.quantile(estimates, [tail, 1.0 - tail])
    return float(lower), float(upper)


def historical_var_es(
    returns: pd.Series | Sequence[float] | np.ndarray,
    confidence: float = 0.95,
) -> pd.Series:
    """历史模拟 VaR 与 ES，均以正的损失金额表示。

    VaR 是收益率左尾的线性分位数的相反数；ES 是不高于该分位数的观测均值
    的相反数。因此全为正收益的样本可得到负 VaR/ES，表示没有历史损失。
    """

    if not 0 < confidence < 1:
        raise ValueError("confidence 必须在 (0, 1) 内")
    sample = np.asarray(returns, dtype=float).reshape(-1)
    sample = sample[np.isfinite(sample)]
    if sample.size == 0:
        raise ValueError("returns 至少需要 1 个有限观测")
    threshold = float(np.quantile(sample, 1.0 - confidence))
    tail = sample[sample <= threshold]
    return pd.Series(
        {"var": -threshold, "es": -float(tail.mean())},
        name=f"historical_{confidence:.1%}",
        dtype=float,
    )


def drawdown_recovery_periods(returns: pd.Series) -> pd.DataFrame:
    """列出每轮回撤的峰值、谷底、恢复点和持续观测数。

    尚未恢复的最后一轮 ``recovery`` 为 NaN，``recovered`` 为 False，持续时间
    计算到样本末尾。恢复是净值重新达到或超过此前峰值。
    """

    if not isinstance(returns, pd.Series):
        raise TypeError("returns 必须是 pandas Series")
    if not returns.index.is_unique:
        raise ValueError("returns 索引必须唯一")
    clean = pd.to_numeric(returns, errors="coerce")
    if clean.isna().any() or np.isinf(clean.to_numpy()).any():
        raise ValueError("returns 必须全部是有限数")
    if (clean < -1).any():
        raise ValueError("简单收益率不能小于 -1")
    if clean.empty:
        return pd.DataFrame(
            columns=["peak", "trough", "recovery", "duration", "recovered", "max_drawdown"]
        )

    wealth = (1.0 + clean).cumprod()
    records: list[dict[str, object]] = []
    peak_position = 0
    in_drawdown = False
    trough_position = 0
    for position in range(1, len(wealth)):
        if wealth.iloc[position] >= wealth.iloc[peak_position]:
            if in_drawdown:
                records.append(
                    {
                        "peak": wealth.index[peak_position],
                        "trough": wealth.index[trough_position],
                        "recovery": wealth.index[position],
                        "duration": position - peak_position,
                        "recovered": True,
                        "max_drawdown": wealth.iloc[trough_position]
                        / wealth.iloc[peak_position]
                        - 1.0,
                    }
                )
            peak_position = position
            in_drawdown = False
        else:
            if not in_drawdown:
                in_drawdown = True
                trough_position = position
            elif wealth.iloc[position] < wealth.iloc[trough_position]:
                trough_position = position
    if in_drawdown:
        records.append(
            {
                "peak": wealth.index[peak_position],
                "trough": wealth.index[trough_position],
                "recovery": pd.NaT if isinstance(wealth.index, pd.DatetimeIndex) else np.nan,
                "duration": len(wealth) - 1 - peak_position,
                "recovered": False,
                "max_drawdown": wealth.iloc[trough_position] / wealth.iloc[peak_position] - 1.0,
            }
        )
    return pd.DataFrame.from_records(
        records,
        columns=["peak", "trough", "recovery", "duration", "recovered", "max_drawdown"],
    )


def recovery_period(returns: pd.Series) -> int:
    """返回最长回撤恢复期（观测数），未恢复回撤计算到样本末尾。"""

    periods = drawdown_recovery_periods(returns)
    return int(periods["duration"].max()) if not periods.empty else 0


# 教材中常用的简写。
vif = variance_inflation_factors
fdr_bh = benjamini_hochberg
moving_block_bootstrap_ci = moving_block_bootstrap_mean_interval
maximum_recovery_period = recovery_period
