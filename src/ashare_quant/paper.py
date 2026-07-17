"""简化的 A 股模拟成交器，用于连接研究信号与每日运行流程。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class PaperConfig:
    commission_rate: float = 0.0003
    minimum_commission: float = 5.0
    stamp_duty: float = 0.0005
    slippage: float = 0.0005
    lot_size: int = 100


@dataclass
class PaperBroker:
    cash: float = 1_000_000.0
    config: PaperConfig = field(default_factory=PaperConfig)
    holdings: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["shares", "last_buy_date"])
    )
    trades: list[dict[str, object]] = field(default_factory=list)

    def net_asset_value(self, prices: pd.Series) -> float:
        shares = self.holdings["shares"].astype(float).reindex(prices.index).fillna(0.0)
        return float(self.cash + (shares * prices).sum())

    def rebalance(
        self,
        date: pd.Timestamp,
        prices: pd.Series,
        target_weights: pd.Series,
        *,
        suspended: pd.Series | None = None,
        limit_up: pd.Series | None = None,
        limit_down: pd.Series | None = None,
    ) -> pd.DataFrame:
        """按 100 股整数手调仓；先卖后买，并执行 T+1、停牌和涨跌停限制。"""
        date = pd.Timestamp(date).normalize()
        symbols = prices.index
        flags = {
            "suspended": suspended.reindex(symbols).fillna(False) if suspended is not None else False,
            "limit_up": limit_up.reindex(symbols).fillna(False) if limit_up is not None else False,
            "limit_down": (
                limit_down.reindex(symbols).fillna(False) if limit_down is not None else False
            ),
        }
        if self.holdings.empty:
            self.holdings = pd.DataFrame(
                {"shares": 0, "last_buy_date": pd.NaT}, index=symbols
            )
        else:
            self.holdings = self.holdings.reindex(symbols).fillna({"shares": 0})

        nav = self.net_asset_value(prices)
        desired_shares = (
            (target_weights.reindex(symbols).fillna(0.0) * nav / prices)
            // self.config.lot_size
            * self.config.lot_size
        ).astype(int)
        orders = desired_shares - self.holdings["shares"].astype(int)
        today_trades: list[dict[str, object]] = []

        for side in ("SELL", "BUY"):
            candidates = orders[orders < 0] if side == "SELL" else orders[orders > 0]
            for symbol, requested_shares in candidates.items():
                blocked_reason = self._blocked_reason(
                    symbol, side, date, flags["suspended"], flags["limit_up"], flags["limit_down"]
                )
                if blocked_reason:
                    today_trades.append(
                        self._trade_record(date, symbol, side, 0, prices[symbol], 0.0, blocked_reason)
                    )
                    continue
                shares = abs(int(requested_shares))
                execution_price = float(
                    prices[symbol]
                    * (1 + self.config.slippage if side == "BUY" else 1 - self.config.slippage)
                )
                if side == "BUY":
                    shares = self._affordable_shares(shares, execution_price)
                if shares <= 0:
                    continue
                value = shares * execution_price
                commission = max(self.config.minimum_commission, value * self.config.commission_rate)
                tax = value * self.config.stamp_duty if side == "SELL" else 0.0
                fee = commission + tax
                if side == "SELL":
                    self.cash += value - fee
                    self.holdings.loc[symbol, "shares"] -= shares
                else:
                    self.cash -= value + fee
                    self.holdings.loc[symbol, "shares"] += shares
                    self.holdings.loc[symbol, "last_buy_date"] = date
                today_trades.append(
                    self._trade_record(date, symbol, side, shares, execution_price, fee, "FILLED")
                )

        self.trades.extend(today_trades)
        return pd.DataFrame(today_trades)

    def save_state(self, directory: str | Path) -> None:
        output = Path(directory)
        output.mkdir(parents=True, exist_ok=True)
        self.holdings.to_csv(output / "paper_holdings.csv", index_label="symbol")
        pd.DataFrame(self.trades).to_csv(output / "paper_trades.csv", index=False)
        pd.Series({"cash": self.cash}).to_json(output / "paper_account.json", force_ascii=False)

    def _affordable_shares(self, requested: int, price: float) -> int:
        lots = requested // self.config.lot_size
        while lots > 0:
            shares = lots * self.config.lot_size
            value = shares * price
            fee = max(self.config.minimum_commission, value * self.config.commission_rate)
            if value + fee <= self.cash:
                return shares
            lots -= 1
        return 0

    def _blocked_reason(
        self,
        symbol: str,
        side: str,
        date: pd.Timestamp,
        suspended: pd.Series | bool,
        limit_up: pd.Series | bool,
        limit_down: pd.Series | bool,
    ) -> str | None:
        if isinstance(suspended, pd.Series) and bool(suspended[symbol]):
            return "SUSPENDED"
        if side == "BUY" and isinstance(limit_up, pd.Series) and bool(limit_up[symbol]):
            return "LIMIT_UP"
        if side == "SELL":
            if isinstance(limit_down, pd.Series) and bool(limit_down[symbol]):
                return "LIMIT_DOWN"
            last_buy = self.holdings.loc[symbol, "last_buy_date"]
            if pd.notna(last_buy) and pd.Timestamp(last_buy).normalize() >= date:
                return "T_PLUS_ONE"
        return None

    @staticmethod
    def _trade_record(
        date: pd.Timestamp,
        symbol: str,
        side: str,
        shares: int,
        price: float,
        fee: float,
        status: str,
    ) -> dict[str, object]:
        return {
            "date": date,
            "symbol": symbol,
            "side": side,
            "shares": shares,
            "price": price,
            "fee": fee,
            "status": status,
        }
