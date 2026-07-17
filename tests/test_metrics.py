import numpy as np
import pandas as pd

from ashare_quant.metrics import (
    annualized_return,
    drawdown,
    max_drawdown,
    wealth_index,
)


def test_compounding_and_drawdown() -> None:
    returns = pd.Series([0.10, -0.10])
    assert np.isclose(wealth_index(returns).iloc[-1], 0.99)
    assert np.isclose(drawdown(returns).iloc[-1], -0.10)
    assert np.isclose(max_drawdown(returns), -0.10)


def test_annualized_return_uses_geometric_growth() -> None:
    returns = pd.Series([0.01] * 252)
    assert np.isclose(annualized_return(returns), 1.01**252 - 1.0)
