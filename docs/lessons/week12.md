---
week: 12
title: "阶段验收与研究报告"
phase: "模拟盘"
reading_order:
  - "先复习第 11 周执行账本与对账边界"
  - "再阅读本文的回撤、PSI、停止规则、锁存状态与阶段报告"
  - "运行 python scripts/learn.py 12"
  - "按 daily_monitoring→stop_rules→summary→PNG→stage_report/report→验收顺序复核"
artifacts:
  daily_monitoring.csv:
    summary: "逐日保存合成净值、回撤、信号 PSI、停止决定和锁存状态。"
    columns:
      date: "连续监控记录对应的交易日期。"
      nav: "由初始资金和截至当日合成收益累乘得到的净值。"
      daily_return: "用于更新当日净值的合成日收益率。"
      drawdown: "当日净值相对截至当日历史峰值的有符号回撤。"
      psi: "当日信号样本相对固定基准信号分布的五箱 PSI。"
      should_stop: "当日回撤或 PSI 是否至少触发一项停止规则。"
      strategy_halted: "首次触发停止后持续保持为真的锁存停机状态。"
      reconciliation_matched: "固定写为真的阶段占位字段，不代表真实账户对账结果。"
  stop_rules.csv:
    summary: "逐日保存停止规则决定、触发原因及规则使用的风险指标。"
    columns:
      date: "停止规则评估对应的交易日期。"
      should_stop: "当日至少命中一个预设停止原因时为真。"
      reasons: "以竖线连接的停止原因码，无触发原因时为空。"
      max_drawdown: "截至当日净值路径的正值最大回撤幅度。"
      psi: "当日停止规则评估使用的信号分布 PSI。"
  summary.csv:
    summary: "以指标名和 week12 数值列汇总监控天数、风险极值和首次停止位置。"
    columns:
      "Unnamed: 0": "CSV 中未显式命名的首列，保存监控天数、期末净值、风险极值和停止状态等汇总指标名称。"
      week12: "第 12 周各汇总指标对应的数值。"
  stage_report.md:
    summary: "记录阶段监控范围、风险结果、首次停止日期和治理结论。"
  stage_monitoring.png:
    summary: "展示十四日净值、首次停止标记、回撤与 PSI 阈值。"
  report.md:
    summary: "与阶段报告同步摘要监控结果、停止规则和合成数据边界。"
  homework.md:
    summary: "要求复核首次停止原因并补全故障处置与下一阶段准入结论。"
  acceptance.json:
    summary: "保存第 12 周机器可读的课程验收标准与完成状态。"
  acceptance_checklist.md:
    summary: "提供第 12 周阶段监控与研究报告的人工验收清单。"
  manifest.json:
    summary: "记录第 12 周运行元数据、产物清单及讲义字段释义。"
  run_manifest.json:
    summary: "与 manifest.json 同步保存本次第 12 周运行清单。"
---

# 第 12 周：阶段验收与研究报告

本周将前 11 周的方法放进连续监控和治理框架：用 14 个交易日的离线合成净值、信号分布 PSI、对账占位状态和预先声明的阈值生成停止决定，并在首次触发后锁存停机状态。目标是证明“异常能被检测、停止可复算、恢复不能被静默自动化”，不是证明两周模拟盘策略有效。

## 学习目标

1. 从净值序列复算逐日回撤与全期最大回撤。
2. 写出 PSI 公式，解释基准分箱、平滑项和适用边界。
3. 区分当日 `should_stop`、锁存后的 `strategy_halted` 和恢复决策。
4. 从两个 CSV 独立复核首次停止日期、原因和阈值。
5. 写出包含失败条件、局限、复现步骤和下一阶段准入结论的阶段报告。

## 前置知识与实验设定

实验固定 seed，生成 14 个工作日收益，初始净值 1,000,000；第 10 个观测被注入 \(-7\%\) 日收益。另生成 200 个基准信号值，每日生成 100 个当前信号值；前 8 日均值约 0，之后均值移到约 0.9，用于制造分布漂移。

监控阈值预先设定为：

- 最大回撤达到或超过 5%；
- PSI 达到或超过 0.25。

任一条件触发即 `should_stop=True`。首次触发后 `strategy_halted` 永久保持真，演示“先停止、后调查”。本 runner 没有实现自动恢复。

## 核心理论：净值与回撤停止规则

日净值为

\[
NAV_t=1{,}000{,}000\prod_{s\le t}(1+r_s).
\]

当前峰值 \(H_t=\max_{s\le t}NAV_s\)，CSV 中有符号回撤为

\[
DD_t=\frac{NAV_t}{H_t}-1\le0.
\]

停止函数内部使用正的最大回撤幅度：

\[
MDD_t=\max_{s\le t}\left(1-\frac{NAV_s}{H_s}\right)
=-\min_{s\le t}DD_s.
\]

当 \(MDD_t\ge0.05\) 时加入原因 `MAX_DRAWDOWN`。因此 `daily_monitoring.csv` 的 `drawdown` 是负数，而 `stop_rules.csv` 的 `max_drawdown` 和 `summary.csv` 的 `max_drawdown` 是正的损失幅度；符号不同不是矛盾。

## 理论：PSI

Population Stability Index 比较基准分布和当前分布。代码先用基准样本的 0%、20%、40%、60%、80%、100% 分位点构造 5 箱，并把首尾改为无穷边界。对每箱 \(b\)，设基准比例为 \(e_b\)，当前比例为 \(a_b\)：

\[
PSI=\sum_b(a_b-e_b)\ln\frac{a_b}{e_b}.
\]

为避免零比例导致对数无定义，比例下限截到 \(\epsilon=10^{-6}\)。PSI 非负附近表示分布相似，数值越大表示边际分布差异越大。本课程阈值 0.25 是治理配置，不是普适统计定律。

必须注意：

- 分箱边界只由基准样本估计，不能每天同时重算两边边界；
- PSI 不使用标签，不能证明预测性能下降；
- PSI 不告诉你漂移来自均值、方差、尾部还是数据错误；
- 样本量、分箱数和基准区间改变都会影响数值；
- 单特征 PSI 正常不代表联合分布或其他特征正常。

若基准样本为常数，代码在当前也相同时返回 0，否则返回无穷；无穷值会触发 `PSI_DRIFT`。

## 停止决策与锁存

每日 `evaluate_stop_rules` 检查截至当日的最大回撤和当日 PSI。原因码可能是：

- `MAX_DRAWDOWN`；
- `PSI_DRIFT`；
- 在通用监控模块中还支持 `DATA_ANOMALY`、`ACCOUNT_MISMATCH`，但本周调用没有传入数据错误或账户对账对象。

`should_stop` 是该日规则评估结果。`strategy_halted` 是状态机：第一次 `should_stop=True` 后，即使后续某日 PSI 回落，仍保持真。恢复应要求根因定位、数据修复、离线重放、影子运行和人工批准，不能因为指标暂时回到阈值内就自动重启。

`daily_monitoring.csv` 中 `reconciliation_matched` 被 runner 固定写为 `True`，只是阶段表中的占位字段，不是从第 11 周订单、成交或外部账户复算所得。不得用它宣称账户对账已经被真实验证。

## 阅读顺序

先复习第 11 周真实对账应具备的证据，再学习回撤、PSI 和锁存停止状态；运行后依次复算 daily monitoring、连接 stop rules、核对 summary、阅读 PNG，最后审查两个报告。准入结论只能在作业、局限和验收全部完成后给出。

## 实验步骤

1. 运行 `python scripts/learn.py 12`。
2. 从 manifest 核对 `week=12`、标题、phase、runner、quick 和所有声明产物。
3. 从第一行起用 `daily_return` 累乘复算 NAV；允许 CSV 浮点精度范围内微小差异。
4. 用历史峰值复算负的 `drawdown`，再转成正的累计最大回撤。
5. 对每行检查：`should_stop` 是否等于“最大回撤幅度 ≥ 0.05 或 PSI ≥ 0.25”。
6. 找到第一次 `should_stop=True` 的日期，并验证此后 `strategy_halted` 全为真。
7. 将 daily monitoring 与 `stop_rules.csv` 按日期连接，核对布尔值、原因和指标。
8. 复算 summary 的期末净值、最大回撤、最大 PSI、首次停止日序号。
9. 阅读 PNG、`stage_report.md` 和 `report.md`，确认结论与 CSV 一致且没有宣称策略有效。
10. 补全作业和阶段报告后完成验收，明确是否允许进入第 13 周。

## 逐文件与字段解释（产物与字段字典）

### `daily_monitoring.csv`

- `date`：连续 14 个工作日。
- `nav`：从初始资金和合成日收益累乘得到的净值。
- `daily_return`：当日合成收益，第 10 个观测被注入 -7%。
- `drawdown`：当前净值相对截至当日峰值的有符号回撤，非正数。
- `psi`：当日信号样本相对固定基准信号的 5 箱 PSI。
- `should_stop`：当日规则是否至少命中一个原因。
- `strategy_halted`：首次停止后锁存的停机状态。
- `reconciliation_matched`：固定为真占位，不是实际账户对账结果。

### `stop_rules.csv`

- `date`：规则评估日期。
- `should_stop`：当日停止决定，应与 monitoring 同日字段一致。
- `reasons`：原因码用 `|` 拼接；无原因时为空。
- `max_drawdown`：截至当日正的最大回撤幅度。
- `psi`：当日 PSI。

若两个条件同日触发，`reasons` 可同时包含两个原因。判断时不要依赖整串文本顺序，应拆分原因码。

### `summary.csv`

指标索引配 `week12` 值列：

- `monitoring_days`：14。
- `ending_nav`：最后一日净值。
- `max_drawdown`：全期最大回撤的正幅度。
- `max_psi`：全期 PSI 最大值。
- `stop_triggered`：是否曾触发，以 1.0/0.0 保存。
- `first_stop_day`：首次停止在 14 日序列中的 1 基序号；未触发则为 0。

`first_stop_day` 不是月份日期，也不是 DataFrame 的 0 基索引。

### 图表解读：`stage_monitoring.png`

上图为 14 日 NAV，红色竖虚线标记首次停止日。下图同时画负的 `drawdown` 与非负的 `psi`，并画 \(-0.05\) 和 \(0.25\) 阈值。两种不同量纲共用坐标轴只便于教学定位，不适合比较数值大小。应分别按各自阈值判断。

### `stage_report.md` 与 `report.md`

两者内容相同：范围、期末净值、最大回撤、最大 PSI、是否停止、首次停止日期和风险结论。runner 先写 `stage_report.md`，再由统一收尾把同一文本写入 `report.md`。报告明确“回撤 5% 或 PSI 0.25”触发和合成数据边界。

### 作业与控制文件

`homework.md` 要求复核停止日、区分故障类别并补全阶段报告。`acceptance.json` 有三条验收标准；checklist 是人工版。两个 manifest 记录运行元数据。完成实验生成只代表 `completed`，经作业和人工审阅后才应进入 `reviewed`。

## 动态指标判断与结果边界

可以判断监控记录是否连续、公式是否可复算、阈值是否按预声明执行、停止状态是否锁存，以及阶段报告是否忠实。不能由 14 日数据判断策略长期收益、真实漂移频率、阈值最优性或生产系统可靠性。

停止规则命中也不等于策略经济逻辑永久失效：

- 回撤可能来自正常但超出风险预算的波动；
- PSI 可能来自市场状态变化，也可能来自数据口径错误；
- 数据异常和账户不一致属于操作风险，不应与 alpha 衰减混为一谈。

但在根因未知时，治理动作仍应先停。停止阈值是风险承诺，不应因“相信模型”而临时放宽。

## 常见误区（常见误读）

1. 将 CSV 的负 `drawdown` 与 summary 的正 `max_drawdown` 当成冲突。
2. 将 PSI 0.25 当统计显著性或所有市场的标准答案。
3. PSI 超阈值就断言模型失效；它只说明输入边际分布变化。
4. 当日 `should_stop` 回到假就自动恢复，忽略锁存状态。
5. 把固定为真的 `reconciliation_matched` 当真实账户对账证据。
6. 用 14 日 NAV 证明策略有效。
7. 看到注入的 -7% 后才事后设计 5% 阈值。
8. 只写“停止”，不定义撤单、冻结、通知、调查和恢复门槛。

## 思考题

1. PSI 对均值平移和尾部变化的敏感性如何受分箱数影响？
2. 若 PSI 超阈值但模型 Rank IC 正常，应停、降级还是影子运行？
3. 回撤规则使用组合净值、策略超额净值还是单模型净值，各有何后果？
4. 为什么自动停止通常比自动恢复更容易治理？
5. 如何把第 11 周真实订单/账户对账结果接入 `evaluate_stop_rules`？
6. 阶段准入应要求哪些独立复现证据，而不只看收益？

## 作业提示

复核首次停止日时分别计算两个布尔条件，并保存原因，不要只复制 `should_stop`。处置流程至少区分策略表现、数据异常、模型漂移和账户不一致，写明负责人、立即动作、调查证据和恢复门槛。阶段报告必须包含失败实验、已知局限、固定 seed、运行命令、产物路径以及“允许/有条件允许/不允许进入下一阶段”的明确结论。

## 验收标准

- [ ] 14 个交易日均有完整监控和规则记录。
- [ ] 能复算 NAV、负回撤、正的最大回撤和 PSI 触发判断。
- [ ] `daily_monitoring.csv` 与 `stop_rules.csv` 按日期完全对得上。
- [ ] 首次停止日可复算，且之后 `strategy_halted` 始终为真。
- [ ] 明确 PSI 不证明模型失效，固定对账字段也不证明真实账户一致。
- [ ] 阶段报告包含失败条件、局限、复现步骤、停止/恢复门槛和下一阶段准入结论。
- [ ] 未用两周合成数据宣称策略具有真实市场有效性。
