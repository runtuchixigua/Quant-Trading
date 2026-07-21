from ashare_quant.lesson_content import load_lesson_content
from ashare_quant.lesson_registry import get_lesson


REQUIRED_SECTIONS = (
    "学习目标",
    "前置知识",
    "核心理论",
    "实验步骤",
    "阅读顺序",
    "字段",
    "图表解读",
    "动态指标判断",
    "常见误区",
    "思考题",
    "作业提示",
    "验收标准",
)


def test_all_24_lessons_have_complete_teaching_content() -> None:
    for week in range(1, 25):
        content = load_lesson_content(week)
        registered = get_lesson(week)

        assert content.week == week
        assert content.title == registered.title
        assert content.phase == registered.phase
        assert content.reading_order
        assert all(section in content.body for section in REQUIRED_SECTIONS)


def test_every_declared_csv_has_specific_column_explanations() -> None:
    for week in range(1, 25):
        content = load_lesson_content(week)
        for filename, artifact in content.artifacts.items():
            if not filename.endswith(".csv"):
                continue
            assert artifact.columns, f"week {week} 的 {filename} 缺少字段解释"
            assert all(
                description and "未单独提供" not in description
                for description in artifact.columns.values()
            )
