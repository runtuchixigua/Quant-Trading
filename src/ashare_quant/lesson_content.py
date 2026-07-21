"""课程讲义 frontmatter 的解析与注册表校验。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .lesson_registry import get_lesson


@dataclass(frozen=True)
class ArtifactSpec:
    """讲义中一个实验产物的释义。"""

    filename: str
    summary: str
    columns: dict[str, str] | None = None


@dataclass(frozen=True)
class LessonContent:
    """解析后的静态讲义。"""

    week: int
    title: str
    phase: str
    reading_order: list[str]
    artifacts: dict[str, ArtifactSpec]
    body: str
    source_path: Path


def _default_lessons_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "lessons"


def _require_string(value: Any, field: str, source: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source} 的 {field} 必须是非空字符串")
    return value.strip()


def _parse_artifacts(value: Any, source: Path) -> dict[str, ArtifactSpec]:
    # 兼容早期讲义使用的 [{name, summary, columns}] 写法；新讲义应使用
    # filename -> {summary, columns} mapping。
    if isinstance(value, list):
        normalized: dict[str, Any] = {}
        for item in value:
            if isinstance(item, str) and item.strip():
                normalized[item] = {"summary": "本周讲义列出的实验产物。"}
                continue
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise ValueError(f"{source} 的 artifacts 列表项必须含字符串 name")
            filename = item["name"]
            normalized[filename] = {key: raw for key, raw in item.items() if key != "name"}
        value = normalized
    if not isinstance(value, dict):
        raise ValueError(f"{source} 的 artifacts 必须是 mapping")
    parsed: dict[str, ArtifactSpec] = {}
    for filename, raw_spec in value.items():
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError(f"{source} 的 artifacts 文件名必须是非空字符串")
        if not isinstance(raw_spec, dict):
            raise ValueError(f"{source} 的 artifacts.{filename} 必须是 mapping")
        summary = _require_string(raw_spec.get("summary"), f"artifacts.{filename}.summary", source)
        raw_columns = raw_spec.get("columns")
        columns: dict[str, str] | None = None
        if raw_columns is not None:
            if isinstance(raw_columns, list) and all(
                isinstance(column, str) and column.strip() for column in raw_columns
            ):
                raw_columns = {column: "讲义未单独提供该列的释义。" for column in raw_columns}
            if not isinstance(raw_columns, dict):
                raise ValueError(f"{source} 的 artifacts.{filename}.columns 必须是 mapping")
            columns = {}
            for column, description in raw_columns.items():
                if not isinstance(column, str) or not column.strip():
                    raise ValueError(f"{source} 的 {filename} 列名必须是非空字符串")
                columns[column] = _require_string(
                    description, f"artifacts.{filename}.columns.{column}", source
                )
        parsed[filename] = ArtifactSpec(filename=filename, summary=summary, columns=columns)
    return parsed


def load_lesson_content(
    week_or_path: int | str | Path,
    *,
    lessons_dir: str | Path | None = None,
) -> LessonContent:
    """加载一周讲义，并核对 week、title、phase 与课程注册表一致。"""
    if isinstance(week_or_path, int):
        source = Path(lessons_dir or _default_lessons_dir()) / f"week{week_or_path:02d}.md"
    else:
        source = Path(week_or_path)
    text = source.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{source} 缺少 YAML frontmatter 起始分隔符")
    try:
        closing = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError(f"{source} 缺少 YAML frontmatter 结束分隔符") from exc

    try:
        metadata = yaml.safe_load("\n".join(lines[1:closing]))
    except yaml.YAMLError as exc:
        raise ValueError(f"{source} 的 YAML frontmatter 无法解析：{exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError(f"{source} 的 YAML frontmatter 必须是 mapping")

    week = metadata.get("week")
    if not isinstance(week, int) or isinstance(week, bool):
        raise ValueError(f"{source} 的 week 必须是 int")
    title = _require_string(metadata.get("title"), "title", source)
    phase = _require_string(metadata.get("phase"), "phase", source)
    raw_order = metadata.get("reading_order")
    if not isinstance(raw_order, list) or not all(
        isinstance(item, str) and item.strip() for item in raw_order
    ):
        raise ValueError(f"{source} 的 reading_order 必须是 list[str]")
    artifacts = _parse_artifacts(metadata.get("artifacts"), source)

    registered = get_lesson(week)
    if title != registered.title:
        raise ValueError(
            f"{source} 的 title 与 lesson_registry 不一致：{title!r} != {registered.title!r}"
        )
    if phase != registered.phase:
        raise ValueError(
            f"{source} 的 phase 与 lesson_registry 不一致：{phase!r} != {registered.phase!r}"
        )
    if isinstance(week_or_path, int) and week != week_or_path:
        raise ValueError(f"{source} 的 week 为 {week}，预期为 {week_or_path}")

    body = "\n".join(lines[closing + 1 :]).lstrip("\n")
    if text.endswith("\n") and body:
        body += "\n"
    return LessonContent(
        week=week,
        title=title,
        phase=phase,
        reading_order=[item.strip() for item in raw_order],
        artifacts=artifacts,
        body=body,
        source_path=source,
    )
