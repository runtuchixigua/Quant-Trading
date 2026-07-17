import pandas as pd

from ashare_quant.paper import PaperBroker, PaperConfig


def test_paper_broker_uses_lots_and_enforces_t_plus_one() -> None:
    broker = PaperBroker(
        cash=100_000.0,
        config=PaperConfig(
            commission_rate=0.0,
            minimum_commission=0.0,
            stamp_duty=0.0,
            slippage=0.0,
        ),
    )
    date = pd.Timestamp("2024-01-02")
    prices = pd.Series({"A": 10.0})
    broker.rebalance(date, prices, pd.Series({"A": 0.5}))
    assert broker.holdings.loc["A", "shares"] == 5_000

    rejected = broker.rebalance(date, prices, pd.Series({"A": 0.0}))
    assert broker.holdings.loc["A", "shares"] == 5_000
    assert rejected.iloc[0]["status"] == "T_PLUS_ONE"

    broker.rebalance(date + pd.Timedelta(days=1), prices, pd.Series({"A": 0.0}))
    assert broker.holdings.loc["A", "shares"] == 0
