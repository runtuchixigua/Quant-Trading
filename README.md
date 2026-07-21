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

课程分为 12 周入门阶段与 12 周进阶阶段。每周运行后，先读
`artifacts/learning/weekNN/GUIDE.md`，再读下方对应的静态讲义。`GUIDE.md`
解释本次运行真实生成的文件、路径和检查顺序；静态讲义解释理论、字段语义、实验方法
和常见误区。两者职责不同，不要跳过其中之一。

运行成功得到 `completed` 只代表实验程序完成，不等于作业和验收已被审阅；
完成 `homework.md`、按 `acceptance.json` 验收并经人工审阅后才是 `reviewed`。
每次实验都应保留配置、指标、图表和结论，不覆盖旧结果。

### 第 1–12 周：入门

- [入门课程手册](docs/course.md)
- [入门研究日志模板](docs/research_log_template.md)
- [第 1 周：收益与风险](docs/lessons/week01.md)
- [第 2 周：A 股市场机制](docs/lessons/week02.md)
- [第 3 周：无未来函数回测](docs/lessons/week03.md)
- [第 4 周：交易成本与成交约束](docs/lessons/week04.md)
- [第 5 周：回测偏差与稳健性](docs/lessons/week05.md)
- [第 6 周：因子构造与预处理](docs/lessons/week06.md)
- [第 7 周：IC 与分组检验](docs/lessons/week07.md)
- [第 8 周：组合构建与风险约束](docs/lessons/week08.md)
- [第 9 周：横截面机器学习](docs/lessons/week09.md)
- [第 10 周：Walk-Forward 与标签隔离](docs/lessons/week10.md)
- [第 11 周：模拟盘与执行](docs/lessons/week11.md)
- [第 12 周：阶段验收与研究报告](docs/lessons/week12.md)

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

- [第 13 周：Point-in-Time 数据工程与可追溯性](docs/lessons/week13.md)
- [第 14 周：历史股票池、退市与选择偏差](docs/lessons/week14.md)
- [第 15 周：事件研究与公告效应](docs/lessons/week15.md)
- [第 16 周：多因子诊断与冗余控制](docs/lessons/week16.md)
- [第 17 周：风险模型与收益归因](docs/lessons/week17.md)
- [第 18 周：约束组合优化与估计误差](docs/lessons/week18.md)
- [第 19 周：嵌套验证、过拟合与统计可信度](docs/lessons/week19.md)
- [第 20 周：市场状态、压力测试与尾部风险](docs/lessons/week20.md)
- [第 21 周：机器学习稳定性、漂移与解释](docs/lessons/week21.md)
- [第 22 周：执行建模、冲击成本与策略容量](docs/lessons/week22.md)
- [第 23 周：组合监控、模型治理与应急演练](docs/lessons/week23.md)
- [第 24 周：毕业研究、独立复现与答辩](docs/lessons/week24.md)

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
