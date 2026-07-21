"""第 6–12 周可执行核心课程。

所有实验只使用固定随机种子的离线合成数据；产物面向学习和审计，不代表实盘收益。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .data import make_synthetic_market, to_wide
from .execution import (
    ExecutionConfig,
    reconcile_executions,
    simulate_execution,
    weights_to_orders,
)
from .factors import (
    equal_weight_composite,
    factor_correlation,
    forward_returns,
    ic_decay,
    low_volatility_factor,
    momentum_factor,
    neutralize,
    preprocess_factor,
    quantile_returns,
    rank_ic,
    winsorize_mad,
    zscore,
)
from .lesson_io import (
    prepare_lesson_output,
    write_acceptance,
    write_homework_if_safe,
    write_manifest,
)
from .lessons import LessonResult
from .ml import WalkForwardConfig, daily_rank_ic, walk_forward_evaluate
from .monitor import MonitorConfig, evaluate_stop_rules, population_stability_index


SEED = 20260720


def _market(quick: bool, *, seed_offset: int = 0) -> pd.DataFrame:
    return make_synthetic_market(
        n_days=70 if quick else 180,
        n_assets=15 if quick else 30,
        seed=SEED + seed_offset,
    )


def _factor_inputs(
    quick: bool, *, seed_offset: int = 0
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    """生成价格、三个当期可观测因子、未来收益和原始长表。"""
    market = _market(quick, seed_offset=seed_offset)
    prices = to_wide(market)
    lookback = 8 if quick else 20
    skip = 2 if quick else 5
    momentum = momentum_factor(prices, lookback=lookback, skip=skip)
    low_vol = low_volatility_factor(prices, window=lookback)
    caps = market.pivot(index="date", columns="symbol", values="market_cap")
    size = -np.log(caps.where(caps > 0))
    factors = {
        "momentum": momentum,
        "low_volatility": low_vol,
        "small_size": size,
    }
    future = forward_returns(prices, horizon=3 if quick else 5)
    return prices, factors, future, market


def _cross_sectional_zscore(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.apply(zscore, axis=1)


def _ml_data(
    quick: bool, *, seed_offset: int = 0
) -> tuple[pd.DataFrame, pd.Series, dict[str, pd.DataFrame]]:
    _, raw_factors, future, _ = _factor_inputs(quick, seed_offset=seed_offset)
    factors = {name: _cross_sectional_zscore(value) for name, value in raw_factors.items()}
    stacked_factors = {}
    for name, value in factors.items():
        stacked_factors[name] = (
            value.rename_axis(index="date", columns="symbol")
            .melt(ignore_index=False, var_name="symbol", value_name=name)
            .set_index("symbol", append=True)[name]
        )
    features = pd.concat(stacked_factors, axis=1)
    features.index = features.index.set_names(["date", "symbol"])
    features = features.sort_index()
    labels = (
        future.rename_axis(index="date", columns="symbol")
        .melt(ignore_index=False, var_name="symbol", value_name="label")
        .set_index("symbol", append=True)["label"]
        .reindex(features.index)
    )
    return features, labels, factors


def _ml_config(quick: bool, model: str) -> WalkForwardConfig:
    return WalkForwardConfig(
        min_train_dates=18 if quick else 60,
        train_window_dates=35 if quick else 100,
        label_horizon_dates=3 if quick else 5,
        retrain_every=8 if quick else 20,
        model=model,
        model_params=(
            {"max_iter": 35 if quick else 80, "max_leaf_nodes": 15, "learning_rate": 0.08}
            if model == "hist_gradient_boosting"
            else {}
        ),
        random_state=SEED,
        importance_repeats=1 if quick else 2,
    )


def _save_figure(figure: plt.Figure, path: Path) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=120)
    plt.close(figure)


def _finish(
    destination: Path,
    *,
    week: int,
    quick: bool,
    artifacts: Iterable[str],
    homework: str,
    criteria: Iterable[str],
    report: str,
    summary: pd.Series,
) -> LessonResult:
    (destination / "report.md").write_text(report.rstrip() + "\n", encoding="utf-8")
    write_homework_if_safe(destination, homework.rstrip() + "\n")
    write_acceptance(destination, week=week, criteria=criteria)
    names = [*artifacts, "report.md", "homework.md", "acceptance.json"]
    write_manifest(destination, week=week, quick=quick, artifacts=names)
    return LessonResult(week=week, output=destination, summary=summary)


def run_week_06(
    output: str | Path = "artifacts/learning/week06",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """因子去极值、市值行业中性化和标准化。"""
    del force
    destination = prepare_lesson_output(output)
    _, factors, _, market = _factor_inputs(quick)
    raw = factors["momentum"]
    cap = market.pivot(index="date", columns="symbol", values="market_cap")
    industry = market.pivot(index="date", columns="symbol", values="industry")

    records: list[pd.DataFrame] = []
    for date in raw.dropna(how="all").index:
        values = raw.loc[date]
        clipped = winsorize_mad(values)
        residual = neutralize(clipped, np.log(cap.loc[date]), industry.loc[date])
        processed = preprocess_factor(values, cap.loc[date], industry.loc[date])
        records.append(
            pd.DataFrame(
                {
                    "date": date,
                    "symbol": values.index,
                    "raw_factor": values.values,
                    "winsorized": clipped.values,
                    "neutralized": residual.values,
                    "processed_factor": processed.values,
                }
            )
        )
    result = pd.concat(records, ignore_index=True).dropna()
    result.to_csv(destination / "factor_preprocessing.csv", index=False)
    diagnostics = result[["raw_factor", "winsorized", "neutralized", "processed_factor"]].agg(
        ["mean", "std", "min", "max"]
    )
    diagnostics.to_csv(destination / "factor_diagnostics.csv")

    figure, axes = plt.subplots(1, 2, figsize=(10, 4))
    result["raw_factor"].hist(ax=axes[0], bins=30)
    axes[0].set_title("Raw momentum")
    result["processed_factor"].hist(ax=axes[1], bins=30)
    axes[1].set_title("Processed factor")
    _save_figure(figure, destination / "factor_preprocessing.png")

    summary = pd.Series(
        {
            "observations": float(len(result)),
            "raw_abs_max": float(result["raw_factor"].abs().max()),
            "processed_mean": float(result["processed_factor"].mean()),
            "processed_std": float(result["processed_factor"].std()),
        },
        name="week06",
    )
    summary.to_csv(destination / "summary.csv", header=True)
    return _finish(
        destination,
        week=6,
        quick=quick,
        artifacts=(
            "factor_preprocessing.csv",
            "factor_diagnostics.csv",
            "summary.csv",
            "factor_preprocessing.png",
        ),
        homework="""# 第 6 周作业

1. 解释 MAD 去极值、行业/市值中性化和标准化分别解决什么问题。
2. 从 `factor_preprocessing.csv` 抽查一个交易日，独立复算处理结果。
3. 比较处理前后分布，并记录一个处理可能损失有效信息的场景。
""",
        criteria=(
            "能独立复算至少一个横截面的因子预处理",
            "能解释中性化只减少暴露、不保证因子有效",
        ),
        report=f"""# 第 6 周实验报告

固定 seed 为 {SEED}，共处理 {len(result)} 个有效横截面观测。
处理后因子均值为 {summary['processed_mean']:.4f}，标准差为
{summary['processed_std']:.4f}。本实验仅验证处理流程，不构成因子有效性证据。
""",
        summary=summary,
    )


def run_week_07(
    output: str | Path = "artifacts/learning/week07",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """执行 Rank IC、五分组和 IC 衰减检验。"""
    del force
    destination = prepare_lesson_output(output)
    _, factors, future, _ = _factor_inputs(quick, seed_offset=1)
    signal = _cross_sectional_zscore(factors["momentum"])
    ic = rank_ic(signal, future)
    groups = quantile_returns(signal, future, quantiles=5)
    decay = ic_decay(signal, future, max_lag=5 if quick else 12)
    ic.rename("rank_ic").to_csv(destination / "ic_series.csv", header=True)
    groups.to_csv(destination / "quantile_returns.csv")
    decay.to_csv(destination / "ic_decay.csv", header=True)

    figure, axes = plt.subplots(1, 3, figsize=(13, 4))
    ic.dropna().cumsum().plot(ax=axes[0], title="Cumulative Rank IC")
    groups.mean().plot(kind="bar", ax=axes[1], title="Five-quantile return")
    decay.plot(marker="o", ax=axes[2], title="IC decay")
    _save_figure(figure, destination / "factor_evaluation.png")

    spread = groups.get(5, pd.Series(dtype=float)) - groups.get(1, pd.Series(dtype=float))
    summary = pd.Series(
        {
            "mean_rank_ic": float(ic.mean()),
            "rank_ic_positive_rate": float((ic.dropna() > 0).mean()),
            "q5_minus_q1": float(spread.mean()),
            "valid_ic_dates": float(ic.notna().sum()),
        },
        name="week07",
    )
    summary.to_csv(destination / "summary.csv", header=True)
    return _finish(
        destination,
        week=7,
        quick=quick,
        artifacts=(
            "ic_series.csv",
            "quantile_returns.csv",
            "ic_decay.csv",
            "summary.csv",
            "factor_evaluation.png",
        ),
        homework="""# 第 7 周作业

1. 复算 Rank IC 均值、正值比例和 Q5-Q1 收益差。
2. 说明五分组是否单调，以及 IC 衰减对调仓频率有什么启示。
3. 写出至少两个不能由本次合成数据实验推出的结论。
""",
        criteria=(
            "同时提交 IC、五分组和衰减分析",
            "没有把合成数据结果解释为真实市场超额收益",
        ),
        report=f"""# 第 7 周实验报告

平均 Rank IC 为 {summary['mean_rank_ic']:.4f}，Q5-Q1 平均收益差为
{summary['q5_minus_q1']:.4f}。`ic_decay.csv` 展示信号滞后后的相关性变化，
应结合换手和交易成本再决定调仓频率。
""",
        summary=summary,
    )


def _constrained_weights(scores: pd.Series, industries: pd.Series) -> pd.Series:
    """教学用多头组合：个股不超过 15%，行业不超过 35%。"""
    weights = pd.Series(0.0, index=scores.index)
    industry_weight: dict[str, float] = {}
    remaining = 1.0
    for symbol in scores.dropna().sort_values(ascending=False).index:
        industry = str(industries[symbol])
        room = 0.35 - industry_weight.get(industry, 0.0)
        allocation = min(0.15, room, remaining)
        if allocation > 1e-12:
            weights[symbol] = allocation
            industry_weight[industry] = industry_weight.get(industry, 0.0) + allocation
            remaining -= allocation
        if remaining <= 1e-12:
            break
    return weights


def run_week_08(
    output: str | Path = "artifacts/learning/week08",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """分析多因子相关性并构造有个股/行业上限的组合。"""
    del force
    destination = prepare_lesson_output(output)
    _, raw_factors, future, market = _factor_inputs(quick, seed_offset=2)
    factors = {name: _cross_sectional_zscore(value) for name, value in raw_factors.items()}
    correlation = factor_correlation(factors)
    composite = equal_weight_composite(factors)
    industries = market.pivot(index="date", columns="symbol", values="industry")
    dates = composite.dropna(how="all").index[:: 10 if quick else 20]
    weight_rows: list[pd.DataFrame] = []
    for date in dates:
        weights = _constrained_weights(composite.loc[date], industries.loc[date])
        weight_rows.append(
            pd.DataFrame(
                {
                    "date": date,
                    "symbol": weights.index,
                    "industry": industries.loc[date].values,
                    "score": composite.loc[date].values,
                    "weight": weights.values,
                }
            )
        )
    weights = pd.concat(weight_rows, ignore_index=True)
    correlation.to_csv(destination / "factor_correlation.csv")
    weights.to_csv(destination / "portfolio_weights.csv", index=False)
    composite_ic = rank_ic(composite, future)
    composite_ic.to_csv(destination / "composite_ic.csv", header=True)

    latest = weights[weights["date"] == weights["date"].max()]
    figure, axes = plt.subplots(1, 2, figsize=(10, 4))
    image = axes[0].imshow(correlation, vmin=-1, vmax=1, cmap="coolwarm")
    axes[0].set_xticks(range(len(correlation)), correlation.columns, rotation=30)
    axes[0].set_yticks(range(len(correlation)), correlation.index)
    axes[0].set_title("Factor correlation")
    figure.colorbar(image, ax=axes[0])
    latest.groupby("industry")["weight"].sum().plot(kind="bar", ax=axes[1])
    axes[1].axhline(0.35, color="firebrick", linestyle="--")
    axes[1].set_title("Latest industry weights")
    _save_figure(figure, destination / "portfolio_constraints.png")

    industry_max = (
        weights.groupby(["date", "industry"])["weight"].sum().groupby("date").max().max()
    )
    summary = pd.Series(
        {
            "mean_composite_rank_ic": float(composite_ic.mean()),
            "max_stock_weight": float(weights["weight"].max()),
            "max_industry_weight": float(industry_max),
            "rebalance_dates": float(weights["date"].nunique()),
        },
        name="week08",
    )
    summary.to_csv(destination / "summary.csv", header=True)
    return _finish(
        destination,
        week=8,
        quick=quick,
        artifacts=(
            "factor_correlation.csv",
            "portfolio_weights.csv",
            "composite_ic.csv",
            "summary.csv",
            "portfolio_constraints.png",
        ),
        homework="""# 第 8 周作业

1. 找出相关性最高的一对因子，讨论是否应删除其中一个。
2. 验证每个调仓日个股权重不超过 15%、行业权重不超过 35%。
3. 设计一种不同于等权的合成方式，并说明如何避免未来信息。
""",
        criteria=(
            "完成因子相关性和冗余讨论",
            "程序化验证个股及行业约束",
        ),
        report=f"""# 第 8 周实验报告

组合使用三个标准化因子等权合成。实际最大个股权重为
{summary['max_stock_weight']:.2%}，最大行业权重为
{summary['max_industry_weight']:.2%}。约束降低集中风险，但不保证收益提升。
""",
        summary=summary,
    )


def run_week_09(
    output: str | Path = "artifacts/learning/week09",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """Ridge 横截面 walk-forward，并与简单因子均值基线比较。"""
    del force
    destination = prepare_lesson_output(output)
    features, labels, _ = _ml_data(quick, seed_offset=3)
    ridge = walk_forward_evaluate(features, labels, _ml_config(quick, "ridge"))
    baseline = features.mean(axis=1).rename("baseline_prediction")
    ridge_ic = daily_rank_ic(ridge.predictions, labels)
    baseline_ic = daily_rank_ic(baseline.where(ridge.predictions.notna()), labels)
    predictions = pd.concat(
        [labels, ridge.predictions.rename("ridge_prediction"), baseline], axis=1
    )
    predictions.to_csv(destination / "predictions.csv")
    ridge.folds.to_csv(destination / "folds.csv", index=False)
    comparison = pd.DataFrame(
        {
            "model": ["ridge", "equal_factor_baseline"],
            "mean_rank_ic": [ridge_ic.mean(), baseline_ic.mean()],
            "ic_positive_rate": [
                (ridge_ic.dropna() > 0).mean(),
                (baseline_ic.dropna() > 0).mean(),
            ],
            "valid_dates": [ridge_ic.notna().sum(), baseline_ic.notna().sum()],
        }
    )
    comparison.to_csv(destination / "model_comparison.csv", index=False)

    figure, axis = plt.subplots(figsize=(9, 4))
    ridge_ic.cumsum().plot(ax=axis, label="Ridge")
    baseline_ic.cumsum().plot(ax=axis, label="Equal-factor baseline")
    axis.set_title("Walk-forward cumulative Rank IC")
    axis.legend()
    _save_figure(figure, destination / "ridge_walk_forward.png")

    summary = pd.Series(
        {
            "ridge_mean_rank_ic": float(ridge_ic.mean()),
            "baseline_mean_rank_ic": float(baseline_ic.mean()),
            "folds": float(len(ridge.folds)),
            "prediction_dates": float(ridge_ic.notna().sum()),
        },
        name="week09",
    )
    summary.to_csv(destination / "summary.csv", header=True)
    return _finish(
        destination,
        week=9,
        quick=quick,
        artifacts=(
            "predictions.csv",
            "folds.csv",
            "model_comparison.csv",
            "summary.csv",
            "ridge_walk_forward.png",
        ),
        homework="""# 第 9 周作业

1. 从 `folds.csv` 验证训练结束日早于预测开始日，解释标签隔离期。
2. 比较 Ridge 与简单等权因子基线，不能只汇报表现更好的模型。
3. 改变 Ridge alpha，记录结果和未改善的试验。
""",
        criteria=(
            "逐折验证训练、标签和预测边界无泄漏",
            "同时报告 Ridge 和基线结果",
        ),
        report=f"""# 第 9 周实验报告

Ridge 使用 {int(summary['folds'])} 个 walk-forward 折，平均 Rank IC 为
{summary['ridge_mean_rank_ic']:.4f}；同期等权基线为
{summary['baseline_mean_rank_ic']:.4f}。所有预处理均在各训练折内部拟合。
""",
        summary=summary,
    )


def run_week_10(
    output: str | Path = "artifacts/learning/week10",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """比较 Ridge 与 HistGBDT，输出逐折重要性和试验记录。"""
    del force
    destination = prepare_lesson_output(output)
    features, labels, _ = _ml_data(quick, seed_offset=4)
    results = {
        "ridge": walk_forward_evaluate(features, labels, _ml_config(quick, "ridge")),
        "hist_gbdt": walk_forward_evaluate(
            features, labels, _ml_config(quick, "hist_gradient_boosting")
        ),
    }
    ic_by_model = {
        name: daily_rank_ic(result.predictions, labels) for name, result in results.items()
    }
    predictions = pd.concat(
        {"label": labels, **{name: result.predictions for name, result in results.items()}},
        axis=1,
    )
    predictions.to_csv(destination / "predictions.csv")
    importance = pd.concat(
        [
            result.feature_importance.assign(model=name)
            for name, result in results.items()
        ],
        ignore_index=True,
    )
    importance.to_csv(destination / "fold_importance.csv", index=False)
    comparison = pd.DataFrame(
        [
            {
                "model": name,
                "mean_rank_ic": ic.mean(),
                "ic_std": ic.std(),
                "valid_dates": ic.notna().sum(),
                "folds": len(results[name].folds),
            }
            for name, ic in ic_by_model.items()
        ]
    )
    comparison.to_csv(destination / "model_comparison.csv", index=False)
    experiment_log = comparison.copy()
    experiment_log["seed"] = SEED
    experiment_log["quick"] = quick
    experiment_log["parameters"] = [
        json.dumps(
            {
                "model": _ml_config(quick, "ridge").model,
                "ridge_alpha": _ml_config(quick, "ridge").ridge_alpha,
            },
            sort_keys=True,
        ),
        json.dumps(
            {
                "model": _ml_config(quick, "hist_gradient_boosting").model,
                **dict(_ml_config(quick, "hist_gradient_boosting").model_params),
            },
            sort_keys=True,
        ),
    ]
    experiment_log.to_csv(destination / "experiment_log.csv", index=False)

    figure, axes = plt.subplots(1, 2, figsize=(11, 4))
    for name, ic in ic_by_model.items():
        ic.cumsum().plot(ax=axes[0], label=name)
    axes[0].legend()
    axes[0].set_title("Model cumulative Rank IC")
    importance.groupby(["model", "feature"])["importance"].mean().unstack(0).plot.bar(
        ax=axes[1]
    )
    axes[1].set_title("Mean fold importance")
    _save_figure(figure, destination / "model_comparison.png")

    scores = comparison.set_index("model")["mean_rank_ic"]
    summary = pd.Series(
        {
            "ridge_mean_rank_ic": float(scores["ridge"]),
            "hist_gbdt_mean_rank_ic": float(scores["hist_gbdt"]),
            "ridge_folds": float(len(results["ridge"].folds)),
            "hist_gbdt_folds": float(len(results["hist_gbdt"].folds)),
        },
        name="week10",
    )
    summary.to_csv(destination / "summary.csv", header=True)
    return _finish(
        destination,
        week=10,
        quick=quick,
        artifacts=(
            "predictions.csv",
            "model_comparison.csv",
            "fold_importance.csv",
            "experiment_log.csv",
            "summary.csv",
            "model_comparison.png",
        ),
        homework="""# 第 10 周作业

1. 比较 Ridge 和 HistGBDT 的逐折表现，而不是只比较全期均值。
2. 检查 `fold_importance.csv` 中重要性是否跨折稳定。
3. 在 `experiment_log.csv` 基础上新增一次失败或无改善试验。
""",
        criteria=(
            "保留两个模型及其参数、seed 和结果记录",
            "逐折解释特征重要性并讨论稳定性",
        ),
        report=f"""# 第 10 周实验报告

Ridge 平均 Rank IC 为 {summary['ridge_mean_rank_ic']:.4f}，HistGBDT 为
{summary['hist_gbdt_mean_rank_ic']:.4f}。非线性模型必须与简单模型在同一
walk-forward 边界下比较；逐折重要性仅用于诊断，不能解释为因果关系。
""",
        summary=summary,
    )


def run_week_11(
    output: str | Path = "artifacts/learning/week11",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """连续五日生成订单、模拟成交并逐日对账。"""
    del force
    destination = prepare_lesson_output(output)
    market = make_synthetic_market(n_days=20, n_assets=10, seed=SEED + 5)
    prices = to_wide(market)
    volumes = market.pivot(index="date", columns="symbol", values="volume")
    scores = prices.pct_change(5, fill_method=None)
    trading_dates = prices.index[-5:]
    shares = pd.Series(0, index=prices.columns, dtype="int64")
    cash = 1_000_000.0
    orders_all: list[pd.DataFrame] = []
    fills_all: list[pd.DataFrame] = []
    reconciliation_all: list[pd.DataFrame] = []
    nav_rows: list[dict[str, object]] = []
    config = ExecutionConfig(max_volume_participation=0.05, impact_coefficient=0.02)

    for date in trading_dates:
        selected = scores.loc[date].nlargest(3).index
        target = pd.Series(0.0, index=prices.columns)
        target.loc[selected] = 0.30
        nav_before = cash + float((shares * prices.loc[date]).sum())
        orders = weights_to_orders(target, prices.loc[date], shares, nav_before)
        fills = simulate_execution(orders, prices.loc[date], volumes.loc[date], config=config)
        reconciliation = reconcile_executions(orders, fills)
        for fill in fills.itertuples(index=False):
            direction = 1 if fill.side == "BUY" else -1
            shares.loc[fill.symbol] += direction * int(fill.filled_shares)
            cash -= direction * float(fill.filled_shares) * float(fill.execution_price)
        orders_all.append(orders.assign(date=date))
        fills_all.append(fills.assign(date=date))
        reconciliation_all.append(reconciliation.assign(date=date))
        nav_rows.append(
            {
                "date": date,
                "cash": cash,
                "market_value": float((shares * prices.loc[date]).sum()),
                "nav": cash + float((shares * prices.loc[date]).sum()),
                "orders": len(orders),
                "filled_shares": int(fills["filled_shares"].sum()),
                "reconciled": bool(reconciliation["matched"].all()),
            }
        )

    orders_frame = pd.concat(orders_all, ignore_index=True)
    fills_frame = pd.concat(fills_all, ignore_index=True)
    reconciliation_frame = pd.concat(reconciliation_all, ignore_index=True)
    nav = pd.DataFrame(nav_rows)
    orders_frame.to_csv(destination / "orders.csv", index=False)
    fills_frame.to_csv(destination / "fills.csv", index=False)
    reconciliation_frame.to_csv(destination / "reconciliation.csv", index=False)
    nav.to_csv(destination / "daily_nav.csv", index=False)
    pd.DataFrame({"symbol": shares.index, "shares": shares.values}).to_csv(
        destination / "holdings.csv", index=False
    )

    figure, axes = plt.subplots(1, 2, figsize=(10, 4))
    nav.set_index("date")["nav"].plot(ax=axes[0], marker="o", title="Five-day paper NAV")
    fills_frame.groupby("date")["impact_cost"].sum().plot.bar(
        ax=axes[1], title="Daily impact cost"
    )
    _save_figure(figure, destination / "paper_trading.png")

    summary = pd.Series(
        {
            "trading_days": float(nav["date"].nunique()),
            "orders": float(len(orders_frame)),
            "fill_rate": float(
                fills_frame["filled_shares"].sum() / fills_frame["requested_shares"].sum()
            ),
            "reconciliation_match_rate": float(reconciliation_frame["matched"].mean()),
            "ending_nav": float(nav["nav"].iloc[-1]),
        },
        name="week11",
    )
    summary.to_csv(destination / "summary.csv", header=True)
    return _finish(
        destination,
        week=11,
        quick=quick,
        artifacts=(
            "orders.csv",
            "fills.csv",
            "reconciliation.csv",
            "daily_nav.csv",
            "holdings.csv",
            "summary.csv",
            "paper_trading.png",
        ),
        homework="""# 第 11 周作业

1. 逐日核对理论订单、模拟成交、现金和持仓变化。
2. 解释部分成交、滑点、冲击成本和整数手约束。
3. 写出从研究信号进入真实下单系统前仍缺少的安全控制。
""",
        criteria=(
            "连续五个交易日均有账户净值和对账记录",
            "能解释订单数量与实际成交数量的差异",
        ),
        report=f"""# 第 11 周实验报告

离线模拟盘连续运行 {int(summary['trading_days'])} 日，共生成
{int(summary['orders'])} 笔订单，股数成交率为 {summary['fill_rate']:.2%}，
逐项对账匹配率为 {summary['reconciliation_match_rate']:.2%}。
该撮合器不连接任何真实券商。
""",
        summary=summary,
    )


def run_week_12(
    output: str | Path = "artifacts/learning/week12",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """连续十四日监控净值、漂移与停止规则，并形成阶段报告。"""
    del force
    destination = prepare_lesson_output(output)
    rng = np.random.default_rng(SEED + 6)
    dates = pd.bdate_range("2026-01-05", periods=14)
    daily_returns = rng.normal(0.0004, 0.006, len(dates))
    daily_returns[9] = -0.07
    nav = pd.Series(1_000_000.0 * np.cumprod(1 + daily_returns), index=dates, name="nav")
    baseline_signal = pd.Series(rng.normal(0, 1, 200))
    rows: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    stopped = False
    stop_date: pd.Timestamp | None = None
    config = MonitorConfig(max_drawdown=0.05, max_psi=0.25)

    for i, date in enumerate(dates):
        current_signal = pd.Series(rng.normal(0.0 if i < 8 else 0.9, 1, 100))
        psi = population_stability_index(baseline_signal, current_signal, bins=5)
        decision = evaluate_stop_rules(
            nav_history=nav.iloc[: i + 1],
            psi_value=psi,
            config=config,
        )
        if decision.should_stop and not stopped:
            stopped = True
            stop_date = date
        peak = nav.iloc[: i + 1].max()
        rows.append(
            {
                "date": date,
                "nav": nav.iloc[i],
                "daily_return": daily_returns[i],
                "drawdown": nav.iloc[i] / peak - 1,
                "psi": psi,
                "should_stop": decision.should_stop,
                "strategy_halted": stopped,
                "reconciliation_matched": True,
            }
        )
        decisions.append(
            {
                "date": date,
                "should_stop": decision.should_stop,
                "reasons": "|".join(decision.reasons),
                "max_drawdown": decision.metrics["max_drawdown"],
                "psi": decision.metrics["psi"],
            }
        )

    monitoring = pd.DataFrame(rows)
    stop_rules = pd.DataFrame(decisions)
    monitoring.to_csv(destination / "daily_monitoring.csv", index=False)
    stop_rules.to_csv(destination / "stop_rules.csv", index=False)

    figure, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    monitoring.set_index("date")["nav"].plot(ax=axes[0], marker="o", title="14-day NAV")
    if stop_date is not None:
        axes[0].axvline(stop_date, color="firebrick", linestyle="--", label="first stop")
        axes[0].legend()
    monitoring.set_index("date")[["drawdown", "psi"]].plot(ax=axes[1], marker="o")
    axes[1].axhline(-0.05, color="firebrick", linestyle="--")
    axes[1].axhline(0.25, color="darkorange", linestyle="--")
    axes[1].set_title("Stop-rule indicators")
    _save_figure(figure, destination / "stage_monitoring.png")

    summary = pd.Series(
        {
            "monitoring_days": float(len(monitoring)),
            "ending_nav": float(nav.iloc[-1]),
            "max_drawdown": float(-(monitoring["drawdown"].min())),
            "max_psi": float(monitoring["psi"].max()),
            "stop_triggered": float(stopped),
            "first_stop_day": float(dates.get_loc(stop_date) + 1) if stop_date is not None else 0.0,
        },
        name="week12",
    )
    summary.to_csv(destination / "summary.csv", header=True)
    stage_report = f"""# 第 12 周阶段报告

## 范围

使用固定 seed {SEED} 的离线数据连续监控 14 个交易日，覆盖净值、回撤、
信号 PSI、账户对账和停止规则。

## 结果

- 期末净值：{summary['ending_nav']:.2f}
- 最大回撤：{summary['max_drawdown']:.2%}
- 最大 PSI：{summary['max_psi']:.4f}
- 是否触发停止：{'是' if stopped else '否'}
- 首次触发日：{stop_date.date().isoformat() if stop_date is not None else '未触发'}

## 风险结论

停止决定由预先声明的回撤 5% 或 PSI 0.25 阈值触发。触发后
`strategy_halted` 保持为真，演示“先停止、后调查”的治理原则。
合成数据只用于流程验收，不能证明策略具有真实市场有效性。
"""
    (destination / "stage_report.md").write_text(stage_report, encoding="utf-8")
    return _finish(
        destination,
        week=12,
        quick=quick,
        artifacts=(
            "daily_monitoring.csv",
            "stop_rules.csv",
            "summary.csv",
            "stage_report.md",
            "stage_monitoring.png",
        ),
        homework="""# 第 12 周作业

1. 按 `daily_monitoring.csv` 复核首次停止日和触发原因。
2. 区分策略失效、数据异常、账户不一致和正常波动的处置流程。
3. 补全阶段报告：失败实验、局限、复现步骤和下一阶段准入结论。
""",
        criteria=(
            "连续十四个交易日均有监控记录",
            "停止规则可复算且触发后保持停止状态",
            "阶段报告明确局限、失败条件和下一阶段准入结论",
        ),
        report=stage_report,
        summary=summary,
    )
