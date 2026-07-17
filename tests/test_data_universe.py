import pandas as pd

from ashare_quant.config import UniverseConfig
from ashare_quant.data import make_synthetic_market, make_synthetic_security_master
from ashare_quant.universe import point_in_time_universe, universe_mask


def test_synthetic_market_has_amount_and_security_master() -> None:
    market = make_synthetic_market(n_days=3, n_assets=2)
    master = make_synthetic_security_master(sorted(market["symbol"].unique()))
    assert (market["amount"] == market["close"] * market["volume"]).all()
    assert set(master.columns) == {"symbol", "list_date", "delist_date"}


def test_point_in_time_universe_respects_listing_delisting_and_status() -> None:
    dates = pd.to_datetime(["2024-01-05", "2024-01-10", "2024-01-15"])
    market = pd.DataFrame(
        {
            "date": dates.repeat(2),
            "symbol": ["A", "B"] * 3,
            "is_st": [False, False, False, True, False, False],
            "suspended": [False, False, False, False, False, True],
        }
    )
    securities = pd.DataFrame(
        {
            "symbol": ["A", "B"],
            "list_date": pd.to_datetime(["2024-01-01", "2024-01-08"]),
            "delist_date": [pd.Timestamp("2024-01-15"), pd.NaT],
        }
    )
    config = UniverseConfig(min_listing_days=2)
    selected = point_in_time_universe(market, securities, config)
    assert list(zip(selected["date"], selected["symbol"])) == [
        (pd.Timestamp("2024-01-05"), "A"),
        (pd.Timestamp("2024-01-10"), "A"),
    ]
    mask = universe_mask(market, securities, config)
    assert mask.tolist() == [True, False, True, False, False, False]
