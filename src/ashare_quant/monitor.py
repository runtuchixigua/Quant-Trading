"""连续模拟盘的数据、账户、漂移与风险监控。"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MonitorConfig:
    max_drawdown: float = 0.15
    max_psi: float = 0.25
    max_data_age_days: int = 3
    cash_tolerance: float = 0.01
    share_tolerance: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.max_drawdown <= 1 or self.max_psi < 0:
            raise ValueError("回撤阈值须在 [0,1]，PSI 阈值不能为负")
        if self.max_data_age_days < 0 or min(self.cash_tolerance, self.share_tolerance) < 0:
            raise ValueError("数据时效和对账容差不能为负")


@dataclass(frozen=True)
class ReconciliationResult:
    matched: bool
    cash_difference: float
    share_differences: dict[str, int]


@dataclass(frozen=True)
class MonitorDecision:
    should_stop: bool
    reasons: tuple[str, ...] = ()
    metrics: dict[str, float] = field(default_factory=dict)


def validate_market_data(
    frame: pd.DataFrame,
    *,
    as_of: pd.Timestamp | str | None = None,
    max_age_days: int = 3,
    required_columns: tuple[str, ...] = ("date", "symbol", "close", "volume"),
) -> None:
    """发现缺列、重复、非法值或数据过期时立即抛错。"""
    missing = set(required_columns).difference(frame.columns)
    if missing:
        raise ValueError(f"行情缺少字段: {sorted(missing)}")
    if frame.empty:
        raise ValueError("行情为空")
    dates = pd.to_datetime(frame["date"], errors="coerce")
    if dates.isna().any():
        raise ValueError("date 包含无效日期")
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("行情存在重复的 (date, symbol)")
    close = pd.to_numeric(frame["close"], errors="coerce")
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    if close.isna().any() or (~np.isfinite(close)).any() or (close <= 0).any():
        raise ValueError("close 必须为有限正数")
    if volume.isna().any() or (~np.isfinite(volume)).any() or (volume < 0).any():
        raise ValueError("volume 必须为有限非负数")
    if frame["symbol"].isna().any() or (frame["symbol"].astype(str).str.len() == 0).any():
        raise ValueError("symbol 不能为空")
    if as_of is not None:
        current = pd.Timestamp(as_of)
        latest = dates.max()
        current = current.tz_localize(None) if current.tzinfo else current
        latest = latest.tz_localize(None) if latest.tzinfo else latest
        if current.normalize() < latest.normalize():
            raise ValueError("as_of 早于最新数据日期")
        if (current.normalize() - latest.normalize()).days > max_age_days:
            raise ValueError("行情已过期")


def reconcile_account(
    expected_holdings: pd.Series,
    actual_holdings: pd.Series,
    expected_cash: float,
    actual_cash: float,
    *,
    cash_tolerance: float = 0.01,
    share_tolerance: int = 0,
) -> ReconciliationResult:
    """对账策略账本与模拟账户的持仓和现金。"""
    symbols = expected_holdings.index.union(actual_holdings.index)
    expected = expected_holdings.reindex(symbols).fillna(0).astype("int64")
    actual = actual_holdings.reindex(symbols).fillna(0).astype("int64")
    differences = (actual - expected).astype(int)
    material = differences[differences.abs() > share_tolerance]
    cash_difference = float(actual_cash - expected_cash)
    matched = material.empty and abs(cash_difference) <= cash_tolerance
    return ReconciliationResult(
        matched=matched,
        cash_difference=cash_difference,
        share_differences={str(key): int(value) for key, value in material.items()},
    )


def population_stability_index(
    expected: pd.Series | np.ndarray,
    actual: pd.Series | np.ndarray,
    *,
    bins: int = 10,
    epsilon: float = 1e-6,
) -> float:
    """用基准样本分位点计算 PSI；值越大表示分布漂移越明显。"""
    expected_values = np.asarray(expected, dtype=float)
    actual_values = np.asarray(actual, dtype=float)
    expected_values = expected_values[np.isfinite(expected_values)]
    actual_values = actual_values[np.isfinite(actual_values)]
    if expected_values.size == 0 or actual_values.size == 0:
        raise ValueError("PSI 输入不能是空或全非有限值")
    if bins < 2:
        raise ValueError("bins 至少为 2")
    edges = np.unique(np.quantile(expected_values, np.linspace(0, 1, bins + 1)))
    if edges.size < 2:
        return 0.0 if np.allclose(actual_values, expected_values[0]) else float("inf")
    edges[0], edges[-1] = -np.inf, np.inf
    expected_counts = np.histogram(expected_values, bins=edges)[0]
    actual_counts = np.histogram(actual_values, bins=edges)[0]
    expected_ratio = np.clip(expected_counts / expected_counts.sum(), epsilon, None)
    actual_ratio = np.clip(actual_counts / actual_counts.sum(), epsilon, None)
    return float(np.sum((actual_ratio - expected_ratio) * np.log(actual_ratio / expected_ratio)))


calculate_psi = population_stability_index


def evaluate_stop_rules(
    *,
    nav_history: pd.Series,
    psi_value: float | None = None,
    reconciliation: ReconciliationResult | None = None,
    data_error: Exception | str | None = None,
    config: MonitorConfig | None = None,
) -> MonitorDecision:
    """集中评估回撤、漂移、数据异常和账户不一致停止规则。"""
    config = config or MonitorConfig()
    reasons: list[str] = []
    values = pd.to_numeric(nav_history, errors="coerce").to_numpy(dtype=float)
    if values.size == 0 or (~np.isfinite(values)).any() or (values <= 0).any():
        reasons.append("DATA_ANOMALY")
        drawdown = float("nan")
    else:
        peaks = np.maximum.accumulate(values)
        drawdown = float(np.max(1.0 - values / peaks))
        if drawdown >= config.max_drawdown:
            reasons.append("MAX_DRAWDOWN")
    if psi_value is not None:
        if not np.isfinite(psi_value):
            reasons.append("PSI_DRIFT")
        elif psi_value >= config.max_psi:
            reasons.append("PSI_DRIFT")
    if reconciliation is not None and not reconciliation.matched:
        reasons.append("ACCOUNT_MISMATCH")
    if data_error is not None:
        reasons.append("DATA_ANOMALY")
    reasons = list(dict.fromkeys(reasons))
    metrics = {"max_drawdown": drawdown}
    if psi_value is not None:
        metrics["psi"] = float(psi_value)
    return MonitorDecision(bool(reasons), tuple(reasons), metrics)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> str:
    """输出单行 JSON 结构化日志，并返回文本便于测试和归档。"""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    text = json.dumps(payload, ensure_ascii=False, default=_json_default, sort_keys=True)
    logger.info(text)
    return text


def decision_to_dict(decision: MonitorDecision) -> dict[str, Any]:
    return asdict(decision)


def _json_default(value: Any) -> str:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    return str(value)
