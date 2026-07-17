"""面向 A 股日频研究的透明回测器。

约定：信号在收盘后形成，至少下一交易日收盘执行；持仓承受执行前的当日收益。
涨停不能买、跌停不能卖、停牌不能交易。现金收益暂按 0 处理。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    commission: float = 0.0003
    stamp_duty: float = 0.0005
    slippage: float = 0.0005
    execution_lag: int = 1
    max_gross_exposure: float = 1.0


@dataclass
class BacktestResult:
    returns: pd.Series
    gross_returns: pd.Series
    costs: pd.Series
    turnover: pd.Series
    weights: pd.DataFrame
    rejected_turnover: pd.Series


def _aligned_flag(
    flag: pd.DataFrame | None, prices: pd.DataFrame, default: bool = False
) -> pd.DataFrame:
    if flag is None:
        return pd.DataFrame(default, index=prices.index, columns=prices.columns)
    return flag.reindex_like(prices).fillna(default).astype(bool)


def run_backtest(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    *,
    suspended: pd.DataFrame | None = None,
    limit_up: pd.DataFrame | None = None,
    limit_down: pd.DataFrame | None = None,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """回测收盘到收盘的目标权重策略。

    target_weights 的日期是信号形成日，不是成交日。默认自动滞后一日，避免未来函数。
    """
    cfg = config or BacktestConfig()
    if cfg.execution_lag < 1:
        raise ValueError("execution_lag 必须至少为 1；当日信号当日收盘成交会产生未来函数")
    if prices.empty or (prices <= 0).any().any():
        raise ValueError("prices 必须为非空正数宽表")
    if not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise ValueError("prices 日期索引必须严格递增且不重复")

    prices = prices.astype(float)
    targets = target_weights.reindex_like(prices).fillna(0.0).astype(float)
    if (targets.abs().sum(axis=1) > cfg.max_gross_exposure + 1e-10).any():
        raise ValueError("目标权重超过 max_gross_exposure")
    executable_targets = targets.shift(cfg.execution_lag).fillna(0.0)
    is_suspended = _aligned_flag(suspended, prices)
    at_limit_up = _aligned_flag(limit_up, prices)
    at_limit_down = _aligned_flag(limit_down, prices)
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)

    current = pd.Series(0.0, index=prices.columns)
    weights_history: list[pd.Series] = []
    net_returns: list[float] = []
    gross_returns: list[float] = []
    costs: list[float] = []
    turnovers: list[float] = []
    rejected: list[float] = []

    for date in prices.index:
        daily_asset_return = asset_returns.loc[date].fillna(0.0)
        gross_return = float((current * daily_asset_return).sum())
        denominator = 1.0 + gross_return
        drifted = current * (1.0 + daily_asset_return) / denominator if denominator > 0 else current

        requested = executable_targets.loc[date] - drifted
        blocked_buy = is_suspended.loc[date] | at_limit_up.loc[date]
        blocked_sell = is_suspended.loc[date] | at_limit_down.loc[date]
        blocked = ((requested > 0) & blocked_buy) | ((requested < 0) & blocked_sell)
        executed = requested.mask(blocked, 0.0)

        buy_turnover = float(executed.clip(lower=0.0).sum())
        sell_turnover = float(-executed.clip(upper=0.0).sum())
        turnover = buy_turnover + sell_turnover
        trading_cost = (
            turnover * (cfg.commission + cfg.slippage) + sell_turnover * cfg.stamp_duty
        )
        current = (drifted + executed).replace([np.inf, -np.inf], 0.0).fillna(0.0)

        gross_returns.append(gross_return)
        costs.append(trading_cost)
        net_returns.append(gross_return - trading_cost)
        turnovers.append(turnover)
        rejected.append(float(requested.mask(~blocked, 0.0).abs().sum()))
        weights_history.append(current.copy())

    index = prices.index
    return BacktestResult(
        returns=pd.Series(net_returns, index=index, name="strategy_return"),
        gross_returns=pd.Series(gross_returns, index=index, name="gross_return"),
        costs=pd.Series(costs, index=index, name="cost"),
        turnover=pd.Series(turnovers, index=index, name="turnover"),
        weights=pd.DataFrame(weights_history, index=index),
        rejected_turnover=pd.Series(rejected, index=index, name="rejected_turnover"),
    )
