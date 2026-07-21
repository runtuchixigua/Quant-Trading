"""24 周课程注册表与延迟 runner 解析。"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Callable


LessonRunner = Callable[..., object]


class LessonRunnerUnavailable(LookupError):
    """课程已注册，但对应 runner 尚未实现。"""


@dataclass(frozen=True)
class Lesson:
    week: int
    title: str
    phase: str
    runner: str

    def resolve_runner(self) -> LessonRunner:
        """仅在执行课程时导入 runner。"""
        module_name, separator, attribute = self.runner.partition(":")
        if not separator:
            raise LessonRunnerUnavailable(
                f"第 {self.week} 周 runner 引用无效：{self.runner!r}"
            )
        try:
            module = import_module(module_name)
            candidate = getattr(module, attribute)
        except (ImportError, AttributeError) as exc:
            raise LessonRunnerUnavailable(
                f"第 {self.week} 周“{self.title}”尚未实现 "
                f"(runner: {self.runner})。目前只能运行已有课程。"
            ) from exc
        if not callable(candidate):
            raise LessonRunnerUnavailable(
                f"第 {self.week} 周 runner 不可调用：{self.runner}"
            )
        return candidate


_TITLES = (
    "收益与风险",
    "A 股市场机制",
    "无未来函数回测",
    "交易成本与成交约束",
    "回测偏差与稳健性",
    "因子构造与预处理",
    "IC 与分组检验",
    "组合构建与风险约束",
    "横截面机器学习",
    "Walk-Forward 与标签隔离",
    "模拟盘与执行",
    "阶段验收与研究报告",
    "Point-in-Time 数据工程与可追溯性",
    "历史股票池、退市与选择偏差",
    "事件研究与公告效应",
    "多因子诊断与冗余控制",
    "风险模型与收益归因",
    "约束组合优化与估计误差",
    "嵌套验证、过拟合与统计可信度",
    "市场状态、压力测试与尾部风险",
    "机器学习稳定性、漂移与解释",
    "执行建模、冲击成本与策略容量",
    "组合监控、模型治理与应急演练",
    "毕业研究、独立复现与答辩",
)


def _phase(week: int) -> str:
    if week <= 2:
        return "基础"
    if week <= 5:
        return "回测"
    if week <= 8:
        return "因子与组合"
    if week <= 10:
        return "机器学习"
    if week <= 12:
        return "模拟盘"
    if week <= 15:
        return "数据与事件"
    if week <= 18:
        return "因子、风险与优化"
    if week <= 21:
        return "稳健验证与机器学习"
    return "执行、治理与毕业研究"


def _runner_module(week: int) -> str:
    if week == 1:
        return "ashare_quant.lessons"
    if week <= 5:
        return "ashare_quant.lessons_intro"
    if week <= 12:
        return "ashare_quant.lessons_core"
    if week <= 18:
        return "ashare_quant.lessons_advanced"
    return "ashare_quant.lessons_robust"


LESSONS: tuple[Lesson, ...] = tuple(
    Lesson(
        week=week,
        title=title,
        phase=_phase(week),
        runner=f"{_runner_module(week)}:run_week_{week:02d}",
    )
    for week, title in enumerate(_TITLES, start=1)
)
LESSON_REGISTRY: dict[int, Lesson] = {lesson.week: lesson for lesson in LESSONS}


def get_lesson(week: int) -> Lesson:
    """返回指定周课程，周数必须在 1–24。"""
    try:
        return LESSON_REGISTRY[week]
    except KeyError as exc:
        raise ValueError(f"week 必须在 1 到 24 之间，收到 {week}") from exc


def resolve_runner(week: int) -> LessonRunner:
    """延迟解析指定周的 runner。"""
    return get_lesson(week).resolve_runner()
