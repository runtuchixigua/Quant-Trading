import pytest

from ashare_quant.config import FactorConfig, ResearchConfig, UniverseConfig, load_config


def test_load_nested_yaml_config(tmp_path) -> None:
    path = tmp_path / "research.yaml"
    path.write_text(
        """
start_date: "2021-01-01"
end_date: "2024-12-31"
seed: 11
universe:
  min_listing_days: 90
  exclude_st: true
factors:
  amihud_window: 10
  ic_window: 40
  decay_lags: 6
""",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config == ResearchConfig(
        start_date="2021-01-01",
        end_date="2024-12-31",
        seed=11,
        universe=UniverseConfig(min_listing_days=90),
        factors=FactorConfig(amihud_window=10, ic_window=40, decay_lags=6),
    )


def test_config_rejects_invalid_and_unknown_values(tmp_path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        "start_date: '2024-01-02'\nend_date: '2023-01-02'\nunknown: true\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_config(path)
