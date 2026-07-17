import numpy as np
import pandas as pd
import pytest

from ashare_quant.portfolio import (
    InfeasiblePortfolioError,
    mean_variance_weights,
    minimum_variance_weights,
    portfolio_turnover,
    risk_budget_weights,
    score_to_weights,
)


def test_score_to_weights_obeys_all_constraints() -> None:
    assets = pd.Index(["A", "B", "C", "D"])
    scores = pd.Series([4.0, 3.0, 2.0, 1.0], index=assets)
    industries = pd.Series(["bank", "bank", "tech", "tech"], index=assets)
    benchmark = pd.Series(0.25, index=assets)
    previous = pd.Series(0.25, index=assets)

    weights = score_to_weights(
        scores,
        max_weight=0.4,
        industries=industries,
        benchmark_weights=benchmark,
        max_industry_deviation=0.1,
        previous_weights=previous,
        max_turnover=0.05,
    )

    assert np.isclose(weights.sum(), 1.0)
    assert weights.max() <= 0.4 + 1e-12
    industry_exposure = weights.groupby(industries).sum()
    assert (industry_exposure.sub(0.5).abs() <= 0.1 + 1e-12).all()
    assert portfolio_turnover(weights, previous) <= 0.05 + 1e-12
    assert weights["A"] > weights["B"]


def test_score_to_weights_reports_infeasible_constraints() -> None:
    scores = pd.Series([3.0, 2.0, 1.0], index=["A", "B", "C"])
    with pytest.raises(InfeasiblePortfolioError, match="单票上限"):
        score_to_weights(scores, max_weight=0.3)


def test_classic_portfolio_optimizers() -> None:
    covariance = pd.DataFrame(
        [[1.0, 0.0], [0.0, 4.0]],
        index=["low", "high"],
        columns=["low", "high"],
    )
    minimum = minimum_variance_weights(covariance)
    assert np.allclose(minimum, [0.8, 0.2], atol=1e-6)

    mean_variance = mean_variance_weights(
        pd.Series([2.0, 0.0], index=covariance.index),
        covariance,
        risk_aversion=1.0,
    )
    assert mean_variance["low"] > minimum["low"]
    assert np.isclose(mean_variance.sum(), 1.0)

    risk_budget = risk_budget_weights(covariance)
    marginal = covariance @ risk_budget
    contributions = risk_budget * marginal
    assert np.isclose(risk_budget.sum(), 1.0)
    assert np.allclose(contributions / contributions.sum(), [0.5, 0.5], atol=1e-6)
