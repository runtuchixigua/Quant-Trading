import json

import pandas as pd
import pytest

from ashare_quant.lesson_io import read_manifest
from ashare_quant.lesson_registry import get_lesson
from ashare_quant.lessons import LessonResult
from ashare_quant.lessons_robust import (
    run_week_19,
    run_week_20,
    run_week_21,
    run_week_22,
    run_week_23,
    run_week_24,
)


@pytest.mark.parametrize(
    ("week", "runner", "required"),
    [
        (
            19,
            run_week_19,
            {
                "purged_embargo_folds.csv",
                "experiment_log.csv",
                "deflated_sharpe.json",
                "block_bootstrap.csv",
            },
        ),
        (
            20,
            run_week_20,
            {"regime_stress.csv", "cost_stress.csv", "tail_risk.csv", "joint_stress.csv"},
        ),
        (
            21,
            run_week_21,
            {
                "model_importance.csv",
                "walk_forward_folds.csv",
                "drift_degradation_drill.json",
            },
        ),
        (22, run_week_22, {"capacity_curve.csv"}),
        (23, run_week_23, {"fault_injection.csv", "stop_and_rollback.md"}),
    ],
)
def test_weeks_19_to_23_are_executable_and_self_contained(
    tmp_path, week, runner, required
) -> None:
    output = tmp_path / f"week{week:02d}"
    result = runner(output, quick=True)

    assert isinstance(result, LessonResult)
    assert result.week == week
    assert result.output == output
    assert not result.summary.empty
    assert required.issubset({path.name for path in output.iterdir()})
    assert {"manifest.json", "homework.md", "acceptance.json", "summary.csv"}.issubset(
        {path.name for path in output.iterdir()}
    )
    manifest = read_manifest(output)
    assert manifest["week"] == week
    assert manifest["runner"].endswith(f":run_week_{week:02d}")
    assert callable(get_lesson(week).resolve_runner())


def test_week_19_enforces_gap_and_records_every_trial(tmp_path) -> None:
    output = tmp_path / "week19"
    run_week_19(output, quick=True)

    folds = pd.read_csv(output / "purged_embargo_folds.csv")
    experiments = pd.read_csv(output / "experiment_log.csv")
    deflated = json.loads((output / "deflated_sharpe.json").read_text(encoding="utf-8"))

    assert (folds["gap_dates"] == 7).all()
    assert len(experiments) == 3
    assert deflated["n_trials"] == len(experiments)
    assert 0 <= deflated["probability"] <= 1


def test_week_20_has_joint_tail_stress(tmp_path) -> None:
    output = tmp_path / "week20"
    run_week_20(output, quick=True)

    joint = pd.read_csv(output / "joint_stress.csv")
    tail = pd.read_csv(output / "tail_risk.csv", index_col=0)
    assert {"regime", "cost_multiplier", "var", "es"}.issubset(joint.columns)
    assert joint["regime"].nunique() == 3
    assert joint["cost_multiplier"].nunique() == 3
    assert {"var", "es"}.issubset(tail.index)


def test_week_21_explains_model_and_triggers_degradation(tmp_path) -> None:
    output = tmp_path / "week21"
    run_week_21(output, quick=True)

    importance = pd.read_csv(output / "model_importance.csv")
    drill = json.loads(
        (output / "drift_degradation_drill.json").read_text(encoding="utf-8")
    )
    assert {"fold", "feature", "importance", "kind"}.issubset(importance.columns)
    assert importance["feature"].nunique() == 4
    assert drill["should_stop"] is True
    assert "PSI_DRIFT" in drill["reasons"]
    assert drill["degradation"]


def test_week_22_quick_has_at_least_three_size_liquidity_scenarios(tmp_path) -> None:
    output = tmp_path / "week22"
    run_week_22(output, quick=True)

    curve = pd.read_csv(output / "capacity_curve.csv")
    assert curve["nav"].nunique() >= 3
    assert curve["liquidity_multiplier"].nunique() >= 3
    assert len(curve) >= 9
    assert curve["fill_rate"].between(0, 1).all()
    assert curve["impact_bps"].notna().all()


def test_week_23_injects_at_least_five_detected_stopping_faults(tmp_path) -> None:
    output = tmp_path / "week23"
    run_week_23(output, quick=True)

    faults = pd.read_csv(output / "fault_injection.csv")
    runbook = (output / "stop_and_rollback.md").read_text(encoding="utf-8")
    assert faults["fault"].nunique() >= 5
    assert faults["detected"].all()
    assert faults["should_stop"].all()
    assert faults["rollback"].str.len().gt(0).all()
    assert "停止顺序" in runbook
    assert "恢复门槛" in runbook


def test_week_24_runs_pipeline_in_unique_directories_and_preserves_homework(
    tmp_path,
) -> None:
    output = tmp_path / "week24"
    first = run_week_24(output, quick=True)
    homework = output / "homework.md"
    homework.write_text("# 我的毕业作业\n", encoding="utf-8")
    second = run_week_24(output, force=True, quick=True)

    assert isinstance(first, LessonResult)
    assert first.summary["run_directory"] != second.summary["run_directory"]
    run_directories = sorted((output / "runs").iterdir())
    assert [path.name for path in run_directories] == ["run_001", "run_002"]
    for run_directory in run_directories:
        assert (run_directory / "run_manifest.json").exists()
        assert (run_directory / "graduation_report.md").exists()
    assert homework.read_text(encoding="utf-8") == "# 我的毕业作业\n"
    assert (output / "manifest.json").exists()
    assert (output / "acceptance.json").exists()
    assert (output / "reproduction.md").exists()
    assert (output / "defense_checklist.md").exists()
