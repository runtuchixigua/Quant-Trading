"""第 19—24 周：稳健验证、执行治理与毕业研究的可执行课程。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DataConfig, FactorConfig, PortfolioConfig, ResearchConfig, ValidationConfig
from .execution import ExecutionConfig, simulate_execution, weights_to_orders
from .lesson_io import (
    prepare_lesson_output,
    write_acceptance,
    write_homework_if_safe,
    write_manifest,
)
from .lesson_stats import historical_var_es, moving_block_bootstrap_mean_interval
from .lessons import LessonResult
from .ml import WalkForwardConfig, walk_forward_evaluate
from .monitor import (
    MonitorConfig,
    evaluate_stop_rules,
    population_stability_index,
    reconcile_account,
    validate_market_data,
)
from .pipeline import run_advanced_pipeline
from .validation import (
    ExperimentLog,
    PurgedEmbargoSplit,
    cost_multiplier_stress,
    market_regime_stress,
)

SEED = 202407


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _finish(
    destination: Path,
    *,
    week: int,
    quick: bool,
    summary: pd.Series,
    artifacts: tuple[str, ...],
    homework: str,
    criteria: tuple[str, ...],
) -> LessonResult:
    summary.to_csv(destination / "summary.csv", header=True)
    write_homework_if_safe(destination, homework)
    write_acceptance(destination, week=week, criteria=criteria)
    write_manifest(
        destination,
        week=week,
        quick=quick,
        artifacts=(*artifacts, "summary.csv", "homework.md", "acceptance.json"),
    )
    return LessonResult(week=week, output=destination, summary=summary)


def _returns(n: int, seed: int = SEED) -> pd.Series:
    rng = np.random.default_rng(seed)
    innovations = rng.normal(0.00035, 0.011, n)
    values = np.empty(n)
    values[0] = innovations[0]
    for index in range(1, n):
        values[index] = 0.18 * values[index - 1] + innovations[index]
    return pd.Series(values, index=pd.bdate_range("2020-01-02", periods=n), name="return")


def run_week_19(
    output: str | Path = "artifacts/learning/week19",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """运行嵌套验证、多重试验与区块 bootstrap 实验。"""
    del force
    destination = prepare_lesson_output(output)
    returns = _returns(140 if quick else 504)
    splitter = PurgedEmbargoSplit(
        n_splits=3 if quick else 5,
        purge_dates=5,
        embargo_dates=2,
        min_train_dates=35 if quick else 126,
    )
    fold_rows = []
    for fold, (train, validation) in enumerate(splitter.split(returns.index), 1):
        fold_rows.append(
            {
                "fold": fold,
                "train_start": returns.index[train[0]],
                "train_end": returns.index[train[-1]],
                "validation_start": returns.index[validation[0]],
                "validation_end": returns.index[validation[-1]],
                "train_observations": len(train),
                "validation_observations": len(validation),
                "gap_dates": validation[0] - train[-1] - 1,
            }
        )
    folds = pd.DataFrame(fold_rows)
    folds.to_csv(destination / "purged_embargo_folds.csv", index=False)

    experiments = ExperimentLog()
    candidates: dict[str, pd.Series] = {}
    for lookback in ((5, 10, 20) if quick else (5, 10, 20, 40, 60, 90)):
        signal = np.sign(returns.rolling(lookback).mean()).shift(1).fillna(0.0)
        candidate = (signal * returns).rename(f"momentum_{lookback}")
        candidates[candidate.name] = candidate
        experiments.record(
            candidate.name,
            returns=candidate,
            metadata={"lookback": lookback, "seed": SEED},
        )
    log = experiments.to_frame()
    log.to_csv(destination / "experiment_log.csv", index=False)
    winner = str(log.loc[log["sharpe"].idxmax(), "name"])
    deflated = experiments.deflated_sharpe(winner, candidates[winner])
    _write_json(destination / "deflated_sharpe.json", asdict(deflated))
    lower, upper = moving_block_bootstrap_mean_interval(
        candidates[winner],
        block_size=5,
        n_bootstrap=200 if quick else 2_000,
        seed=SEED,
    )
    bootstrap = pd.Series(
        {"mean_return": candidates[winner].mean(), "ci_lower": lower, "ci_upper": upper}
    )
    bootstrap.to_csv(destination / "block_bootstrap.csv", header=True)
    summary = pd.Series(
        {
            "folds": len(folds),
            "experiments": len(log),
            "selected": winner,
            "deflated_sharpe_probability": deflated.probability,
            "bootstrap_ci_width": upper - lower,
        },
        name="week19",
    )
    return _finish(
        destination,
        week=19,
        quick=quick,
        summary=summary,
        artifacts=(
            "purged_embargo_folds.csv",
            "experiment_log.csv",
            "deflated_sharpe.json",
            "block_bootstrap.csv",
        ),
        homework="""# 第 19 周作业

1. 解释每折训练集与验证集之间的 purge/embargo 空档。
2. 将一次失败试验加入 `experiment_log.csv`，重新解释 Deflated Sharpe。
3. 比较 IID 与 block bootstrap，并说明序列相关性为何重要。
""",
        criteria=(
            "所有参数尝试均进入试验日志",
            "验证折不存在时间泄漏且报告 Deflated Sharpe",
            "固定 seed 的区块 bootstrap 可复现",
        ),
    )


def run_week_20(
    output: str | Path = "artifacts/learning/week20",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """运行市场状态、成本、尾部风险和联合压力实验。"""
    del force
    destination = prepare_lesson_output(output)
    returns = _returns(180 if quick else 756, SEED + 1)
    gross = returns + 0.00035
    costs = pd.Series(
        0.00025 + 0.05 * returns.abs(), index=returns.index, name="cost"
    )
    rolling = returns.rolling(20, min_periods=5).mean()
    regimes = pd.Series(
        np.select(
            [rolling > 0.001, rolling < -0.001],
            ["bull", "bear"],
            default="sideways",
        ),
        index=returns.index,
        name="regime",
    )
    regime_results = market_regime_stress(returns, regimes)
    cost_results = cost_multiplier_stress(gross, costs, (1.0, 2.0, 3.0))
    regime_results.to_csv(destination / "regime_stress.csv")
    cost_results.to_csv(destination / "cost_stress.csv")
    tail = historical_var_es(returns, confidence=0.95)
    tail.to_csv(destination / "tail_risk.csv", header=True)

    rows = []
    for regime in ("bull", "sideways", "bear"):
        mask = regimes == regime
        for multiplier in (1.0, 2.0, 3.0):
            stressed = (gross - multiplier * costs).loc[mask]
            risk = historical_var_es(stressed, confidence=0.95)
            rows.append(
                {
                    "regime": regime,
                    "cost_multiplier": multiplier,
                    "observations": len(stressed),
                    "mean_return": stressed.mean(),
                    "var": risk["var"],
                    "es": risk["es"],
                }
            )
    joint = pd.DataFrame(rows)
    joint.to_csv(destination / "joint_stress.csv", index=False)
    summary = pd.Series(
        {
            "regimes": regime_results.shape[0],
            "cost_scenarios": cost_results.shape[0],
            "var_95": tail["var"],
            "es_95": tail["es"],
            "worst_joint_es": joint["es"].max(),
        },
        name="week20",
    )
    return _finish(
        destination,
        week=20,
        quick=quick,
        summary=summary,
        artifacts=("regime_stress.csv", "cost_stress.csv", "tail_risk.csv", "joint_stress.csv"),
        homework="""# 第 20 周作业

1. 解释 VaR 与 ES 的差异，以及为何 ES 更适合描述尾部损失。
2. 找出市场状态与成本倍数的最差联合情景。
3. 提出一个历史样本未覆盖的压力情景并说明依据。
""",
        criteria=(
            "分别提交市场状态、成本和 VaR/ES 结果",
            "联合压力同时改变市场状态和交易成本",
        ),
    )


def _ml_panel(quick: bool) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(SEED + 2)
    n_dates, n_assets = (60, 6) if quick else (150, 12)
    dates = pd.bdate_range("2021-01-04", periods=n_dates)
    symbols = [f"S{number:03d}" for number in range(n_assets)]
    index = pd.MultiIndex.from_product([dates, symbols], names=["date", "symbol"])
    features = pd.DataFrame(
        rng.normal(size=(len(index), 4)),
        index=index,
        columns=["value", "momentum", "quality", "noise"],
    )
    labels = (
        0.025 * features["value"]
        + 0.015 * features["momentum"]
        - 0.01 * features["quality"]
        + pd.Series(rng.normal(0, 0.03, len(index)), index=index)
    ).rename("future_return")
    return features, labels


def run_week_21(
    output: str | Path = "artifacts/learning/week21",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """运行模型解释、PSI 漂移和自动降级演练。"""
    del force
    destination = prepare_lesson_output(output)
    features, labels = _ml_panel(quick)
    result = walk_forward_evaluate(
        features,
        labels,
        WalkForwardConfig(
            min_train_dates=25 if quick else 60,
            train_window_dates=40 if quick else 100,
            label_horizon_dates=2,
            retrain_every=10 if quick else 20,
            random_state=SEED,
        ),
    )
    result.feature_importance.to_csv(destination / "model_importance.csv", index=False)
    result.folds.to_csv(destination / "walk_forward_folds.csv", index=False)
    reference = features.loc[(slice(None, features.index.levels[0][29]), slice(None)), "value"]
    current = features.loc[(slice(features.index.levels[0][30], None), slice(None)), "value"] + 2.0
    psi = population_stability_index(reference, current)
    decision = evaluate_stop_rules(
        nav_history=pd.Series([1.0, 1.01, 1.005, 1.015]),
        psi_value=psi,
        config=MonitorConfig(max_psi=0.10),
    )
    drill = {
        "fault": "FEATURE_DISTRIBUTION_SHIFT",
        "psi": psi,
        "threshold": 0.10,
        "should_stop": decision.should_stop,
        "reasons": decision.reasons,
        "degradation": "停用 ML 打分，降级到冻结的等权规则组合",
        "recovery_gate": "数据修复、PSI 低于阈值且影子运行通过后人工恢复",
    }
    _write_json(destination / "drift_degradation_drill.json", drill)
    summary = pd.Series(
        {
            "folds": len(result.folds),
            "importance_rows": len(result.feature_importance),
            "psi": psi,
            "degradation_triggered": decision.should_stop,
        },
        name="week21",
    )
    return _finish(
        destination,
        week=21,
        quick=quick,
        summary=summary,
        artifacts=(
            "model_importance.csv",
            "walk_forward_folds.csv",
            "drift_degradation_drill.json",
        ),
        homework="""# 第 21 周作业

1. 比较各折模型重要性，找出符号或排序不稳定的特征。
2. 解释 PSI 只能识别分布变化、不能证明模型失效。
3. 为降级、影子运行和人工恢复补充负责人及证据。
""",
        criteria=(
            "模型重要性按 walk-forward 折留档",
            "PSI 超阈值可触发明确的降级与恢复门槛",
        ),
    )


def run_week_22(
    output: str | Path = "artifacts/learning/week22",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """运行规模×流动性容量曲线和冲击成本实验。"""
    del force
    destination = prepare_lesson_output(output)
    scales = np.geomspace(1_000_000, 30_000_000, 3 if quick else 7)
    liquidity_multipliers = (0.35, 1.0, 2.5)
    symbols = pd.Index(["AAA", "BBB", "CCC", "DDD"])
    prices = pd.Series([10.0, 18.0, 25.0, 42.0], index=symbols)
    weights = pd.Series(0.25, index=symbols)
    base_volumes = pd.Series([80_000, 120_000, 200_000, 300_000], index=symbols)
    rows = []
    for nav in scales:
        orders = weights_to_orders(weights, prices, None, float(nav))
        for liquidity in liquidity_multipliers:
            fills = simulate_execution(
                orders,
                prices,
                base_volumes * liquidity,
                config=ExecutionConfig(
                    max_volume_participation=0.10,
                    slippage=0.0005,
                    impact_coefficient=0.08,
                ),
            )
            requested = int(fills["requested_shares"].sum())
            filled = int(fills["filled_shares"].sum())
            notional = float((fills["filled_shares"] * fills["reference_price"]).sum())
            rows.append(
                {
                    "nav": float(nav),
                    "liquidity_multiplier": liquidity,
                    "requested_shares": requested,
                    "filled_shares": filled,
                    "fill_rate": filled / requested if requested else 1.0,
                    "impact_cost": fills["impact_cost"].sum(),
                    "impact_bps": 10_000 * fills["impact_cost"].sum() / notional
                    if notional
                    else np.nan,
                }
            )
    curve = pd.DataFrame(rows)
    curve.to_csv(destination / "capacity_curve.csv", index=False)
    summary = pd.Series(
        {
            "size_scenarios": len(scales),
            "liquidity_scenarios": len(liquidity_multipliers),
            "joint_scenarios": len(curve),
            "minimum_fill_rate": curve["fill_rate"].min(),
            "maximum_impact_bps": curve["impact_bps"].max(),
        },
        name="week22",
    )
    return _finish(
        destination,
        week=22,
        quick=quick,
        summary=summary,
        artifacts=("capacity_curve.csv",),
        homework="""# 第 22 周作业

1. 绘制 NAV×流动性的容量曲线并定义容量上限。
2. 比较未成交比例与冲击成本，说明二者为何不能只看一个。
3. 写出策略申购规模增长时的执行限制。
""",
        criteria=(
            f"规模维度至少包含 {3 if quick else 7} 个场景",
            "每个规模同时覆盖多个流动性场景并报告成交率和冲击成本",
        ),
    )


def run_week_23(
    output: str | Path = "artifacts/learning/week23",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """运行数据、模型、账户和风险故障注入演练。"""
    del force
    destination = prepare_lesson_output(output)
    dates = pd.bdate_range("2024-01-02", periods=5)
    market = pd.DataFrame(
        {
            "date": np.repeat(dates, 2),
            "symbol": ["AAA", "BBB"] * len(dates),
            "close": np.tile([10.0, 20.0], len(dates)),
            "volume": np.tile([100_000, 150_000], len(dates)),
        }
    )
    injected: list[dict[str, object]] = []

    def data_fault(name: str, frame: pd.DataFrame, as_of: pd.Timestamp) -> None:
        try:
            validate_market_data(frame, as_of=as_of, max_age_days=1)
            error: Exception | None = None
        except ValueError as exc:
            error = exc
        decision = evaluate_stop_rules(nav_history=pd.Series([1.0, 1.01]), data_error=error)
        injected.append(
            {
                "fault": name,
                "detected": error is not None,
                "should_stop": decision.should_stop,
                "reason": "|".join(decision.reasons),
                "rollback": "拒绝新批次并恢复上一已验证数据快照",
            }
        )

    data_fault("MISSING_COLUMN", market.drop(columns="volume"), dates[-1])
    data_fault("DUPLICATE_ROW", pd.concat([market, market.iloc[[0]]]), dates[-1])
    data_fault("STALE_DATA", market, dates[-1] + pd.Timedelta(days=5))

    psi = population_stability_index(
        np.linspace(-1, 1, 200), np.linspace(2, 4, 200)
    )
    drift = evaluate_stop_rules(
        nav_history=pd.Series([1.0, 1.01]), psi_value=psi, config=MonitorConfig(max_psi=0.1)
    )
    injected.append(
        {
            "fault": "MODEL_DRIFT",
            "detected": drift.should_stop,
            "should_stop": drift.should_stop,
            "reason": "|".join(drift.reasons),
            "rollback": "停用新模型并恢复上一批准模型",
        }
    )
    drawdown = evaluate_stop_rules(
        nav_history=pd.Series([1.0, 0.96, 0.80]), config=MonitorConfig(max_drawdown=0.15)
    )
    injected.append(
        {
            "fault": "MAX_DRAWDOWN",
            "detected": drawdown.should_stop,
            "should_stop": drawdown.should_stop,
            "reason": "|".join(drawdown.reasons),
            "rollback": "撤销未成交订单、冻结调仓并进入人工复核",
        }
    )
    reconciliation = reconcile_account(
        pd.Series({"AAA": 1_000}),
        pd.Series({"AAA": 900}),
        100_000,
        99_000,
    )
    mismatch = evaluate_stop_rules(
        nav_history=pd.Series([1.0, 1.01]), reconciliation=reconciliation
    )
    injected.append(
        {
            "fault": "ACCOUNT_MISMATCH",
            "detected": mismatch.should_stop,
            "should_stop": mismatch.should_stop,
            "reason": "|".join(mismatch.reasons),
            "rollback": "冻结账户、对账并从已确认账本恢复",
        }
    )
    drills = pd.DataFrame(injected)
    drills.to_csv(destination / "fault_injection.csv", index=False)
    (destination / "stop_and_rollback.md").write_text(
        """# 停止与回滚手册

## 停止顺序
1. 停止生成新订单并撤销尚未成交订单。
2. 保存行情批次、模型版本、账户状态和结构化告警。
3. 根据故障类型恢复上一份已验证数据、批准模型或已确认账本。

## 恢复门槛
- 根因、影响范围与修复证据已由第二人复核。
- 离线重放和影子运行均通过，停止规则不再触发。
- 恢复必须人工批准；不得因告警自动消失而自动重启。
""",
        encoding="utf-8",
    )
    summary = pd.Series(
        {
            "fault_types": len(drills),
            "detected_faults": int(drills["detected"].sum()),
            "stop_decisions": int(drills["should_stop"].sum()),
        },
        name="week23",
    )
    return _finish(
        destination,
        week=23,
        quick=quick,
        summary=summary,
        artifacts=("fault_injection.csv", "stop_and_rollback.md"),
        homework="""# 第 23 周作业

1. 为每类故障指定负责人、SLA、通知对象和恢复证据。
2. 任选一种故障执行桌面推演，记录发现时间与恢复时间。
3. 解释为何停止可以自动化，而恢复应保留人工批准。
""",
        criteria=(
            "至少五类故障均有检测、停止和回滚结果",
            "停止与恢复门槛形成独立文档且恢复需人工批准",
        ),
    )


def _next_run_directory(runs: Path) -> Path:
    runs.mkdir(parents=True, exist_ok=True)
    numbers = [
        int(path.name.removeprefix("run_"))
        for path in runs.glob("run_[0-9][0-9][0-9]")
        if path.name.removeprefix("run_").isdigit()
    ]
    return runs / f"run_{max(numbers, default=0) + 1:03d}"


def run_week_24(
    output: str | Path = "artifacts/learning/week24",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """在唯一运行目录执行毕业流水线，并在周根目录生成答辩材料。"""
    del force
    destination = prepare_lesson_output(output)
    run_directory = _next_run_directory(destination / "runs")
    config = ResearchConfig(
        start_date="2020-01-02",
        end_date="2023-12-31",
        seed=SEED,
        data=DataConfig(n_days=260 if quick else 600, n_assets=20 if quick else 40),
        factors=FactorConfig(
            amihud_window=10 if quick else 20,
            ic_window=30 if quick else 60,
            decay_lags=3 if quick else 12,
        ),
        portfolio=PortfolioConfig(max_weight=0.05 if quick else 0.025),
        validation=ValidationConfig(
            min_train_dates=60 if quick else 180,
            train_window_dates=120 if quick else 360,
            label_horizon_dates=10 if quick else 20,
            retrain_every=20,
            purge_dates=10 if quick else 20,
            embargo_dates=2 if quick else 5,
        ),
    )
    pipeline_manifest = run_advanced_pipeline(config, run_directory)
    relative_run = run_directory.relative_to(destination)
    (destination / "reproduction.md").write_text(
        "# 独立复现清单\n\n"
        f"- 本次只读产物目录：`{relative_run}`\n"
        f"- 固定 seed：`{SEED}`\n"
        "- 核对配置、数据声明、依赖环境和所有 CSV/JSON 产物。\n"
        "- 在新目录以相同配置重跑，并比较关键指标与文件结构。\n",
        encoding="utf-8",
    )
    (destination / "defense_checklist.md").write_text(
        """# 答辩清单

- [ ] 能说明研究假设、经济逻辑与适用边界
- [ ] 能证明 PIT 数据、标签隔离和最终测试集纪律
- [ ] 能解释失败试验、Deflated Sharpe、压力测试与容量
- [ ] 能演示监控停止、模型降级和人工恢复
- [ ] 能由第三方在独立目录复现核心结果
""",
        encoding="utf-8",
    )
    summary = pd.Series(
        {
            "run_directory": str(relative_run),
            "assets": pipeline_manifest["assets"],
            "strategy_sharpe": pipeline_manifest["strategy_sharpe"],
            "monitor_should_stop": pipeline_manifest["monitor_should_stop"],
            "seed": SEED,
        },
        name="week24",
    )
    return _finish(
        destination,
        week=24,
        quick=quick,
        summary=summary,
        artifacts=(
            str(relative_run / "run_manifest.json"),
            str(relative_run / "graduation_report.md"),
            "reproduction.md",
            "defense_checklist.md",
        ),
        homework="""# 第 24 周作业

1. 补全运行目录中的毕业报告，明确经济逻辑、失败实验与实盘边界。
2. 请第三方按 `reproduction.md` 在独立目录复现。
3. 逐项完成 `defense_checklist.md`，保留质询与修改记录。
""",
        criteria=(
            "毕业流水线位于 week24/runs 下的唯一目录",
            "周根目录同时具备作业、验收、manifest、复现与答辩清单",
            "第三方可用固定 seed 离线复现核心结果",
        ),
    )
