"""横截面因子处理、检验和组合构建。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def winsorize_mad(values: pd.Series, n_mad: float = 5.0) -> pd.Series:
    median = values.median()
    mad = (values - median).abs().median()
    if pd.isna(mad) or mad == 0:
        return values.copy()
    scale = 1.4826 * mad
    return values.clip(median - n_mad * scale, median + n_mad * scale)


def zscore(values: pd.Series) -> pd.Series:
    std = values.std(ddof=0)
    return (values - values.mean()) / std if std and np.isfinite(std) else values * 0.0


def neutralize(
    factor: pd.Series, log_market_cap: pd.Series, industry: pd.Series
) -> pd.Series:
    """用市值和行业哑变量做 OLS，返回残差。"""
    frame = pd.concat(
        [factor.rename("factor"), log_market_cap.rename("size"), industry.rename("industry")],
        axis=1,
    ).dropna()
    if len(frame) < 3:
        return pd.Series(np.nan, index=factor.index)
    design = pd.concat(
        [
            pd.Series(1.0, index=frame.index, name="intercept"),
            frame[["size"]],
            pd.get_dummies(frame["industry"], drop_first=True, dtype=float),
        ],
        axis=1,
    )
    beta, *_ = np.linalg.lstsq(
        design.to_numpy(dtype=float), frame["factor"].to_numpy(dtype=float), rcond=None
    )
    residual = frame["factor"] - design.to_numpy(dtype=float) @ beta
    return residual.reindex(factor.index)


def preprocess_factor(
    factor: pd.Series, market_cap: pd.Series, industry: pd.Series
) -> pd.Series:
    cleaned = winsorize_mad(factor)
    residual = neutralize(cleaned, np.log(market_cap.where(market_cap > 0)), industry)
    return zscore(residual)


def momentum_factor(prices: pd.DataFrame, lookback: int = 60, skip: int = 5) -> pd.DataFrame:
    """截至信号日可观测的动量：跳过最近 skip 日。"""
    return prices.shift(skip).pct_change(lookback, fill_method=None)


def low_volatility_factor(prices: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    return -prices.pct_change(fill_method=None).rolling(window).std()


def forward_returns(prices: pd.DataFrame, horizon: int = 20) -> pd.DataFrame:
    """仅供标签与事后评价；严禁作为当期特征。"""
    return prices.pct_change(horizon, fill_method=None).shift(-horizon)


def rank_ic(factor: pd.DataFrame, future_return: pd.DataFrame) -> pd.Series:
    aligned_factor, aligned_return = factor.align(future_return, join="inner")
    return aligned_factor.corrwith(aligned_return, axis=1, method="spearman").rename("rank_ic")


def quantile_returns(
    factor: pd.DataFrame, future_return: pd.DataFrame, quantiles: int = 5
) -> pd.DataFrame:
    """返回每个日期各因子分组的未来等权收益。"""
    records: list[dict[str, object]] = []
    for date in factor.index.intersection(future_return.index):
        frame = pd.concat(
            [factor.loc[date].rename("factor"), future_return.loc[date].rename("return")], axis=1
        ).dropna()
        if len(frame) < quantiles:
            continue
        groups = pd.qcut(frame["factor"].rank(method="first"), quantiles, labels=False)
        means = frame.groupby(groups)["return"].mean()
        for group, value in means.items():
            records.append({"date": date, "quantile": int(group) + 1, "return": value})
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).pivot(index="date", columns="quantile", values="return")


def top_quantile_weights(
    scores: pd.DataFrame, quantile: float = 0.2, rebalance: str = "monthly"
) -> pd.DataFrame:
    """在每个调仓日等权持有最高分组，其余日期保持上一目标权重。"""
    if not 0 < quantile <= 1:
        raise ValueError("quantile 必须在 (0, 1] 内")
    if rebalance != "monthly":
        raise ValueError("当前教学版本仅支持 monthly 调仓")
    month = scores.index.to_period("M")
    rebalancing_scores = scores.groupby(month, group_keys=False).tail(1)
    weights = pd.DataFrame(0.0, index=rebalancing_scores.index, columns=scores.columns)
    for date, row in rebalancing_scores.iterrows():
        valid = row.dropna()
        count = max(1, int(np.ceil(len(valid) * quantile)))
        selected = valid.nlargest(count).index
        weights.loc[date, selected] = 1.0 / count
    return weights.reindex(scores.index).ffill().fillna(0.0)
