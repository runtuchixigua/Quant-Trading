"""横截面因子处理、检验和组合构建。"""

from __future__ import annotations

from collections.abc import Mapping

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


def earnings_yield(net_profit: pd.Series, market_cap: pd.Series) -> pd.Series:
    """EP：归母净利润除以信号日总市值。"""

    return net_profit / market_cap.where(market_cap > 0)


def book_to_price(book_equity: pd.Series, market_cap: pd.Series) -> pd.Series:
    """BP：账面权益除以信号日总市值。"""

    return book_equity / market_cap.where(market_cap > 0)


def return_on_equity(net_profit: pd.Series, book_equity: pd.Series) -> pd.Series:
    """ROE：净利润除以账面权益。"""

    return net_profit / book_equity.where(book_equity > 0)


def accruals(
    net_profit: pd.Series,
    operating_cash_flow: pd.Series,
    total_assets: pd.Series,
) -> pd.Series:
    """总应计项：(净利润 - 经营现金流) / 总资产。"""

    return (net_profit - operating_cash_flow) / total_assets.where(total_assets > 0)


def amihud_illiquidity(
    returns: pd.DataFrame,
    amount: pd.DataFrame,
    window: int = 20,
    min_periods: int | None = None,
) -> pd.DataFrame:
    """Amihud 非流动性：窗口内 ``abs(return) / amount`` 的均值。"""

    if window < 1:
        raise ValueError("window 必须为正数")
    aligned_return, aligned_amount = returns.align(amount, join="inner")
    daily = aligned_return.abs() / aligned_amount.where(aligned_amount > 0)
    return daily.rolling(window, min_periods=min_periods or window).mean()


def amihud_from_prices(
    prices: pd.DataFrame,
    amount: pd.DataFrame,
    window: int = 20,
    min_periods: int | None = None,
) -> pd.DataFrame:
    """由收盘价和成交额计算 Amihud 非流动性。"""

    returns = prices.pct_change(fill_method=None)
    return amihud_illiquidity(returns, amount, window, min_periods)


def ic_ir(ic: pd.Series, ddof: int = 1) -> float:
    """ICIR：有效日 IC 均值除以标准差，不隐含年化。"""

    valid = ic.dropna()
    std = valid.std(ddof=ddof)
    if valid.empty or pd.isna(std) or std == 0:
        return float("nan")
    return float(valid.mean() / std)


def yearly_ic(ic: pd.Series) -> pd.DataFrame:
    """按自然年汇总 IC 均值、标准差、ICIR 和有效样本数。"""

    if not isinstance(ic.index, pd.DatetimeIndex):
        raise ValueError("ic 必须使用 DatetimeIndex")
    grouped = ic.dropna().groupby(ic.dropna().index.year)
    result = grouped.agg(["mean", "std", "count"])
    result["icir"] = result["mean"] / result["std"].replace(0, np.nan)
    result.index.name = "year"
    return result[["mean", "std", "icir", "count"]]


def ic_decay(
    factor: pd.DataFrame,
    future_return: pd.DataFrame,
    max_lag: int = 12,
) -> pd.Series:
    """计算信号滞后 0..max_lag 期后的平均 Rank IC 衰减。"""

    if max_lag < 0:
        raise ValueError("max_lag 不能为负数")
    values = {
        lag: rank_ic(factor.shift(lag), future_return).mean()
        for lag in range(max_lag + 1)
    }
    return pd.Series(values, name="mean_rank_ic").rename_axis("lag")


def factor_correlation(factors: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """计算多个因子每日横截面 Pearson 相关系数的时间均值。"""

    if not factors:
        raise ValueError("factors 不能为空")
    names = list(factors)
    result = pd.DataFrame(np.eye(len(names)), index=names, columns=names)
    for left_position, left_name in enumerate(names):
        for right_name in names[left_position + 1 :]:
            left, right = factors[left_name].align(factors[right_name], join="inner")
            daily = left.corrwith(right, axis=1, method="pearson")
            value = daily.mean()
            result.loc[left_name, right_name] = value
            result.loc[right_name, left_name] = value
    return result


def equal_weight_composite(factors: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """按可用因子等权合成；单个缺失值不会污染其他因子。"""

    if not factors:
        raise ValueError("factors 不能为空")
    stacked = pd.concat(factors, axis=0, names=["factor"])
    return stacked.groupby(level=1).mean()


def rolling_ic_composite(
    factors: Mapping[str, pd.DataFrame],
    future_return: pd.DataFrame,
    window: int = 60,
    min_periods: int | None = None,
) -> pd.DataFrame:
    """使用历史滚动 IC 加权合成因子，权重滞后一日以杜绝未来信息。

    每日权重为过去窗口内各因子平均 Rank IC，并按绝对值之和归一化。
    历史不足或权重全零时，合成结果为空。
    """

    if not factors:
        raise ValueError("factors 不能为空")
    if window < 2:
        raise ValueError("window 必须至少为 2")
    required = min_periods if min_periods is not None else window
    if required < 1 or required > window:
        raise ValueError("min_periods 必须在 [1, window] 内")

    names = list(factors)
    histories = pd.concat(
        {name: rank_ic(value, future_return) for name, value in factors.items()},
        axis=1,
    )
    weights = histories.rolling(window, min_periods=required).mean().shift(1)
    weights = weights.div(weights.abs().sum(axis=1).replace(0, np.nan), axis=0)

    common_index = future_return.index
    common_columns = future_return.columns
    total = pd.DataFrame(0.0, index=common_index, columns=common_columns)
    available_weight = pd.DataFrame(0.0, index=common_index, columns=common_columns)
    for name in names:
        values = factors[name].reindex(index=common_index, columns=common_columns)
        daily_weight = weights[name].reindex(common_index)
        valid_weight = values.notna().mul(daily_weight.abs(), axis=0)
        total = total.add(values.mul(daily_weight, axis=0).fillna(0.0), fill_value=0.0)
        available_weight = available_weight.add(valid_weight, fill_value=0.0)
    return total.div(available_weight.where(available_weight > 0))


# 常用缩写别名，保留清晰的完整名称作为主 API。
ep_factor = earnings_yield
bp_factor = book_to_price
roe_factor = return_on_equity
accrual_factor = accruals
icir = ic_ir
annual_ic = yearly_ic
