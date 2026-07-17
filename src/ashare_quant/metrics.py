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
    if turnover is not None:
        result["average_daily_turnover"] = float(turnover.mean())
        result["annualized_turnover"] = float(turnover.mean() * TRADING_DAYS)
    return pd.Series(result, name="value")
