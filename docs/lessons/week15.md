---
week: 15
title: "事件研究与公告效应"
phase: "数据与事件"
reading_order:
  - "先读 synthetic_events.csv：核对事件、相对日与理论效应"
  - "再读 abnormal_returns.csv：检查事件乘相对日的异常收益矩阵"
  - "然后读 car_and_placebo.csv：比较真实事件与安慰剂 CAR"
  - "最后读 event_summary.csv：解释均值、bootstrap 区间与差值"
artifacts:
  synthetic_events.csv:
    summary: "保存合成公告事件在各相对交易日的市场收益、资产收益与异常收益。"
    columns:
      event_id: "事件编号。"
      relative_day: "相对事件交易日。"
      asset_return: "事件资产的日简单收益。"
      market_return: "合成市场日简单收益。"
      true_abnormal_return: "数据生成时注入的理论异常收益。"
      abnormal_return: "资产收益减市场收益得到的市场调整异常收益。"
  abnormal_returns.csv:
    summary: "以事件为行、相对交易日为列的异常收益宽表。"
    columns:
      event_id: "事件编号索引。"
      "-5": "相对事件日 -5 的异常收益。"
      "-4": "相对事件日 -4 的异常收益。"
      "-3": "相对事件日 -3 的异常收益。"
      "-2": "相对事件日 -2 的异常收益。"
      "-1": "相对事件日 -1 的异常收益。"
      "0": "事件日 0 的异常收益。"
      "1": "相对事件日 1 的异常收益。"
      "2": "相对事件日 2 的异常收益。"
      "3": "相对事件日 3 的异常收益。"
      "4": "相对事件日 4 的异常收益。"
      "5": "相对事件日 5 的异常收益。"
      "6": "相对事件日 6 的异常收益。"
      "7": "相对事件日 7 的异常收益。"
      "8": "相对事件日 8 的异常收益。"
      "9": "相对事件日 9 的异常收益。"
      "10": "相对事件日 10 的异常收益。"
  car_and_placebo.csv:
    summary: "按事件编号并列保存真实事件与独立零效应样本的 CAR。"
    columns:
      event_id: "事件编号索引。"
      car: "真实事件在相对日 -1 至 1 的累计异常收益。"
      placebo_car: "独立零效应事件在相对日 -1 至 1 的累计异常收益。"
  event_summary.csv:
    summary: "以指标名为行保存 CAR 均值、bootstrap 区间和安慰剂对照。"
    columns:
      unnamed_index: "CSV 未命名索引列，保存汇总指标名称。"
      week15: "第 15 周对应汇总指标值。"
  homework.md:
    summary: "本周事件窗、市场模型与安慰剂检验作业。"
  acceptance.json:
    summary: "本周程序化验收条件。"
  manifest.json:
    summary: "本周运行模式与产物清单。"
---

# 第 15 周：事件研究与公告效应

## 学习目标

本周建立一条完整的事件研究链：把不同事件对齐到相对交易日，估计正常收益，计算异常收益 AR 与累计异常收益 CAR，用 bootstrap 给出不确定性区间，再用安慰剂事件检验流程是否会在无效应数据中制造“显著结果”。

完成后，你应能清楚区分事件窗与估计窗、市场调整模型与市场模型，并能解释为什么“真实事件强于 placebo”仍不等于因果证明。

## 前置知识

- 理解简单收益率、均值、OLS 和置信区间。
- 能区分自然日与交易日，理解事件日需要映射到交易索引。
- 了解公告时间的 PIT 约束；盘后公告通常不能使用当日收盘前的信息。
- 会使用长表与“事件 × 相对日”宽表。

## 核心理论

市场调整模型的异常收益为

\[
AR_{i,\tau}=r_{i,\tau}-r_{m,\tau}.
\]

市场模型先在估计窗拟合

\[
r_{i,t}=\alpha_i+\beta_i r_{m,t}+\varepsilon_{i,t},
\]

再在事件窗计算

\[
AR_{i,\tau}=r_{i,\tau}-(\hat\alpha_i+\hat\beta_i r_{m,\tau}).
\]

事件 \(i\) 在窗口 \([a,b]\) 的累计异常收益是

\[
CAR_i[a,b]=\sum_{\tau=a}^{b}AR_{i,\tau},
\]

平均 CAR 为 \(\overline{CAR}=N^{-1}\sum_i CAR_i\)。

本实验对事件级 CAR 做 iid percentile bootstrap：从 \(N\) 个 CAR 中有放回抽取 \(N\) 个，重复 \(B\) 次，计算每次均值，并取 2.5% 与 97.5% 分位数作为 95% 区间。完整模式 \(B=2000\)，`quick` 模式 \(B=300\)。

## 实验步骤：AR、CAR、bootstrap 与 placebo

完整模式生成 160 个事件，`quick` 模式为 40 个。每个事件窗口为 \([-5,10]\)，随机种子固定。

1. 合成市场收益与个体噪声；资产收益满足 `alpha + beta * market + effect + noise`。
2. 真实事件在相对日 0 注入 `0.02` 的理论异常收益。
3. 实验主流程使用市场调整法：`abnormal_return = asset_return - market_return`。
4. 将长表透视为事件行、相对日列的异常收益矩阵。
5. 对 \([-1,1]\) 三日求和，得到每个事件的 CAR。
6. 对真实 CAR 均值执行 percentile bootstrap。
7. 用另一随机种子生成 `event_effect=0` 的独立 placebo 面板，并以相同流程计算 placebo CAR。
8. 报告真实均值、区间、placebo 均值及二者差值。

工具模块还支持市场模型、事件窗口对齐和 placebo 日期抽样。`placebo_dates` 会排除真实事件前后指定交易日并无放回抽样，但本周 runner 的 placebo 是直接生成零效应合成面板，并没有调用日期抽样函数。两者不要混淆。

## 逐文件与字段解释

### `synthetic_events.csv`

- `event_id`：事件编号。
- `relative_day`：相对事件交易日，范围 -5 至 10。
- `asset_return`：资产简单收益。
- `market_return`：市场简单收益。
- `true_abnormal_return`：已知理论异常收益，仅事件日 0 为 0.02。
- `abnormal_return`：市场调整异常收益。

### `abnormal_returns.csv`

宽表：

- 行索引 `event_id`：事件编号。
- 列名为相对日 `-5` 至 `10`。
- 单元格为对应事件和相对日的 `abnormal_return`。

### `car_and_placebo.csv`

- 行索引 `event_id`。
- `car`：真实事件 \([-1,1]\) 窗口的 CAR。
- `placebo_car`：零效应合成事件相同窗口的 CAR。

两列按事件编号拼接，但它们来自独立随机样本，不应把同行解释成同一公司的配对事件。

### `event_summary.csv`

这是一个以指标名为行索引、`week15` 为值列的 Series 导出结果：

- `mean_car`：真实事件平均 CAR。
- `bootstrap_lower`：均值的 95% bootstrap 下界。
- `bootstrap_upper`：均值的 95% bootstrap 上界。
- `placebo_mean_car`：placebo 平均 CAR。
- `event_minus_placebo`：两者均值之差。

### 框架产物

- `homework.md`：窗口比较、市场模型和 placebo 讨论。
- `acceptance.json`：AR/CAR、bootstrap、真实事件对比 placebo 的验收项。
- `manifest.json`：完整产物与运行模式。

## 阅读顺序

1. 先读 `synthetic_events.csv`，确认每个事件有 16 个相对日，且理论效应只在 0 日。
2. 对一个事件手算 `asset_return - market_return`，再与 `abnormal_returns.csv` 对齐。
3. 将该事件 -1、0、1 三列相加，核对 `car_and_placebo.csv`。
4. 查看真实 CAR 与 placebo CAR 的分布、均值和极端值。
5. 最后读 `event_summary.csv`，判断区间是否覆盖 0、真实效应是否高于 placebo。

## 图表解读

本周 runner 不生成图表，产物保留事件级明细以便自行选择窗口。建议先用 `abnormal_returns.csv` 按相对日计算平均 AR，并绘制带标准误区间的事件时间曲线；0 日附近的峰值应与注入效应对应，窗口外若持续偏离 0 则需检查模型设定。再把平均 AR 累加成 CAAR 曲线，观察效应是瞬时、提前还是延后形成。最后用直方图或箱线图并列比较 `car` 与 `placebo_car`；分布重叠程度比只比较两个均值更能展示不确定性，但不能替代 bootstrap 区间和样本依赖检验。

## 动态指标判断

- 每个真实事件在 \([-1,1]\) 有三期 AR，CAR 等于三期之和。
- `mean_car` 应接近注入的 0.02，但有限样本和噪声使其不会精确等于 0.02。
- `bootstrap_lower <= mean_car <= bootstrap_upper` 通常成立。
- 在当前设计下，真实均值通常高于 placebo 均值，且完整样本的区间通常不覆盖 0；仍应以实际输出为准。
- placebo 均值应围绕 0 波动，但单次实验不必恰好为 0。
- 更换事件窗会同时改变信号覆盖与噪声累积，不能只挑结果最好的窗口。

## 常见误区

- 把原始收益当作异常收益，未扣除市场或正常收益。
- 用事件窗数据估计 \(\alpha,\beta\)，造成估计窗污染。
- 将自然日偏移当成交易日偏移，或错误处理盘后公告。
- 在看过结果后反复选择窗口，却不校正多重检验。
- 对有横截面相关、行业聚类或同日事件的数据仍使用 iid bootstrap。
- 认为 placebo 不显著即可证明因果。它只能排查部分伪发现机制。
- 把 `car_and_placebo.csv` 的同一行当作配对样本。

## 思考题

1. \([-1,1]\) 与 \([0,3]\) 分别适合捕捉提前泄露、延迟反应中的哪些部分？
2. 多家公司同一天公告时，事件级 iid bootstrap 会低估还是高估不确定性？
3. 市场模型的估计窗应离事件窗多远？如何处理估计窗内的其他重大公告？
4. placebo 日期需要排除真实事件多远，才不会受到真实效应污染？
5. 若事件选择由未来涨幅决定，即使 AR 公式正确，会发生什么？

## 作业提示

- 比较两个窗口时固定同一事件样本，同时报告均值、区间和样本数。
- 替换为市场模型时，明确估计掩码；返回结果的 `attrs` 中有 `alpha`、`beta` 和 `estimation_count`。
- 重复 placebo 时汇总多次 placebo 均值分布，而不是只挑一次结果。
- 真实数据中应先建立公告日到交易日的确定性映射，并保留映射规则。

## 验收标准

- [ ] 能正确计算市场调整 AR 与 \([-1,1]\) CAR。
- [ ] 能解释市场模型、估计窗及污染风险。
- [ ] 能复述 percentile bootstrap 的抽样单位、次数和区间含义。
- [ ] 能区分零效应合成 placebo 与 placebo 日期抽样。
- [ ] 能逐字段说明四个核心产物和三个框架产物。
- [ ] 能说明“真实事件强于 placebo”为何仍不能单独证明因果。
