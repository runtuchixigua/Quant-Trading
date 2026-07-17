"""数据读取、校验与离线教学数据生成。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_PANEL_COLUMNS = {"date", "symbol", "close"}


def load_price_panel(path: str | Path) -> pd.DataFrame:
    """读取长表行情，并拒绝重复主键和非正价格。"""
    frame = pd.read_csv(path, parse_dates=["date"])
    missing = REQUIRED_PANEL_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"行情缺少字段: {sorted(missing)}")
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("行情存在重复的 (date, symbol)")
    if frame["close"].isna().any() or (frame["close"] <= 0).any():
        raise ValueError("close 必须为非空正数")
    return frame.sort_values(["date", "symbol"]).reset_index(drop=True)


def to_wide(frame: pd.DataFrame, value: str = "close") -> pd.DataFrame:
    return frame.pivot(index="date", columns="symbol", values=value).sort_index()


def make_synthetic_market(
    n_days: int = 800, n_assets: int = 40, seed: int = 7
) -> pd.DataFrame:
    """生成可重复的教学数据；仅用于验证代码，不能证明策略有效。"""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2019-01-02", periods=n_days)
    symbols = [f"{600000 + i:06d}.SH" for i in range(n_assets)]
    market = rng.normal(0.0002, 0.009, size=(n_days, 1))
    quality = rng.normal(0.0, 1.0, size=(1, n_assets))
    noise = rng.normal(0.0, 0.012, size=(n_days, n_assets))
    returns = market + 0.00008 * quality + noise
    prices = 20.0 * np.cumprod(1.0 + returns, axis=0)

    rows = pd.MultiIndex.from_product([dates, symbols], names=["date", "symbol"]).to_frame(
        index=False
    )
    rows["close"] = prices.reshape(-1)
    rows["volume"] = rng.lognormal(15.0, 0.7, size=len(rows))
    rows["market_cap"] = (
        np.repeat(rng.lognormal(23.0, 0.8, size=n_assets)[None, :], n_days, axis=0).reshape(-1)
        * (rows["close"].to_numpy() / 20.0)
    )
    rows["industry"] = np.tile([f"I{i % 8}" for i in range(n_assets)], n_days)
    rows["is_st"] = False
    rows["suspended"] = False
    rows["limit_up"] = False
    rows["limit_down"] = False
    return rows


def fetch_510300(start_date: str, end_date: str) -> pd.DataFrame:
    """通过可选依赖 AkShare 获取 510300 后复权日线。"""
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("请先执行 pip install -e '.[data]' 安装 AkShare") from exc
    frame = ak.fund_etf_hist_em(
        symbol="510300",
        period="daily",
        start_date=start_date.replace("-", ""),
        end_date=end_date.replace("-", ""),
        adjust="hfq",
    )
    frame = frame.rename(
        columns={"日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low"}
    )
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.set_index("date").sort_index()
