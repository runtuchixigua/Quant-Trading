"""可重复调用的每日模拟盘入口；只读本地文件，不连接真实券商。"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from ashare_quant.execution import reconcile_executions, weights_to_orders
from ashare_quant.monitor import (
    MonitorConfig,
    evaluate_stop_rules,
    log_event,
    validate_market_data,
)
from ashare_quant.paper import PaperBroker


def run_paper_day(
    market: pd.DataFrame,
    target_weights: pd.Series,
    state_directory: str | Path,
    *,
    initial_cash: float = 1_000_000.0,
    as_of: pd.Timestamp | str | None = None,
    monitor_config: MonitorConfig | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, object]:
    """加载昨日状态，运行一个交易日，监控后原子化地延续本地状态。"""
    logger = logger or logging.getLogger("ashare_quant.paper")
    config = monitor_config or MonitorConfig()
    validate_market_data(
        market, as_of=as_of, max_age_days=config.max_data_age_days
    )
    frame = market.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    latest_date = frame["date"].max().normalize()
    daily = frame.loc[frame["date"].dt.normalize() == latest_date].set_index("symbol")
    state = Path(state_directory)
    broker = (
        PaperBroker.load_state(state)
        if (state / "paper_account.json").exists()
        else PaperBroker(cash=initial_cash)
    )
    held_symbols = (
        broker.holdings.index[broker.holdings["shares"].astype(float) != 0]
        if not broker.holdings.empty
        else pd.Index([])
    )
    missing_held = held_symbols.difference(daily.index)
    if not missing_held.empty:
        raise ValueError(f"当日行情缺少持仓代码: {missing_held.tolist()}")
    prices = daily["close"].astype(float)
    volumes = daily["volume"].astype(float)
    current = (
        broker.holdings["shares"]
        if not broker.holdings.empty
        else pd.Series(dtype="int64")
    )
    theoretical = weights_to_orders(
        target_weights,
        prices,
        current,
        broker.net_asset_value(prices),
        lot_size=broker.config.lot_size,
    )
    fills = broker.rebalance(
        latest_date,
        prices,
        target_weights,
        volumes=volumes,
        suspended=_optional_bool_column(daily, "suspended"),
        limit_up=_optional_bool_column(daily, "limit_up"),
        limit_down=_optional_bool_column(daily, "limit_down"),
    )
    simulated = fills.rename(columns={"shares": "filled_shares"})
    reconciliation = reconcile_executions(theoretical, simulated)

    nav = broker.net_asset_value(prices)
    nav_path = state / "paper_nav.csv"
    if nav_path.exists():
        nav_frame = pd.read_csv(nav_path, parse_dates=["date"])
    else:
        nav_frame = pd.DataFrame(columns=["date", "nav"])
    nav_frame = pd.concat(
        [nav_frame, pd.DataFrame([{"date": latest_date, "nav": nav}])],
        ignore_index=True,
    )
    nav_frame = nav_frame.drop_duplicates("date", keep="last").sort_values("date")
    decision = evaluate_stop_rules(nav_history=nav_frame["nav"], config=config)
    if decision.should_stop:
        log_event(
            logger,
            "paper_stopped",
            date=latest_date,
            reasons=decision.reasons,
            metrics=decision.metrics,
        )
        raise RuntimeError(f"模拟盘触发停止规则: {', '.join(decision.reasons)}")

    state.mkdir(parents=True, exist_ok=True)
    broker.save_state(state)
    nav_frame.to_csv(nav_path, index=False)
    reconciliation.to_csv(state / "paper_reconciliation.csv", index=False)
    log_event(
        logger,
        "paper_day_completed",
        date=latest_date,
        nav=nav,
        cash=broker.cash,
        orders=len(theoretical),
        fills=int((simulated.get("filled_shares", pd.Series(dtype=int)) > 0).sum()),
    )
    return {
        "date": latest_date,
        "nav": nav,
        "cash": broker.cash,
        "trades": fills,
        "reconciliation": reconciliation,
    }


def _optional_bool_column(frame: pd.DataFrame, column: str) -> pd.Series | None:
    return frame[column].astype(bool) if column in frame else None


def _load_weights(path: str | Path) -> pd.Series:
    frame = pd.read_csv(path)
    if not {"symbol", "weight"}.issubset(frame):
        raise ValueError("权重文件必须包含 symbol 和 weight")
    return frame.set_index("symbol")["weight"].astype(float)


def main() -> None:
    parser = argparse.ArgumentParser(description="本地 A 股连续模拟盘（日频）")
    parser.add_argument("--market", required=True, help="长表行情 CSV")
    parser.add_argument("--weights", required=True, help="symbol,weight 权重 CSV")
    parser.add_argument("--state-dir", required=True, help="连续状态输出目录")
    parser.add_argument("--initial-cash", type=float, default=1_000_000.0)
    parser.add_argument("--as-of", help="数据时效检查日期，默认使用当前日期")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    market = pd.read_csv(args.market)
    result = run_paper_day(
        market,
        _load_weights(args.weights),
        args.state_dir,
        initial_cash=args.initial_cash,
        as_of=args.as_of or pd.Timestamp.now(),
    )
    print(json.dumps({"date": str(result["date"]), "nav": result["nav"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
