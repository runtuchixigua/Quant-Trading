# 第 1–12 周入门课程手册

本手册是 24 周课程的入门阶段。完成本阶段并通过第 12 周流程验收后，再进入 [第 13–24 周进阶课程](course_advanced.md)。进阶阶段统一使用 [数据字典](data_dictionary.md)、[进阶研究日志](research_log_advanced.md) 和 [实验清单规范](experiment_manifest_spec.md)，最终按 [毕业报告模板](graduation_report_template.md) 提交成果。

## 统一执行与通关规则

每周在项目根目录运行 `python scripts/learn.py N`，默认输出到
`artifacts/learning/weekNN/`。`--list` 列出课程，`--status` 查看进度，
`--quick` 使用快速教学数据，`--force` 重新运行已完成周次，
`N --mark-reviewed` 将已完成且经审阅的周次标记为 `reviewed`。

`completed` 只表示实验生成成功；完成输出目录内的 `homework.md`、按
`acceptance.json` 验收并经人工审阅后，才是 `reviewed`。上一周达到
`reviewed` 后再继续，快速运行也不能跳过作业和验收。

## 第 1 周：收益与风险

课程唯一入口是项目根目录的以下命令：

```bash
python scripts/learn.py 1
```

命令完成后，只处理 `artifacts/learning/week01/` 中的文件。不要提前运行完整回测
或进阶流水线。详细操作见 [从这里开始](../START_HERE.md)。
完成作业与验收并标记 `reviewed` 后，第 2 周入口是
`python scripts/learn.py 2`，输出到 `artifacts/learning/week02/`。

学习简单收益、对数收益和复利。算术平均日收益不能直接代表长期增长率，因为财富按乘法演化，波动会造成复利损耗。完成以下任务：

1. 第 1 天：运行离线实验，理解 `daily_data.csv` 的四列。
2. 第 2–3 天：不用 `metrics.py`，自行计算净值与最大回撤。
3. 第 4 天：完成收益顺序打乱实验，观察路径风险。
4. 第 5 天：填写 `homework.md`，记录假设和仍不理解的问题。
5. 可选：完成离线实验后，再获取 510300 后复权日线重复实验，并保留原始文件。

验收：提交 `homework.md` 和自己的计算代码；能解释“总收益相同但路径不同为何最大
回撤不同”。使用真实数据的同学还需解释前复权和后复权各适合什么场景。

## 第 2 周：A 股市场机制

执行 `python scripts/learn.py 2`，输出到 `artifacts/learning/week02/`；完成其中
的作业与验收、经审阅标记 `reviewed` 后再继续。

重点掌握 T+1、100 股整数手、主板/创业板/科创板涨跌幅规则、ST、停牌、除权除息、上市和退市。涨跌停价格不意味着必然成交，回测中的可成交假设必须保守。

任务：制作一份字段字典，至少包含交易日、代码、OHLC、成交量、复权因子、停牌、ST、涨跌停状态和上市日期。逐字段写明来源、发布时间和可用时点。

## 第 3–5 周：回测

按顺序执行：

```bash
python scripts/learn.py 3  # artifacts/learning/week03/
python scripts/learn.py 4  # artifacts/learning/week04/
python scripts/learn.py 5  # artifacts/learning/week05/
```

每一周都先完成对应目录中的作业与验收，经审阅标记 `reviewed` 后再运行下一条。

先阅读 `backtest.py` 的时间顺序。某日先由旧持仓获得当日收益，再在收盘执行前一日信号；执行后的持仓从下一日开始产生收益。

实验顺序：

1. 买入持有等权组合，和同股票池等权基准对比。
2. 实现 20/60 日均线、60 日动量与短期反转。
3. 分别令佣金、滑点和印花税为 0、基准值、基准值两倍，观察策略是否脆弱。
4. 人工制造涨停买单、跌停卖单和停牌订单，检查 `rejected_turnover`。
5. 故意把未来 20 日收益作为信号，确认异常高收益，再删除泄漏；把该实验保留为反例测试。

不要仅挑最佳参数。先约定少量有经济含义的参数，再报告全部结果。

## 第 6–8 周：因子和组合

按顺序执行：

```bash
python scripts/learn.py 6  # artifacts/learning/week06/
python scripts/learn.py 7  # artifacts/learning/week07/
python scripts/learn.py 8  # artifacts/learning/week08/
```

每一周都先完成对应目录中的作业与验收，经审阅标记 `reviewed` 后再运行下一条。

标准流程是：定义股票池 → 构造原始因子 → 按日去极值 → 行业与市值中性化 → 标准化 → 计算未来收益标签 → IC/分组检验 → 组合约束 → 成本后回测。

建议研究：

- 动量：过去 60/120/252 日收益，跳过最近 5–20 日。
- 低波动：过去 60 日波动率取负。
- 估值：EP、BP；必须正确处理负值和公告时点。
- 质量：ROE、毛利率、应计项；使用 point-in-time 财务数据。
- 流动性：成交额、换手率或 Amihud 指标。

每个因子报告 Rank IC 均值、ICIR、分年度 IC、五分组收益、单调性、换手和因子相关性。组合至少限制单股权重和行业偏离，并做成本敏感性分析。

## 第 9–10 周：机器学习

按顺序执行：

```bash
python scripts/learn.py 9   # artifacts/learning/week09/
python scripts/learn.py 10  # artifacts/learning/week10/
```

每一周都先完成对应目录中的作业与验收，经审阅标记 `reviewed` 后再运行下一条。

把每个交易日的股票视为一个横截面，预测未来固定期限的超额收益或排序。先用 Ridge 作为基线，再考虑 LightGBM/排序模型。

关键约束：

- 标签期限为 20 日时，预测日之前至少隔离 20 个交易日，避免尚未实现的训练标签。
- 缺失值填充和标准化只在训练窗口拟合。
- 不随机打散，不根据最终测试区间反复调参。
- 比较对象是简单因子模型，不是零模型。

验收：保存每次训练截止日、特征列表、模型参数、每日 Rank IC，以及 ML 相对基线的成本后增量。

## 第 11–12 周：模拟盘

按顺序执行：

```bash
python scripts/learn.py 11  # artifacts/learning/week11/
python scripts/learn.py 12  # artifacts/learning/week12/
```

每一周都先完成对应目录中的作业与验收，经审阅标记 `reviewed` 后再运行下一条；
第 12 周审阅通过后才进入进阶课程。

每天固定时间运行：

1. 获取并校验新数据，失败时停止而不是沿用不明数据。
2. 生成信号和目标权重，记录模型及数据版本。
3. 检查停牌、涨跌停、T+1、整数手和现金。
4. 保存订单、成交、拒单、持仓、现金与净值。
5. 对比理论成交与模拟成交，解释偏差。

至少连续运行两周。预先定义停止规则：数据异常、持仓无法对账、回撤超过研究阈值或模型输入分布显著漂移。两周只是流程验收，不足以证明策略有效。

## 毕业报告结构

1. 研究问题与经济逻辑。
2. 数据来源、时间范围、股票池和 point-in-time 处理。
3. 信号定义与所有参数。
4. 回测时间线、成交假设和成本。
5. 样本内、验证集、最终样本外结果。
6. 风险、容量、换手、年度和市场状态分析。
7. 失败实验与已知局限。
8. 复现命令、环境和数据版本。

以上结构可用于第 12 周阶段总结；第 24 周最终提交应使用进阶毕业报告模板，并补充风险归因、容量、稳健性、失败实验和独立复现证据。
