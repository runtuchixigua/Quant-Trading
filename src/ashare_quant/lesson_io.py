"""每周课程共享产物与安全写入工具。"""

from __future__ import annotations

import hashlib
import json
import os
from fnmatch import fnmatch
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .lesson_content import ArtifactSpec, LessonContent, load_lesson_content
from .lesson_registry import get_lesson


_COMMON_ARTIFACTS: dict[str, ArtifactSpec] = {
    "homework.md": ArtifactSpec("homework.md", "需要学习者完成并保留的本周作业。"),
    "acceptance.json": ArtifactSpec("acceptance.json", "机器可读的通关验收状态与标准。"),
    "acceptance_checklist.md": ArtifactSpec(
        "acceptance_checklist.md", "供学习者和导师逐项勾选的验收清单。"
    ),
    "report.md": ArtifactSpec("report.md", "本周实验结果、解释与局限汇总。"),
    "summary.csv": ArtifactSpec("summary.csv", "本周运行关键指标摘要。"),
}


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


def _fallback_spec(filename: str, week: int) -> ArtifactSpec:
    suffix = Path(filename).suffix.lower()
    kind = {
        ".csv": "表格数据",
        ".json": "结构化数据",
        ".md": "说明文档",
        ".png": "可视化图表",
        ".html": "交互式报告",
    }.get(suffix, "实验文件")
    return ArtifactSpec(filename, f"第 {week} 周 runner 生成的{kind}。")


def _lesson_content_if_available(week: int) -> LessonContent | None:
    try:
        return load_lesson_content(week)
    except (FileNotFoundError, ValueError):
        # 老版本仓库没有讲义或仍使用不完整 frontmatter 时，runner 仍须可运行；
        # 显式调用 load_lesson_content 依然会返回具体校验错误。
        return None


def _artifact_glossary(
    filenames: list[str], week: int, content: LessonContent | None
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    declared = content.artifacts if content is not None else {}
    for filename in filenames:
        spec = declared.get(filename) or _COMMON_ARTIFACTS.get(filename)
        if spec is None:
            spec = next(
                (
                    candidate
                    for pattern, candidate in declared.items()
                    if "*" in pattern and fnmatch(filename, pattern)
                ),
                None,
            )
        if spec is None:
            if content is not None:
                raise ValueError(
                    f"第 {week} 周讲义未解释 manifest 产物：{filename}"
                )
            spec = _fallback_spec(filename, week)
        entry: dict[str, object] = {"summary": spec.summary}
        if spec.columns is not None:
            entry["columns"] = spec.columns
        result[filename] = entry
    return result


def _write_guide(
    destination: Path,
    *,
    week: int,
    title: str,
    doc_path: Path,
    reading_order: list[str],
    artifacts: list[str],
    glossary: dict[str, dict[str, object]],
) -> Path:
    relative_doc = Path(
        os.path.relpath(doc_path.resolve(), start=destination.resolve())
    ).as_posix()
    lines = [
        f"# 第 {week} 周实验指南：{title}",
        "",
        f"- 静态讲义：[docs/lessons/week{week:02d}.md]({relative_doc})",
        f"- 运行命令：`python scripts/learn.py {week}`",
        "",
        "## 推荐阅读顺序",
        "",
    ]
    order = reading_order or ["先阅读静态讲义", *artifacts, "完成作业与验收"]
    lines.extend(f"{index}. {item}" for index, item in enumerate(order, start=1))
    lines.extend(
        [
            "",
            "## 本次运行产物",
            "",
            "| 文件 | 说明 | 列说明 |",
            "| --- | --- | --- |",
        ]
    )
    for filename in artifacts:
        entry = glossary[filename]
        columns = entry.get("columns")
        column_text = "—"
        if isinstance(columns, dict) and columns:
            column_text = "；".join(f"`{name}`：{description}" for name, description in columns.items())
        lines.append(f"| `{filename}` | {entry['summary']} | {column_text} |")
    lines.extend(
        [
            "",
            "## 通关步骤",
            "",
            "1. 按推荐顺序阅读讲义并检查本次运行产物。",
            "2. 完成 `homework.md`，不要用 `--force` 覆盖自己的实验记录。",
            "3. 按 `acceptance_checklist.md`（及 `acceptance.json`）逐项验收。",
            f"4. 经导师审阅后运行 `python scripts/learn.py {week} --mark-reviewed`。",
            "",
        ]
    )
    path = destination / "GUIDE.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_manifest(
    output: str | Path,
    *,
    week: int,
    quick: bool = False,
    artifacts: Iterable[str] = (),
) -> Path:
    """写入本次课程运行清单，并据此自动生成 GUIDE.md。"""
    destination = prepare_lesson_output(output)
    lesson = get_lesson(week)
    artifact_names = list(artifacts)
    content = _lesson_content_if_available(week)
    project_root = Path(__file__).resolve().parents[2]
    doc_path = (
        content.source_path
        if content is not None
        else project_root / "docs" / "lessons" / f"week{week:02d}.md"
    )
    try:
        doc_ref = doc_path.resolve().relative_to(project_root).as_posix()
    except ValueError:
        doc_ref = doc_path.resolve().as_posix()
    glossary = _artifact_glossary(artifact_names, week, content)
    payload = {
        "schema_version": 2,
        "week": week,
        "title": lesson.title,
        "phase": lesson.phase,
        "runner": lesson.runner,
        "quick": quick,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "artifacts": artifact_names,
        "doc_refs": [doc_ref],
        "artifact_glossary": glossary,
    }
    _write_json(destination / "manifest.json", payload)
    result = _write_json(destination / "run_manifest.json", payload)
    _write_guide(
        destination,
        week=week,
        title=lesson.title,
        doc_path=doc_path,
        reading_order=content.reading_order if content is not None else [],
        artifacts=artifact_names,
        glossary=glossary,
    )
    return result


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
