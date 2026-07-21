---
week: 17
title: "风险模型与收益归因"
phase: "因子、风险与优化"
reading_order:
  - "先读 asset_returns.csv 与 factor_exposures.csv：核对资产和因子维度"
  - "再比较 sample_covariance.csv 与 ledoit_wolf_covariance.csv：检查协方差估计"
  - "然后读 covariance_comparison.csv：比较两类特征值"
  - "最后读两份 attribution CSV：分别验证资产风险与因子风险收益归因"
artifacts:
  asset_returns.csv:
    summary: "逐交易日保存合成资产的日简单收益。"
    columns:
      date: "交易日。"
      A00: "合成资产 A00 的日简单收益。"
      A01: "合成资产 A01 的日简单收益。"
      A02: "合成资产 A02 的日简单收益。"
      A03: "合成资产 A03 的日简单收益。"
      A04: "合成资产 A04 的日简单收益。"
      A05: "合成资产 A05 的日简单收益。"
      A06: "合成资产 A06 的日简单收益。"
      A07: "合成资产 A07 的日简单收益。"
      A08: "合成资产 A08 的日简单收益。"
      A09: "合成资产 A09 的日简单收益。"
      A10: "合成资产 A10 的日简单收益，仅完整模式生成。"
      A11: "合成资产 A11 的日简单收益，仅完整模式生成。"
      A12: "合成资产 A12 的日简单收益，仅完整模式生成。"
      A13: "合成资产 A13 的日简单收益，仅完整模式生成。"
      A14: "合成资产 A14 的日简单收益，仅完整模式生成。"
      A15: "合成资产 A15 的日简单收益，仅完整模式生成。"
      A16: "合成资产 A16 的日简单收益，仅完整模式生成。"
      A17: "合成资产 A17 的日简单收益，仅完整模式生成。"
      A18: "合成资产 A18 的日简单收益，仅完整模式生成。"
      A19: "合成资产 A19 的日简单收益，仅完整模式生成。"
  factor_exposures.csv:
    summary: "按资产保存 market、value 与 momentum 三个静态因子暴露。"
    columns:
      unnamed_index: "CSV 未命名索引列，保存资产代码。"
      market: "资产的市场因子静态暴露。"
      value: "资产的价值因子静态暴露。"
      momentum: "资产的动量因子静态暴露。"
  sample_covariance.csv:
    summary: "资产日收益估计并年化的样本协方差矩阵。"
    columns: &week17_covariance_columns
      unnamed_index: "CSV 未命名索引列，保存协方差矩阵的行资产代码。"
      A00: "矩阵中资产 A00 对应的协方差列。"
      A01: "矩阵中资产 A01 对应的协方差列。"
      A02: "矩阵中资产 A02 对应的协方差列。"
      A03: "矩阵中资产 A03 对应的协方差列。"
      A04: "矩阵中资产 A04 对应的协方差列。"
      A05: "矩阵中资产 A05 对应的协方差列。"
      A06: "矩阵中资产 A06 对应的协方差列。"
      A07: "矩阵中资产 A07 对应的协方差列。"
      A08: "矩阵中资产 A08 对应的协方差列。"
      A09: "矩阵中资产 A09 对应的协方差列。"
      A10: "矩阵中资产 A10 对应的协方差列，仅完整模式生成。"
      A11: "矩阵中资产 A11 对应的协方差列，仅完整模式生成。"
      A12: "矩阵中资产 A12 对应的协方差列，仅完整模式生成。"
      A13: "矩阵中资产 A13 对应的协方差列，仅完整模式生成。"
      A14: "矩阵中资产 A14 对应的协方差列，仅完整模式生成。"
      A15: "矩阵中资产 A15 对应的协方差列，仅完整模式生成。"
      A16: "矩阵中资产 A16 对应的协方差列，仅完整模式生成。"
      A17: "矩阵中资产 A17 对应的协方差列，仅完整模式生成。"
      A18: "矩阵中资产 A18 对应的协方差列，仅完整模式生成。"
      A19: "矩阵中资产 A19 对应的协方差列，仅完整模式生成。"
  ledoit_wolf_covariance.csv:
    summary: "Ledoit-Wolf 收缩估计并年化的资产协方差矩阵。"
    columns: *week17_covariance_columns
  covariance_comparison.csv:
    summary: "按从小到大排序位置并列比较样本与收缩协方差特征值。"
    columns:
      sample_eigenvalue: "样本协方差矩阵从小到大排列的特征值。"
      ledoit_wolf_eigenvalue: "Ledoit-Wolf 协方差矩阵从小到大排列的特征值。"
  asset_risk_attribution.csv:
    summary: "使用收缩协方差按资产分解等权组合风险。"
    columns:
      unnamed_index: "CSV 未命名索引列，保存资产代码。"
      weight: "资产的等权组合权重。"
      marginal_volatility: "协方差乘权重的资产分量除以组合波动率。"
      variance_contribution: "资产权重乘边际方差得到的方差贡献。"
      volatility_contribution: "资产方差贡献除以组合波动率。"
      percent_contribution: "资产方差贡献占组合总方差的比例。"
  factor_attribution.csv:
    summary: "并列保存因子及资产特异项的方差贡献与因子年化收益贡献。"
    columns:
      unnamed_index: "CSV 未命名索引列，保存 factor 或 specific 归因项名称。"
      variance_contribution: "因子或资产特异项对组合方差的贡献。"
      annual_return_contribution: "因子对组合年化收益的贡献，特异项为空。"
  homework.md:
    summary: "本周协方差比较与风险收益归因作业。"
  acceptance.json:
    summary: "本周程序化验收条件。"
  manifest.json:
    summary: "本周运行模式与产物清单。"
---

# 第 17 周：风险模型与收益归因

## 学习目标

本周把协方差估计、因子风险模型、资产风险贡献和因子收益归因连接起来。完成后，你应能解释样本协方差在小样本高维环境中的不稳定性，理解 Ledoit–Wolf 收缩为何改善条件数，并能分别回答“组合风险来自哪里”和“组合平均收益由哪些因子暴露贡献”。

风险归因和收益归因使用相似的因子名称，却回答不同问题：前者分解方差，后者分解期望或实现收益。把二者混为一谈，会产生“高风险贡献必然带来高收益贡献”的错误结论。

## 前置知识

- 掌握矩阵乘法、协方差、特征值、条件数和组合方差。
- 理解线性因子模型、因子暴露和残差。
- 能区分方差、波动率及其贡献。
- 了解年化规则：日协方差乘 252，日均收益乘 252。

## 核心理论

样本协方差为

\[
\hat\Sigma_{\text{sample}}
=\frac{1}{T-1}\sum_{t=1}^{T}(r_t-\bar r)(r_t-\bar r)' \times 252.
\]

Ledoit–Wolf 收缩可概括为

\[
\hat\Sigma_{\text{LW}}
=(1-\delta)\hat\Sigma_{\text{sample}}+\delta F,
\]

其中目标矩阵 \(F\) 和收缩强度 \(\delta\) 由估计器确定。收缩牺牲一部分样本拟合，以降低估计方差、改善特征值和条件数。

静态暴露因子风险模型为

\[
\Sigma=BFB'+D,
\]

\(B\) 为资产因子暴露，\(F\) 为因子收益协方差，\(D\) 为资产特异方差对角阵。实验逐期做横截面回归估计因子收益：

\[
r_t=Bf_t+\epsilon_t.
\]

组合方差为 \(\sigma_p^2=w'\Sigma w\)。资产 \(i\) 的方差贡献与波动率贡献分别为

\[
VC_i=w_i(\Sigma w)_i,\qquad
RC_i=\frac{VC_i}{\sigma_p}.
\]

因此 \(\sum_i VC_i=\sigma_p^2\)，\(\sum_i RC_i=\sigma_p\)。因子风险贡献为

\[
FC_k=(B'w)_k\,[F(B'w)]_k,
\]

特异贡献为 \(w_i^2D_{ii}\)。收益归因则使用组合因子暴露 \(b_p=B'w\) 与年化平均因子收益：

\[
\text{ReturnContribution}_k=b_{p,k}\,\bar f_k\times252.
\]

## 实验步骤：收缩协方差与双重归因

完整模式生成 252 日、20 只资产；`quick` 模式为 80 日、10 只资产。因子为 `market`、`value`、`momentum`，随机种子固定为 17。

1. 为每只资产生成静态三因子暴露。
2. 生成因子收益和特异噪声，构造资产收益。
3. 分别估计年化样本协方差与 Ledoit–Wolf 协方差。
4. 用静态暴露逐日横截面回归，估计因子收益、因子协方差和各资产特异方差。
5. 建立等权组合。
6. 使用收缩协方差完成资产层风险分解。
7. 使用因子风险模型完成因子与资产特异方差贡献分解。
8. 以组合因子暴露乘年化平均因子收益，计算因子收益贡献。
9. 比较两种协方差的排序特征值与条件数。

风险模型默认不含截距，回归中加入极小 ridge `1e-8` 提高数值稳定性。它是教学用静态暴露模型；真实模型还需时变暴露、行业约束和稳健回归。

## 逐文件与字段解释

### `asset_returns.csv`

- `date`：交易日。
- `A00` 等资产列：日简单收益。

### `factor_exposures.csv`

- 行索引为资产。
- `market`、`value`、`momentum`：静态因子暴露。

### `sample_covariance.csv`

行列均为资产的年化样本协方差矩阵，`ddof=1`。

### `ledoit_wolf_covariance.csv`

行列均为资产的年化 Ledoit–Wolf 收缩协方差矩阵。

### `covariance_comparison.csv`

- `sample_eigenvalue`：样本协方差从小到大排列的特征值。
- `ledoit_wolf_eigenvalue`：收缩协方差从小到大排列的特征值。

两列按排序位置对照，不对应具体资产。

### `asset_risk_attribution.csv`

行索引为资产：

- `weight`：等权权重。
- `marginal_volatility`：\((\Sigma w)_i/\sigma_p\)。
- `variance_contribution`：\(w_i(\Sigma w)_i\)。
- `volatility_contribution`：方差贡献除以组合波动率。
- `percent_contribution`：方差贡献占总方差比例。

DataFrame 的内存 `attrs` 还保存 `variance` 与 `volatility`，CSV 不保存这些 attrs。

### `factor_attribution.csv`

行索引包含 `factor:market`、`factor:value`、`factor:momentum` 和各资产的 `specific:Axx`：

- `variance_contribution`：因子或特异项的组合方差贡献。
- `annual_return_contribution`：仅因子行有值，等于组合因子暴露乘年化平均因子收益；特异行为空。

### 框架产物

- `homework.md`：协方差、加总验证及风险/收益归因讨论。
- `acceptance.json`：两种协方差、风险贡献可加总、双重归因验收。
- `manifest.json`：运行信息和全部产物。

## 阅读顺序

1. 先读 `asset_returns.csv` 与 `factor_exposures.csv`，明确资产、日期和因子维度。
2. 对照两个协方差矩阵，检查对称性、对角线和资产顺序。
3. 读 `covariance_comparison.csv`，观察小特征值与谱的收缩。
4. 在 `asset_risk_attribution.csv` 验证各类贡献的加总恒等式。
5. 最后读 `factor_attribution.csv`，分别解释方差贡献列和收益贡献列。

## 图表解读

本周 runner 不直接生成图表，避免把不同协方差模型下的贡献混在同一视觉尺度。建议将 `covariance_comparison.csv` 的两列特征值按排序位置画成对数纵轴折线图：收缩后极小特征值通常被抬高、谱更稳定，但应以实际输出为准。再分别绘制资产 `percent_contribution` 条形图和因子/特异项 `variance_contribution` 条形图；前者基于 Ledoit–Wolf 协方差，后者基于因子模型，不能把两图中的单项高度直接一一比较。收益贡献应另画一张有正负方向的条形图。

## 动态指标判断

- 两种协方差应近似对称且半正定；特征值不应显著为负。
- 收缩协方差的条件数通常低于样本协方差，但应以结果为准。
- `variance_contribution` 之和应等于 \(w'\Sigma w\)。
- `volatility_contribution` 之和应等于组合波动率。
- `percent_contribution` 之和应为 1。
- `factor_attribution.csv` 的全部方差贡献之和等于因子风险模型的总方差，不必等于 Ledoit–Wolf 矩阵下的组合方差，因为估计模型不同。
- 收益贡献只覆盖模型解释的因子部分，不包含截距、特异平均收益或交易成本。

## 常见误区

- 认为收缩后每个协方差元素都更“接近真值”；收缩改善的是整体估计风险。
- 用相关矩阵代替协方差矩阵做金额风险计算。
- 把方差贡献直接称为波动率贡献，忽略除以 \(\sigma_p\)。
- 要求单个贡献都为正；在存在对冲或负权重时，边际贡献可以为负。
- 将因子风险占比和因子收益占比混为一谈。
- 期待因子模型总方差与收缩协方差下总方差完全一致。
- 忘记 CSV 不保存 pandas `attrs`。

## 思考题

1. 当资产数接近或超过样本数时，样本协方差会发生什么？
2. 条件数改善为何通常能提高优化权重稳定性？
3. 因子之间相关时，单因子方差贡献如何受交叉协方差影响？
4. 特异风险很高但权重很小的资产，对组合风险贡献一定高吗？
5. 因子收益归因如何扩展到逐日实现收益和残差收益？

## 作业提示

- 从矩阵自行计算特征值和条件数，注意极小特征值会放大条件数。
- 用 `asset_risk_attribution.csv` 的贡献列分别验证方差、波动率、百分比三种加总。
- 风险与收益归因要分开写结论，并注明使用的协方差模型不同。
- 可改变样本长度与资产数量，观察收缩优势何时最明显。

## 验收标准

- [ ] 正确比较样本与 Ledoit–Wolf 协方差、特征值和条件数。
- [ ] 能写出并解释 \(\Sigma=BFB'+D\)。
- [ ] 能验证资产风险贡献的三种加总关系。
- [ ] 能区分因子方差贡献、特异方差贡献和年化收益贡献。
- [ ] 能逐字段说明七个核心产物和三个框架产物。
- [ ] 能指出教学模型的静态暴露、无截距及模型间方差不一致边界。
