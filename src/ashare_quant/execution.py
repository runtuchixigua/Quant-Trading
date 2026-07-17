"""A 股模拟执行：订单生成、容量约束、冲击成本与成交对账。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ExecutionConfig:
    """仅用于模拟撮合的执行参数，不包含任何真实券商连接。"""

    lot_size: int = 100
    max_volume_participation: float = 0.10
    slippage: float = 0.0005
    impact_coefficient: float = 0.10
    impact_exponent: float = 0.5

    def __post_init__(self) -> None:
        if self.lot_size <= 0:
            raise ValueError("lot_size 必须为正整数")
        if not 0 < self.max_volume_participation <= 1:
            raise ValueError("max_volume_participation 必须在 (0, 1] 内")
        if min(self.slippage, self.impact_coefficient, self.impact_exponent) < 0:
            raise ValueError("滑点、冲击系数和冲击指数不能为负")


def weights_to_orders(
    target_weights: pd.Series,
    prices: pd.Series,
    current_shares: pd.Series | None,
    net_asset_value: float,
    *,
    lot_size: int = 100,
) -> pd.DataFrame:
    """将目标权重转换为 100 股整数手订单。"""
    if net_asset_value < 0 or lot_size <= 0:
        raise ValueError("净资产不能为负且 lot_size 必须为正")
    symbols = prices.index.union(target_weights.index)
    px = prices.reindex(symbols)
    weights = target_weights.reindex(symbols).fillna(0.0).astype(float)
    if px.isna().any() or (~np.isfinite(px)).any() or (px <= 0).any():
        raise ValueError("订单涉及的价格必须为有限正数")
    if (~np.isfinite(weights)).any() or (weights < 0).any():
        raise ValueError("目标权重必须为有限非负数")
    if weights.sum() > 1.0 + 1e-10:
        raise ValueError("目标权重之和不能超过 1")

    current = (
        pd.Series(0, index=symbols, dtype="int64")
        if current_shares is None
        else current_shares.reindex(symbols).fillna(0).astype("int64")
    )
    target = ((weights * net_asset_value / px) // lot_size * lot_size).astype("int64")
    delta = target - current
    frame = pd.DataFrame(
        {
            "symbol": symbols,
            "side": np.where(delta >= 0, "BUY", "SELL"),
            "requested_shares": delta.abs().astype("int64"),
            "reference_price": px.to_numpy(dtype=float),
            "target_shares": target.to_numpy(dtype="int64"),
        }
    )
    return frame.loc[frame["requested_shares"] > 0].reset_index(drop=True)


def simulate_execution(
    orders: pd.DataFrame,
    prices: pd.Series,
    volumes: pd.Series,
    *,
    config: ExecutionConfig | None = None,
) -> pd.DataFrame:
    """按成交量参与上限模拟部分成交，并加入方向性冲击成本。"""
    config = config or ExecutionConfig()
    required = {"symbol", "side", "requested_shares"}
    missing = required.difference(orders.columns)
    if missing:
        raise ValueError(f"订单缺少字段: {sorted(missing)}")

    records: list[dict[str, object]] = []
    for row in orders.itertuples(index=False):
        symbol = str(row.symbol)
        side = str(row.side).upper()
        requested = int(row.requested_shares)
        if side not in {"BUY", "SELL"} or requested <= 0:
            raise ValueError("side 必须为 BUY/SELL，requested_shares 必须为正")
        price = float(prices.get(symbol, np.nan))
        volume = float(volumes.get(symbol, np.nan))
        if not np.isfinite(price) or price <= 0:
            raise ValueError(f"{symbol} 缺少有效价格")
        if not np.isfinite(volume) or volume < 0:
            raise ValueError(f"{symbol} 缺少有效成交量")

        capacity = int(volume * config.max_volume_participation // config.lot_size)
        capacity *= config.lot_size
        filled = min(requested, capacity)
        participation = filled / volume if volume > 0 else 0.0
        impact = config.impact_coefficient * participation**config.impact_exponent
        direction = 1.0 if side == "BUY" else -1.0
        execution_price = price * (1.0 + direction * (config.slippage + impact))
        status = "FILLED" if filled == requested else ("PARTIALLY_FILLED" if filled else "UNFILLED")
        records.append(
            {
                "symbol": symbol,
                "side": side,
                "requested_shares": requested,
                "filled_shares": filled,
                "unfilled_shares": requested - filled,
                "reference_price": price,
                "execution_price": execution_price,
                "volume": volume,
                "participation_rate": participation,
                "impact_cost": abs(execution_price - price) * filled,
                "status": status,
            }
        )
    return pd.DataFrame.from_records(records)


def reconcile_executions(
    theoretical_orders: pd.DataFrame,
    simulated_fills: pd.DataFrame,
    *,
    share_tolerance: int = 0,
) -> pd.DataFrame:
    """按代码和方向对账理论订单与模拟成交。"""
    order_column = (
        "requested_shares" if "requested_shares" in theoretical_orders else "shares"
    )
    fill_column = "filled_shares" if "filled_shares" in simulated_fills else "shares"
    required_orders = {"symbol", "side", order_column}
    required_fills = {"symbol", "side", fill_column}
    if not required_orders.issubset(theoretical_orders) or not required_fills.issubset(
        simulated_fills
    ):
        raise ValueError("理论订单或模拟成交缺少 symbol/side/数量字段")

    keys = ["symbol", "side"]
    expected = (
        theoretical_orders.groupby(keys, as_index=False)[order_column]
        .sum()
        .rename(columns={order_column: "theoretical_shares"})
    )
    actual = (
        simulated_fills.groupby(keys, as_index=False)[fill_column]
        .sum()
        .rename(columns={fill_column: "simulated_shares"})
    )
    result = expected.merge(actual, on=keys, how="outer").fillna(0)
    result[["theoretical_shares", "simulated_shares"]] = result[
        ["theoretical_shares", "simulated_shares"]
    ].astype("int64")
    result["share_difference"] = result["simulated_shares"] - result["theoretical_shares"]
    result["matched"] = result["share_difference"].abs() <= share_tolerance
    return result.sort_values(keys).reset_index(drop=True)
