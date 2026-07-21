# 从这里开始

不要先读完整源码，也不要先运行 24 周毕业流水线。第一次学习只做第 1 周。

## 第一次运行

在项目根目录依次执行：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/learn.py 1
```

这一步使用离线合成数据，不需要注册数据服务，也不需要联网。

## 以后每周都用同一个入口

在 `python scripts/learn.py N` 中把 `N` 替换为周次（`1`–`24`）；默认输出目录是
`artifacts/learning/weekNN/`。辅助命令如下：

```bash
python scripts/learn.py --list             # 列出全部周次
python scripts/learn.py --status           # 查看 completed/reviewed 等状态
python scripts/learn.py N --quick           # 快速教学运行，不替代正式验收
python scripts/learn.py N --force           # 重新运行已完成周次
python scripts/learn.py N --mark-reviewed   # 作业与验收经审阅通过后标记
```

实验成功生成后状态是 `completed`，只说明程序执行完成；`reviewed` 表示
`homework.md` 已完成、`acceptance.json` 已逐项验收并经过人工审阅。不要把
`completed` 当作通关，也不要在未审阅时提前标记。使用 `--force` 前先保存需要
保留的旧实验记录。

## 你会得到什么

命令会创建 `artifacts/learning/week01/`：

- `daily_data.csv`：价格、日收益、复利净值和回撤；
- `metrics.csv`：年化收益、波动、Sharpe 和最大回撤；
- `wealth_and_drawdown.png`：净值与回撤图；
- `homework.md`：本周必须提交的四道题。

## 正确的学习顺序

1. 运行命令，先观察输出，不看实现。
2. 打开图表和 CSV，尝试解释每一列。
3. 自己重新实现累计净值与最大回撤，不直接复制 `metrics.py`。
4. 完成 `homework.md`。
5. 按 `acceptance.json` 逐项检查，把作业、代码和“不理解的问题”发给我审阅。
6. 审阅通过后执行 `python scripts/learn.py 1 --mark-reviewed`。
7. 确认状态为 `reviewed` 后，再开始 [第 2 周](docs/course.md)：

```bash
python scripts/learn.py 2
```

## 第 1 周通过标准

你需要能够独立解释：

- 简单收益与复利净值的关系；
- 为什么 `mean(daily_return) * 252` 不等于长期复合收益；
- 最大回撤为什么依赖收益发生顺序；
- Sharpe 高不等于一定赚钱，也不代表尾部风险小。

当前阶段不用做：

- 不用研究 LightGBM；
- 不用运行 `run_course_demo.py` 或 `run_advanced_demo.py`；
- 不用下载全市场数据；
- 不用考虑实盘和券商接口。

先完成一课，再进入下一课。
