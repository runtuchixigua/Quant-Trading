import pandas as pd

from ashare_quant.execution import (
    ExecutionConfig,
    reconcile_executions,
    simulate_execution,
    weights_to_orders,
)
from ashare_quant.paper import PaperBroker, PaperConfig


def test_weights_convert_to_lots_and_execution_can_partially_fill() -> None:
    orders = weights_to_orders(
        pd.Series({"A": 0.55}),
        pd.Series({"A": 10.0}),
        pd.Series({"A": 0}),
        100_000.0,
    )
    assert orders.loc[0, "requested_shares"] == 5_500

    fills = simulate_execution(
        orders,
        pd.Series({"A": 10.0}),
        pd.Series({"A": 20_000}),
        config=ExecutionConfig(
            max_volume_participation=0.1,
            slippage=0.0,
            impact_coefficient=0.1,
        ),
    )
    assert fills.loc[0, "filled_shares"] == 2_000
    assert fills.loc[0, "status"] == "PARTIALLY_FILLED"
    assert fills.loc[0, "execution_price"] > 10.0

    reconciliation = reconcile_executions(orders, fills)
    assert not bool(reconciliation.loc[0, "matched"])
    assert reconciliation.loc[0, "share_difference"] == -3_500


def test_paper_broker_restores_state_and_continues(tmp_path) -> None:
    broker = PaperBroker(
        cash=100_000.0,
        config=PaperConfig(
            commission_rate=0.0,
            minimum_commission=0.0,
            stamp_duty=0.0,
            slippage=0.0,
            max_volume_participation=0.1,
        ),
    )
    prices = pd.Series({"A": 10.0})
    first = broker.rebalance(
        pd.Timestamp("2024-01-02"),
        prices,
        pd.Series({"A": 0.5}),
        volumes=pd.Series({"A": 20_000}),
    )
    assert first.loc[0, "status"] == "PARTIALLY_FILLED"
    assert broker.holdings.loc["A", "shares"] == 2_000
    broker.save_state(tmp_path)

    restored = PaperBroker.load_state(tmp_path)
    assert restored.cash == broker.cash
    assert restored.holdings.loc["A", "shares"] == 2_000
    restored.rebalance(
        pd.Timestamp("2024-01-03"),
        prices,
        pd.Series({"A": 0.5}),
        volumes=pd.Series({"A": 20_000}),
    )
    assert restored.holdings.loc["A", "shares"] == 4_000
