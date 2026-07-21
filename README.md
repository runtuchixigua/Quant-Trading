# A 股量化交易 24 周课程项目

目标不是展示一条“高收益曲线”，而是建立可信的研究闭环：数据时间点正确、交易约束可解释、验证严格、实验可复现。

## 第一次学习：只从这里开始

先阅读 [START_HERE.md](START_HERE.md)，然后执行：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/learn.py 1
```

完成 `artifacts/learning/week01/homework.md` 并提交审阅后，再进入第 2 周。
第一次学习不要运行完整演示，它们是阶段验收工具，不是课程入口。

## 统一学习命令

所有周次都从项目根目录执行 `python scripts/learn.py N`，其中 `N` 为 `1` 到
`24`。默认输出到 `artifacts/learning/weekNN/`。常用操作：

```bash
python scripts/learn.py --list             # 列出 24 周课程
python scripts/learn.py --status           # 查看各周进度
python scripts/learn.py N --quick           # 使用快速教学数据
python scripts/learn.py N --force           # 明确重新生成已完成周次的产物
python scripts/learn.py N --mark-reviewed   # 人工审阅通过后标记 reviewed
```

运行成功只表示实验已生成，状态为 `completed`；它不表示作业或验收已通过。
完成该周 `homework.md`、按 `acceptance.json` 验收并提交审阅后，才标记为
`reviewed` 并继续下一周。`--force` 可能重新生成产物，使用前先确认需要保留的
实验记录已另行保存；`--quick` 用于缩短教学运行，不替代正式验收。

## 阶段验收命令

完成对应阶段后才使用：

```bash
pytest
python scripts/run_course_demo.py
python scripts/run_advanced_demo.py
```

两个验收演示均使用固定随机种子的合成数据，因此无需联网。入门结果写入
`artifacts/demo/`，进阶结果默认写入带时间戳的 `artifacts/advanced_*`。合成数据
只能验证代码流程，不能用于评价策略是否有效。自定义进阶实验可执行：

```bash
python scripts/run_advanced_demo.py \
  --config configs/advanced_research.yaml \
  --output artifacts/my_first_advanced_run
```

输出目录必须尚不存在，以避免覆盖旧实验。

需要下载 510300 ETF 数据时：

```bash
pip install -e ".[data]"
```

然后调用 `ashare_quant.data.fetch_510300()`。AkShare 是学习入口，不保证生产级稳定性；真实研究应保存原始快照、数据版本和获取时间。

## 24 周课程入口

课程分为 12 周入门阶段与 12 周进阶阶段。每周依次阅读对应章节，完成实验、作业和量化验收；每次实验都应保留配置、指标、图表和结论，不覆盖旧结果。

### 第 1–12 周：入门

- [入门课程手册](docs/course.md)
- [入门研究日志模板](docs/research_log_template.md)
- 第 1–2 周：依次执行 `python scripts/learn.py 1`、`python scripts/learn.py 2`，
  学习收益、风险、复权与 A 股交易制度。
- 第 3–5 周：依次执行周次 `3`、`4`、`5`，完成无未来函数回测、交易成本和
  成交约束实验。
- 第 6–8 周：依次执行周次 `6`、`7`、`8`，完成因子预处理、IC、分组检验和
  组合构建实验。
- 第 9–10 周：依次执行周次 `9`、`10`，完成横截面预测、标签隔离和
  walk-forward 实验。
- 第 11–12 周：依次执行周次 `11`、`12`，完成模拟成交、运行日志和阶段报告。

每周输出目录均为 `artifacts/learning/weekNN/`；上一周达到 `reviewed` 后再执行
下一周。第 1 周审阅通过后的明确入口是：

```bash
python scripts/learn.py 2
```

### 第 13–24 周：进阶

- [进阶课程手册](docs/course_advanced.md)：逐周理论、实验、作业、思考题、陷阱和验收标准。
- [数据字典](docs/data_dictionary.md)：字段语义、时点、质量规则与版本管理。
- [进阶研究日志](docs/research_log_advanced.md)：研究假设、证据链、偏差检查与决策记录。
- [实验清单规范](docs/experiment_manifest_spec.md)：实验身份、配置、输入、输出与可复现约束。
- [毕业报告模板](docs/graduation_report_template.md)：完整研究报告与答辩检查表。

进阶阶段路线：

1. 第 13–15 周：依次执行周次 `13`–`15`，完成 point-in-time 数据工程、股票池偏差与事件研究。
2. 第 16–18 周：依次执行周次 `16`–`18`，完成多因子诊断、风险模型与约束优化。
3. 第 19–21 周：依次执行周次 `19`–`21`，完成稳健验证、市场状态与机器学习解释。
4. 第 22–24 周：依次执行周次 `22`–`24`，完成执行容量、组合监控与毕业研究复现。

每周仍使用 `python scripts/learn.py N`，输出到 `artifacts/learning/weekNN/`，并在
作业、验收和审阅全部完成后才进入下一周。

## 模块

- `data.py`：行情校验、合成教学数据、可选在线数据入口。
- `metrics.py`：复利净值、年化指标、Sharpe、回撤与 Calmar。
- `backtest.py`：信号强制滞后一日，处理成本、停牌和涨跌停。
- `factors.py`：去极值、标准化、中性化、IC 与分组收益。
- `fundamentals.py` / `universe.py`：公告日 PIT 对齐与历史时点股票池。
- `portfolio.py` / `risk.py`：约束组合优化、协方差估计和风险归因。
- `ml.py` / `validation.py`：可插拔模型、purged/embargo 验证与压力测试。
- `execution.py` / `paper.py`：容量、冲击、整数手、T+1 和连续模拟盘。
- `monitor.py`：数据质量、账户对账、漂移和停止规则。
- `pipeline.py`：配置驱动的第 24 周毕业研究流水线。

## 研究纪律

- 任何 `t` 日收盘后才能知道的信号，最早在 `t+1` 日执行。
- 财务数据按实际公告日对齐，不能按报告期末对齐。
- 股票池必须使用历史时点成分，不能拿今天仍上市的股票回看历史。
- 随机切分不适用于时间序列策略评估；模型选择和最终测试集必须分离。
- 优先报告样本外、成本后的收益，同时给出换手、回撤、年度稳定性和基准。
- 在模拟流程稳定、数据和风控经过检查前，不投入真实资金。

本项目仅用于教育和研究，不构成投资建议。
