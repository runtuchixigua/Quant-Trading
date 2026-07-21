"""课程唯一学习入口。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from ashare_quant.lesson_progress import LessonProgress
from ashare_quant.lesson_registry import LESSONS, LessonRunnerUnavailable, get_lesson


def _print_lessons(progress: LessonProgress, *, include_status: bool) -> None:
    statuses = {entry.week: entry.status for entry in progress.all()}
    for lesson in LESSONS:
        suffix = f"  [{statuses[lesson.week]}]" if include_status else ""
        print(f"{lesson.week:02d}. {lesson.title}（{lesson.phase}）{suffix}")


def run_lesson(
    week: int,
    *,
    output: str | Path | None = None,
    force: bool = False,
    quick: bool = False,
    progress: LessonProgress | None = None,
) -> object:
    """通过注册表执行一周课程并维护状态。"""
    lesson = get_lesson(week)
    tracker = progress or LessonProgress()
    current = tracker.get(week)
    if current.status in {"completed", "reviewed"} and not force:
        raise RuntimeError(
            f"第 {week} 周状态已是 {current.status}；如需重新生成产物，请使用 --force。"
        )

    destination = Path(output or f"artifacts/learning/week{week:02d}")
    tracker.set(week, "running", output=destination)
    try:
        runner = lesson.resolve_runner()
        result = runner(destination, force=force, quick=quick)
    except Exception as exc:
        tracker.set(week, "failed", output=destination, error=str(exc))
        raise
    tracker.set(week, "completed", output=destination)
    return result


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="A 股量化课程学习入口；第一次使用请直接运行 `python scripts/learn.py 1`"
    )
    parser.add_argument("week", type=int, nargs="?")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--list", action="store_true", help="列出 24 周课程")
    parser.add_argument("--status", action="store_true", help="显示课程进度")
    parser.add_argument("--force", action="store_true", help="允许重新运行已完成课程")
    parser.add_argument(
        "--mark-reviewed",
        action="store_true",
        help="将指定周从 completed 标记为 reviewed",
    )
    parser.add_argument("--quick", action="store_true", help="使用快速教学数据运行")
    args = parser.parse_args(argv)
    progress = LessonProgress()

    if args.list:
        _print_lessons(progress, include_status=False)
        return
    if args.status:
        _print_lessons(progress, include_status=True)
        return

    week = args.week if args.week is not None else 1
    try:
        lesson = get_lesson(week)
        if args.mark_reviewed:
            entry = progress.mark_reviewed(week)
            print(f"第 {week} 周已标记为 {entry.status}。")
            return
        result = run_lesson(
            week,
            output=args.output,
            force=args.force,
            quick=args.quick,
            progress=progress,
        )
    except (ValueError, RuntimeError, LessonRunnerUnavailable) as exc:
        parser.exit(2, f"错误：{exc}\n")

    print(f"\n第 {week} 周“{lesson.title}”实验已完成。")
    summary = getattr(result, "summary", None)
    if summary is not None:
        print(f"\n{summary.to_string()}")
    destination = getattr(result, "output", args.output)
    print(f"\n实验目录：{destination}")
    print("请完成 homework.md，并按 acceptance_checklist.md 逐项验收。")


if __name__ == "__main__":
    main()
