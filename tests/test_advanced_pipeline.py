from ashare_quant.config import (
    DataConfig,
    FactorConfig,
    PortfolioConfig,
    ResearchConfig,
    ValidationConfig,
)
from ashare_quant.pipeline import run_advanced_pipeline


def test_advanced_pipeline_writes_auditable_artifacts(tmp_path) -> None:
    config = ResearchConfig(
        start_date="2020-01-02",
        end_date="2021-01-01",
        seed=5,
        data=DataConfig(n_days=260, n_assets=20),
        factors=FactorConfig(amihud_window=10, ic_window=30, decay_lags=3),
        portfolio=PortfolioConfig(max_weight=0.05),
        validation=ValidationConfig(
            min_train_dates=60,
            train_window_dates=120,
            label_horizon_dates=10,
            retrain_every=20,
            purge_dates=10,
            embargo_dates=2,
        ),
    )
    output = tmp_path / "advanced"
    manifest = run_advanced_pipeline(config, output)

    assert manifest["course_week"] == 24
    assert manifest["assets"] == 20
    for filename in (
        "run_manifest.json",
        "factor_summary.csv",
        "performance_summary.csv",
        "asset_risk_decomposition.csv",
        "validation_protocol.json",
        "ml_folds.csv",
        "execution_reconciliation.csv",
        "monitor_decision.json",
        "graduation_report.md",
    ):
        assert (output / filename).exists()
    assert (output / "paper_state" / "paper_account.json").exists()
