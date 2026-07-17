"""协方差估计、因子风险模型与组合风险分解。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


def _clean_returns(returns: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame(returns, dtype=float).replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna(axis=0, how="any")
    if len(frame) < 2:
        raise ValueError("协方差估计至少需要两期完整收益")
    if frame.columns.has_duplicates:
        raise ValueError("资产名称不能重复")
    return frame


def sample_covariance(
    returns: pd.DataFrame,
    *,
    annualization: float = 252.0,
) -> pd.DataFrame:
    """样本协方差（ddof=1），默认按 252 个交易日年化。"""
    if annualization <= 0:
        raise ValueError("annualization 必须为正")
    clean = _clean_returns(returns)
    return clean.cov() * annualization


def ledoit_wolf_covariance(
    returns: pd.DataFrame,
    *,
    annualization: float = 252.0,
) -> pd.DataFrame:
    """Ledoit-Wolf 收缩协方差，适合资产数较多的小样本场景。"""
    if annualization <= 0:
        raise ValueError("annualization 必须为正")
    clean = _clean_returns(returns)
    estimate = LedoitWolf().fit(clean.to_numpy()).covariance_ * annualization
    return pd.DataFrame(estimate, index=clean.columns, columns=clean.columns)


@dataclass(frozen=True)
class FactorRiskModel:
    """线性因子风险模型 Σ = B F B' + D。"""

    exposures: pd.DataFrame
    factor_returns: pd.DataFrame
    factor_covariance: pd.DataFrame
    specific_variance: pd.Series

    @property
    def covariance(self) -> pd.DataFrame:
        """模型隐含的资产协方差矩阵。"""
        factors = self.exposures.columns
        factor_covariance = self.factor_covariance.reindex(index=factors, columns=factors)
        common = (
            self.exposures.to_numpy()
            @ factor_covariance.to_numpy()
            @ self.exposures.to_numpy().T
        )
        matrix = common + np.diag(self.specific_variance.reindex(self.exposures.index))
        return pd.DataFrame(matrix, index=self.exposures.index, columns=self.exposures.index)


def fit_factor_risk_model(
    asset_returns: pd.DataFrame,
    factor_exposures: pd.DataFrame,
    *,
    annualization: float = 252.0,
    ridge: float = 1e-8,
    include_intercept: bool = False,
) -> FactorRiskModel:
    """逐期横截面回归估计因子收益，再估计因子与特异风险。

    ``asset_returns`` 的列是资产，``factor_exposures`` 的行是资产、列是因子。
    这是静态暴露的教学实现；生产模型还需时变暴露、行业约束与稳健回归。
    """
    if annualization <= 0 or ridge < 0:
        raise ValueError("annualization 必须为正且 ridge 不能为负")
    returns = pd.DataFrame(asset_returns, dtype=float)
    exposures = pd.DataFrame(factor_exposures, dtype=float)
    assets = returns.columns.intersection(exposures.index, sort=False)
    if len(assets) == 0:
        raise ValueError("收益列与因子暴露索引没有共同资产")
    returns = returns.reindex(columns=assets)
    exposures = exposures.reindex(assets)
    if exposures.isna().any().any() or not np.isfinite(exposures.to_numpy()).all():
        raise ValueError("因子暴露不能包含缺失或无穷值")
    if exposures.columns.has_duplicates or exposures.index.has_duplicates:
        raise ValueError("资产和因子名称不能重复")

    design = exposures.to_numpy()
    if include_intercept:
        design = np.column_stack([np.ones(len(assets)), design])
        factor_names = pd.Index(["intercept", *exposures.columns])
    else:
        factor_names = exposures.columns
    if len(assets) <= design.shape[1]:
        raise ValueError("横截面资产数必须多于待估参数数")

    coefficients: list[np.ndarray] = []
    residual_rows: list[np.ndarray] = []
    dates: list[object] = []
    for date, row in returns.iterrows():
        values = row.to_numpy()
        valid = np.isfinite(values)
        if valid.sum() <= design.shape[1]:
            continue
        current_design = design[valid]
        gram = current_design.T @ current_design + ridge * np.eye(design.shape[1])
        coefficient = np.linalg.solve(gram, current_design.T @ values[valid])
        residual = np.full(len(assets), np.nan)
        residual[valid] = values[valid] - current_design @ coefficient
        coefficients.append(coefficient)
        residual_rows.append(residual)
        dates.append(date)
    if len(coefficients) < 2:
        raise ValueError("有效横截面回归期数至少为两期")

    factor_returns = pd.DataFrame(coefficients, index=dates, columns=factor_names)
    residuals = pd.DataFrame(residual_rows, index=dates, columns=assets)
    factor_covariance = factor_returns.cov() * annualization
    specific_variance = residuals.var(ddof=1) * annualization
    if include_intercept:
        model_exposures = pd.concat(
            [
                pd.Series(1.0, index=assets, name="intercept"),
                exposures,
            ],
            axis=1,
        )
    else:
        model_exposures = exposures
    return FactorRiskModel(
        exposures=model_exposures,
        factor_returns=factor_returns,
        factor_covariance=factor_covariance,
        specific_variance=specific_variance.rename("specific_variance"),
    )


def portfolio_risk_decomposition(
    weights: pd.Series,
    covariance: pd.DataFrame,
) -> pd.DataFrame:
    """按资产分解组合波动率；volatility_contribution 之和等于组合波动率。"""
    covariance = pd.DataFrame(covariance, dtype=float)
    assets = covariance.index
    if not covariance.columns.equals(assets):
        covariance = covariance.reindex(index=assets, columns=assets)
    aligned = pd.Series(weights, dtype=float).reindex(assets)
    if aligned.isna().any() or covariance.isna().any().any():
        raise ValueError("权重与协方差资产必须完整对齐")
    matrix = (covariance.to_numpy() + covariance.to_numpy().T) / 2.0
    weight_array = aligned.to_numpy()
    marginal_variance = matrix @ weight_array
    variance_contribution = weight_array * marginal_variance
    total_variance = float(weight_array @ marginal_variance)
    if total_variance <= 0:
        raise ValueError("组合方差必须为正")
    volatility = np.sqrt(total_variance)
    result = pd.DataFrame(
        {
            "weight": aligned,
            "marginal_volatility": marginal_variance / volatility,
            "variance_contribution": variance_contribution,
            "volatility_contribution": variance_contribution / volatility,
            "percent_contribution": variance_contribution / total_variance,
        }
    )
    result.attrs["variance"] = total_variance
    result.attrs["volatility"] = volatility
    return result


def factor_risk_decomposition(
    weights: pd.Series,
    model: FactorRiskModel,
) -> pd.Series:
    """将组合方差拆成各因子与各资产特异风险贡献。"""
    aligned = pd.Series(weights, dtype=float).reindex(model.exposures.index)
    if aligned.isna().any():
        raise ValueError("权重必须覆盖风险模型中的全部资产")
    exposure = model.exposures.T @ aligned
    factor_marginal = model.factor_covariance @ exposure
    factor_contribution = exposure * factor_marginal
    specific_contribution = aligned.pow(2) * model.specific_variance
    components = pd.concat(
        [
            factor_contribution.rename(index=lambda value: f"factor:{value}"),
            specific_contribution.rename(index=lambda value: f"specific:{value}"),
        ]
    ).rename("variance_contribution")
    total_variance = float(components.sum())
    components.attrs["total_variance"] = total_variance
    components.attrs["volatility"] = np.sqrt(max(total_variance, 0.0))
    components.attrs["factor_variance"] = float(factor_contribution.sum())
    components.attrs["specific_variance"] = float(specific_contribution.sum())
    return components


component_risk_contributions = portfolio_risk_decomposition
