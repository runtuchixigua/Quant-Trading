"""历史时点股票池构建，避免存活者偏差。"""

from __future__ import annotations

import pandas as pd

from .config import UniverseConfig


def point_in_time_universe(
    market: pd.DataFrame,
    securities: pd.DataFrame,
    config: UniverseConfig | None = None,
) -> pd.DataFrame:
    """按每个交易日当时可知的上市状态和交易状态过滤行情。

    ``market`` 至少包含 ``date``、``symbol``；``securities`` 至少包含
    ``symbol``、``list_date``，可含 ``delist_date``。退市日视为不再属于股票池。
    """

    rules = config or UniverseConfig()
    rules.validate()
    required_market = {"date", "symbol"}
    required_securities = {"symbol", "list_date"}
    missing_market = required_market.difference(market.columns)
    missing_securities = required_securities.difference(securities.columns)
    if missing_market or missing_securities:
        raise ValueError(
            f"缺少字段: market={sorted(missing_market)}, "
            f"securities={sorted(missing_securities)}"
        )
    if securities["symbol"].duplicated().any():
        raise ValueError("securities 中 symbol 必须唯一")

    result = market.copy()
    result["date"] = pd.to_datetime(result["date"])
    master = securities.copy()
    master["list_date"] = pd.to_datetime(master["list_date"])
    if "delist_date" not in master:
        master["delist_date"] = pd.NaT
    else:
        master["delist_date"] = pd.to_datetime(master["delist_date"])
    result = result.merge(
        master[["symbol", "list_date", "delist_date"]],
        on="symbol",
        how="left",
        validate="many_to_one",
    )
    if result["list_date"].isna().any():
        unknown = sorted(result.loc[result["list_date"].isna(), "symbol"].unique())
        raise ValueError(f"股票主数据缺少 symbol: {unknown}")

    eligible_date = result["date"] >= (
        result["list_date"] + pd.to_timedelta(rules.min_listing_days, unit="D")
    )
    before_delist = result["delist_date"].isna() | (result["date"] < result["delist_date"])
    eligible = eligible_date & before_delist
    if rules.exclude_st and "is_st" in result:
        eligible &= ~result["is_st"].fillna(False).astype(bool)
    if rules.exclude_suspended and "suspended" in result:
        eligible &= ~result["suspended"].fillna(False).astype(bool)
    return (
        result.loc[eligible, market.columns]
        .sort_values(["date", "symbol"])
        .reset_index(drop=True)
    )


def universe_mask(
    market: pd.DataFrame,
    securities: pd.DataFrame,
    config: UniverseConfig | None = None,
) -> pd.Series:
    """返回与原行情行索引一致的历史时点入池布尔掩码。"""

    tagged = market.copy()
    marker = "__pit_original_index__"
    tagged[marker] = range(len(tagged))
    selected = point_in_time_universe(tagged, securities, config)
    selected_positions = selected[marker].to_numpy()
    mask = pd.Series(False, index=market.index, name="in_universe")
    mask.iloc[selected_positions] = True
    return mask
