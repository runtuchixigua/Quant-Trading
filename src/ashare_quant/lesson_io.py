"""每周课程共享产物与安全写入工具。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .lesson_registry import get_lesson


def _write_json(path: Path, value: object) -> Path:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def prepare_lesson_output(output: str | Path) -> Path:
    """创建并返回课程输出目录。"""
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def write_manifest(
    output: str | Path,
    *,
    week: int,
    quick: bool = False,
    artifacts: Iterable[str] = (),
) -> Path:
    """写入本次课程运行清单。"""
    destination = prepare_lesson_output(output)
    lesson = get_lesson(week)
    payload = {
        "schema_version": 1,
        "week": week,
        "title": lesson.title,
        "phase": lesson.phase,
        "runner": lesson.runner,
        "quick": quick,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "artifacts": list(artifacts),
    }
    _write_json(destination / "manifest.json", payload)
    return _write_json(destination / "run_manifest.json", payload)


def write_acceptance(
    output: str | Path,
    *,
    week: int,
    criteria: Iterable[str],
) -> Path:
    """写入机器可读的课程验收清单。"""
    destination = prepare_lesson_output(output)
    descriptions = list(criteria)
    payload = {
        "schema_version": 1,
        "week": week,
        "status": "pending",
        "criteria": [
            {"description": criterion, "accepted": False}
            for criterion in descriptions
        ],
    }
    _write_json(destination / "acceptance.json", payload)
    checklist = [f"# 第 {week} 周验收清单", ""]
    checklist.extend(f"- [ ] {criterion}" for criterion in descriptions)
    checklist.extend(["", "- 导师审阅：", "- 审阅日期：", ""])
    (destination / "acceptance_checklist.md").write_text(
        "\n".join(checklist), encoding="utf-8"
    )
    return destination / "acceptance_checklist.md"


def write_homework_if_safe(
    output: str | Path,
    content: str,
    *,
    filename: str = "homework.md",
) -> tuple[Path, bool]:
    """仅创建不存在的作业，绝不覆盖学习者已有编辑。"""
    destination = prepare_lesson_output(output)
    path = destination / filename
    if path.exists():
        return path, False
    path.write_text(content, encoding="utf-8")
    return path, True


def file_sha256(path: str | Path) -> str:
    """返回文件 SHA-256，供调用方记录自定义产物。"""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_manifest(output: str | Path) -> dict[str, Any]:
    """读取课程 manifest。"""
    destination = Path(output)
    path = destination / "run_manifest.json"
    if not path.exists():
        path = destination / "manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"manifest 格式错误：{path}")
    return value
