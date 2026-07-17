"""简化的 A 股模拟成交器，用于连接研究信号与每日运行流程。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PaperConfig:
    commission_rate: float = 0.0003
    minimum_commission: float = 5.0
    stamp_duty: float = 0.0005
    slippage: float = 0.0005
    lot_size: int = 100
    max_volume_participation: float = 1.0
    impact_coefficient: float = 0.0
    impact_exponent: float = 0.5

    def __post_init__(self) -> None:
        if self.lot_size <= 0:
            raise ValueError("lot_size 必须为正")
        if not 0 < self.max_volume_participation <= 1:
            raise ValueError("max_volume_participation 必须在 (0, 1] 内")
        if min(
            self.commission_rate,
            self.minimum_commission,
            self.stamp_duty,
            self.slippage,
            self.impact_coefficient,
            self.impact_exponent,
        ) < 0:
            raise ValueError("费用、滑点和冲击参数不能为负")


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
        volumes: pd.Series | None = None,
    ) -> pd.DataFrame:
        """按整数手调仓，并执行 T+1、交易限制、容量和冲击成本。"""
        date = pd.Timestamp(date).normalize()
        symbols = prices.index
        prices = prices.astype(float)
        if prices.isna().any() or (~np.isfinite(prices)).any() or (prices <= 0).any():
            raise ValueError("prices 必须为有限正数")
        if volumes is not None:
            aligned_volumes = volumes.reindex(symbols)
            if (
                aligned_volumes.isna().any()
                or (~np.isfinite(aligned_volumes)).any()
                or (aligned_volumes < 0).any()
            ):
                raise ValueError("volumes 必须覆盖全部代码且为有限非负数")
        else:
            aligned_volumes = None
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
        weights = target_weights.reindex(symbols).fillna(0.0).astype(float)
        if (weights < 0).any() or (~np.isfinite(weights)).any() or weights.sum() > 1.0 + 1e-10:
            raise ValueError("目标权重必须有限、非负且总和不超过 1")
        desired_shares = (
            (weights * nav / prices)
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
                requested = abs(int(requested_shares))
                shares = requested
                if aligned_volumes is not None:
                    capacity = int(
                        aligned_volumes[symbol]
                        * self.config.max_volume_participation
                        // self.config.lot_size
                    ) * self.config.lot_size
                    shares = min(shares, capacity)
                participation = (
                    shares / float(aligned_volumes[symbol])
                    if aligned_volumes is not None and aligned_volumes[symbol] > 0
                    else 0.0
                )
                impact = self.config.impact_coefficient * (
                    participation**self.config.impact_exponent
                )
                execution_price = float(
                    prices[symbol]
                    * (
                        1 + self.config.slippage + impact
                        if side == "BUY"
                        else 1 - self.config.slippage - impact
                    )
                )
                if side == "BUY":
                    shares = self._affordable_shares(shares, execution_price)
                if shares <= 0:
                    today_trades.append(
                        self._trade_record(
                            date,
                            symbol,
                            side,
                            0,
                            execution_price,
                            0.0,
                            "UNFILLED",
                            requested_shares=requested,
                            reference_price=float(prices[symbol]),
                        )
                    )
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
                    self._trade_record(
                        date,
                        symbol,
                        side,
                        shares,
                        execution_price,
                        fee,
                        "FILLED" if shares == requested else "PARTIALLY_FILLED",
                        requested_shares=requested,
                        reference_price=float(prices[symbol]),
                    )
                )

        self.trades.extend(today_trades)
        return pd.DataFrame(today_trades)

    def save_state(self, directory: str | Path) -> None:
        output = Path(directory)
        output.mkdir(parents=True, exist_ok=True)
        self.holdings.to_csv(output / "paper_holdings.csv", index_label="symbol")
        pd.DataFrame(self.trades).to_csv(output / "paper_trades.csv", index=False)
        account = {"cash": self.cash, "config": asdict(self.config)}
        (output / "paper_account.json").write_text(
            json.dumps(account, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load_state(cls, directory: str | Path) -> PaperBroker:
        """从持久化目录恢复现金、持仓、成交和配置，供跨日连续运行。"""
        source = Path(directory)
        account_path = source / "paper_account.json"
        holdings_path = source / "paper_holdings.csv"
        if not account_path.exists() or not holdings_path.exists():
            raise FileNotFoundError("模拟盘状态不完整：缺少账户或持仓文件")
        account = json.loads(account_path.read_text(encoding="utf-8"))
        holdings = pd.read_csv(holdings_path, index_col="symbol")
        if "shares" not in holdings or "last_buy_date" not in holdings:
            raise ValueError("持仓状态缺少 shares 或 last_buy_date")
        holdings["shares"] = holdings["shares"].astype("int64")
        holdings["last_buy_date"] = pd.to_datetime(holdings["last_buy_date"], errors="coerce")
        trades_path = source / "paper_trades.csv"
        trades: list[dict[str, object]] = []
        if trades_path.exists() and trades_path.stat().st_size:
            try:
                trade_frame = pd.read_csv(trades_path)
            except pd.errors.EmptyDataError:
                trade_frame = pd.DataFrame()
            if not trade_frame.empty:
                if "date" in trade_frame:
                    trade_frame["date"] = pd.to_datetime(trade_frame["date"], errors="coerce")
                trades = trade_frame.to_dict("records")
        config = PaperConfig(**account.get("config", {}))
        return cls(cash=float(account["cash"]), config=config, holdings=holdings, trades=trades)

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
        *,
        requested_shares: int | None = None,
        reference_price: float | None = None,
    ) -> dict[str, object]:
        return {
            "date": date,
            "symbol": symbol,
            "side": side,
            "shares": shares,
            "requested_shares": shares if requested_shares is None else requested_shares,
            "price": price,
            "reference_price": price if reference_price is None else reference_price,
            "fee": fee,
            "status": status,
        }
