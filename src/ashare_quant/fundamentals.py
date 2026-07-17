"""财务公告日 PIT 对齐与离线合成财务数据。"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


FUNDAMENTAL_KEYS = {"symbol", "report_period", "announcement_date"}


def validate_fundamentals(frame: pd.DataFrame) -> pd.DataFrame:
    """校验并规范财务长表，不允许重复公告记录。"""

    missing = FUNDAMENTAL_KEYS.difference(frame.columns)
    if missing:
        raise ValueError(f"财务数据缺少字段: {sorted(missing)}")
    result = frame.copy()
    result["report_period"] = pd.to_datetime(result["report_period"])
    result["announcement_date"] = pd.to_datetime(result["announcement_date"])
    if result[list(FUNDAMENTAL_KEYS)].isna().any().any():
        raise ValueError("财务主键字段不能为空")
    if (result["announcement_date"] < result["report_period"]).any():
        raise ValueError("announcement_date 不能早于 report_period")
    if result.duplicated(["symbol", "report_period", "announcement_date"]).any():
        raise ValueError("财务数据存在重复公告记录")
    return result.sort_values(["symbol", "announcement_date", "report_period"]).reset_index(
        drop=True
    )


def align_fundamentals_asof(
    observations: pd.DataFrame,
    fundamentals: pd.DataFrame,
    date_column: str = "date",
) -> pd.DataFrame:
    """把每个股票在信号日已公告的最新一期财务数据对齐到观测行。

    对齐严格使用公告日，绝不会按报告期末提前暴露未来公告。返回顺序和索引与
    ``observations`` 一致；尚无可见公告时财务字段为空。
    """

    required = {date_column, "symbol"}
    missing = required.difference(observations.columns)
    if missing:
        raise ValueError(f"观测数据缺少字段: {sorted(missing)}")
    reports = validate_fundamentals(fundamentals)
    left = observations.copy()
    left[date_column] = pd.to_datetime(left[date_column])
    left["__pit_order__"] = np.arange(len(left))

    pieces: list[pd.DataFrame] = []
    report_columns = [column for column in reports.columns if column != "symbol"]
    for symbol, group in left.groupby("symbol", sort=False, dropna=False):
        group_reports = reports.loc[reports["symbol"] == symbol, report_columns]
        ordered = group.sort_values(date_column)
        if group_reports.empty:
            merged = ordered.copy()
            for column in report_columns:
                merged[column] = pd.NaT if column.endswith("date") or column == "report_period" else np.nan
        else:
            merged = pd.merge_asof(
                ordered,
                group_reports.sort_values("announcement_date"),
                left_on=date_column,
                right_on="announcement_date",
                direction="backward",
                allow_exact_matches=True,
            )
        pieces.append(merged)
    result = pd.concat(pieces).sort_values("__pit_order__").drop(columns="__pit_order__")
    result.index = observations.index
    return result


def fundamentals_asof(
    fundamentals: pd.DataFrame,
    as_of_date: str | pd.Timestamp,
    symbols: Sequence[str] | None = None,
) -> pd.DataFrame:
    """返回指定历史时点每只股票最新可见的财务记录。"""

    reports = validate_fundamentals(fundamentals)
    cutoff = pd.Timestamp(as_of_date)
    visible = reports.loc[reports["announcement_date"] <= cutoff]
    if symbols is not None:
        visible = visible.loc[visible["symbol"].isin(symbols)]
    return (
        visible.sort_values(["symbol", "announcement_date", "report_period"])
        .groupby("symbol", as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )


def make_synthetic_fundamentals(
    symbols: Sequence[str],
    n_periods: int = 16,
    seed: int = 7,
    start: str = "2020-03-31",
) -> pd.DataFrame:
    """生成可重复的季度财务公告长表，仅用于离线流程测试。"""

    if n_periods < 1:
        raise ValueError("n_periods 必须为正数")
    rng = np.random.default_rng(seed)
    periods = pd.date_range(start, periods=n_periods, freq="QE")
    rows: list[dict[str, object]] = []
    for symbol in symbols:
        assets = rng.uniform(5e9, 5e10)
        equity_ratio = rng.uniform(0.35, 0.75)
        for period in periods:
            growth = rng.normal(1.025, 0.025)
            assets = max(assets * growth, 1e8)
            equity = assets * np.clip(equity_ratio + rng.normal(0, 0.015), 0.2, 0.9)
            revenue = assets * rng.uniform(0.08, 0.22)
            net_profit = revenue * rng.uniform(0.04, 0.18)
            operating_cash_flow = net_profit * rng.uniform(0.65, 1.35)
            lag = int(rng.integers(25, 61))
            rows.append(
                {
                    "symbol": symbol,
                    "report_period": period,
                    "announcement_date": period + pd.Timedelta(days=lag),
                    "revenue": revenue,
                    "net_profit": net_profit,
                    "book_equity": equity,
                    "total_assets": assets,
                    "operating_cash_flow": operating_cash_flow,
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["announcement_date", "symbol", "report_period"]
    ).reset_index(drop=True)
