import pandas as pd

from ashare_quant.fundamentals import (
    align_fundamentals_asof,
    fundamentals_asof,
    make_synthetic_fundamentals,
)


def test_announcement_asof_alignment_never_uses_future_report() -> None:
    observations = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-04-19", "2024-04-20", "2024-08-01"]),
            "symbol": ["A", "A", "A"],
        }
    )
    reports = pd.DataFrame(
        {
            "symbol": ["A", "A"],
            "report_period": pd.to_datetime(["2023-12-31", "2024-03-31"]),
            "announcement_date": pd.to_datetime(["2024-04-20", "2024-07-30"]),
            "net_profit": [10.0, 12.0],
        }
    )
    aligned = align_fundamentals_asof(observations, reports)
    assert pd.isna(aligned.loc[0, "net_profit"])
    assert aligned.loc[1, "net_profit"] == 10.0
    assert aligned.loc[2, "net_profit"] == 12.0
    assert (aligned["announcement_date"].dropna() <= aligned.loc[
        aligned["announcement_date"].notna(), "date"
    ]).all()


def test_synthetic_fundamentals_are_reproducible_and_asof_filtered() -> None:
    first = make_synthetic_fundamentals(["A", "B"], n_periods=3, seed=4)
    second = make_synthetic_fundamentals(["A", "B"], n_periods=3, seed=4)
    pd.testing.assert_frame_equal(first, second)
    cutoff = first["announcement_date"].sort_values().iloc[2]
    visible = fundamentals_asof(first, cutoff)
    assert (visible["announcement_date"] <= cutoff).all()
    assert visible["symbol"].is_unique
