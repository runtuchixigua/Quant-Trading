"""事件研究教学工具。

收益率均为小数。函数不访问网络，随机过程均可通过 ``seed`` 复现。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Literal

import numpy as np
import pandas as pd


AbnormalReturnModel = Literal["market_adjusted", "market_model"]


def _numeric_series(values: pd.Series, name: str) -> pd.Series:
    if not isinstance(values, pd.Series):
        raise TypeError(f"{name} 必须是 pandas Series")
    result = pd.to_numeric(values, errors="coerce").astype(float)
    if np.isinf(result.to_numpy()).any():
        raise ValueError(f"{name} 不能包含无穷值")
    return result


def align_event_windows(
    returns: pd.Series,
    event_dates: Sequence[object],
    window: tuple[int, int] = (-5, 20),
) -> pd.DataFrame:
    """把多个事件对齐到相对交易日，返回“事件 × 相对日”面板。

    不在收益率索引中的事件日会报错；位于样本边缘的窗口以 NaN 补齐。
    重复事件被保留，并以输入顺序作为 ``event_id``。
    """

    values = _numeric_series(returns, "returns")
    if not values.index.is_unique:
        raise ValueError("returns 索引必须唯一")
    start, end = window
    if start > end:
        raise ValueError("window 起点不能晚于终点")
    dates = list(event_dates)
    if not dates:
        raise ValueError("event_dates 不能为空")

    relative_days = pd.RangeIndex(start, end + 1, name="relative_day")
    rows: list[np.ndarray] = []
    missing: list[object] = []
    for date in dates:
        location = values.index.get_indexer([date])[0]
        if location < 0:
            missing.append(date)
            continue
        row = np.full(len(relative_days), np.nan)
        left = max(0, location + start)
        right = min(len(values), location + end + 1)
        target_left = left - (location + start)
        row[target_left : target_left + right - left] = values.iloc[left:right].to_numpy()
        rows.append(row)
    if missing:
        raise ValueError(f"事件日不在 returns 索引中: {missing[:3]}")

    result = pd.DataFrame(rows, columns=relative_days)
    result.index = pd.Index(range(len(dates)), name="event_id")
    result.attrs["event_dates"] = dates
    return result


def generate_synthetic_events(
    n_events: int = 100,
    window: tuple[int, int] = (-5, 20),
    alpha: float = 0.0,
    beta: float = 1.0,
    event_effect: float = 0.02,
    market_volatility: float = 0.01,
    idiosyncratic_volatility: float = 0.015,
    seed: int | None = None,
) -> pd.DataFrame:
    """生成可离线复现的合成事件面板。

    返回长表，包含 ``event_id``、``relative_day``、市场收益、资产收益和
    已知的理论异常收益；``event_effect`` 仅施加在事件日 0。
    """

    start, end = window
    if n_events < 1:
        raise ValueError("n_events 必须为正")
    if start > 0 or end < 0 or start > end:
        raise ValueError("window 必须包含事件日 0，且起点不能晚于终点")
    if market_volatility < 0 or idiosyncratic_volatility < 0:
        raise ValueError("波动率不能为负")
    for value, name in ((alpha, "alpha"), (beta, "beta"), (event_effect, "event_effect")):
        if not np.isfinite(value):
            raise ValueError(f"{name} 必须是有限数")

    rng = np.random.default_rng(seed)
    relative_days = np.arange(start, end + 1)
    shape = (n_events, len(relative_days))
    market = rng.normal(0.0, market_volatility, size=shape)
    noise = rng.normal(0.0, idiosyncratic_volatility, size=shape)
    effect = np.zeros(shape)
    effect[:, -start] = event_effect
    asset = alpha + beta * market + effect + noise
    return pd.DataFrame(
        {
            "event_id": np.repeat(np.arange(n_events), len(relative_days)),
            "relative_day": np.tile(relative_days, n_events),
            "asset_return": asset.ravel(),
            "market_return": market.ravel(),
            "true_abnormal_return": effect.ravel(),
        }
    )


def market_adjusted_abnormal_returns(
    asset_returns: pd.Series,
    market_returns: pd.Series,
) -> pd.Series:
    """市场调整异常收益 ``asset - market``。"""

    asset = _numeric_series(asset_returns, "asset_returns")
    market = _numeric_series(market_returns, "market_returns")
    aligned = pd.concat([asset.rename("asset"), market.rename("market")], axis=1)
    result = aligned["asset"] - aligned["market"]
    result[aligned.isna().any(axis=1)] = np.nan
    return result.rename("abnormal_return")


def market_model_abnormal_returns(
    asset_returns: pd.Series,
    market_returns: pd.Series,
    estimation_mask: pd.Series | np.ndarray | Sequence[bool] | None = None,
) -> pd.Series:
    """用估计样本 OLS 拟合市场模型并计算异常收益。

    ``estimation_mask`` 与对齐后的完整索引等长；实际拟合时会自动剔除缺失值。
    拟合出的 ``alpha``、``beta`` 和 ``estimation_count`` 保存在返回值 attrs 中。
    """

    asset = _numeric_series(asset_returns, "asset_returns")
    market = _numeric_series(market_returns, "market_returns")
    aligned = pd.concat([asset.rename("asset"), market.rename("market")], axis=1)
    if estimation_mask is None:
        selected = pd.Series(True, index=aligned.index)
    elif isinstance(estimation_mask, pd.Series):
        if not estimation_mask.index.equals(aligned.index):
            raise ValueError("estimation_mask 的索引必须与对齐后的收益索引一致")
        selected = estimation_mask.astype(bool)
    else:
        mask_array = np.asarray(estimation_mask)
        if mask_array.ndim != 1 or len(mask_array) != len(aligned):
            raise ValueError("estimation_mask 必须是一维且与对齐后的收益等长")
        selected = pd.Series(mask_array.astype(bool), index=aligned.index)

    estimation = aligned.loc[selected].dropna()
    if len(estimation) < 3:
        raise ValueError("市场模型至少需要 3 个有效估计样本")
    if estimation["market"].var(ddof=0) <= 0:
        raise ValueError("估计样本中的市场收益必须有正方差")
    design = np.column_stack([np.ones(len(estimation)), estimation["market"].to_numpy()])
    coefficients, *_ = np.linalg.lstsq(
        design, estimation["asset"].to_numpy(dtype=float), rcond=None
    )
    alpha, beta = map(float, coefficients)
    expected = alpha + beta * aligned["market"]
    result = (aligned["asset"] - expected).rename("abnormal_return")
    result[aligned.isna().any(axis=1)] = np.nan
    result.attrs.update(alpha=alpha, beta=beta, estimation_count=len(estimation))
    return result


def abnormal_returns(
    asset_returns: pd.Series,
    market_returns: pd.Series,
    model: AbnormalReturnModel = "market_adjusted",
    estimation_mask: pd.Series | np.ndarray | Sequence[bool] | None = None,
) -> pd.Series:
    """按指定模型计算异常收益。"""

    if model == "market_adjusted":
        if estimation_mask is not None:
            raise ValueError("market_adjusted 模型不使用 estimation_mask")
        return market_adjusted_abnormal_returns(asset_returns, market_returns)
    if model == "market_model":
        return market_model_abnormal_returns(asset_returns, market_returns, estimation_mask)
    raise ValueError("model 必须是 'market_adjusted' 或 'market_model'")


def event_window_car(
    abnormal_return: pd.Series | pd.DataFrame,
    window: tuple[int, int] | None = None,
) -> float | pd.Series:
    """计算事件窗 CAR；DataFrame 每行代表一个事件。"""

    if not isinstance(abnormal_return, (pd.Series, pd.DataFrame)):
        raise TypeError("abnormal_return 必须是 Series 或 DataFrame")
    selected = abnormal_return
    if window is not None:
        start, end = window
        if start > end:
            raise ValueError("window 起点不能晚于终点")
        selected = abnormal_return.loc[start:end] if isinstance(
            abnormal_return, pd.Series
        ) else abnormal_return.loc[:, start:end]
    if selected.size == 0:
        raise ValueError("事件窗中没有观测")
    if isinstance(selected, pd.Series):
        return float(selected.sum(min_count=1))
    return selected.sum(axis=1, min_count=1).rename("car")


def bootstrap_confidence_interval(
    values: pd.Series | Sequence[float] | np.ndarray,
    confidence: float = 0.95,
    n_bootstrap: int = 2_000,
    statistic: Callable[[np.ndarray], float] = np.mean,
    seed: int | None = None,
) -> tuple[float, float]:
    """用 iid percentile bootstrap 计算统计量置信区间。"""

    if not 0 < confidence < 1:
        raise ValueError("confidence 必须在 (0, 1) 内")
    if n_bootstrap < 1:
        raise ValueError("n_bootstrap 必须为正")
    sample = np.asarray(values, dtype=float).reshape(-1)
    sample = sample[np.isfinite(sample)]
    if sample.size < 2:
        raise ValueError("至少需要 2 个有限观测")
    rng = np.random.default_rng(seed)
    estimates = np.empty(n_bootstrap)
    for index in range(n_bootstrap):
        draw = rng.choice(sample, size=sample.size, replace=True)
        estimates[index] = float(statistic(draw))
    if not np.isfinite(estimates).all():
        raise ValueError("statistic 必须对每个 bootstrap 样本返回有限标量")
    tail = (1.0 - confidence) / 2.0
    lower, upper = np.quantile(estimates, [tail, 1.0 - tail])
    return float(lower), float(upper)


def placebo_dates(
    trading_index: pd.Index,
    event_dates: Sequence[object],
    exclusion: int = 5,
    seed: int | None = None,
) -> pd.Index:
    """为每个真实事件抽取一个非事件交易日。

    候选日与任一真实事件至少相隔 ``exclusion + 1`` 个交易日。同一次抽样不重复；
    若候选日不足会明确报错。
    """

    if not isinstance(trading_index, pd.Index) or not trading_index.is_unique:
        raise ValueError("trading_index 必须是唯一的 pandas Index")
    if exclusion < 0:
        raise ValueError("exclusion 不能为负")
    dates = list(event_dates)
    if not dates:
        raise ValueError("event_dates 不能为空")
    positions = trading_index.get_indexer(dates)
    if (positions < 0).any():
        raise ValueError("所有事件日都必须位于 trading_index 中")
    allowed = np.ones(len(trading_index), dtype=bool)
    for position in positions:
        left = max(0, position - exclusion)
        right = min(len(trading_index), position + exclusion + 1)
        allowed[left:right] = False
    candidates = np.flatnonzero(allowed)
    if len(candidates) < len(dates):
        raise ValueError("满足排除距离的候选日期不足")
    rng = np.random.default_rng(seed)
    selected = rng.choice(candidates, size=len(dates), replace=False)
    return pd.Index(trading_index.take(selected), name="placebo_date")


# 便于课程讲义采用不同但常见的术语。
synthetic_event_data = generate_synthetic_events
cumulative_abnormal_return = event_window_car
bootstrap_ci = bootstrap_confidence_interval
generate_placebo_dates = placebo_dates
