"""面向时间序列策略研究的稳健验证工具。

本模块刻意把最终测试集、模型选择集和训练集分开；所有日期切分均以“日期组”
为单位，横截面同一天的样本不会被拆到不同集合。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import product
from math import e
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

from ashare_quant.metrics import annualized_return, max_drawdown, sharpe_ratio


def _date_values(data: Any, groups: Sequence[Any] | None = None) -> pd.Index:
    if groups is not None:
        values = pd.Index(groups)
    elif isinstance(data, (pd.DataFrame, pd.Series)):
        index = data.index
        if isinstance(index, pd.MultiIndex):
            if "date" not in index.names:
                raise ValueError("MultiIndex 必须包含名为 date 的层级")
            values = pd.Index(index.get_level_values("date"))
        else:
            values = pd.Index(index)
    else:
        values = pd.Index(data)
    if values.hasnans:
        raise ValueError("日期不能包含缺失值")
    return values


@dataclass(frozen=True)
class PurgedEmbargoSplit:
    """按日期扩展窗口切分，并在验证集前留出 purge 与 embargo 间隔。

    返回值是样本行位置而非日期位置，因此可直接用于 sklearn 风格的 ``iloc``。
    默认只使用验证期之前的数据训练，比允许未来样本进入训练集的组合式切分更保守。
    """

    n_splits: int = 5
    purge_dates: int = 0
    embargo_dates: int = 0
    min_train_dates: int = 20

    def split(
        self,
        X: Any,
        y: Any | None = None,
        groups: Sequence[Any] | None = None,
    ) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        del y
        if self.n_splits < 1:
            raise ValueError("n_splits 必须至少为 1")
        if min(self.purge_dates, self.embargo_dates) < 0:
            raise ValueError("purge_dates 和 embargo_dates 不能为负数")
        if self.min_train_dates < 1:
            raise ValueError("min_train_dates 必须至少为 1")

        row_dates = _date_values(X, groups)
        unique_dates = row_dates.drop_duplicates().sort_values()
        gap = self.purge_dates + self.embargo_dates
        first_validation = self.min_train_dates + gap
        if first_validation >= len(unique_dates):
            raise ValueError("日期不足以形成首个无泄漏验证折")
        validation_blocks = np.array_split(
            np.arange(first_validation, len(unique_dates)), self.n_splits
        )
        if any(len(block) == 0 for block in validation_blocks):
            raise ValueError("日期不足以形成指定数量的验证折")

        row_array = row_dates.to_numpy()
        for block in validation_blocks:
            validation_start = int(block[0])
            train_end = validation_start - gap
            train_dates = unique_dates[:train_end]
            validation_dates = unique_dates[block]
            train_rows = np.flatnonzero(np.isin(row_array, train_dates.to_numpy()))
            validation_rows = np.flatnonzero(
                np.isin(row_array, validation_dates.to_numpy())
            )
            yield train_rows, validation_rows

    def get_n_splits(
        self,
        X: Any | None = None,
        y: Any | None = None,
        groups: Sequence[Any] | None = None,
    ) -> int:
        del X, y, groups
        return self.n_splits


def purged_embargo_split(
    dates: Sequence[Any] | pd.Index,
    *,
    n_splits: int = 5,
    purge_dates: int = 0,
    embargo_dates: int = 0,
    min_train_dates: int = 20,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """函数式入口，返回 sklearn 风格的逐折行位置。"""
    splitter = PurgedEmbargoSplit(
        n_splits=n_splits,
        purge_dates=purge_dates,
        embargo_dates=embargo_dates,
        min_train_dates=min_train_dates,
    )
    return list(splitter.split(dates))


@dataclass(frozen=True)
class TrainValidationTestSplit:
    """严格按时间排序的训练、调参与一次性最终测试协议。"""

    train_dates: pd.Index
    validation_dates: pd.Index
    final_test_dates: pd.Index
    purge_dates: int
    embargo_dates: int

    @property
    def train(self) -> pd.Index:
        return self.train_dates

    @property
    def validation(self) -> pd.Index:
        return self.validation_dates

    @property
    def final_test(self) -> pd.Index:
        return self.final_test_dates

    def as_dict(self) -> dict[str, pd.Index]:
        return {
            "train": self.train_dates,
            "validation": self.validation_dates,
            "final_test": self.final_test_dates,
        }


def train_validation_test_split(
    dates: Sequence[Any] | pd.Index,
    *,
    train_size: float = 0.6,
    validation_size: float = 0.2,
    purge_dates: int = 0,
    embargo_dates: int = 0,
) -> TrainValidationTestSplit:
    """建立固定的 train/validation/final-test 日期协议。

    ``purge_dates`` 从前一集合尾部移除，``embargo_dates`` 从后一集合开头移除。
    final-test 应只在研究规则和参数冻结后查看一次。
    """
    unique_dates = _date_values(dates).drop_duplicates().sort_values()
    if not 0 < train_size < 1 or not 0 < validation_size < 1:
        raise ValueError("train_size 和 validation_size 必须在 (0, 1) 内")
    if train_size + validation_size >= 1:
        raise ValueError("必须为 final-test 保留正比例日期")
    if min(purge_dates, embargo_dates) < 0:
        raise ValueError("purge_dates 和 embargo_dates 不能为负数")

    train_boundary = int(np.floor(len(unique_dates) * train_size))
    validation_boundary = train_boundary + int(
        np.floor(len(unique_dates) * validation_size)
    )
    train_end = train_boundary - purge_dates
    validation_start = train_boundary + embargo_dates
    validation_end = validation_boundary - purge_dates
    test_start = validation_boundary + embargo_dates
    split = TrainValidationTestSplit(
        train_dates=unique_dates[:train_end],
        validation_dates=unique_dates[validation_start:validation_end],
        final_test_dates=unique_dates[test_start:],
        purge_dates=purge_dates,
        embargo_dates=embargo_dates,
    )
    if any(len(part) == 0 for part in split.as_dict().values()):
        raise ValueError("日期或切分比例不足，应用 purge/embargo 后存在空集合")
    return split


def _expected_maximum_sharpe(n_trials: int, standard_error: float) -> float:
    """Bailey/Lopez de Prado 常用的最大 Sharpe 期望近似。"""
    if n_trials <= 1 or standard_error <= 0:
        return 0.0
    normal = NormalDist()
    gamma = 0.5772156649015329
    first = normal.inv_cdf(1.0 - 1.0 / n_trials)
    second = normal.inv_cdf(1.0 - 1.0 / (n_trials * e))
    return standard_error * ((1.0 - gamma) * first + gamma * second)


@dataclass(frozen=True)
class DeflatedSharpeResult:
    probability: float
    observed_sharpe: float
    benchmark_sharpe: float
    n_trials: int
    observations: int
    skewness: float
    kurtosis: float


def deflated_sharpe_details(
    returns: pd.Series | Sequence[float] | None = None,
    *,
    observed_sharpe: float | None = None,
    n_trials: int = 1,
    trial_sharpes: Sequence[float] | None = None,
    observations: int | None = None,
    skewness: float | None = None,
    kurtosis: float | None = None,
    periods: int = 252,
) -> DeflatedSharpeResult:
    """计算教学版 Deflated Sharpe 的概率及中间量。

    输入和输出中的 Sharpe 均按 ``periods`` 年化；公式内部转换为单期 Sharpe。
    若提供历次试验 Sharpe，则用其离散度估计选择偏差，否则使用 Sharpe 的近似
    标准误 ``1/sqrt(T)``。结果是观察到的 Sharpe 超过多重试验门槛的概率。
    """
    if n_trials < 1:
        raise ValueError("n_trials 必须至少为 1")
    clean: pd.Series | None = None
    if returns is not None:
        clean = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < 3:
            raise ValueError("Deflated Sharpe 至少需要 3 个有效收益观测")
        if observed_sharpe is None:
            observed_sharpe = sharpe_ratio(clean, periods=periods)
        observations = len(clean) if observations is None else observations
        skewness = float(clean.skew()) if skewness is None else skewness
        kurtosis = float(clean.kurt() + 3.0) if kurtosis is None else kurtosis
    if observed_sharpe is None or not np.isfinite(observed_sharpe):
        raise ValueError("必须提供有限的 observed_sharpe 或有效 returns")
    if observations is None or observations < 3:
        raise ValueError("observations 必须至少为 3")
    skewness = 0.0 if skewness is None else float(skewness)
    kurtosis = 3.0 if kurtosis is None else float(kurtosis)

    annualizer = np.sqrt(periods)
    observed_single = float(observed_sharpe) / annualizer
    if trial_sharpes is not None:
        trials = np.asarray(list(trial_sharpes), dtype=float)
        trials = trials[np.isfinite(trials)] / annualizer
        if len(trials) > 1:
            standard_error = float(trials.std(ddof=1))
        else:
            standard_error = 1.0 / np.sqrt(observations)
        effective_trials = max(n_trials, len(trials))
    else:
        standard_error = 1.0 / np.sqrt(observations)
        effective_trials = n_trials
    benchmark_single = _expected_maximum_sharpe(effective_trials, standard_error)

    variance_term = (
        1.0
        - skewness * observed_single
        + ((kurtosis - 1.0) / 4.0) * observed_single**2
    )
    if variance_term <= 0:
        raise ValueError("收益高阶矩导致 Sharpe 方差项非正")
    z_score = (observed_single - benchmark_single) * np.sqrt(observations - 1)
    z_score /= np.sqrt(variance_term)
    probability = float(NormalDist().cdf(float(z_score)))
    return DeflatedSharpeResult(
        probability=probability,
        observed_sharpe=float(observed_sharpe),
        benchmark_sharpe=float(benchmark_single * annualizer),
        n_trials=effective_trials,
        observations=observations,
        skewness=skewness,
        kurtosis=kurtosis,
    )


def deflated_sharpe_ratio(
    returns: pd.Series | Sequence[float] | None = None,
    **kwargs: Any,
) -> float:
    """返回 Deflated Sharpe 概率；详尽中间量见 ``deflated_sharpe_details``。"""
    return deflated_sharpe_details(returns, **kwargs).probability


@dataclass(frozen=True)
class ExperimentRecord:
    name: str
    sharpe: float
    observations: int
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ExperimentLog:
    """记录所有尝试，避免只把胜出参数算作一次试验。"""

    def __init__(self) -> None:
        self._records: list[ExperimentRecord] = []

    @property
    def records(self) -> tuple[ExperimentRecord, ...]:
        return tuple(self._records)

    def record(
        self,
        name: str,
        *,
        returns: pd.Series | Sequence[float] | None = None,
        sharpe: float | None = None,
        observations: int | None = None,
        metadata: Mapping[str, Any] | None = None,
        periods: int = 252,
    ) -> ExperimentRecord:
        if any(item.name == name for item in self._records):
            raise ValueError(f"试验名称已存在: {name}")
        if returns is not None:
            clean = pd.Series(returns, dtype=float).dropna()
            sharpe = sharpe_ratio(clean, periods=periods) if sharpe is None else sharpe
            observations = len(clean) if observations is None else observations
        if sharpe is None or not np.isfinite(sharpe):
            raise ValueError("必须提供可计算出有限 Sharpe 的收益或 sharpe")
        if observations is None or observations < 3:
            raise ValueError("observations 必须至少为 3")
        item = ExperimentRecord(
            name=name,
            sharpe=float(sharpe),
            observations=int(observations),
            metadata=dict(metadata or {}),
        )
        self._records.append(item)
        return item

    def to_frame(self) -> pd.DataFrame:
        rows = [
            {
                "name": item.name,
                "sharpe": item.sharpe,
                "observations": item.observations,
                **dict(item.metadata),
            }
            for item in self._records
        ]
        return pd.DataFrame(rows)

    def deflated_sharpe(
        self,
        name: str,
        returns: pd.Series | Sequence[float] | None = None,
        *,
        periods: int = 252,
    ) -> DeflatedSharpeResult:
        selected = next((item for item in self._records if item.name == name), None)
        if selected is None:
            raise KeyError(f"未记录试验: {name}")
        return deflated_sharpe_details(
            returns,
            observed_sharpe=selected.sharpe,
            observations=selected.observations,
            n_trials=len(self._records),
            trial_sharpes=[item.sharpe for item in self._records],
            periods=periods,
        )


MultipleTestingLog = ExperimentLog
ExperimentRegistry = ExperimentLog


def _performance(returns: pd.Series, periods: int = 252) -> dict[str, float]:
    clean = returns.replace([np.inf, -np.inf], np.nan).dropna()
    return {
        "observations": float(len(clean)),
        "annualized_return": annualized_return(clean, periods=periods),
        "sharpe": sharpe_ratio(clean, periods=periods),
        "max_drawdown": max_drawdown(clean),
    }


def cost_multiplier_stress(
    gross_returns: pd.Series,
    costs: pd.Series,
    multipliers: Iterable[float] = (1.0, 2.0, 3.0),
    *,
    periods: int = 252,
) -> pd.DataFrame:
    """在相同毛收益上将已实现交易成本倍增。"""
    aligned = pd.concat(
        [gross_returns.rename("gross"), costs.rename("cost")], axis=1
    ).dropna()
    rows: list[dict[str, float]] = []
    for multiplier in multipliers:
        value = float(multiplier)
        if value < 0:
            raise ValueError("成本倍数不能为负数")
        net = aligned["gross"] - value * aligned["cost"]
        rows.append({"cost_multiplier": value, **_performance(net, periods)})
    return pd.DataFrame(rows).set_index("cost_multiplier")


def _result_mapping(result: Any) -> dict[str, Any]:
    if isinstance(result, pd.Series):
        return result.to_dict()
    if isinstance(result, Mapping):
        return dict(result)
    if np.isscalar(result):
        return {"score": float(result)}
    raise TypeError("evaluator 必须返回标量、Series 或 Mapping")


def parameter_neighborhood_stress(
    evaluator: Callable[[Mapping[str, Any]], Any],
    base_params: Mapping[str, Any],
    neighborhoods: Mapping[str, Sequence[Any]],
) -> pd.DataFrame:
    """评估参数邻域的笛卡尔积；evaluator 应只读取既定验证集。"""
    unknown = set(neighborhoods) - set(base_params)
    if unknown:
        raise ValueError(f"邻域参数不在 base_params 中: {sorted(unknown)}")
    names = list(neighborhoods)
    values = [list(neighborhoods[name]) for name in names]
    if any(not choices for choices in values):
        raise ValueError("每个参数邻域至少包含一个值")
    rows: list[dict[str, Any]] = []
    for combination in product(*values):
        params = dict(base_params)
        params.update(dict(zip(names, combination, strict=True)))
        rows.append({**params, **_result_mapping(evaluator(params))})
    return pd.DataFrame(rows)


def subsample_stress(
    returns: pd.Series,
    subsamples: Mapping[str, Any] | None = None,
    *,
    n_splits: int = 3,
    periods: int = 252,
) -> pd.DataFrame:
    """按指定掩码/日期片段，或按连续等长时间块评估子样本稳定性。"""
    clean = returns.dropna().sort_index()
    selected: dict[str, pd.Series] = {}
    if subsamples is None:
        if n_splits < 2 or len(clean) < n_splits:
            raise ValueError("自动子样本至少需要 2 折且每折有观测")
        for number, positions in enumerate(np.array_split(np.arange(len(clean)), n_splits), 1):
            selected[f"subsample_{number}"] = clean.iloc[positions]
    else:
        for name, selector in subsamples.items():
            if isinstance(selector, slice):
                selected[name] = clean.loc[selector]
            else:
                mask = pd.Series(selector, index=clean.index) if not isinstance(
                    selector, pd.Series
                ) else selector.reindex(clean.index)
                selected[name] = clean.loc[mask.fillna(False).astype(bool)]
    rows = [
        {"subsample": name, **_performance(sample, periods)}
        for name, sample in selected.items()
    ]
    return pd.DataFrame(rows).set_index("subsample")


def market_regime_stress(
    returns: pd.Series,
    regimes: pd.Series,
    *,
    periods: int = 252,
) -> pd.DataFrame:
    """按同期、事先定义的市场状态分别报告表现。"""
    aligned = pd.concat(
        [returns.rename("returns"), regimes.rename("regime")], axis=1
    ).dropna()
    if aligned.empty:
        raise ValueError("returns 与 regimes 没有重叠的有效观测")
    rows = [
        {"regime": regime, **_performance(group["returns"], periods)}
        for regime, group in aligned.groupby("regime", sort=False)
    ]
    return pd.DataFrame(rows).set_index("regime")


# 便于教学材料使用的显式别名。
cost_stress_test = cost_multiplier_stress
parameter_stress_test = parameter_neighborhood_stress
subsample_stress_test = subsample_stress
market_regime_stress_test = market_regime_stress
