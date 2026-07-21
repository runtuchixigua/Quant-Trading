import pandas as pd

from ashare_quant.lessons import run_week_01


def test_week_01_creates_a_self_contained_first_lesson(tmp_path) -> None:
    result = run_week_01(tmp_path / "week01")

    assert result.week == 1
    assert (result.output / "daily_data.csv").exists()
    assert (result.output / "metrics.csv").exists()
    assert (result.output / "wealth_and_drawdown.png").exists()
    assert (result.output / "homework.md").exists()

    daily = pd.read_csv(result.output / "daily_data.csv")
    assert {"close", "return", "wealth", "drawdown"}.issubset(daily.columns)
    assert len(daily) == 252
