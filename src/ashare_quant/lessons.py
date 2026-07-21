"""可执行课程实验。每次只暴露当前一课，避免被完整项目淹没。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .data import make_synthetic_market
from .lesson_io import (
    prepare_lesson_output,
    write_acceptance,
    write_homework_if_safe,
    write_manifest,
)
from .metrics import drawdown, performance_summary, wealth_index


@dataclass(frozen=True)
class LessonResult:
    week: int
    output: Path
    summary: pd.Series


def run_week_01(
    output: str | Path = "artifacts/learning/week01",
    force: bool = False,
    quick: bool = False,
) -> LessonResult:
    """运行第一周实验：从价格计算收益、复利净值和回撤。"""
    destination = prepare_lesson_output(output)

    n_days = 60 if quick else 252
    market = make_synthetic_market(n_days=n_days, n_assets=1, seed=1)
    prices = market.set_index("date")["close"].rename("close")
    returns = prices.pct_change(fill_method=None).fillna(0.0).rename("return")
    wealth = wealth_index(returns).rename("wealth")
    underwater = drawdown(returns).rename("drawdown")
    summary = performance_summary(returns)

    pd.concat([prices, returns, wealth, underwater], axis=1).to_csv(
        destination / "daily_data.csv", index_label="date"
    )
    summary.to_csv(destination / "metrics.csv", header=True)

    figure, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    wealth.plot(ax=axes[0], title="Week 01: compounded wealth")
    axes[0].set_ylabel("wealth")
    underwater.plot(ax=axes[1], color="firebrick", title="Drawdown")
    axes[1].set_ylabel("drawdown")
    figure.tight_layout()
    figure.savefig(destination / "wealth_and_drawdown.png", dpi=150)
    plt.close(figure)

    write_homework_if_safe(
        destination,
        """# 第 1 周作业

请不要先看源码答案，直接基于 `daily_data.csv` 和 `metrics.csv` 完成。

## 必做

1. 用自己的 NumPy/pandas 代码重新计算累计净值，并与 `wealth` 列比较。
2. 找出最大回撤的峰值日、谷底日和恢复日。
3. 将每日收益顺序随机打乱 100 次：总收益是否改变？最大回撤是否改变？为什么？
4. 回答：算术平均日收益为什么不能直接乘以 252 得到长期复利收益？

## 实验记录

- 我使用的数据区间：
- 年化收益：
- 年化波动：
- Sharpe：
- 最大回撤：
- 我的关键结论：
- 我仍不理解的问题：

完成后，把本文件、你的代码和图表交给导师审阅，再进入第 2 周。
""",
    )
    write_acceptance(
        destination,
        week=1,
        criteria=(
            "提交 homework.md 和自己的计算代码",
            "能解释总收益相同但路径不同时最大回撤为何不同",
        ),
    )
    write_manifest(
        destination,
        week=1,
        quick=quick,
        artifacts=(
            "daily_data.csv",
            "metrics.csv",
            "wealth_and_drawdown.png",
            "homework.md",
            "acceptance.json",
        ),
    )
    return LessonResult(week=1, output=destination, summary=summary)
