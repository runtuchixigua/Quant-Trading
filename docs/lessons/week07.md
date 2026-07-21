---
week: 7
title: "IC 与分组检验"
phase: "因子与组合"
reading_order:
  - "先复习第 6 周因子预处理与 forward_returns 的标签时点"
  - "再阅读本文的 Rank IC、ICIR、五分组与衰减理论"
  - "运行 python scripts/learn.py 7"
  - "按本文顺序检查 CSV、PNG、report、homework 与 acceptance"
artifacts:
  ic_series.csv:
    summary: "逐日保存动量因子与固定期限未来收益之间的 Spearman Rank IC。"
    columns:
      date: "计算横截面 Rank IC 的交易日期。"
      rank_ic: "当日因子排序与未来收益排序的 Spearman 相关系数。"
  quantile_returns.csv:
    summary: "逐日保存按因子值从低到高划分的五组未来等权收益。"
    columns:
      date: "进行因子分组与未来收益评价的交易日期。"
      "1": "当日因子值最低组 Q1 的未来等权平均收益。"
      "2": "当日因子值第二组 Q2 的未来等权平均收益。"
      "3": "当日因子值中间组 Q3 的未来等权平均收益。"
      "4": "当日因子值第四组 Q4 的未来等权平均收益。"
      "5": "当日因子值最高组 Q5 的未来等权平均收益。"
  ic_decay.csv:
    summary: "保存信号按不同滞后期使用时的跨日期平均 Rank IC。"
    columns:
      lag: "因子信号相对评价日期滞后的期数。"
      mean_rank_ic: "对应信号滞后期下逐日 Rank IC 的平均值。"
  summary.csv:
    summary: "以指标名和 week07 数值列汇总 IC、分组收益差与有效日期数。"
    columns:
      "Unnamed: 0": "CSV 中未显式命名的首列，保存平均 IC、正值比例、Q5-Q1 和有效日期数等汇总指标名称。"
      week07: "第 7 周各汇总指标对应的数值。"
  factor_evaluation.png:
    summary: "展示累计 Rank IC、五组平均未来收益和 IC 衰减曲线。"
  report.md:
    summary: "摘要平均 Rank IC、Q5-Q1 收益差及信号衰减的解释边界。"
  homework.md:
    summary: "要求复算 IC、检查五分组单调性并说明实验结论边界。"
  acceptance.json:
    summary: "保存第 7 周机器可读的课程验收标准与完成状态。"
  acceptance_checklist.md:
    summary: "提供第 7 周实验结果的人工逐项验收清单。"
  manifest.json:
    summary: "记录第 7 周运行元数据、产物清单及讲义字段释义。"
  run_manifest.json:
    summary: "与 manifest.json 同步保存本次第 7 周运行清单。"
---

# 第 7 周：IC 与分组检验

本周回答的不是“这个因子赚不赚钱”，而是更基础的问题：在每个截面上，因子排序与随后收益排序是否存在稳定关系；这种关系能否在分组收益中看到；信号延迟使用后是否迅速失效。实验使用固定随机种子的离线合成数据，只验证计算和解释流程，不构成真实 A 股有效性证据。

## 学习目标

完成本周后，你应当能够：

1. 从定义独立复算单日 Spearman Rank IC、全期平均 IC、正值比例与 ICIR。
2. 解释五分组检验的排序方向、Q1/Q5 含义、单调性和 Q5−Q1 多空差。
3. 区分“IC 显著”“分组单调”“可交易收益”三个不同命题。
4. 阅读 IC 衰减曲线，并只把它作为调仓频率的输入之一。
5. 识别样本少、横截面少、重叠标签、极端日期和数据泄漏造成的误读。

## 前置知识与时间对齐

第 6 周已完成按日去极值、中性化和标准化。本周 runner 使用动量因子的横截面 z-score 作为 `signal`，并以未来 3 个交易日（快速模式）或 5 个交易日（完整模式）的收益作为标签：

\[
R_{i,t\rightarrow t+h}=\frac{P_{i,t+h}}{P_{i,t}}-1.
\]

标签由 `forward_returns` 生成，内部是 `pct_change(h).shift(-h)`。它只能用于事后评价，严禁回填到时点 \(t\) 的特征。对每个日期，因子和未来收益按股票代码对齐，缺失配对被排除。最后 \(h\) 日没有完整未来收益，出现空值是正确现象。

## 核心理论：Rank IC 与 ICIR

对日期 \(t\) 的 \(N_t\) 只股票，Rank IC 是因子值 \(f_{i,t}\) 与未来收益 \(R_{i,t\rightarrow t+h}\) 的 Spearman 相关：

\[
IC_t=\operatorname{corr}\bigl(\operatorname{rank}(f_{i,t}),
\operatorname{rank}(R_{i,t\rightarrow t+h})\bigr).
\]

Spearman 只要求单调关系，不要求线性关系，也减弱了极端数值幅度的影响。\(IC_t>0\) 表示高因子值股票倾向于获得更高未来收益；若因子经济定义本应反向，则应先统一方向，不能看到负 IC 后临时翻转并隐去原结果。

全期平均 IC 为

\[
\overline{IC}=\frac{1}{T}\sum_{t=1}^{T}IC_t,
\]

正值比例为 \(\frac{1}{T}\sum_t\mathbf{1}(IC_t>0)\)。ICIR 常用口径是

\[
ICIR=\frac{\overline{IC}}{s(IC)},
\]

其中 \(s(IC)\) 是有效日期 IC 的样本标准差。若要年化，才额外乘 \(\sqrt{A}\)；\(A\) 应与 IC 的独立观测频率一致。由于本实验每天计算重叠的 3 日或 5 日标签，相邻 \(IC_t\) 并不独立，直接乘 \(\sqrt{252}\) 会高估精度。默认先报告未年化 ICIR，并明确标签期限和采样频率。

本周 `summary.csv` 没有现成 ICIR 字段；必须从 `ic_series.csv` 的非空 `rank_ic` 独立计算。这是有意的学习要求，不要把 `mean_rank_ic` 或正值比例误称为 ICIR。

## 理论：五分组与单调性

每个日期先按因子排序，再用 `rank(method="first")` 打破并列，按 `qcut` 分为五组。Q1 是最低因子组，Q5 是最高因子组；每组未来收益是组内股票的等权平均：

\[
r_{q,t}=\frac{1}{N_{q,t}}\sum_{i\in q}R_{i,t\rightarrow t+h}.
\]

多空差为 \(r_{5,t}-r_{1,t}\)。平均 Q5−Q1 与平均 IC 符号通常应一致，但二者不必完全同步：IC 使用全截面排序，Q5−Q1 只强调两端；非单调的中间组、组内极端收益或股票数不足都可能造成差异。

单调性不能只看一张柱图。至少检查：

- 各组全期均值是否大体随组号递增；
- 逐日 Q5−Q1 的分布、正值比例和极端日期；
- 分年度或分市场状态结果是否同向；
- 组内股票数、换手和成本是否可接受。

本 runner 只输出毛的未来等权收益，没有建仓时点、换手、手续费、滑点、涨跌停或容量模型，因此 Q5−Q1 不是可实现策略收益。

## 理论：IC 衰减

代码对滞后 \(k=0,\ldots,K\) 计算：

\[
D(k)=\operatorname{mean}_t\left[
\operatorname{RankIC}(f_{t-k},R_{t\rightarrow t+h})
\right].
\]

这里是把因子表向后移动后与当前未来收益比较，表示旧信号在晚 \(k\) 期使用时的平均排序能力。快速模式输出 0–5，完整模式输出 0–12。衰减慢说明旧信号可能仍有信息，衰减快说明延迟代价可能大；但不能据此直接选择“IC 最大”的调仓频率。真实决策还要同时考虑换手、成本、成交约束、标签重叠和信号计算延迟。

## 阅读顺序

先复习第 6 周的因子预处理和标签时点，再读 Rank IC、ICIR、分组与衰减定义；随后运行实验。产物必须按 `ic_series.csv`、`quantile_returns.csv`、`ic_decay.csv`、`summary.csv`、PNG、report 的顺序阅读，最后才完成作业和验收，避免先看摘要后为结果寻找解释。

## 实验步骤

1. 在项目根目录运行 `python scripts/learn.py 7`；若只检查流程，可显式使用 `--quick`。
2. 先打开 `manifest.json` 或 `run_manifest.json`，核对 `week=7`、标题、phase、runner、`quick` 和产物列表。
3. 检查 `ic_series.csv` 的有效日期数和空值位置，手工选一个日期用秩相关复算。
4. 用非空 IC 复算均值、样本标准差、未年化 ICIR 和正值比例，并与 `summary.csv` 对账。
5. 检查 `quantile_returns.csv` 的五组均值、Q5−Q1、单调性及异常日期。
6. 检查 `ic_decay.csv` 的 lag 范围、0 阶值和后续变化，不强求机械单调下降。
7. 最后阅读 PNG 和 `report.md`，确认文字没有超出 CSV 能支持的范围。
8. 完成 `homework.md`，再按 `acceptance.json` 或 `acceptance_checklist.md` 验收。

## 逐文件与字段解释（产物与字段字典）

### `ic_series.csv`

- 首列是写出时保留的日期索引，读入后通常名为 `date` 或未命名索引列。
- `rank_ic`：该日因子排序与未来收益排序的 Spearman 相关；范围为 \([-1,1]\)，空值表示有效配对不足或标签不可得。

### `quantile_returns.csv`

- `date`：评价截面日期，是索引写出的列。
- `1`、`2`、`3`、`4`、`5`：Q1 至 Q5 的组内未来等权收益。列名来自整数分组，CSV 读入后通常是字符串列名。

不要把每行五组相加解释为组合收益，也不要把同一日期各组样本视为跨期独立样本。

### `ic_decay.csv`

- `lag`：信号滞后期数；快速模式 0–5，完整模式 0–12。
- `mean_rank_ic`：该 lag 下跨日期平均 Rank IC。

### `summary.csv`

该文件由命名 Series 写出，通常是“指标名索引 + `week07` 值列”：

- `mean_rank_ic`：`ic_series.csv` 非空 IC 的均值。
- `rank_ic_positive_rate`：非空 IC 中大于 0 的比例。
- `q5_minus_q1`：逐日 Q5 收益减 Q1 收益后的时间均值。
- `valid_ic_dates`：非空 IC 日期数，以浮点形式保存。

### 图表解读：`factor_evaluation.png`

左图是 IC 的累计和，不是累计收益或净值；斜率表示一段时期 IC 的平均方向。中图是五组未来收益的全期均值，观察排序方向和大体单调性。右图是 IC 衰减均值。PNG 是 CSV 的可视化摘要，任何结论都应回到数值文件复算。

### 报告与控制文件

`report.md` 只摘要平均 Rank IC、Q5−Q1 和衰减用途；它不提供显著性、成本后收益或真实市场结论。`homework.md` 是学习者作答文件，runner 不覆盖已有内容。`acceptance.json` 包含 `schema_version`、`week`、`status` 及由 `description`/`accepted` 组成的 `criteria`；`acceptance_checklist.md` 是人工勾选版。两个 manifest 记录标题、phase、runner、quick、生成时间和产物清单。

## 动态指标判断与结果边界

本周可以判断计算链路是否正确、平均排序关系方向、分组是否大体单调、旧信号是否衰减，以及不同诊断是否互相矛盾。不能据此判断真实市场盈利、统计显著性、因果关系、容量、成本后收益或未来稳定性。

一个“值得继续”的教学结果应同时满足：有效日期足够、均值不是由极少数日期驱动、IC 与 Q5−Q1 方向大体一致、分组不是完全紊乱、衰减具有可解释形态。即使都满足，也只是进入更严格样本外和成本检验的资格。若结果很差，不应删除记录；应先检查方向、时点、股票池和预处理，再记录因子失效这一结果。

## 常见误区（常见误读）

1. 把累计 IC 当累计收益。二者量纲不同。
2. 把 ICIR 当 Sharpe。ICIR 衡量排序相关的均值相对波动，不是组合收益风险比。
3. 用重叠日标签直接年化 ICIR而不披露自相关。
4. 只看 Q5−Q1，不看中间组单调性和极端日期。
5. 看到衰减第 2 阶偶尔回升就认定信号“二次生效”；有限样本中波动很常见。
6. 看到合成数据正 IC 就宣称 A 股存在该异象。
7. 为提高结果事后翻转因子方向、筛日期或改组数，却不记录所有尝试。

## 思考题

1. 若平均 IC 为正但 Q5−Q1 为负，可能由哪些截面结构造成？
2. 5 日未来收益逐日滚动会怎样影响 IC 标准误和 ICIR 年化？
3. 若 IC 衰减缓慢但组合换手很高，问题可能出在哪里？
4. 为什么分组收益单调仍不能证明因子提供独立于行业和市值的收益？
5. 如何设计按年度、行业和市场状态的稳健性表而不进行结果挑选？

## 作业提示

复算时使用 `dropna()` 后的同一批 IC；标准差明确采用样本标准差还是总体标准差。分组检验至少给出五组均值和逐日 Q5−Q1，不要只复制 PNG。讨论衰减时写清 `lag` 是信号滞后而非未来收益期限。最后列出至少两个本实验不能推出的结论，例如真实市场有效性和成本后可交易性。

## 验收标准

- [ ] 能手工复算至少一个日期的 Spearman Rank IC。
- [ ] 能从 `ic_series.csv` 复算平均 IC、正值比例和未年化 ICIR。
- [ ] 同时提交五分组、Q5−Q1、单调性和 IC 衰减解释。
- [ ] 明确累计 IC 不是净值，分组未来收益不是可成交策略收益。
- [ ] 没有把固定 seed 的合成数据结果解释为真实市场超额收益。
- [ ] 所有结论均可追溯到 CSV，且与 report 和 PNG 一致。
