import numpy as np
import pandas as pd

from ashare_quant.metrics import (
    active_risk_attribution,
    beta,
    information_ratio,
    tracking_error,
)
from ashare_quant.risk import (
    factor_risk_decomposition,
    fit_factor_risk_model,
    ledoit_wolf_covariance,
    portfolio_risk_decomposition,
    sample_covariance,
)


def test_covariance_estimators_are_labeled_and_positive_semidefinite() -> None:
    rng = np.random.default_rng(8)
    returns = pd.DataFrame(rng.normal(size=(30, 5)), columns=list("ABCDE"))

    sample = sample_covariance(returns, annualization=1.0)
    shrunk = ledoit_wolf_covariance(returns, annualization=1.0)

    assert sample.index.equals(returns.columns)
    assert np.allclose(sample, returns.cov())
    assert shrunk.index.equals(returns.columns)
    assert np.linalg.eigvalsh(shrunk).min() >= -1e-12


def test_factor_model_covariance_and_decomposition() -> None:
    rng = np.random.default_rng(11)
    assets = pd.Index(["A", "B", "C", "D"])
    exposures = pd.DataFrame(
        [[1.0, 0.2], [0.5, 1.0], [-0.5, 0.8], [0.2, -0.4]],
        index=assets,
        columns=["value", "momentum"],
    )
    factor_returns = rng.normal(scale=0.01, size=(100, 2))
    residual = rng.normal(scale=0.002, size=(100, 4))
    returns = pd.DataFrame(
        factor_returns @ exposures.to_numpy().T + residual,
        columns=assets,
    )
    model = fit_factor_risk_model(returns, exposures, annualization=1.0)
    weights = pd.Series(0.25, index=assets)

    assert model.covariance.shape == (4, 4)
    assert np.linalg.eigvalsh(model.covariance).min() >= -1e-12
    decomposition = factor_risk_decomposition(weights, model)
    model_variance = float(weights @ model.covariance @ weights)
    assert np.isclose(decomposition.sum(), model_variance)

    asset_decomposition = portfolio_risk_decomposition(weights, model.covariance)
    assert np.isclose(
        asset_decomposition["volatility_contribution"].sum(),
        np.sqrt(model_variance),
    )


def test_active_return_metrics_and_attribution() -> None:
    benchmark = pd.Series([-0.015, -0.005, 0.005, 0.015])
    portfolio = 1.5 * benchmark + pd.Series([0.001, -0.001, 0.001, -0.001])

    assert np.isclose(beta(portfolio, benchmark), 1.46)
    assert tracking_error(portfolio, benchmark, periods=1) > 0
    assert np.isclose(information_ratio(portfolio, benchmark, periods=1), 0.0)

    portfolio_weights = pd.Series([0.6, 0.4], index=["A", "B"])
    benchmark_weights = pd.Series([0.5, 0.5], index=["A", "B"])
    covariance = pd.DataFrame(
        [[0.04, 0.01], [0.01, 0.09]],
        index=["A", "B"],
        columns=["A", "B"],
    )
    attribution = active_risk_attribution(
        portfolio_weights,
        benchmark_weights,
        covariance,
        periods=1,
    )
    assert np.isclose(
        attribution["tracking_error_contribution"].sum(),
        attribution.attrs["tracking_error"],
    )
