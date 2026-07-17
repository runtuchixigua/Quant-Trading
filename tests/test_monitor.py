import json
import logging

import pandas as pd
import pytest

from ashare_quant.monitor import (
    MonitorConfig,
    evaluate_stop_rules,
    log_event,
    population_stability_index,
    reconcile_account,
    validate_market_data,
)


def test_data_validation_fails_fast_on_stale_or_invalid_data() -> None:
    market = pd.DataFrame(
        {
            "date": ["2024-01-02"],
            "symbol": ["A"],
            "close": [10.0],
            "volume": [1000],
        }
    )
    validate_market_data(market, as_of="2024-01-03", max_age_days=1)
    with pytest.raises(ValueError, match="过期"):
        validate_market_data(market, as_of="2024-01-10", max_age_days=1)
    market.loc[0, "close"] = -1
    with pytest.raises(ValueError, match="close"):
        validate_market_data(market)


def test_account_psi_drawdown_and_structured_log(caplog) -> None:
    reconciliation = reconcile_account(
        pd.Series({"A": 100}),
        pd.Series({"A": 200}),
        1000.0,
        999.0,
    )
    assert not reconciliation.matched

    baseline = pd.Series(range(100), dtype=float)
    shifted = pd.Series(range(100, 200), dtype=float)
    psi = population_stability_index(baseline, shifted)
    decision = evaluate_stop_rules(
        nav_history=pd.Series([100.0, 110.0, 80.0]),
        psi_value=psi,
        reconciliation=reconciliation,
        config=MonitorConfig(max_drawdown=0.2, max_psi=0.1),
    )
    assert decision.should_stop
    assert set(decision.reasons) == {"MAX_DRAWDOWN", "PSI_DRIFT", "ACCOUNT_MISMATCH"}

    logger = logging.getLogger("test-structured")
    with caplog.at_level(logging.INFO, logger="test-structured"):
        text = log_event(logger, "risk_checked", stop=decision.should_stop)
    payload = json.loads(text)
    assert payload["event"] == "risk_checked"
    assert payload["stop"] is True
    assert json.loads(caplog.records[-1].message)["event"] == "risk_checked"
