import json
from pathlib import Path

import pytest

import ashare_quant.lesson_content as lesson_content_module
from ashare_quant.lesson_content import load_lesson_content
from ashare_quant.lesson_io import read_manifest, write_manifest


def _write_lesson(path: Path, *, title: str = "收益与风险") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
week: 1
title: {title}
phase: 基础
reading_order:
  - 阅读讲义
  - 查看 daily_data.csv
  - 完成验收
artifacts:
  daily_data.csv:
    summary: 每日收益与净值路径。
    columns:
      return: 日收益率
      wealth: 累计净值
  homework.md:
    summary: 本周作业。
---
# 收益与风险

先理解路径依赖。
""",
        encoding="utf-8",
    )


def test_load_lesson_content_parses_frontmatter_and_body(tmp_path) -> None:
    lesson_path = tmp_path / "docs" / "lessons" / "week01.md"
    _write_lesson(lesson_path)

    content = load_lesson_content(1, lessons_dir=lesson_path.parent)

    assert content.week == 1
    assert content.reading_order[1] == "查看 daily_data.csv"
    assert content.artifacts["daily_data.csv"].columns == {
        "return": "日收益率",
        "wealth": "累计净值",
    }
    assert content.body.startswith("# 收益与风险")


def test_load_lesson_content_validates_registry(tmp_path) -> None:
    lesson_path = tmp_path / "week01.md"
    _write_lesson(lesson_path, title="错误标题")

    with pytest.raises(ValueError, match="lesson_registry"):
        load_lesson_content(lesson_path)


def test_write_manifest_generates_guide_from_lesson(tmp_path, monkeypatch) -> None:
    lessons_dir = tmp_path / "docs" / "lessons"
    lesson_path = lessons_dir / "week01.md"
    _write_lesson(lesson_path)
    monkeypatch.setattr(lesson_content_module, "_default_lessons_dir", lambda: lessons_dir)
    output = tmp_path / "artifacts" / "learning" / "week01"

    returned = write_manifest(
        output,
        week=1,
        quick=True,
        artifacts=("daily_data.csv", "homework.md", "acceptance.json"),
    )

    manifest = read_manifest(output)
    assert returned == output / "run_manifest.json"
    assert manifest["schema_version"] == 2
    assert manifest["doc_refs"] == [lesson_path.resolve().as_posix()]
    assert manifest["artifact_glossary"]["daily_data.csv"]["columns"]["return"] == "日收益率"
    assert manifest["artifact_glossary"]["acceptance.json"]["summary"]
    assert json.loads((output / "manifest.json").read_text(encoding="utf-8")) == manifest

    guide = (output / "GUIDE.md").read_text(encoding="utf-8")
    assert "[docs/lessons/week01.md]" in guide
    assert "python scripts/learn.py 1" in guide
    assert "查看 daily_data.csv" in guide
    assert "| `daily_data.csv` | 每日收益与净值路径。" in guide
    assert "## 通关步骤" in guide
