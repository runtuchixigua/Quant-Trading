"""第 13–18 周可离线复现的进阶课程实验。"""

from __future__ import annotations

import json
from math import erfc, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

from .event_study import (
    bootstrap_confidence_interval,
    generate_synthetic_events,
)
from .lesson_io import (
    file_sha256,
    prepare_lesson_output,
    write_acceptance,
    write_homework_if_safe,
    write_manifest,
)
from .lesson_stats import benjamini_hochberg, variance_inflation_factors
from .lessons import LessonResult
from .portfolio import (
    mean_variance_weights,
    minimum_variance_weights,
    risk_budget_weights,
)
from .risk import (
    factor_risk_decomposition,
    fit_factor_risk_model,
    ledoit_wolf_covariance,
    portfolio_risk_decomposition,
    sample_covariance,
)


def _finish(
    destination: Path,
    *,
    week: int,
    quick: bool,
    artifacts: tuple[str, ...],
    homework: str,
    criteria: tuple[str, ...],
    summary: pd.Series,
) -> LessonResult:
    write_homework_if_safe(
        destination,
        f"# 第 {week} 周作业\n\n{homework.strip()}\n\n"
        "## 实验记录\n\n- 我的实现：\n- 核心结果：\n- 风险与局限：\n",
    )
    write_acceptance(destination, week=week, criteria=criteria)
    write_manifest(
        destination,
        week=week,
        quick=quick,
        artifacts=(*artifacts, "homework.md", "acceptance.json"),
    )
    return LessonResult(week=week, output=destination, summary=summary)


def run_week_13(
    output: str | Path = "artifacts/learning/week13",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """生成 PIT 基本面快照，并记录哈希、血缘和公告日审计。"""
    del force  # 统一 runner 签名；作业始终由安全写入函数保护。
    destination = prepare_lesson_output(output)
    rng = np.random.default_rng(13)
    symbols = [f"{600000 + index:06d}.SH" for index in range(6 if quick else 12)]
    periods = pd.date_range("2023-03-31", periods=5 if quick else 8, freq="QE")
    rows: list[dict[str, object]] = []
    for symbol_index, symbol in enumerate(symbols):
        for period_index, report_period in enumerate(periods):
            announcement_date = report_period + pd.Timedelta(
                days=25 + (symbol_index * 7 + period_index * 3) % 35
            )
            base = 80.0 + 3.0 * symbol_index + 4.0 * period_index
            rows.append(
                {
                    "symbol": symbol,
                    "report_period": report_period,
                    "announcement_date": announcement_date,
                    "ingested_at": announcement_date + pd.Timedelta(days=1),
                    "revenue": base + rng.normal(0.0, 1.0),
                    "net_income": base * 0.11 + rng.normal(0.0, 0.2),
                    "source": "synthetic_exchange_filing",
                }
            )
    raw = pd.DataFrame(rows).sort_values(["symbol", "report_period"])
    as_of = pd.Timestamp("2024-09-30")
    eligible = raw.loc[raw["announcement_date"] <= as_of]
    snapshot = (
        eligible.sort_values(["symbol", "report_period", "ingested_at"])
        .groupby("symbol", as_index=False)
        .tail(1)
        .sort_values("symbol")
    )
    audit = raw.assign(
        as_of=as_of,
        available_on_as_of=raw["announcement_date"].le(as_of),
        days_from_announcement=(as_of - raw["announcement_date"]).dt.days,
    )
    audit["violation"] = audit["available_on_as_of"] & audit["announcement_date"].gt(as_of)

    raw.to_csv(destination / "fundamentals_raw.csv", index=False)
    snapshot.to_csv(destination / "pit_snapshot.csv", index=False)
    audit.to_csv(destination / "announcement_audit.csv", index=False)
    lineage = {
        "schema_version": 1,
        "as_of": as_of.isoformat(),
        "source": "fundamentals_raw.csv",
        "transform": "announcement_date <= as_of; latest report_period per symbol",
        "source_sha256": file_sha256(destination / "fundamentals_raw.csv"),
        "snapshot_sha256": file_sha256(destination / "pit_snapshot.csv"),
        "row_count": len(snapshot),
    }
    (destination / "lineage.json").write_text(
        json.dumps(lineage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = pd.Series(
        {
            "raw_rows": len(raw),
            "snapshot_rows": len(snapshot),
            "future_announcement_violations": int(
                (snapshot["announcement_date"] > as_of).sum()
            ),
        },
        name="week13",
        dtype=float,
    )
    return _finish(
        destination,
        week=13,
        quick=quick,
        artifacts=(
            "fundamentals_raw.csv",
            "pit_snapshot.csv",
            "announcement_audit.csv",
            "lineage.json",
        ),
        homework="""
1. 独立重建 `pit_snapshot.csv`，证明任何入选记录在 as-of 日已经公告。
2. 修改 as-of 日期，解释快照哈希为何变化，并补充修订版本的选取规则。
3. 画出公告延迟分布，列出生产环境还需保存的来源字段。
""",
        criteria=("快照无未来公告", "可用 SHA-256 复核来源与快照", "说明完整血缘链"),
        summary=summary,
    )


def run_week_14(
    output: str | Path = "artifacts/learning/week14",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """比较逐日历史股票池与只保留期末幸存者的回测偏差。"""
    del force
    destination = prepare_lesson_output(output)
    rng = np.random.default_rng(14)
    n_days = 90 if quick else 252
    n_assets = 12 if quick else 24
    dates = pd.bdate_range("2022-01-04", periods=n_days)
    symbols = pd.Index([f"S{index:03d}" for index in range(n_assets)], name="symbol")
    delisted = np.arange(n_assets) % 4 == 0
    delist_positions = np.where(delisted, n_days * (55 + np.arange(n_assets) % 25) // 100, n_days)
    market = rng.normal(0.0002, 0.009, size=(n_days, 1))
    drift = np.where(delisted, -0.0018, 0.00035)
    values = market + drift + rng.normal(0.0, 0.012, size=(n_days, n_assets))
    membership = np.arange(n_days)[:, None] < delist_positions
    values[~membership] = np.nan
    returns = pd.DataFrame(values, index=dates, columns=symbols)
    members = pd.DataFrame(membership, index=dates, columns=symbols)
    final_survivors = symbols[~delisted]
    historical_return = returns.where(members).mean(axis=1)
    survivor_return = returns.loc[:, final_survivors].mean(axis=1)
    comparison = pd.DataFrame(
        {
            "historical_universe_return": historical_return,
            "survivor_only_return": survivor_return,
        }
    )
    comparison["historical_wealth"] = (1.0 + historical_return).cumprod()
    comparison["survivor_only_wealth"] = (1.0 + survivor_return).cumprod()
    security_master = pd.DataFrame(
        {
            "symbol": symbols,
            "list_date": dates[0],
            "delist_date": [
                dates[position] if position < n_days else pd.NaT for position in delist_positions
            ],
            "survived_to_end": ~delisted,
        }
    )
    security_master.to_csv(destination / "security_master.csv", index=False)
    members.stack().rename("is_member").reset_index().to_csv(
        destination / "historical_universe.csv", index=False
    )
    returns.to_csv(destination / "asset_returns.csv", index_label="date")
    comparison.to_csv(destination / "bias_comparison.csv", index_label="date")
    bias = float(comparison["survivor_only_wealth"].iloc[-1] - comparison["historical_wealth"].iloc[-1])
    summary = pd.Series(
        {
            "historical_terminal_wealth": comparison["historical_wealth"].iloc[-1],
            "survivor_terminal_wealth": comparison["survivor_only_wealth"].iloc[-1],
            "survivorship_bias": bias,
            "delisted_assets": delisted.sum(),
        },
        name="week14",
        dtype=float,
    )
    return _finish(
        destination,
        week=14,
        quick=quick,
        artifacts=(
            "security_master.csv",
            "historical_universe.csv",
            "asset_returns.csv",
            "bias_comparison.csv",
        ),
        homework="""
1. 分别复算历史池和幸存者池的等权净值，量化选择偏差。
2. 将退市日前最后一期收益改为 -30%，观察偏差变化。
3. 解释上市、停牌、ST 与退市信息应在何时进入股票池。
""",
        criteria=("历史池按日期变化", "退市股票保留在历史样本", "量化幸存者偏差"),
        summary=summary,
    )


def run_week_15(
    output: str | Path = "artifacts/learning/week15",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """完成合成公告事件的异常收益、CAR、bootstrap 与安慰剂检验。"""
    del force
    destination = prepare_lesson_output(output)
    n_events = 40 if quick else 160
    n_bootstrap = 300 if quick else 2_000
    panel = generate_synthetic_events(
        n_events=n_events, window=(-5, 10), event_effect=0.02, seed=15
    )
    panel["abnormal_return"] = panel["asset_return"] - panel["market_return"]
    abnormal = panel.pivot(index="event_id", columns="relative_day", values="abnormal_return")
    cars = abnormal.loc[:, -1:1].sum(axis=1).rename("car")
    lower, upper = bootstrap_confidence_interval(
        cars, n_bootstrap=n_bootstrap, seed=1501
    )
    placebo_panel = generate_synthetic_events(
        n_events=n_events, window=(-5, 10), event_effect=0.0, seed=1502
    )
    placebo_panel["abnormal_return"] = (
        placebo_panel["asset_return"] - placebo_panel["market_return"]
    )
    placebo_car = (
        placebo_panel.pivot(
            index="event_id", columns="relative_day", values="abnormal_return"
        )
        .loc[:, -1:1]
        .sum(axis=1)
        .rename("placebo_car")
    )
    car_frame = pd.concat([cars, placebo_car], axis=1)
    event_summary = pd.Series(
        {
            "mean_car": cars.mean(),
            "bootstrap_lower": lower,
            "bootstrap_upper": upper,
            "placebo_mean_car": placebo_car.mean(),
            "event_minus_placebo": cars.mean() - placebo_car.mean(),
        },
        name="week15",
        dtype=float,
    )
    panel.to_csv(destination / "synthetic_events.csv", index=False)
    abnormal.to_csv(destination / "abnormal_returns.csv")
    car_frame.to_csv(destination / "car_and_placebo.csv")
    event_summary.to_csv(destination / "event_summary.csv", header=True)
    return _finish(
        destination,
        week=15,
        quick=quick,
        artifacts=(
            "synthetic_events.csv",
            "abnormal_returns.csv",
            "car_and_placebo.csv",
            "event_summary.csv",
        ),
        homework="""
1. 比较 [-1, 1]、[0, 3] 两个事件窗的 CAR 与置信区间。
2. 将市场调整模型替换为市场模型，讨论估计窗污染。
3. 重复安慰剂实验并解释它为何不能单独证明因果关系。
""",
        criteria=("正确计算异常收益与 CAR", "报告 bootstrap 区间", "真实事件强于安慰剂"),
        summary=event_summary,
    )


def _ols_diagnostics(features: pd.DataFrame, target: pd.Series) -> pd.DataFrame:
    design = np.column_stack([np.ones(len(features)), features.to_numpy()])
    coefficient, *_ = np.linalg.lstsq(design, target.to_numpy(), rcond=None)
    residual = target.to_numpy() - design @ coefficient
    dof = len(target) - design.shape[1]
    sigma2 = float(residual @ residual / dof)
    standard_error = np.sqrt(np.diag(sigma2 * np.linalg.pinv(design.T @ design)))
    t_value = coefficient / standard_error
    p_value = np.array([erfc(abs(value) / sqrt(2.0)) for value in t_value])
    return pd.DataFrame(
        {
            "coefficient": coefficient[1:],
            "standard_error": standard_error[1:],
            "t_value": t_value[1:],
            "p_value": p_value[1:],
        },
        index=features.columns,
    )


def run_week_16(
    output: str | Path = "artifacts/learning/week16",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """诊断因子相关性、VIF、多重检验与样本外边际贡献。"""
    del force
    destination = prepare_lesson_output(output)
    rng = np.random.default_rng(16)
    n_observations = 180 if quick else 700
    base = rng.normal(size=(n_observations, 3))
    features = pd.DataFrame(
        {
            "value": base[:, 0],
            "quality": base[:, 1],
            "momentum": base[:, 2],
            "value_clone": 0.92 * base[:, 0] + rng.normal(0.0, 0.25, n_observations),
            "noise": rng.normal(size=n_observations),
        }
    )
    target = pd.Series(
        0.025 * features["value"]
        + 0.018 * features["quality"]
        + 0.012 * features["momentum"]
        + rng.normal(0.0, 0.12, n_observations),
        name="forward_return",
    )
    split = int(n_observations * 0.7)
    train_x, test_x = features.iloc[:split], features.iloc[split:]
    train_y, test_y = target.iloc[:split], target.iloc[split:]
    diagnostics = _ols_diagnostics(train_x, train_y)
    diagnostics["vif"] = variance_inflation_factors(train_x)
    fdr = benjamini_hochberg(diagnostics["p_value"])
    diagnostics[["adjusted_p_value", "reject"]] = fdr[["adjusted_p_value", "reject"]]
    full_design = np.column_stack([np.ones(len(train_x)), train_x])
    full_coef, *_ = np.linalg.lstsq(full_design, train_y, rcond=None)
    full_prediction = np.column_stack([np.ones(len(test_x)), test_x]) @ full_coef
    baseline_mse = float(np.mean((test_y.to_numpy() - full_prediction) ** 2))
    marginal: dict[str, float] = {}
    for column in features:
        reduced = train_x.drop(columns=column)
        coef, *_ = np.linalg.lstsq(
            np.column_stack([np.ones(len(reduced)), reduced]), train_y, rcond=None
        )
        prediction = np.column_stack(
            [np.ones(len(test_x)), test_x.drop(columns=column)]
        ) @ coef
        marginal[column] = float(np.mean((test_y.to_numpy() - prediction) ** 2) - baseline_mse)
    diagnostics["marginal_oos_mse_reduction"] = pd.Series(marginal)
    pd.concat([features, target], axis=1).to_csv(destination / "factor_sample.csv", index=False)
    features.corr().to_csv(destination / "factor_correlations.csv")
    diagnostics.to_csv(destination / "factor_diagnostics.csv")
    summary = pd.Series(
        {
            "max_absolute_correlation": features.corr().where(
                ~np.eye(features.shape[1], dtype=bool)
            ).abs().max().max(),
            "max_vif": diagnostics["vif"].max(),
            "fdr_discoveries": diagnostics["reject"].sum(),
            "positive_marginal_factors": (
                diagnostics["marginal_oos_mse_reduction"] > 0
            ).sum(),
        },
        name="week16",
        dtype=float,
    )
    return _finish(
        destination,
        week=16,
        quick=quick,
        artifacts=("factor_sample.csv", "factor_correlations.csv", "factor_diagnostics.csv"),
        homework="""
1. 找出高相关且高 VIF 的因子，提出删除或正交化方案。
2. 对比原始 p 值与 FDR 结论，解释多重检验风险。
3. 用样本外边际 MSE 贡献决定保留因子，并说明不稳定性。
""",
        criteria=("同时报告相关与 VIF", "完成 BH-FDR 修正", "报告样本外边际贡献"),
        summary=summary,
    )


def _synthetic_factor_market(
    *, seed: int, n_days: int, n_assets: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    assets = pd.Index([f"A{index:02d}" for index in range(n_assets)])
    exposures = pd.DataFrame(
        rng.normal(size=(n_assets, 3)),
        index=assets,
        columns=["market", "value", "momentum"],
    )
    factor_returns = rng.normal(
        [0.00025, 0.00010, 0.00015], [0.009, 0.005, 0.006], size=(n_days, 3)
    )
    residual = rng.normal(0.0, 0.005, size=(n_days, n_assets))
    returns = pd.DataFrame(
        factor_returns @ exposures.to_numpy().T + residual,
        index=pd.bdate_range("2021-01-04", periods=n_days),
        columns=assets,
    )
    return returns, exposures


def run_week_17(
    output: str | Path = "artifacts/learning/week17",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """比较协方差估计，拟合因子风险模型并完成风险/收益归因。"""
    del force
    destination = prepare_lesson_output(output)
    returns, exposures = _synthetic_factor_market(
        seed=17, n_days=80 if quick else 252, n_assets=10 if quick else 20
    )
    sample = sample_covariance(returns)
    shrunk = ledoit_wolf_covariance(returns)
    model = fit_factor_risk_model(returns, exposures)
    weights = pd.Series(1.0 / returns.shape[1], index=returns.columns)
    asset_risk = portfolio_risk_decomposition(weights, shrunk)
    factor_risk = factor_risk_decomposition(weights, model)
    portfolio_factor_exposure = exposures.T @ weights
    mean_factor_return = model.factor_returns.mean() * 252.0
    return_attribution = (portfolio_factor_exposure * mean_factor_return).rename(
        "annual_return_contribution"
    )
    covariance_comparison = pd.DataFrame(
        {
            "sample_eigenvalue": np.sort(np.linalg.eigvalsh(sample)),
            "ledoit_wolf_eigenvalue": np.sort(np.linalg.eigvalsh(shrunk)),
        }
    )
    returns.to_csv(destination / "asset_returns.csv", index_label="date")
    exposures.to_csv(destination / "factor_exposures.csv")
    sample.to_csv(destination / "sample_covariance.csv")
    shrunk.to_csv(destination / "ledoit_wolf_covariance.csv")
    covariance_comparison.to_csv(destination / "covariance_comparison.csv", index=False)
    asset_risk.to_csv(destination / "asset_risk_attribution.csv")
    pd.concat(
        [factor_risk, return_attribution.rename(index=lambda value: f"factor:{value}")],
        axis=1,
    ).to_csv(destination / "factor_attribution.csv")
    summary = pd.Series(
        {
            "sample_condition_number": np.linalg.cond(sample),
            "ledoit_condition_number": np.linalg.cond(shrunk),
            "portfolio_volatility": asset_risk.attrs["volatility"],
            "factor_risk_share": factor_risk.attrs["factor_variance"]
            / factor_risk.attrs["total_variance"],
        },
        name="week17",
        dtype=float,
    )
    return _finish(
        destination,
        week=17,
        quick=quick,
        artifacts=(
            "asset_returns.csv",
            "factor_exposures.csv",
            "sample_covariance.csv",
            "ledoit_wolf_covariance.csv",
            "covariance_comparison.csv",
            "asset_risk_attribution.csv",
            "factor_attribution.csv",
        ),
        homework="""
1. 比较样本与 Ledoit-Wolf 协方差的特征值和条件数。
2. 验证资产风险贡献之和等于组合波动率。
3. 区分因子风险归因与因子收益归因，并解释特异风险。
""",
        criteria=("比较两种协方差估计", "风险贡献可加总", "完成因子风险与收益归因"),
        summary=summary,
    )


def _portfolio_metrics(
    weights: dict[str, pd.Series], expected: pd.Series, covariance: pd.DataFrame
) -> pd.DataFrame:
    records = []
    for method, current in weights.items():
        records.append(
            {
                "method": method,
                "expected_return": float(current @ expected),
                "volatility": float(np.sqrt(current @ covariance @ current)),
                "max_weight": float(current.max()),
                "effective_assets": float(1.0 / current.pow(2).sum()),
            }
        )
    return pd.DataFrame(records).set_index("method")


def run_week_18(
    output: str | Path = "artifacts/learning/week18",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """比较四类组合并测量输入扰动造成的权重不稳定性。"""
    del force
    destination = prepare_lesson_output(output)
    returns, _ = _synthetic_factor_market(
        seed=18, n_days=100 if quick else 300, n_assets=8 if quick else 16
    )
    covariance = ledoit_wolf_covariance(returns)
    expected = returns.mean() * 252.0
    equal = pd.Series(1.0 / returns.shape[1], index=returns.columns, name="weight")
    portfolios = {
        "equal_weight": equal,
        "minimum_variance": minimum_variance_weights(covariance, max_weight=0.35),
        "mean_variance": mean_variance_weights(
            expected, covariance, risk_aversion=8.0, max_weight=0.35
        ),
        "risk_budget": risk_budget_weights(covariance),
    }
    rng = np.random.default_rng(1801)
    scale = np.sqrt(np.diag(covariance))
    noise = rng.normal(0.0, 0.015, size=covariance.shape)
    noise = (noise + noise.T) / 2.0
    perturbed_covariance = covariance + np.outer(scale, scale) * noise
    eigenvalues, eigenvectors = np.linalg.eigh(perturbed_covariance)
    perturbed_covariance = pd.DataFrame(
        (eigenvectors * np.maximum(eigenvalues, 1e-8)) @ eigenvectors.T,
        index=covariance.index,
        columns=covariance.columns,
    )
    perturbed_expected = expected + pd.Series(
        rng.normal(0.0, 0.02, len(expected)), index=expected.index
    )
    perturbed = {
        "equal_weight": equal,
        "minimum_variance": minimum_variance_weights(
            perturbed_covariance, max_weight=0.35
        ),
        "mean_variance": mean_variance_weights(
            perturbed_expected, perturbed_covariance, risk_aversion=8.0, max_weight=0.35
        ),
        "risk_budget": risk_budget_weights(perturbed_covariance),
    }
    weight_frame = pd.DataFrame(portfolios)
    metrics = _portfolio_metrics(portfolios, expected, covariance)
    perturbation = pd.DataFrame(
        {
            "l1_weight_change": {
                method: float((portfolios[method] - perturbed[method]).abs().sum())
                for method in portfolios
            },
            "max_weight_change": {
                method: float((portfolios[method] - perturbed[method]).abs().max())
                for method in portfolios
            },
        }
    )
    returns.to_csv(destination / "asset_returns.csv", index_label="date")
    covariance.to_csv(destination / "covariance.csv")
    weight_frame.to_csv(destination / "portfolio_weights.csv")
    metrics.to_csv(destination / "portfolio_metrics.csv")
    perturbation.to_csv(destination / "input_perturbation.csv")
    summary = pd.Series(
        {
            "methods": len(portfolios),
            "largest_l1_perturbation": perturbation["l1_weight_change"].max(),
            "mean_variance_l1_perturbation": perturbation.loc[
                "mean_variance", "l1_weight_change"
            ],
            "all_weights_sum_to_one": float(
                np.allclose(weight_frame.sum(axis=0), 1.0)
            ),
        },
        name="week18",
        dtype=float,
    )
    return _finish(
        destination,
        week=18,
        quick=quick,
        artifacts=(
            "asset_returns.csv",
            "covariance.csv",
            "portfolio_weights.csv",
            "portfolio_metrics.csv",
            "input_perturbation.csv",
        ),
        homework="""
1. 比较等权、最小方差、均值方差、风险预算的集中度与风险。
2. 复核每种权重和为 1，并验证风险预算贡献。
3. 改变预期收益和协方差扰动幅度，讨论估计误差与稳健约束。
""",
        criteria=("四种组合均可执行且权重归一", "报告风险收益指标", "量化输入扰动敏感性"),
        summary=summary,
    )
