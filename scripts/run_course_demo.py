"""离线跑通数据、因子、回测、机器学习与模拟盘完整闭环。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ashare_quant.backtest import BacktestConfig, run_backtest
from ashare_quant.data import make_synthetic_market, to_wide
from ashare_quant.factors import (
    forward_returns,
    low_volatility_factor,
    momentum_factor,
    quantile_returns,
    rank_ic,
    top_quantile_weights,
)
from ashare_quant.metrics import drawdown, performance_summary, wealth_index
from ashare_quant.ml import WalkForwardConfig, daily_rank_ic, walk_forward_predict
from ashare_quant.paper import PaperBroker


def cross_sectional_zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean = frame.mean(axis=1)
    std = frame.std(axis=1).replace(0.0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)


def build_ml_dataset(
    momentum: pd.DataFrame,
    low_volatility: pd.DataFrame,
    market_cap: pd.DataFrame,
    future: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    features = pd.concat(
        {
            "momentum": momentum.stack(future_stack=True),
            "low_volatility": low_volatility.stack(future_stack=True),
            "log_market_cap": np.log(market_cap).stack(future_stack=True),
        },
        axis=1,
    )
    features.index.names = ["date", "symbol"]
    labels = future.stack(future_stack=True).reindex(features.index).rename("future_return")
    return features, labels


def save_report(
    output: Path,
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    turnover: pd.Series,
) -> None:
    summary = performance_summary(strategy_returns, benchmark_returns, turnover)
    summary.to_csv(output / "performance_summary.csv", header=True)
    report = pd.DataFrame(
        {
            "strategy_wealth": wealth_index(strategy_returns),
            "benchmark_wealth": wealth_index(benchmark_returns),
            "drawdown": drawdown(strategy_returns),
        }
    )
    report.to_csv(output / "daily_report.csv", index_label="date")
    axes = report[["strategy_wealth", "benchmark_wealth"]].plot(figsize=(11, 7))
    axes.set_title("Synthetic data: strategy vs benchmark")
    axes.set_ylabel("wealth")
    drawdown_axis = axes.twinx()
    report["drawdown"].plot(ax=drawdown_axis, color="grey", alpha=0.25)
    drawdown_axis.set_ylabel("drawdown")
    axes.figure.tight_layout()
    axes.figure.savefig(output / "performance.png", dpi=150)
    plt.close(axes.figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/demo"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    panel = make_synthetic_market()
    prices = to_wide(panel)
    market_cap = to_wide(panel, "market_cap")
    future = forward_returns(prices, horizon=20)
    momentum = momentum_factor(prices)
    low_volatility = low_volatility_factor(prices)
    score = cross_sectional_zscore(momentum) + cross_sectional_zscore(low_volatility)

    ic = rank_ic(score, future)
    ic.to_csv(args.output / "factor_rank_ic.csv", header=True)
    quantile_returns(score, future).to_csv(args.output / "factor_quantile_returns.csv")

    target_weights = top_quantile_weights(score, quantile=0.2)
    result = run_backtest(prices, target_weights, config=BacktestConfig())
    benchmark = prices.pct_change(fill_method=None).mean(axis=1).fillna(0.0)
    save_report(args.output, result.returns, benchmark, result.turnover)

    features, labels = build_ml_dataset(momentum, low_volatility, market_cap, future)
    predictions = walk_forward_predict(
        features,
        labels,
        WalkForwardConfig(
            min_train_dates=252,
            train_window_dates=504,
            label_horizon_dates=20,
            retrain_every=20,
        ),
    )
    ml_ic = daily_rank_ic(predictions, labels)
    ml_ic.to_csv(args.output / "ml_rank_ic.csv", header=True)
    predictions.rename("prediction").dropna().to_csv(args.output / "ml_predictions.csv")

    latest_date = target_weights.dropna(how="all").index[-1]
    broker = PaperBroker()
    broker.rebalance(latest_date, prices.loc[latest_date], target_weights.loc[latest_date])
    broker.save_state(args.output)

    manifest = {
        "data": "synthetic_for_code_validation_only",
        "start": str(prices.index.min().date()),
        "end": str(prices.index.max().date()),
        "assets": prices.shape[1],
        "factor_mean_rank_ic": float(ic.mean()),
        "ml_mean_rank_ic": float(ml_ic.mean()),
        "execution_lag": 1,
    }
    (args.output / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
