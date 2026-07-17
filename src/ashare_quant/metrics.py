"""收益与风险指标。所有收益率均使用小数，而非百分数。"""

from __future__ import annotations

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def wealth_index(returns: pd.Series, initial: float = 1.0) -> pd.Series:
    """由简单收益率计算复利净值。"""
    clean = returns.fillna(0.0).astype(float)
    return initial * (1.0 + clean).cumprod()


def drawdown(returns: pd.Series) -> pd.Series:
    """计算相对历史最高净值的回撤。"""
    wealth = wealth_index(returns)
    return wealth / wealth.cummax() - 1.0


def annualized_return(returns: pd.Series, periods: int = TRADING_DAYS) -> float:
    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    growth = float((1.0 + clean).prod())
    if growth <= 0:
        return -1.0
    return growth ** (periods / len(clean)) - 1.0


def annualized_volatility(returns: pd.Series, periods: int = TRADING_DAYS) -> float:
    clean = returns.dropna()
    return float(clean.std(ddof=1) * np.sqrt(periods)) if len(clean) > 1 else float("nan")


def sharpe_ratio(
    returns: pd.Series, risk_free_rate: float = 0.0, periods: int = TRADING_DAYS
) -> float:
    """基于日超额收益的年化 Sharpe。risk_free_rate 为年化值。"""
    clean = returns.dropna()
    if len(clean) < 2:
        return float("nan")
    daily_rf = (1.0 + risk_free_rate) ** (1.0 / periods) - 1.0
    excess = clean - daily_rf
    volatility = excess.std(ddof=1)
    return float(excess.mean() / volatility * np.sqrt(periods)) if volatility > 0 else float("nan")


def max_drawdown(returns: pd.Series) -> float:
    dd = drawdown(returns)
    return float(dd.min()) if not dd.empty else float("nan")


def tracking_error(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    periods: int = TRADING_DAYS,
) -> float:
    """策略相对基准主动收益的年化标准差。"""
    aligned = pd.concat(
        [returns.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1
    ).dropna()
    if len(aligned) < 2:
        return float("nan")
    active = aligned["portfolio"] - aligned["benchmark"]
    return float(active.std(ddof=1) * np.sqrt(periods))


def information_ratio(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    periods: int = TRADING_DAYS,
) -> float:
    """主动收益均值除以主动风险，并按 periods 年化。"""
    aligned = pd.concat(
        [returns.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1
    ).dropna()
    if len(aligned) < 2:
        return float("nan")
    active = aligned["portfolio"] - aligned["benchmark"]
    active_volatility = active.std(ddof=1)
    if active_volatility <= 0:
        return float("nan")
    return float(active.mean() / active_volatility * np.sqrt(periods))


def beta(returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """基于同期简单收益 OLS 斜率计算市场 beta。"""
    aligned = pd.concat(
        [returns.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1
    ).dropna()
    if len(aligned) < 2:
        return float("nan")
    benchmark_variance = aligned["benchmark"].var(ddof=1)
    if benchmark_variance <= 0:
        return float("nan")
    covariance = aligned["portfolio"].cov(aligned["benchmark"])
    return float(covariance / benchmark_variance)


def active_risk_attribution(
    portfolio_weights: pd.Series,
    benchmark_weights: pd.Series,
    covariance: pd.DataFrame,
    periods: int = TRADING_DAYS,
) -> pd.DataFrame:
    """按资产归因主动风险（tracking error）。

    输入协方差为单期协方差；返回的 tracking_error_contribution 已按
    ``periods`` 年化，且其和等于年化 tracking error。
    """
    if periods <= 0:
        raise ValueError("periods 必须为正")
    portfolio, benchmark = portfolio_weights.align(
        benchmark_weights, join="outer", fill_value=0.0
    )
    active = portfolio.astype(float) - benchmark.astype(float)
    covariance = pd.DataFrame(covariance, dtype=float).reindex(
        index=active.index, columns=active.index
    )
    if covariance.isna().any().any():
        raise ValueError("协方差矩阵必须覆盖组合与基准中的全部资产")
    matrix = (covariance.to_numpy() + covariance.to_numpy().T) / 2.0
    active_array = active.to_numpy()
    marginal_variance = matrix @ active_array
    variance = float(active_array @ marginal_variance)
    if variance <= 0:
        raise ValueError("主动组合方差必须为正")
    per_period_error = np.sqrt(variance)
    contribution = active_array * marginal_variance / per_period_error * np.sqrt(periods)
    result = pd.DataFrame(
        {
            "active_weight": active,
            "marginal_tracking_error": marginal_variance
            / per_period_error
            * np.sqrt(periods),
            "tracking_error_contribution": contribution,
            "percent_contribution": active_array * marginal_variance / variance,
        },
        index=active.index,
    )
    result.attrs["tracking_error"] = per_period_error * np.sqrt(periods)
    result.attrs["active_variance"] = variance * periods
    return result


def performance_summary(
    returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
    turnover: pd.Series | None = None,
) -> pd.Series:
    """生成策略核心指标；传入基准时同时计算年化超额收益。"""
    result: dict[str, float] = {
        "total_return": float(wealth_index(returns).iloc[-1] - 1.0) if len(returns) else np.nan,
        "annualized_return": annualized_return(returns),
        "annualized_volatility": annualized_volatility(returns),
        "sharpe": sharpe_ratio(returns),
        "max_drawdown": max_drawdown(returns),
    }
    result["calmar"] = (
        result["annualized_return"] / abs(result["max_drawdown"])
        if result["max_drawdown"] < 0
        else np.nan
    )
    if benchmark_returns is not None:
        aligned = pd.concat([returns, benchmark_returns], axis=1).dropna()
        result["annualized_excess_return"] = annualized_return(
            aligned.iloc[:, 0] - aligned.iloc[:, 1]
        )
        result["tracking_error"] = tracking_error(returns, benchmark_returns)
        result["information_ratio"] = information_ratio(returns, benchmark_returns)
        result["beta"] = beta(returns, benchmark_returns)
    if turnover is not None:
        result["average_daily_turnover"] = float(turnover.mean())
        result["annualized_turnover"] = float(turnover.mean() * TRADING_DAYS)
    return pd.Series(result, name="value")
