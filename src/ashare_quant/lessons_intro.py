"""第 2–5 周可执行入门课程；全部实验使用固定种子的离线合成数据。"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .backtest import BacktestConfig, BacktestResult, run_backtest
from .data import make_synthetic_market, to_wide
from .lesson_io import (
    prepare_lesson_output,
    write_acceptance,
    write_homework_if_safe,
    write_manifest,
)
from .lessons import LessonResult
from .metrics import performance_summary, wealth_index


def _market(*, quick: bool, seed: int, assets: int = 6) -> pd.DataFrame:
    """返回足够覆盖 60 日窗口、但 quick 模式仍可快速运行的合成行情。"""
    return make_synthetic_market(
        n_days=100 if quick else 320,
        n_assets=assets,
        seed=seed,
    )


def _long_only(signal: pd.DataFrame) -> pd.DataFrame:
    """把布尔信号逐日归一化为不超过 100% 的多头权重。"""
    selected = signal.fillna(False).astype(float)
    counts = selected.sum(axis=1).replace(0.0, np.nan)
    return selected.div(counts, axis=0).fillna(0.0)


def _strategy_inputs(
    *, quick: bool, seed: int = 303
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.Series]:
    market = _market(quick=quick, seed=seed)
    prices = to_wide(market)
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    equal_weight_returns = asset_returns.mean(axis=1).rename("equal_weight_benchmark")

    initial_shares = (1.0 / len(prices.columns)) / prices.iloc[0]
    buy_hold_value = prices.mul(initial_shares, axis=1).sum(axis=1)
    buy_hold_returns = buy_hold_value.pct_change(fill_method=None).fillna(0.0)

    strategies = {
        "buy_and_hold": pd.DataFrame(
            np.full(
                (len(prices), len(prices.columns)),
                1.0 / len(prices.columns),
            ),
            index=prices.index,
            columns=prices.columns,
        ),
        "ma_20_60": _long_only(prices.rolling(20).mean() > prices.rolling(60).mean()),
        "momentum_60": _long_only(prices.pct_change(60, fill_method=None) > 0.0),
        "reversal_5": _long_only(prices.pct_change(5, fill_method=None) < 0.0),
    }
    # 买入持有的真实漂移收益单独保留；其余策略由统一时间线回测。
    strategies["buy_and_hold"].attrs["returns"] = buy_hold_returns
    return prices, strategies, equal_weight_returns


def _run_strategies(
    prices: pd.DataFrame,
    targets: dict[str, pd.DataFrame],
    *,
    config: BacktestConfig | None = None,
) -> tuple[pd.DataFrame, dict[str, BacktestResult]]:
    results = {
        name: run_backtest(prices, weights, config=config)
        for name, weights in targets.items()
        if name != "buy_and_hold"
    }
    returns = {
        "buy_and_hold": targets["buy_and_hold"].attrs["returns"],
        **{name: result.returns for name, result in results.items()},
    }
    return pd.DataFrame(returns), results


def run_week_02(
    output: str | Path = "artifacts/learning/week02",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """生成字段字典和 A 股交易机制案例。"""
    del force
    destination = prepare_lesson_output(output)

    fields = pd.DataFrame(
        [
            ("date", "交易日", "交易所日历", "盘前已知", "不可用自然日替代"),
            ("symbol", "证券代码", "交易所/主数据", "上市前可知", "代码需含市场后缀"),
            ("open", "开盘价", "日行情", "开盘后", "当日开盘前不可用"),
            ("high", "最高价", "日行情", "收盘后", "盘中策略需使用逐笔数据"),
            ("low", "最低价", "日行情", "收盘后", "盘中策略需使用逐笔数据"),
            ("close", "收盘价", "日行情", "收盘后", "信号最早下一交易日成交"),
            ("volume", "成交量（股）", "日行情", "收盘后", "注意手与股的单位"),
            ("adjust_factor", "复权因子", "公司行动/行情商", "事件生效后", "不得提前使用"),
            ("suspended", "停牌标志", "交易状态", "盘前或实时", "停牌期间不可成交"),
            ("is_st", "ST 标志", "证券主数据", "公告生效后", "影响涨跌幅限制"),
            ("limit_up", "涨停状态", "价格与规则计算", "触及后实时", "涨停不等于可以买到"),
            ("limit_down", "跌停状态", "价格与规则计算", "触及后实时", "跌停不等于可以卖出"),
            ("list_date", "上市日期", "证券主数据", "上市前公告后", "避免上市前进入股票池"),
            ("delist_date", "退市日期", "证券主数据", "公告后", "避免幸存者偏差"),
        ],
        columns=["field", "meaning", "source", "available_at", "research_note"],
    )
    fields.to_csv(destination / "field_dictionary.csv", index=False)

    cases = pd.DataFrame(
        [
            ("T+1", "当日买入后当日卖出", "拒绝卖出", "持仓需按可卖数量分层"),
            ("100股整数手", "用资金除价格得到 253 股买单", "下取整为 200 股", "卖出零股另行处理"),
            ("主板涨跌幅", "普通主板股票前收盘 10 元", "通常 10% 限制", "IPO 等情形例外"),
            ("创业板/科创板", "普通股票前收盘 10 元", "通常 20% 限制", "必须按板块和日期匹配规则"),
            ("ST", "ST 股票前收盘 10 元", "使用对应 ST 限制", "规则可能变化，不硬编码历史"),
            ("涨停", "策略发出买单且封板", "保守拒绝买入", "触及涨停不保证成交"),
            ("跌停", "策略发出卖单且封板", "保守拒绝卖出", "不得假设能按跌停价退出"),
            ("停牌", "停牌日有调仓信号", "买卖均拒绝", "持仓仍保留到复牌"),
            ("除权除息", "现金分红或拆股", "使用点时复权因子", "避免把除权缺口当亏损"),
            ("退市", "历史股票退出样本", "保留退市前历史", "禁止只使用当前成分股"),
        ],
        columns=["mechanism", "scenario", "conservative_treatment", "backtest_requirement"],
    )
    cases.to_csv(destination / "mechanism_cases.csv", index=False)

    counts = (
        fields.assign(
            availability=fields["available_at"].map(
                {
                    "盘前已知": "known pre-market",
                    "上市前可知": "known before listing",
                    "开盘后": "after open",
                    "收盘后": "after close",
                    "事件生效后": "after effective date",
                    "盘前或实时": "pre-market / real-time",
                    "触及后实时": "real-time after hit",
                    "上市前公告后": "after listing notice",
                    "公告后": "after notice",
                }
            )
        )
        .groupby("availability")
        .size()
        .sort_values()
    )
    figure, axis = plt.subplots(figsize=(9, 4.5))
    counts.plot.barh(ax=axis, color="#4472C4", title="Week 02: data availability")
    axis.set_xlabel("number of fields")
    figure.tight_layout()
    figure.savefig(destination / "market_mechanisms.png", dpi=140)
    plt.close(figure)

    (destination / "ashare_mechanisms.md").write_text(
        """# A 股机制实验说明

字段“存在于最终日线文件”不代表它在决策时已经可用。请始终按 `available_at`
约束信号时间。回测采用保守成交规则：涨停拒绝买入、跌停拒绝卖出、停牌拒绝
双向交易；T+1 和整数手约束应在订单层验证。规则会随板块、日期和证券状态变化，
生产研究必须使用带生效日期的规则表，不能把今天的规则套到全部历史。
""",
        encoding="utf-8",
    )
    write_homework_if_safe(
        destination,
        """# 第 2 周作业

1. 为 `field_dictionary.csv` 每个字段补充你实际数据源的发布时间证据。
2. 分别解释 T+1、整数手、涨跌停和停牌会怎样改变回测成交。
3. 找一个历史规则变更案例，写明生效日期，禁止用当前规则回填历史。
""",
    )
    write_acceptance(
        destination,
        week=2,
        criteria=(
            "字段字典包含来源、发布时间或可用时点",
            "能解释涨跌停价格为何不代表一定成交",
            "能识别复权、上市退市和当前成分股带来的偏差",
        ),
    )
    artifacts = (
        "field_dictionary.csv",
        "mechanism_cases.csv",
        "market_mechanisms.png",
        "ashare_mechanisms.md",
        "homework.md",
        "acceptance.json",
    )
    write_manifest(destination, week=2, quick=quick, artifacts=artifacts)
    summary = pd.Series(
        {"field_count": len(fields), "mechanism_count": len(cases)}, name="value"
    )
    return LessonResult(week=2, output=destination, summary=summary)


def run_week_03(
    output: str | Path = "artifacts/learning/week03",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """比较买入持有、均线、动量、反转策略，并展示信号成交时间线。"""
    del force
    destination = prepare_lesson_output(output)
    prices, targets, benchmark = _strategy_inputs(quick=quick)
    returns, results = _run_strategies(prices, targets)
    returns["equal_weight_benchmark"] = benchmark
    returns.to_csv(destination / "strategy_returns.csv", index_label="date")

    metrics = pd.DataFrame(
        {
            name: performance_summary(series, benchmark_returns=benchmark)
            for name, series in returns.items()
            if name != "equal_weight_benchmark"
        }
    ).T
    metrics.to_csv(destination / "strategy_metrics.csv", index_label="strategy")

    figure, axis = plt.subplots(figsize=(10, 5.5))
    returns.apply(wealth_index).plot(ax=axis, title="Week 03: strategy wealth")
    axis.set_ylabel("wealth")
    figure.tight_layout()
    figure.savefig(destination / "strategy_comparison.png", dpi=140)
    plt.close(figure)

    (destination / "execution_timeline.md").write_text(
        """# 信号与成交时间线

| 时点 | 已知信息 | 动作 |
|---|---|---|
| T 日收盘前 | 仅有 T-1 及更早完整日线 | 保持旧持仓并承受 T 日收益 |
| T 日收盘后 | T 日收盘价和日线完整 | 计算 20/60 均线、60 日动量、5 日反转信号 |
| T+1 日收盘 | T 日信号已知 | 尝试成交；若涨跌停或停牌则拒单 |
| T+2 日 | T+1 收盘后持仓 | 新持仓开始贡献完整日收益 |

`run_backtest` 强制 `execution_lag >= 1`。这条时间线避免使用同一收盘价同时
生成信号并假设已按该收盘价成交。买入持有与同股票池每日等权基准均被完整报告，
没有仅挑选表现最好的策略。
""",
        encoding="utf-8",
    )
    write_homework_if_safe(
        destination,
        """# 第 3 周作业

1. 画出四种策略相对等权基准的超额净值。
2. 逐行解释 `execution_timeline.md`，并把信号整体提前一天观察结果。
3. 比较买入持有和每日等权基准为何不完全相同。
4. 不调参，解释均线、动量和反转策略的经济假设。
""",
    )
    write_acceptance(
        destination,
        week=3,
        criteria=(
            "报告买入持有、20/60 均线、60 日动量和短期反转的全部结果",
            "能画出并解释信号日、成交日和持仓收益日",
            "能说明买入持有与每日等权再平衡基准的差异",
        ),
    )
    artifacts = (
        "strategy_returns.csv",
        "strategy_metrics.csv",
        "strategy_comparison.png",
        "execution_timeline.md",
        "homework.md",
        "acceptance.json",
    )
    write_manifest(destination, week=3, quick=quick, artifacts=artifacts)
    summary = metrics["total_return"].rename("total_return")
    summary.loc["rejected_turnover"] = sum(
        result.rejected_turnover.sum() for result in results.values()
    )
    return LessonResult(week=3, output=destination, summary=summary)


def run_week_04(
    output: str | Path = "artifacts/learning/week04",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """运行佣金、滑点和印花税的 3×3×3 成本网格。"""
    del force
    destination = prepare_lesson_output(output)
    prices, targets, _ = _strategy_inputs(quick=quick, seed=404)
    target = targets["ma_20_60"]
    base = {"commission": 0.0003, "slippage": 0.0005, "stamp_duty": 0.0005}
    rows: list[dict[str, float | str]] = []
    for commission_label, commission_factor in (("zero", 0.0), ("base", 1.0), ("double", 2.0)):
        for slippage_label, slippage_factor in (("zero", 0.0), ("base", 1.0), ("double", 2.0)):
            for stamp_label, stamp_factor in (("zero", 0.0), ("base", 1.0), ("double", 2.0)):
                cfg = BacktestConfig(
                    commission=base["commission"] * commission_factor,
                    slippage=base["slippage"] * slippage_factor,
                    stamp_duty=base["stamp_duty"] * stamp_factor,
                )
                result = run_backtest(prices, target, config=cfg)
                stats = performance_summary(result.returns, turnover=result.turnover)
                rows.append(
                    {
                        "commission_level": commission_label,
                        "slippage_level": slippage_label,
                        "stamp_duty_level": stamp_label,
                        "commission": cfg.commission,
                        "slippage": cfg.slippage,
                        "stamp_duty": cfg.stamp_duty,
                        "total_cost": float(result.costs.sum()),
                        "total_return": float(stats["total_return"]),
                        "annualized_return": float(stats["annualized_return"]),
                        "sharpe": float(stats["sharpe"]),
                        "max_drawdown": float(stats["max_drawdown"]),
                    }
                )
    grid = pd.DataFrame(rows).sort_values(
        ["commission", "slippage", "stamp_duty"]
    ).reset_index(drop=True)
    grid.to_csv(destination / "cost_grid.csv", index=False)

    plot_data = grid.groupby(["commission_level", "slippage_level"], sort=False)[
        "total_return"
    ].mean().unstack()
    figure, axis = plt.subplots(figsize=(8, 5))
    plot_data.plot.bar(ax=axis, title="Week 04: mean return across stamp-duty levels")
    axis.set_ylabel("total return")
    axis.legend(title="slippage")
    figure.tight_layout()
    figure.savefig(destination / "cost_sensitivity.png", dpi=140)
    plt.close(figure)

    worst = grid.loc[grid["total_return"].idxmin()]
    best = grid.loc[grid["total_return"].idxmax()]
    (destination / "cost_analysis.md").write_text(
        f"""# 成本敏感性说明

本实验预先约定 0、基准、2 倍三档佣金、滑点和印花税，共 {len(grid)} 组，
全部写入 CSV，不筛掉不利结果。最高总收益为 {best['total_return']:.4f}，
最低总收益为 {worst['total_return']:.4f}。印花税只对卖出成交额收取，而佣金
和滑点作用于双边换手。合成数据只能检验成本传导流程，不能证明策略有效。
""",
        encoding="utf-8",
    )
    write_homework_if_safe(
        destination,
        """# 第 4 周作业

1. 对 27 组结果分别按佣金、滑点和印花税分组，计算边际影响。
2. 找出成本翻倍后结论反转的组合，并说明策略是否脆弱。
3. 解释为何高换手策略对成本假设更敏感。
""",
    )
    write_acceptance(
        destination,
        week=4,
        criteria=(
            "至少报告 9 组成本网格且不只挑最佳参数",
            "分别解释佣金、滑点和印花税的作用对象",
            "能判断策略结论是否对合理成本假设脆弱",
        ),
    )
    artifacts = (
        "cost_grid.csv",
        "cost_sensitivity.png",
        "cost_analysis.md",
        "homework.md",
        "acceptance.json",
    )
    write_manifest(destination, week=4, quick=quick, artifacts=artifacts)
    summary = pd.Series(
        {
            "grid_size": len(grid),
            "best_total_return": float(best["total_return"]),
            "worst_total_return": float(worst["total_return"]),
            "return_spread": float(best["total_return"] - worst["total_return"]),
        },
        name="value",
    )
    return LessonResult(week=4, output=destination, summary=summary)


def run_week_05(
    output: str | Path = "artifacts/learning/week05",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """演示涨跌停/停牌拒单和未来收益泄漏反例。"""
    del force
    destination = prepare_lesson_output(output)

    dates = pd.bdate_range("2024-01-02", periods=6)
    symbols = ["LIMIT_UP", "LIMIT_DOWN", "SUSPENDED"]
    prices = pd.DataFrame(
        [[10.0, 10.0, 10.0], [10.1, 9.9, 10.0], [11.11, 8.91, 10.0],
         [11.0, 9.0, 10.0], [10.9, 9.1, 10.1], [11.0, 9.2, 10.2]],
        index=dates,
        columns=symbols,
    )
    targets = pd.DataFrame(0.0, index=dates, columns=symbols)
    targets.loc[dates[0], ["LIMIT_DOWN", "SUSPENDED"]] = 0.5
    targets.loc[dates[1], "LIMIT_UP"] = 1.0
    limit_up = pd.DataFrame(False, index=dates, columns=symbols)
    limit_down = limit_up.copy()
    suspended = limit_up.copy()
    limit_up.loc[dates[2], "LIMIT_UP"] = True
    limit_down.loc[dates[2], "LIMIT_DOWN"] = True
    suspended.loc[dates[2], "SUSPENDED"] = True
    blocked = run_backtest(
        prices,
        targets,
        limit_up=limit_up,
        limit_down=limit_down,
        suspended=suspended,
    )
    rejection = pd.DataFrame(
        {
            "date": dates,
            "limit_up": limit_up.any(axis=1).to_numpy(),
            "limit_down": limit_down.any(axis=1).to_numpy(),
            "suspended": suspended.any(axis=1).to_numpy(),
            "requested_target_gross": targets.sum(axis=1).to_numpy(),
            "executed_turnover": blocked.turnover.to_numpy(),
            "rejected_turnover": blocked.rejected_turnover.to_numpy(),
        }
    )
    rejection["status"] = np.where(
        rejection["rejected_turnover"] > 0.0, "REJECTED", "NO_REJECTION"
    )
    rejection.to_csv(destination / "rejected_orders.csv", index=False)

    market = _market(quick=quick, seed=505, assets=8)
    leak_prices = to_wide(market)
    past = leak_prices.pct_change(20, fill_method=None)
    future_earned = leak_prices.shift(-2).div(leak_prices.shift(-1)).sub(1.0)
    honest_targets = past.eq(past.max(axis=1), axis=0).astype(float)
    leaked_targets = future_earned.eq(future_earned.max(axis=1), axis=0).astype(float)
    honest = run_backtest(leak_prices, honest_targets)
    leaked = run_backtest(leak_prices, leaked_targets)
    comparison_returns = pd.DataFrame(
        {"honest_past_momentum": honest.returns, "leaked_future_winner": leaked.returns}
    )
    comparison_returns.to_csv(destination / "leakage_returns.csv", index_label="date")
    leakage = pd.DataFrame(
        {
            "honest_past_momentum": performance_summary(honest.returns),
            "leaked_future_winner": performance_summary(leaked.returns),
        }
    ).T
    leakage.to_csv(destination / "leakage_comparison.csv", index_label="experiment")

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    rejection.set_index("date")["rejected_turnover"].plot.bar(
        ax=axes[0], color="#C44E52", title="Rejected turnover"
    )
    comparison_returns.apply(wealth_index).plot(
        ax=axes[1], title="Honest vs leaked wealth"
    )
    axes[1].set_ylabel("wealth")
    figure.tight_layout()
    figure.savefig(destination / "execution_and_leakage.png", dpi=140)
    plt.close(figure)

    (destination / "execution_and_leakage.md").write_text(
        """# 拒单与未来泄漏反例

在事件日，涨停证券的买入、跌停证券的卖出和停牌证券的双向订单均应保守拒绝，
未成交目标不能伪装成成交持仓。`rejected_orders.csv` 明确记录拒绝换手。

泄漏实验故意在信号日查看策略实际持有期的未来收益，并选择未来赢家，因此结果
异常乐观。对照组只使用过去 20 日收益。泄漏策略不是可交易策略，保留它仅用于
建立自动反例：特征可用时点、标签区间、信号日、成交日必须逐项审计。
""",
        encoding="utf-8",
    )
    write_homework_if_safe(
        destination,
        """# 第 5 周作业

1. 指出三个拒单案例在目标权重、成交权重上的差异。
2. 画出未来泄漏反例的数据时间线，圈出决策时未知的数据。
3. 删除未来字段后重跑，并解释收益为何显著回落。
4. 写一个测试，确保执行滞后不能设为 0。
""",
    )
    write_acceptance(
        destination,
        week=5,
        criteria=(
            "涨停买入、跌停卖出和停牌订单均产生可观察拒单",
            "能准确指出未来收益信号使用了决策时未知的数据",
            "未来泄漏反例与无泄漏对照被同时完整保留",
        ),
    )
    artifacts = (
        "rejected_orders.csv",
        "leakage_returns.csv",
        "leakage_comparison.csv",
        "execution_and_leakage.png",
        "execution_and_leakage.md",
        "homework.md",
        "acceptance.json",
    )
    write_manifest(destination, week=5, quick=quick, artifacts=artifacts)
    summary = pd.Series(
        {
            "rejected_turnover": float(blocked.rejected_turnover.sum()),
            "honest_total_return": float(leakage.loc["honest_past_momentum", "total_return"]),
            "leaked_total_return": float(leakage.loc["leaked_future_winner", "total_return"]),
        },
        name="value",
    )
    return LessonResult(week=5, output=destination, summary=summary)
