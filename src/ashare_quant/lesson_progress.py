"""课程进度的 JSON 持久化。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, cast

from .lesson_registry import LESSONS, get_lesson


LessonStatus = Literal["planned", "running", "completed", "reviewed", "failed"]
VALID_STATUSES = frozenset({"planned", "running", "completed", "reviewed", "failed"})
DEFAULT_PROGRESS_PATH = Path("artifacts/learning/progress.json")


@dataclass(frozen=True)
class ProgressEntry:
    week: int
    status: LessonStatus
    updated_at: str | None = None
    output: str | None = None
    error: str | None = None


class LessonProgress:
    """读取和原子更新 24 周课程状态。"""

    def __init__(self, path: str | Path = DEFAULT_PROGRESS_PATH) -> None:
        self.path = Path(path)

    def all(self) -> list[ProgressEntry]:
        stored = self._read()
        return [
            self._entry(lesson.week, stored.get(str(lesson.week), {}))
            for lesson in LESSONS
        ]

    def get(self, week: int) -> ProgressEntry:
        get_lesson(week)
        data = self._read().get(str(week), {})
        return self._entry(week, data)

    def set(
        self,
        week: int,
        status: LessonStatus,
        *,
        output: str | Path | None = None,
        error: str | None = None,
    ) -> ProgressEntry:
        get_lesson(week)
        if status not in VALID_STATUSES:
            raise ValueError(f"未知课程状态：{status}")
        data = self._read()
        entry = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "output": str(output) if output is not None else None,
            "error": error,
        }
        data[str(week)] = entry
        self._write(data)
        return self._entry(week, entry)

    def mark_reviewed(self, week: int) -> ProgressEntry:
        current = self.get(week)
        if current.status not in {"completed", "reviewed"}:
            raise ValueError(
                f"第 {week} 周当前状态为 {current.status}，完成课程后才能标记 reviewed"
            )
        return self.set(week, "reviewed", output=current.output)

    def _read(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"课程进度文件格式错误：{self.path}")
        weeks = raw.get("weeks", {})
        if not isinstance(weeks, dict):
            raise ValueError(f"课程进度文件缺少 weeks 对象：{self.path}")
        return cast(dict[str, dict[str, object]], weeks)

    def _write(self, weeks: dict[str, dict[str, object]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {"schema_version": 1, "weeks": weeks},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    @staticmethod
    def _entry(week: int, data: dict[str, object]) -> ProgressEntry:
        status = str(data.get("status", "planned"))
        if status not in VALID_STATUSES:
            raise ValueError(f"第 {week} 周包含未知状态：{status}")
        return ProgressEntry(
            week=week,
            status=cast(LessonStatus, status),
            updated_at=cast(str | None, data.get("updated_at")),
            output=cast(str | None, data.get("output")),
            error=cast(str | None, data.get("error")),
        )
