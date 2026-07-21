from ashare_quant.lesson_io import read_manifest
from ashare_quant.lesson_registry import get_lesson


def test_all_24_lessons_run_and_create_required_learning_files(tmp_path) -> None:
    for week in range(1, 25):
        output = tmp_path / f"week{week:02d}"
        result = get_lesson(week).resolve_runner()(
            output,
            force=True,
            quick=True,
        )

        assert result.week == week
        assert (output / "homework.md").exists()
        assert (output / "acceptance_checklist.md").exists()
        assert (output / "run_manifest.json").exists()
        assert read_manifest(output)["week"] == week


def test_rerun_preserves_student_homework(tmp_path) -> None:
    output = tmp_path / "week02"
    runner = get_lesson(2).resolve_runner()
    runner(output, quick=True)
    homework = output / "homework.md"
    homework.write_text("# 我的真实答案\n", encoding="utf-8")

    runner(output, force=True, quick=True)

    assert homework.read_text(encoding="utf-8") == "# 我的真实答案\n"
