"""研究配置的 dataclass 定义、YAML 加载与校验。"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Mapping, TypeVar

import yaml


@dataclass(frozen=True)
class UniverseConfig:
    """历史股票池过滤规则。"""

    min_listing_days: int = 60
    exclude_st: bool = True
    exclude_suspended: bool = True

    def validate(self) -> None:
        if self.min_listing_days < 0:
            raise ValueError("universe.min_listing_days 不能为负数")


@dataclass(frozen=True)
class FactorConfig:
    """因子计算和检验参数。"""

    amihud_window: int = 20
    ic_window: int = 60
    decay_lags: int = 12

    def validate(self) -> None:
        if self.amihud_window < 2:
            raise ValueError("factors.amihud_window 必须至少为 2")
        if self.ic_window < 2:
            raise ValueError("factors.ic_window 必须至少为 2")
        if self.decay_lags < 1:
            raise ValueError("factors.decay_lags 必须为正数")


@dataclass(frozen=True)
class DataConfig:
    source: str = "synthetic"
    n_days: int = 600
    n_assets: int = 40

    def validate(self) -> None:
        if self.source != "synthetic":
            raise ValueError("教学流水线当前仅支持 synthetic 数据源")
        if self.n_days < 100 or self.n_assets < 5:
            raise ValueError("data.n_days 至少 100，data.n_assets 至少 5")


@dataclass(frozen=True)
class PortfolioConfig:
    max_weight: float = 0.05
    max_industry_deviation: float = 0.05
    max_turnover: float = 0.30
    rebalance: str = "monthly"

    def validate(self) -> None:
        if not 0 < self.max_weight <= 1:
            raise ValueError("portfolio.max_weight 必须在 (0, 1] 内")
        if self.max_industry_deviation < 0 or self.max_turnover < 0:
            raise ValueError("行业偏离和换手上限不能为负")
        if self.rebalance != "monthly":
            raise ValueError("教学流水线当前仅支持 monthly 调仓")


@dataclass(frozen=True)
class BacktestSettings:
    commission: float = 0.0003
    stamp_duty: float = 0.0005
    slippage: float = 0.0005
    execution_lag: int = 1

    def validate(self) -> None:
        if min(self.commission, self.stamp_duty, self.slippage) < 0:
            raise ValueError("回测费用不能为负")
        if self.execution_lag < 1:
            raise ValueError("backtest.execution_lag 至少为 1")


@dataclass(frozen=True)
class ValidationConfig:
    min_train_dates: int = 180
    train_window_dates: int = 360
    label_horizon_dates: int = 20
    retrain_every: int = 20
    model: str = "ridge"
    purge_dates: int = 20
    embargo_dates: int = 5

    def validate(self) -> None:
        if self.min_train_dates < 20 or self.train_window_dates < self.min_train_dates:
            raise ValueError("验证训练窗口设置无效")
        if min(self.label_horizon_dates, self.purge_dates, self.embargo_dates) < 0:
            raise ValueError("标签、purge 和 embargo 日期不能为负")
        if self.retrain_every < 1:
            raise ValueError("validation.retrain_every 必须为正数")


@dataclass(frozen=True)
class ExecutionSettings:
    initial_cash: float = 1_000_000.0
    lot_size: int = 100
    max_volume_participation: float = 0.10
    impact_coefficient: float = 0.10

    def validate(self) -> None:
        if self.initial_cash <= 0 or self.lot_size <= 0:
            raise ValueError("初始现金和整数手必须为正数")
        if not 0 < self.max_volume_participation <= 1:
            raise ValueError("成交量参与率必须在 (0, 1] 内")
        if self.impact_coefficient < 0:
            raise ValueError("冲击系数不能为负")


@dataclass(frozen=True)
class MonitorSettings:
    max_drawdown: float = 0.20
    max_psi: float = 0.25

    def validate(self) -> None:
        if not 0 <= self.max_drawdown <= 1 or self.max_psi < 0:
            raise ValueError("监控阈值无效")


@dataclass(frozen=True)
class ResearchConfig:
    """完整、可复现的 PIT 因子研究配置。"""

    start_date: str
    end_date: str
    seed: int = 7
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    factors: FactorConfig = field(default_factory=FactorConfig)
    data: DataConfig = field(default_factory=DataConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    backtest: BacktestSettings = field(default_factory=BacktestSettings)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    execution: ExecutionSettings = field(default_factory=ExecutionSettings)
    monitor: MonitorSettings = field(default_factory=MonitorSettings)

    def validate(self) -> None:
        import pandas as pd

        try:
            start = pd.Timestamp(self.start_date)
            end = pd.Timestamp(self.end_date)
        except (TypeError, ValueError) as exc:
            raise ValueError("start_date 和 end_date 必须是有效日期") from exc
        if start > end:
            raise ValueError("start_date 不能晚于 end_date")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise ValueError("seed 必须是整数")
        self.universe.validate()
        self.factors.validate()
        self.data.validate()
        self.portfolio.validate()
        self.backtest.validate()
        self.validation.validate()
        self.execution.validate()
        self.monitor.validate()


_T = TypeVar("_T")


def _strict_dataclass(cls: type[_T], values: Mapping[str, Any], section: str) -> _T:
    allowed = {item.name for item in fields(cls)}
    unknown = set(values).difference(allowed)
    if unknown:
        raise ValueError(f"{section} 含未知配置项: {sorted(unknown)}")
    return cls(**values)


def config_from_dict(values: Mapping[str, Any]) -> ResearchConfig:
    """从字典构建配置，并拒绝未知字段和非法参数。"""

    if not isinstance(values, Mapping):
        raise ValueError("配置根节点必须是映射")
    root = dict(values)
    sections: tuple[tuple[str, type[Any]], ...] = (
        ("universe", UniverseConfig),
        ("factors", FactorConfig),
        ("data", DataConfig),
        ("portfolio", PortfolioConfig),
        ("backtest", BacktestSettings),
        ("validation", ValidationConfig),
        ("execution", ExecutionSettings),
        ("monitor", MonitorSettings),
    )
    parsed: dict[str, Any] = {}
    for name, section_type in sections:
        values_for_section = root.pop(name, {})
        if not isinstance(values_for_section, Mapping):
            raise ValueError(f"{name} 必须是映射")
        parsed[name] = _strict_dataclass(section_type, values_for_section, name)
    config = _strict_dataclass(
        ResearchConfig,
        {**root, **parsed},
        "配置根节点",
    )
    config.validate()
    return config


def load_config(path: str | Path) -> ResearchConfig:
    """安全加载 YAML 研究配置并执行完整校验。"""

    with Path(path).open("r", encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if values is None:
        raise ValueError("配置文件不能为空")
    return config_from_dict(values)
