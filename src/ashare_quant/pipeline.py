"""第 24 周配置驱动的离线毕业研究流水线。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .backtest import BacktestConfig, run_backtest
from .config import ResearchConfig
from .data import make_synthetic_market, make_synthetic_security_master, to_wide
from .execution import ExecutionConfig, reconcile_executions, simulate_execution, weights_to_orders
from .factors import (
    accruals,
    amihud_from_prices,
    book_to_price,
    earnings_yield,
    equal_weight_composite,
    factor_correlation,
    forward_returns,
    ic_decay,
    ic_ir,
    low_volatility_factor,
    momentum_factor,
    rank_ic,
    return_on_equity,
    yearly_ic,
)
from .fundamentals import align_fundamentals_asof, make_synthetic_fundamentals
from .metrics import active_risk_attribution, performance_summary, wealth_index
from .ml import WalkForwardConfig, daily_rank_ic, walk_forward_evaluate
from .monitor import MonitorConfig, decision_to_dict, evaluate_stop_rules, population_stability_index
from .paper import PaperBroker, PaperConfig
from .portfolio import portfolio_turnover, score_to_weights
from .risk import (
    factor_risk_decomposition,
    fit_factor_risk_model,
    ledoit_wolf_covariance,
    portfolio_risk_decomposition,
)
from .universe import point_in_time_universe
from .validation import (
    ExperimentLog,
    cost_multiplier_stress,
    market_regime_stress,
    subsample_stress,
    train_validation_test_split,
)


def _cross_sectional_zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean = frame.mean(axis=1)
    std = frame.std(axis=1).replace(0.0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)


def _to_feature_panel(factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
    stacked = {
        name: values.stack(future_stack=True)
        for name, values in factors.items()
    }
    features = pd.concat(stacked, axis=1).sort_index()
    features.index.names = ["date", "symbol"]
    return features


def _monthly_constrained_weights(
    scores: pd.DataFrame,
    industries: pd.DataFrame,
    config: ResearchConfig,
) -> pd.DataFrame:
    rebalance_scores = scores.groupby(scores.index.to_period("M"), group_keys=False).tail(1)
    rows: list[pd.Series] = []
    previous: pd.Series | None = None
    for date, current_scores in rebalance_scores.iterrows():
        valid = current_scores.dropna()
        if len(valid) * config.portfolio.max_weight < 1.0 - 1e-12:
            continue
        current_industries = industries.loc[date].reindex(valid.index)
        benchmark = pd.Series(1.0 / len(valid), index=valid.index)
        kwargs: dict[str, Any] = {}
        if previous is not None:
            kwargs = {
                "previous_weights": previous.reindex(valid.index, fill_value=0.0),
                "max_turnover": config.portfolio.max_turnover,
            }
        weights = score_to_weights(
            valid,
            max_weight=config.portfolio.max_weight,
            industries=current_industries,
            benchmark_weights=benchmark,
            max_industry_deviation=config.portfolio.max_industry_deviation,
            **kwargs,
        )
        weights = weights.reindex(scores.columns, fill_value=0.0)
        weights.name = date
        rows.append(weights)
        previous = weights
    if not rows:
        raise ValueError("没有足够股票形成满足单票上限的组合")
    schedule = pd.DataFrame(rows)
    return schedule.reindex(scores.index).ffill().fillna(0.0)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def run_advanced_pipeline(config: ResearchConfig, output: str | Path) -> dict[str, Any]:
    """运行完整离线研究并写出可审计产物；output 必须是尚不存在的目录。"""
    config.validate()
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=False)

    market = make_synthetic_market(
        n_days=config.data.n_days,
        n_assets=config.data.n_assets,
        seed=config.seed,
        start_date=config.start_date,
    )
    symbols = sorted(market["symbol"].unique())
    security_master = make_synthetic_security_master(
        symbols, pd.Timestamp(config.start_date) - pd.Timedelta(days=730)
    )
    eligible = point_in_time_universe(market, security_master, config.universe)
    prices = to_wide(eligible)
    amounts = to_wide(eligible, "amount")
    industries = eligible.pivot(index="date", columns="symbol", values="industry").sort_index()

    first_quarter = pd.offsets.QuarterEnd().rollforward(pd.Timestamp(config.start_date))
    fundamentals = make_synthetic_fundamentals(
        symbols,
        n_periods=max(8, config.data.n_days // 63),
        seed=config.seed,
        start=str(first_quarter.date()),
    )
    aligned = align_fundamentals_asof(eligible, fundamentals)
    aligned["ep"] = earnings_yield(aligned["net_profit"], aligned["market_cap"])
    aligned["bp"] = book_to_price(aligned["book_equity"], aligned["market_cap"])
    aligned["roe"] = return_on_equity(aligned["net_profit"], aligned["book_equity"])
    aligned["accrual_quality"] = -accruals(
        aligned["net_profit"], aligned["operating_cash_flow"], aligned["total_assets"]
    )

    raw_factors = {
        "momentum": momentum_factor(prices),
        "low_volatility": low_volatility_factor(prices),
        "earnings_yield": to_wide(aligned, "ep"),
        "book_to_price": to_wide(aligned, "bp"),
        "roe": to_wide(aligned, "roe"),
        "accrual_quality": to_wide(aligned, "accrual_quality"),
        "liquidity": -amihud_from_prices(
            prices, amounts, window=config.factors.amihud_window
        ),
    }
    standardized = {name: _cross_sectional_zscore(value) for name, value in raw_factors.items()}
    future = forward_returns(prices, config.validation.label_horizon_dates)
    composite = equal_weight_composite(standardized).reindex_like(prices)

    factor_ics = pd.concat(
        {name: rank_ic(value, future) for name, value in standardized.items()}, axis=1
    )
    factor_summary = pd.DataFrame(
        {
            "mean_rank_ic": factor_ics.mean(),
            "icir": factor_ics.apply(ic_ir),
            "observations": factor_ics.count(),
        }
    )
    factor_summary.to_csv(destination / "factor_summary.csv")
    factor_ics.to_csv(destination / "factor_daily_ic.csv", index_label="date")
    yearly_ic(rank_ic(composite, future)).to_csv(destination / "composite_yearly_ic.csv")
    ic_decay(composite, future, config.factors.decay_lags).to_csv(
        destination / "factor_ic_decay.csv", header=True
    )
    factor_correlation(standardized).to_csv(destination / "factor_correlation.csv")

    target_weights = _monthly_constrained_weights(composite, industries, config)
    backtest = run_backtest(
        prices,
        target_weights,
        suspended=eligible.pivot(index="date", columns="symbol", values="suspended"),
        limit_up=eligible.pivot(index="date", columns="symbol", values="limit_up"),
        limit_down=eligible.pivot(index="date", columns="symbol", values="limit_down"),
        config=BacktestConfig(
            commission=config.backtest.commission,
            stamp_duty=config.backtest.stamp_duty,
            slippage=config.backtest.slippage,
            execution_lag=config.backtest.execution_lag,
        ),
    )
    benchmark = prices.pct_change(fill_method=None).mean(axis=1).fillna(0.0)
    performance = performance_summary(backtest.returns, benchmark, backtest.turnover)
    performance.to_csv(destination / "performance_summary.csv", header=True)
    pd.DataFrame(
        {
            "strategy_return": backtest.returns,
            "benchmark_return": benchmark,
            "strategy_nav": wealth_index(backtest.returns),
            "turnover": backtest.turnover,
            "cost": backtest.costs,
        }
    ).to_csv(destination / "daily_performance.csv", index_label="date")

    asset_returns = prices.pct_change(fill_method=None).dropna().iloc[-252:]
    covariance = ledoit_wolf_covariance(asset_returns, annualization=1.0)
    final_weights = target_weights.iloc[-1].reindex(covariance.index, fill_value=0.0)
    benchmark_weights = pd.Series(1.0 / len(final_weights), index=final_weights.index)
    portfolio_risk_decomposition(final_weights, covariance).to_csv(
        destination / "asset_risk_decomposition.csv"
    )
    active_risk_attribution(
        final_weights, benchmark_weights, covariance, periods=252
    ).to_csv(destination / "active_risk_attribution.csv")

    final_exposures = pd.DataFrame(
        {name: value.iloc[-1] for name, value in standardized.items()}
    ).dropna()
    risk_assets = asset_returns.columns.intersection(final_exposures.index)
    factor_model = fit_factor_risk_model(
        asset_returns[risk_assets], final_exposures.loc[risk_assets]
    )
    factor_risk_decomposition(
        final_weights.reindex(risk_assets), factor_model
    ).to_csv(destination / "factor_risk_decomposition.csv", header=True)

    cost_multiplier_stress(backtest.gross_returns, backtest.costs).to_csv(
        destination / "stress_costs.csv"
    )
    subsample_stress(backtest.returns).to_csv(destination / "stress_subsamples.csv")
    regimes = pd.Series(
        np.where(benchmark.rolling(60, min_periods=20).mean() >= 0, "bull", "bear"),
        index=benchmark.index,
    )
    market_regime_stress(backtest.returns, regimes).to_csv(
        destination / "stress_market_regimes.csv"
    )
    split = train_validation_test_split(
        prices.index,
        purge_dates=config.validation.purge_dates,
        embargo_dates=config.validation.embargo_dates,
    )
    _write_json(
        destination / "validation_protocol.json",
        {name: [str(values.min()), str(values.max()), len(values)] for name, values in split.as_dict().items()},
    )
    experiments = ExperimentLog()
    experiments.record("baseline", returns=backtest.returns)
    experiments.record("double_cost", returns=backtest.gross_returns - 2.0 * backtest.costs)
    experiments.to_frame().to_csv(destination / "experiment_registry.csv", index=False)
    deflated = experiments.deflated_sharpe("baseline", backtest.returns)
    _write_json(destination / "deflated_sharpe.json", asdict(deflated))

    ml_factors = {
        name: values
        for name, values in standardized.items()
        if name in {"momentum", "low_volatility", "earnings_yield", "roe", "liquidity"}
    }
    features = _to_feature_panel(ml_factors)
    feature_dates = features.index.get_level_values("date")
    first_observed = [
        feature_dates[features[column].notna()].min()
        for column in features
        if features[column].notna().any()
    ]
    if len(first_observed) != features.shape[1]:
        raise ValueError("至少一个 ML 特征在整个样本内均无有效值")
    features = features.loc[(slice(max(first_observed), None), slice(None)), :]
    labels = future.stack(future_stack=True).reindex(features.index).rename("future_return")
    ml_result = walk_forward_evaluate(
        features,
        labels,
        WalkForwardConfig(
            min_train_dates=config.validation.min_train_dates,
            train_window_dates=config.validation.train_window_dates,
            label_horizon_dates=config.validation.label_horizon_dates,
            retrain_every=config.validation.retrain_every,
            model=config.validation.model,
            random_state=config.seed,
        ),
    )
    ml_ic = daily_rank_ic(ml_result.predictions, labels)
    ml_ic.to_csv(destination / "ml_daily_rank_ic.csv", header=True)
    ml_result.folds.to_csv(destination / "ml_folds.csv", index=False)
    ml_result.feature_importance.to_csv(destination / "ml_feature_importance.csv", index=False)

    latest_date = prices.index[-1]
    latest_prices = prices.loc[latest_date]
    latest_volumes = to_wide(eligible, "volume").loc[latest_date]
    orders = weights_to_orders(
        final_weights,
        latest_prices,
        None,
        config.execution.initial_cash,
        lot_size=config.execution.lot_size,
    )
    fills = simulate_execution(
        orders,
        latest_prices,
        latest_volumes,
        config=ExecutionConfig(
            lot_size=config.execution.lot_size,
            max_volume_participation=config.execution.max_volume_participation,
            slippage=config.backtest.slippage,
            impact_coefficient=config.execution.impact_coefficient,
        ),
    )
    orders.to_csv(destination / "theoretical_orders.csv", index=False)
    fills.to_csv(destination / "simulated_fills.csv", index=False)
    reconcile_executions(orders, fills).to_csv(
        destination / "execution_reconciliation.csv", index=False
    )

    broker = PaperBroker(
        cash=config.execution.initial_cash,
        config=PaperConfig(
            commission_rate=config.backtest.commission,
            stamp_duty=config.backtest.stamp_duty,
            slippage=config.backtest.slippage,
            lot_size=config.execution.lot_size,
            max_volume_participation=config.execution.max_volume_participation,
            impact_coefficient=config.execution.impact_coefficient,
        ),
    )
    volume_wide = to_wide(eligible, "volume")
    for date in prices.index[-5:]:
        broker.rebalance(
            date,
            prices.loc[date],
            target_weights.loc[date],
            volumes=volume_wide.loc[date],
        )
    broker.save_state(destination / "paper_state")

    reference_feature = standardized["momentum"].iloc[-120:-60].stack().dropna()
    current_feature = standardized["momentum"].iloc[-60:].stack().dropna()
    psi = population_stability_index(reference_feature, current_feature)
    decision = evaluate_stop_rules(
        nav_history=wealth_index(backtest.returns),
        psi_value=psi,
        config=MonitorConfig(
            max_drawdown=config.monitor.max_drawdown,
            max_psi=config.monitor.max_psi,
        ),
    )
    _write_json(destination / "monitor_decision.json", decision_to_dict(decision))

    manifest = {
        "course_week": 24,
        "data": "synthetic_for_process_validation_only",
        "config": asdict(config),
        "date_range": [str(prices.index.min().date()), str(prices.index.max().date())],
        "assets": int(prices.shape[1]),
        "mean_composite_rank_ic": float(rank_ic(composite, future).mean()),
        "mean_ml_rank_ic": float(ml_ic.mean()),
        "strategy_sharpe": float(performance["sharpe"]),
        "final_turnover": float(
            portfolio_turnover(target_weights.iloc[-1], target_weights.iloc[-2])
        ),
        "monitor_should_stop": decision.should_stop,
    }
    _write_json(destination / "run_manifest.json", manifest)
    (destination / "graduation_report.md").write_text(
        "# 进阶课程毕业报告\n\n"
        "> 本报告基于合成数据，只用于验证研究流程，不构成投资建议。\n\n"
        "## 摘要\n\n"
        f"- 策略 Sharpe：{manifest['strategy_sharpe']:.3f}\n"
        f"- 多因子平均 Rank IC：{manifest['mean_composite_rank_ic']:.4f}\n"
        f"- ML 平均 Rank IC：{manifest['mean_ml_rank_ic']:.4f}\n"
        f"- 监控停止：{manifest['monitor_should_stop']}\n\n"
        "其余章节请依据 `docs/graduation_report_template.md` 补充经济逻辑、"
        "PIT 数据审计、稳健性证据、失败实验与实盘边界。\n",
        encoding="utf-8",
    )
    return manifest
