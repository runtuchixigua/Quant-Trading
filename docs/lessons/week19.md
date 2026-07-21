---
week: 19
title: "嵌套验证、过拟合与统计可信度"
phase: "稳健验证与机器学习"
reading_order:
  - "先检查 purged_embargo_folds.csv 的时间边界与空档"
  - "再核对 experiment_log.csv 与 deflated_sharpe.json 的试验数"
  - "随后阅读 block_bootstrap.csv 与 summary.csv"
  - "最后完成 homework.md 并检查 acceptance.json 和 manifest.json"
artifacts:
  purged_embargo_folds.csv:
    summary: "逐折保存 purge 与 embargo 后的训练、验证日期边界和观测数量，用于审计时间泄漏。"
    columns:
      fold: "从 1 开始的验证折编号。"
      train_start: "该折训练集的首个交易日。"
      train_end: "该折训练集的最后一个交易日。"
      validation_start: "该折验证集的首个交易日。"
      validation_end: "该折验证集的最后一个交易日。"
      train_observations: "该折训练集包含的交易日观测数。"
      validation_observations: "该折验证集包含的交易日观测数。"
      gap_dates: "验证首位置与训练末位置之间被 purge 和 embargo 隔离的交易日位置数。"
  experiment_log.csv:
    summary: "登记全部候选动量回看期及其收益表现，供多重试验修正和胜者选择使用。"
    columns:
      name: "候选试验的唯一名称，例如 momentum_20。"
      sharpe: "候选策略日收益按 252 个交易日年化得到的 Sharpe。"
      observations: "该候选去除无效值后的收益观测数。"
      lookback: "生成动量信号所使用的历史交易日回看长度。"
      seed: "生成本次教学实验数据所使用的固定随机种子。"
  deflated_sharpe.json:
    summary: "保存胜出候选经试验次数、样本长度、偏度和峰度修正后的 Deflated Sharpe 结果。"
  block_bootstrap.csv:
    summary: "以指标名和数值的长表保存胜出候选的日均收益及移动区块 bootstrap 置信区间。"
    columns:
      unnamed_index: "CSV 中未显式命名的索引列，依次保存 mean_return、ci_lower 和 ci_upper 指标名。"
      value: "对应指标的数值；原始无名 Series 写出时表头可能显示为 0。"
  summary.csv:
    summary: "以指标名和数值的长表汇总验证折数、试验数、入选策略、DSR 概率和区间宽度。"
    columns:
      unnamed_index: "CSV 中未显式命名的索引列，保存本周汇总指标名称。"
      week19: "对应第 19 周汇总指标的值。"
  homework.md:
    summary: "要求补充失败试验、验证时间轴和不同 bootstrap 方案的比较。"
  acceptance.json:
    summary: "记录第 19 周机器可读的验收状态和验收条件。"
  manifest.json:
    summary: "记录第 19 周运行模式、产物路径、讲义引用和产物字段词典。"
---

# 第 19 周：嵌套验证、过拟合与统计可信度

## 学习目标（本周定位与目标）

策略研究最危险的结果不是“回测很差”，而是“反复试验后偶然很好，却被误认为有规律”。本周把验证设计、试验登记、多重比较修正和相关序列置信区间连成一条证据链。完成后，你应当能够：

1. 按日期而不是按样本行切分横截面数据，解释 purge 与 embargo 各自隔离什么。
2. 区分训练、模型选择和最终测试；最终测试集只在规则冻结后查看一次。
3. 将所有参数尝试纳入试验次数，而不是只登记胜者。
4. 解释 Deflated Sharpe Ratio（DSR）如何同时惩罚多重试验、样本长度、偏度和峰度。
5. 用 moving block bootstrap 保留短程时序依赖，并判断均值区间是否跨过零。

## 前置知识

你需要会计算简单收益、年化 Sharpe、均值与分位数；理解滚动信号必须 `shift(1)`；能阅读按日期排序的 `pandas` 表。还应记住：同一交易日的横截面股票共享市场信息，不能随机拆入训练和验证两边。

## 核心理论

本周核心理论由时间隔离、嵌套验证、多重试验修正和相关序列置信区间四部分组成。阅读时先确认每种方法要排除的偏差，再检查产物是否提供了对应证据。

## 理论一：时间切分、purge 与 embargo

设特征在日期 \(t\) 形成，标签使用未来 \(H\) 个交易日收益。若训练样本的标签区间与验证期重叠，即使特征没有直接引用未来，训练目标也已包含验证期价格。purge 的任务是从训练尾部移除可能与验证标签重叠的日期；embargo 则在训练与验证之间再留出缓冲，降低相邻样本、特征窗口或数据发布时间造成的依赖。

本项目的 `PurgedEmbargoSplit` 是保守的扩展窗口：

\[
g=P+E,\qquad
\mathcal T_k=\{d_0,\ldots,d_{v_k-g-1}\},\qquad
\mathcal V_k=\{d_{v_k},\ldots,d_{v_{k+1}-1}\}
\]

其中 \(P\) 是 `purge_dates`，\(E\) 是 `embargo_dates`。实现先对日期去重排序，再以日期组返回样本行位置，所以同日所有股票始终在同一集合。第 19 周 runner 使用 `purge_dates=5`、`embargo_dates=2`，故每折可见的 `gap_dates` 应为 7。快速模式为 3 折、至少 35 个训练日；完整模式为 5 折、至少 126 个训练日。

不要把两者机械理解为同一种“空档”。purge 应由标签跨度和信息实现期决定；embargo 是额外的保守缓冲。空档越大并不必然越正确，因为它也减少有效训练样本。

## 理论二：嵌套验证与最终测试纪律

完整研究应有三层：

- 内层训练：拟合参数，所有预处理也只能在该折训练窗口拟合。
- 外层验证：比较模型族和超参数，估计选择后的泛化表现。
- 最终测试：在假设、特征、参数、成本和停止规则冻结后只打开一次。

本周产物展示 purged/embargo 外层折，但 runner 的候选动量回看期是在同一收益序列上演示试验登记与 DSR，并不等于完整嵌套训练。因此报告中应明确：这是教学实验；不能声称已经得到完全独立的最终测试收益。

## 理论三：多重试验与 Deflated Sharpe

候选策略的年化 Sharpe 为

\[
\widehat{SR}=\sqrt{252}\frac{\bar r}{s_r}.
\]

当做过 \(N\) 次试验时，最优 Sharpe 即便在零技能下也会随 \(N\) 上升。代码用试验 Sharpe 的标准差（只有一个有效值时用 \(1/\sqrt T\)）估计选择噪声，并以 Euler 常数 \(\gamma\) 近似零技能下最大 Sharpe 的期望门槛：

\[
SR^*=\sigma_{SR}\left[(1-\gamma)\Phi^{-1}(1-1/N)
+\gamma\Phi^{-1}(1-1/(Ne))\right].
\]

把年化 Sharpe 转成单期后，教学版 DSR 的统计量为

\[
Z=\frac{(\widehat{SR}-SR^*)\sqrt{T-1}}
{\sqrt{1-\widehat\gamma_3\widehat{SR}
+\frac{\widehat\gamma_4-1}{4}\widehat{SR}^2}},
\qquad DSR=\Phi(Z).
\]

\(\widehat\gamma_3\) 与 \(\widehat\gamma_4\) 分别是偏度和普通峰度。`probability` 是观察 Sharpe 超过多重试验门槛的概率，不是“策略赚钱概率”，也不是未来显著性保证。漏记失败试验会低估 \(N\)，从而虚增 DSR。

## 理论四：moving block bootstrap

IID bootstrap 随机抽单个收益，会破坏波动聚集和自相关。移动块法先构造长度 \(L\) 的所有连续非环形块，再有放回抽块并拼接至原样本长度。每次计算均值，最后取 percentile 区间：

\[
CI_{1-\alpha}=
\left[Q_{\alpha/2}(\bar r^*),Q_{1-\alpha/2}(\bar r^*)\right].
\]

runner 使用 `block_size=5`、`confidence=0.95`、固定 `seed=202407`；快速模式 200 次，完整模式 2,000 次。块太短会遗漏依赖，块太长则有效独立块太少。若区间跨零，只能说当前样本无法排除均值不为正；若不跨零，也仍需面对选择偏差、制度变化和成本误差。

## 阅读顺序

先审计时间边界，再核对试验登记和 DSR，最后判断 bootstrap 区间并完成汇总；这个顺序避免先看到“好指标”后放松对泄漏和选择偏差的检查。

## 实验步骤

1. 运行第 19 周课程，先确认输出目录是本次希望审阅的目录。
2. 读 `purged_embargo_folds.csv`，逐折核对训练早于验证、边界单调、空档为 7。
3. 读 `experiment_log.csv`，确认快速模式 3 个、完整模式 6 个回看期全部登记。
4. 找出 Sharpe 最大的 `name`，再读 `deflated_sharpe.json`，检查所选策略、试验数和样本数一致。
5. 读 `block_bootstrap.csv`，先判断区间是否跨零，再比较区间宽度。
6. 最后用 `summary.csv` 汇总结论，并以 `acceptance.json`、`manifest.json` 检查验收与文件完整性。

候选信号为过去 \(L\) 日收益均值的符号并滞后一天：

\[
s_t=\operatorname{sign}\left(\frac1L\sum_{j=1}^{L}r_{t-j}\right),
\qquad r^{strategy}_t=s_t r_t.
\]

`shift(1)` 是防止当日收益参与当日信号的关键。完整模式测试 \(L\in\{5,10,20,40,60,90\}\)。

## 逐文件与字段解释（逐产物与字段字典）

### `purged_embargo_folds.csv`

- `fold`：从 1 开始的验证折编号。
- `train_start`、`train_end`：训练日期边界。
- `validation_start`、`validation_end`：验证日期边界。
- `train_observations`、`validation_observations`：该折日期观测数。
- `gap_dates`：验证首位置减训练末位置再减 1；本实验应等于 7。

判断顺序：先验证 `train_end < validation_start`，再看空档，最后看训练样本是否足够。折数正确不代表无泄漏，必须检查边界。

### `experiment_log.csv`

- `name`：如 `momentum_20`，是唯一试验标识。
- `sharpe`：候选收益按 252 期年化的 Sharpe。
- `observations`：去除缺失后的收益观测数。
- `lookback`：动量回看交易日数。
- `seed`：本实验固定为 202407。

任何看过结果后做出的参数修改都应新增一行，不能覆盖旧记录。

### `deflated_sharpe.json`

- `probability`：选择后的 Sharpe 超过多试验基准的正态近似概率。
- `observed_sharpe`：胜出候选的年化 Sharpe。
- `benchmark_sharpe`：考虑多重试验后的年化基准。
- `n_trials`：有效试验数，应与日志行数一致。
- `observations`：胜出收益有效样本数。
- `skewness`、`kurtosis`：胜出收益的偏度与普通峰度。

重点检查 `observed_sharpe > benchmark_sharpe` 是否成立，以及高 Sharpe 是否被低 `probability` 揭示为选择噪声。

### `block_bootstrap.csv`

该文件由 Series 写出，第一列是行名：

- `mean_return`：胜出候选的样本日均收益。
- `ci_lower`、`ci_upper`：95% moving-block percentile 区间下、上界。

### `summary.csv`

- `folds`：实际验证折数。
- `experiments`：已登记试验数。
- `selected`：按日志 Sharpe 最大值选出的候选名。
- `deflated_sharpe_probability`：DSR 概率。
- `bootstrap_ci_width`：`ci_upper-ci_lower`。

### `homework.md`、`acceptance.json`、`manifest.json`

`homework.md` 是作业提示；`acceptance.json` 记录周数及本周验收条件；`manifest.json` 是本次运行清单，由 runner 传入 `week`、`quick` 与全部产物路径。核对 manifest 声明的每个路径确实存在，不要把“列在清单中”误当成“统计结论通过”。

## 图表解读（无预生成图时的建议）

本周默认产物以表格和 JSON 为主，没有强制生成图。建议从 `purged_embargo_folds.csv` 画训练—空档—验证横向时间轴，以颜色区分每折并标注 `gap_dates`；从 `experiment_log.csv` 画 `lookback`—`sharpe` 散点，同时画出 `benchmark_sharpe` 水平线；对 bootstrap 重采样均值画直方图或核密度，并标注 `ci_lower`、零和 `ci_upper`。解读时先看边界是否重叠，再看胜者相对门槛的位置，最后看区间是否跨零，不能仅凭最高柱或最右散点下结论。

## 动态指标判断

- 每新增一次参数、特征或停止规则尝试，都应同步增加 `experiment_log.csv` 的试验数；若 Sharpe 上升但 DSR 下降，说明新增选择成本超过表面改善。
- 随样本推进，逐折跟踪训练日期数、验证日期数和 `gap_dates`；空档变化或训练窗口突然缩短应先视为数据/切分异常。
- 滚动重算 bootstrap 区间宽度与是否跨零。区间持续收窄且方向稳定才是证据增强；一次不跨零不代表永久有效。
- 动态决策采用“继续研究/冻结规则/证据不足”三态，不把单次 DSR 或区间结果直接映射成上线许可。

## 如何形成判断

可信结论至少同时满足：折间无时间交叠；所有试验被登记；DSR 没有被未登记试验夸大；block bootstrap 区间支持方向判断；最终测试仍未被反复查看。任何一项失败，都应把研究状态改为“证据不足”，而不是继续搜索更好参数。

## 常见误区

1. 只设置 `TimeSeriesSplit` 就认为无泄漏，忽略标签跨期。
2. 把 purge 和 embargo 都设为标签期限，却不解释信息窗口。
3. 只记录成功参数，令 DSR 的 `n_trials` 严重偏小。
4. 把 DSR 概率当作未来盈利概率。
5. 对自相关收益使用 IID bootstrap，得到过窄区间。
6. 反复查看 final-test，再称其为最终测试。
7. 看到 bootstrap 区间不跨零就忽略交易成本与市场状态。

## 思考题

1. 若标签为未来 20 日收益、特征含 60 日滚动窗口，purge 与 embargo 各应由什么决定？
2. 两个候选 Sharpe 相同，为什么负偏、高峰度候选的 DSR 可能更低？
3. 若 60 个回看期来自高度相似参数，直接把 60 当独立试验数是保守还是激进？还缺什么“有效试验数”模型？
4. block size 从 5 改为 20 时，区间宽度为何可能增大？

## 作业提示（作业）

1. 在不覆盖原日志的前提下加入一个明确失败的候选，重算 DSR，并解释变化来自 `n_trials`、试验离散度还是收益高阶矩。
2. 画出每折训练/空档/验证时间轴，逐折证明没有标签重叠。
3. 用相同 seed 比较 IID bootstrap 与 block size 为 5、10、20 的区间，提交选择块长的依据。
4. 写一页“最终测试开启协议”，列出冻结项、审批人、一次性指标和失败后的处置。

## 验收标准

- `purged_embargo_folds.csv` 每折训练严格早于验证，且能解释 5 日 purge、2 日 embargo 与 7 日空档。
- `experiment_log.csv` 包含全部尝试，`deflated_sharpe.json.n_trials` 与之相符。
- 固定 seed 后 block bootstrap 可复现，并能正确解释区间是否跨零。
- 报告不把 DSR 概率写成盈利概率，不把教学外层折冒充完整独立测试。
- `manifest.json` 所列路径全部存在，作业与验收文件完整。
