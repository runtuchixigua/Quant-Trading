import json

from ashare_quant.lesson_io import read_manifest
from ashare_quant.lesson_progress import LessonProgress
from ashare_quant.lesson_registry import LESSONS, get_lesson
from ashare_quant.lessons import run_week_01


def test_registry_contains_all_24_weeks_and_runners() -> None:
    assert [lesson.week for lesson in LESSONS] == list(range(1, 25))
    assert all(lesson.title and lesson.phase and lesson.runner for lesson in LESSONS)
    assert all(callable(get_lesson(week).resolve_runner()) for week in range(1, 25))


def test_progress_supports_course_lifecycle(tmp_path) -> None:
    progress = LessonProgress(tmp_path / "progress.json")

    assert progress.get(1).status == "planned"
    assert progress.set(1, "running").status == "running"
    assert progress.set(1, "completed", output="week01").status == "completed"
    assert progress.mark_reviewed(1).status == "reviewed"
    assert progress.set(2, "failed", error="not implemented").status == "failed"
    assert len(progress.all()) == 24


def test_week_01_writes_shared_files_and_preserves_homework(tmp_path) -> None:
    output = tmp_path / "week01"
    first = run_week_01(output, quick=True)
    homework = output / "homework.md"
    homework.write_text("# 我的答案\n", encoding="utf-8")

    second = run_week_01(output, force=True, quick=True)

    assert first.week == second.week == 1
    assert homework.read_text(encoding="utf-8") == "# 我的答案\n"
    assert read_manifest(output)["runner"].endswith(":run_week_01")
    acceptance = json.loads((output / "acceptance.json").read_text(encoding="utf-8"))
    assert acceptance["status"] == "pending"
    assert acceptance["criteria"]
