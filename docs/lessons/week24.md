---
week: 24
title: "毕业研究、独立复现与答辩"
phase: "执行、治理与毕业研究"
reading_order:
  - "先用周根 manifest.json 和 summary.csv 锁定唯一 runs/run_NNN"
  - "再按因子、绩效、风险、验证、机器学习、执行和模拟盘顺序审阅运行级产物"
  - "随后核对 reproduction.md、graduation_report.md 与 monitor_decision.json 的结论边界"
  - "最后完成 homework.md、defense_checklist.md 并检查 acceptance.json"
artifacts:
  "runs/run_*/run_manifest.json":
    summary: "保存本次唯一毕业运行的完整配置、数据声明、日期范围、核心 IC、Sharpe、换手和监控停止结果。"
  "runs/run_*/graduation_report.md":
    summary: "提供毕业报告初稿、合成数据边界和待补充的经济逻辑、审计证据及实盘限制。"
  "runs/run_*/factor_summary.csv":
    summary: "按因子汇总平均 Rank IC、ICIR 和有效日数，用于比较方向、强度与稳定性。"
    columns:
      factor: "CSV 索引列中的因子名称。"
      mean_rank_ic: "该因子日度 Rank IC 的时间均值。"
      icir: "日度 Rank IC 均值除以其样本标准差。"
      observations: "该因子 Rank IC 非缺失的交易日数量。"
  "runs/run_*/factor_daily_ic.csv":
    summary: "逐日保存七个标准化因子的横截面 Rank IC，是复算因子摘要和时序稳定性的底表。"
    columns:
      date: "Rank IC 对应的交易日期。"
      momentum: "动量因子与未来收益的当日横截面 Spearman 相关。"
      low_volatility: "低波动因子与未来收益的当日横截面 Spearman 相关。"
      earnings_yield: "盈利收益率因子与未来收益的当日横截面 Spearman 相关。"
      book_to_price: "账面市值比因子与未来收益的当日横截面 Spearman 相关。"
      roe: "净资产收益率因子与未来收益的当日横截面 Spearman 相关。"
      accrual_quality: "应计质量因子与未来收益的当日横截面 Spearman 相关。"
      liquidity: "流动性因子与未来收益的当日横截面 Spearman 相关。"
  "runs/run_*/composite_yearly_ic.csv":
    summary: "按自然年汇总等权复合因子的 Rank IC 均值、波动、ICIR 和有效观测数。"
    columns:
      year: "复合因子 Rank IC 所属自然年。"
      mean: "该年复合因子日度 Rank IC 的均值。"
      std: "该年复合因子日度 Rank IC 的样本标准差。"
      icir: "该年 Rank IC 均值除以样本标准差。"
      count: "该年非缺失 Rank IC 的交易日数量。"
  "runs/run_*/factor_ic_decay.csv":
    summary: "保存复合因子从零滞后到配置最大滞后的平均 Rank IC 衰减路径。"
    columns:
      lag: "因子信号相对未来收益向后移动的交易日滞后数。"
      mean_rank_ic: "该滞后下逐日横截面 Rank IC 的时间均值。"
  "runs/run_*/factor_correlation.csv":
    summary: "保存七个标准化因子两两日度横截面 Pearson 相关的时间均值矩阵。"
    columns:
      factor: "相关矩阵的行因子名称。"
      momentum: "行因子与动量因子的平均横截面相关。"
      low_volatility: "行因子与低波动因子的平均横截面相关。"
      earnings_yield: "行因子与盈利收益率因子的平均横截面相关。"
      book_to_price: "行因子与账面市值比因子的平均横截面相关。"
      roe: "行因子与净资产收益率因子的平均横截面相关。"
      accrual_quality: "行因子与应计质量因子的平均横截面相关。"
      liquidity: "行因子与流动性因子的平均横截面相关。"
  "runs/run_*/performance_summary.csv":
    summary: "以指标名和值的长表保存策略绝对绩效、相对基准绩效和换手指标。"
    columns:
      metric: "CSV 无名索引列中的绩效指标名称。"
      value: "对应绩效指标的数值。"
  "runs/run_*/daily_performance.csv":
    summary: "逐日保存策略与基准收益、策略净值、换手和成本，是复算绩效的底表。"
    columns:
      date: "绩效观测对应的交易日期。"
      strategy_return: "扣除回测成本后的策略日收益率。"
      benchmark_return: "可投资股票等权基准的日收益率。"
      strategy_nav: "由策略日收益复利累计、初值为 1 的财富指数。"
      turnover: "当日目标组合的单边换手率。"
      cost: "当日佣金、印花税与滑点等回测交易成本率。"
  "runs/run_*/asset_risk_decomposition.csv":
    summary: "按资产分解最终组合的方差与波动率贡献，并保存权重和边际风险。"
    columns:
      symbol: "风险分解对应的证券代码索引。"
      weight: "最终组合中该证券的权重。"
      marginal_volatility: "组合波动率对该证券权重的一阶边际量。"
      variance_contribution: "该证券权重乘边际方差所得的组合方差贡献。"
      volatility_contribution: "方差贡献除以组合波动率，跨证券加总为组合波动率。"
      percent_contribution: "该证券方差贡献占组合总方差的比例。"
  "runs/run_*/active_risk_attribution.csv":
    summary: "按证券归因最终组合相对等权基准的年化跟踪误差。"
    columns:
      symbol: "主动风险归因对应的证券代码索引。"
      active_weight: "组合权重减去等权基准权重。"
      marginal_tracking_error: "年化跟踪误差对该证券主动权重的边际量。"
      tracking_error_contribution: "该证券对年化跟踪误差的贡献，加总为组合跟踪误差。"
      percent_contribution: "该证券对主动方差的贡献比例。"
  "runs/run_*/factor_risk_decomposition.csv":
    summary: "以组件名和值的长表保存最终组合各因子及各证券特异方差贡献。"
    columns:
      component: "CSV 无名索引列中的风险组件，前缀为 factor: 或 specific:。"
      variance_contribution: "对应因子或特异风险组件对组合总方差的贡献。"
  "runs/run_*/stress_costs.csv":
    summary: "在相同毛收益上施加不同交易成本倍数，比较压力后的绩效。"
    columns:
      cost_multiplier: "施加于基础交易成本的倍数。"
      observations: "毛收益与成本对齐后的有效交易日数量。"
      annualized_return: "扣除倍增成本后的复合年化收益率。"
      sharpe: "扣除倍增成本后的年化 Sharpe。"
      max_drawdown: "扣除倍增成本后的最大回撤。"
  "runs/run_*/stress_subsamples.csv":
    summary: "把策略收益按连续时间块切分，比较不同时段的绩效稳定性。"
    columns:
      subsample: "连续时间子样本的名称。"
      observations: "该子样本包含的有效交易日数量。"
      annualized_return: "该子样本的复合年化收益率。"
      sharpe: "该子样本的年化 Sharpe。"
      max_drawdown: "该子样本收益序列的最大回撤。"
  "runs/run_*/stress_market_regimes.csv":
    summary: "按同期牛熊市场状态切分策略收益，比较不同状态下的绩效。"
    columns:
      regime: "市场状态名称，取值为 bull 或 bear。"
      observations: "该市场状态下的有效交易日数量。"
      annualized_return: "该状态子样本的复合年化收益率。"
      sharpe: "该状态子样本的年化 Sharpe。"
      max_drawdown: "抽取该状态交易日后收益子序列的最大回撤。"
  "runs/run_*/validation_protocol.json":
    summary: "保存训练、验证和最终测试各自的起止日期与日期数量，供审计 purge/embargo 边界。"
  "runs/run_*/experiment_registry.csv":
    summary: "登记 baseline 与 double_cost 两项流水线试验的 Sharpe 和有效样本数。"
    columns:
      name: "试验唯一名称，本流水线包含 baseline 与 double_cost。"
      sharpe: "该试验收益按 252 个交易日年化的 Sharpe。"
      observations: "该试验收益去除无效值后的观测数量。"
  "runs/run_*/deflated_sharpe.json":
    summary: "保存 baseline 经试验数量、样本长度、偏度和峰度修正后的 Deflated Sharpe 明细。"
  "runs/run_*/ml_daily_rank_ic.csv":
    summary: "逐日保存机器学习预测与未来收益的横截面 Rank IC。"
    columns:
      date: "机器学习 Rank IC 对应的预测日期。"
      ml_rank_ic: "该日模型预测与未来收益的横截面 Spearman 相关。"
  "runs/run_*/ml_folds.csv":
    summary: "保存每次机器学习 walk-forward 重训练的训练边界、预测边界、样本数和模型。"
    columns:
      fold: "从 0 开始的重训练折编号。"
      train_start: "该折训练窗口的首个交易日期。"
      train_end: "该折训练窗口的最后日期，已扣除标签实现期。"
      prediction_start: "该折模型首次生成样本外预测的日期。"
      prediction_end: "该折模型在下一次重训前计划覆盖的最后预测日期。"
      n_train_dates: "该折训练窗口中的唯一交易日数量。"
      n_train_samples: "标签非缺失并实际参与拟合的证券日期样本行数。"
      model: "该折使用的回归模型名称。"
  "runs/run_*/ml_feature_importance.csv":
    summary: "逐折逐特征保存机器学习解释值、解释类型及训练和预测边界。"
    columns:
      fold: "与 ml_folds.csv 对应的重训练折编号。"
      feature: "被解释的模型输入特征名称。"
      importance: "该折模型对该特征给出的系数、原生重要性或置换重要性。"
      kind: "解释值类型：coefficient、native_importance 或 permutation_importance。"
      train_end: "产生该解释值的模型训练截止日期。"
      prediction_start: "该模型首次生成样本外预测的日期。"
  "runs/run_*/theoretical_orders.csv":
    summary: "保存最终目标权重按最新价格和整数手规则转换出的理论订单。"
    columns:
      symbol: "订单对应的证券代码。"
      side: "订单方向，取值为 BUY 或 SELL。"
      requested_shares: "相对当前持仓请求交易的绝对股数。"
      reference_price: "生成理论订单时使用的最新参考价格。"
      target_shares: "按目标权重、净资产、价格和整数手计算的目标持股数。"
  "runs/run_*/simulated_fills.csv":
    summary: "按成交量参与上限、滑点和平方根冲击模拟理论订单的成交结果。"
    columns:
      symbol: "模拟成交对应的证券代码。"
      side: "模拟成交方向，取值为 BUY 或 SELL。"
      requested_shares: "理论订单请求交易的股数。"
      filled_shares: "受成交量参与上限约束后实际模拟成交的股数。"
      unfilled_shares: "请求股数减去模拟成交股数。"
      reference_price: "冲击和滑点施加前的市场参考价格。"
      execution_price: "加入方向性滑点和冲击后的模拟执行价格。"
      volume: "容量约束使用的当日市场成交量。"
      participation_rate: "模拟成交股数除以市场成交量。"
      impact_cost: "执行价相对参考价的绝对金额偏差乘以成交股数，包含滑点与冲击。"
      status: "成交状态：FILLED、PARTIALLY_FILLED 或 UNFILLED。"
  "runs/run_*/execution_reconciliation.csv":
    summary: "按证券和方向对账理论请求股数与模拟成交股数。"
    columns:
      symbol: "对账记录对应的证券代码。"
      side: "对账记录对应的订单方向。"
      theoretical_shares: "同一证券和方向汇总后的理论请求股数。"
      simulated_shares: "同一证券和方向汇总后的模拟成交股数。"
      share_difference: "模拟成交股数减去理论请求股数。"
      matched: "股数差绝对值是否不超过配置容差，本流水线默认容差为 0。"
  "runs/run_*/paper_state/paper_holdings.csv":
    summary: "保存最后五个交易日模拟盘运行结束后的证券持仓与最近买入日期。"
    columns:
      symbol: "持仓对应的证券代码索引。"
      shares: "模拟盘当前持有的证券股数。"
      last_buy_date: "该证券最近一次买入日期，用于执行 T+1 卖出限制。"
  "runs/run_*/paper_state/paper_trades.csv":
    summary: "逐笔保存最后五个交易日模拟盘的请求、成交、价格、费用与状态。"
    columns:
      date: "模拟交易发生的交易日期。"
      symbol: "模拟交易对应的证券代码。"
      side: "交易方向，取值为 BUY 或 SELL。"
      shares: "该笔实际成交股数，受交易限制、容量与现金约束。"
      requested_shares: "该笔调仓原始请求股数。"
      price: "加入滑点和冲击后的模拟成交价格。"
      reference_price: "施加滑点和冲击前的市场参考价格。"
      fee: "该笔交易的佣金与卖出印花税合计。"
      status: "成交或阻塞状态，例如 FILLED、PARTIALLY_FILLED、UNFILLED、SUSPENDED、LIMIT_UP、LIMIT_DOWN 或 T_PLUS_ONE。"
  "runs/run_*/paper_state/paper_account.json":
    summary: "保存模拟盘期末现金和可用于恢复状态的 PaperConfig 配置。"
  "runs/run_*/paper_state/**":
    summary: "目录级入口，汇总模拟盘账户、持仓和逐笔交易状态；具体文件由同一版本 PaperBroker 写出。"
  "runs/run_*/monitor_decision.json":
    summary: "保存最大回撤与 PSI 监控产生的停止判断、结构化原因和指标。"
  reproduction.md:
    summary: "记录本次只读运行目录、固定 seed、配置核对和第三方独立重跑要求。"
  defense_checklist.md:
    summary: "列出经济逻辑、PIT、验证、压力、容量、降级和独立复现的答辩门槛。"
  summary.csv:
    summary: "以指标名和值的长表保存周级运行目录指针、资产数、策略 Sharpe、监控判断和 seed。"
    columns:
      metric: "CSV 无名索引列中的第 24 周汇总指标名称。"
      week24: "对应汇总指标的值。"
  homework.md:
    summary: "要求补全毕业报告、组织第三方复现并完成答辩清单。"
  acceptance.json:
    summary: "记录第 24 周机器可读的验收状态和验收条件。"
  manifest.json:
    summary: "周根课程清单，列出本次唯一运行入口、复现与答辩文件以及公共作业和验收产物。"
---

# 第 24 周：毕业研究、独立复现与答辩

## 学习目标（本周定位与目标）

毕业周不是再跑一次高 Sharpe 回测，而是交付一份第三方可以定位、审计、独立重跑并质询的研究包。runner 每次在 `week24/runs/` 下创建新的 `run_NNN`，绝不覆盖旧运行；周根目录保存复现与答辩入口。完成后，你应能：

1. 从配置、PIT 股票池、因子、组合、回测、风险、稳健验证、ML、执行、模拟盘和监控复述完整链路。
2. 逐项核对周根与运行目录的主要 28 类证据。
3. 用 `run_manifest.json` 固定配置和核心指标，用周根 `manifest.json` 定位实际运行目录。
4. 在独立目录、固定 seed 下重跑，并区分确定性结构、容许浮点误差和不可接受差异。
5. 完成毕业答辩：解释经济逻辑、泄漏防护、失败试验、压力、容量、降级与实盘边界。

## 前置知识

应完成前 23 周，尤其掌握 PIT 数据、历史股票池、因子 IC、组合约束、风险归因、purged/embargo、DSR、压力测试、walk-forward、PSI、执行容量和故障治理。本周数据为合成数据，仅用于验证流程，不构成投资建议，也不能证明真实市场 alpha。

## 运行结构与唯一性

默认周目录为 `artifacts/learning/week24`。每次运行扫描已有 `runs/run_001`、`run_002` 等目录，取最大编号加一。毕业流水线要求目标运行目录尚不存在，因此每次证据天然隔离：

```text
week24/
├── manifest.json
├── summary.csv
├── homework.md
├── acceptance.json
├── reproduction.md
├── defense_checklist.md
└── runs/
    └── run_NNN/
        ├── run_manifest.json
        ├── graduation_report.md
        ├── ...CSV/JSON 研究证据
        └── paper_state/
```

不要把不同 `run_NNN` 的文件拼成一份报告。所有结论必须绑定到 `summary.csv.run_directory` 指定的单一运行。

## 核心理论（理论主线）

### 1. PIT 数据与特征

流水线生成合成行情和证券主数据，使用 point-in-time universe，再按公告可得时间对齐基本面。因子包括动量、低波、盈利收益率、账面市值比、ROE、应计质量和流动性。每个交易日做横截面 z-score：

\[
z_{i,t}=\frac{x_{i,t}-\bar x_t}{s_t}.
\]

等权复合分数来自标准化因子，未来收益期限由验证配置决定。基本面必须按“当时可得”对齐，而不是按报告期直接回填。

### 2. 因子证据

日度 Rank IC 为分数与未来收益的 Spearman 相关：

\[
IC_t=\rho_{\text{Spearman}}(s_{i,t},r_{i,t\to t+H}).
\]

因子摘要报告平均 Rank IC、ICIR 和观测数；年度 IC、衰减和因子相关分别检验时间稳定性、预测期限和冗余。单一平均 IC 不能替代这些诊断。

### 3. 组合与回测

组合月度调仓，受单票上限、行业相对偏离和换手约束。快速模式 20 只资产、单票上限 5%；完整模式 40 只、上限 2.5%，两者恰好允许满仓但几乎没有集中度余量。回测纳入佣金、印花税、滑点、执行滞后、停牌和涨跌停约束。

日度证据同时保存策略收益、基准收益、净值、换手和成本。绩效必须从日度表可重算；不能只引用报告中的 Sharpe。

### 4. 风险与稳健性

资产协方差使用 Ledoit–Wolf 收缩。风险证据覆盖资产风险贡献、相对基准主动风险归因及因子风险分解。稳健验证覆盖成本倍增、连续时间子样本和牛熊状态。

训练/验证/最终测试协议按时间划分，并在边界应用 purge 与 embargo。完整模式的标签期限 20、purge 20、embargo 5；快速模式为 10、10、2。最终测试只应在研究规则冻结后一次性查看。

试验注册至少含 `baseline` 与 `double_cost`。DSR 使用全部登记试验修正选择偏差。当前只有两个登记项并不证明历史研发只做过两次；答辩人必须披露流水线外的全部试验。

### 5. ML、执行与监控

ML 使用动量、低波、盈利收益率、ROE、流动性五个特征，按 walk-forward 训练，严格扣除标签实现期；输出逐日 Rank IC、折边界和逐折解释。

最终权重转换为整数手理论订单，再按成交量参与上限、滑点和平方根冲击模拟成交并对账。随后用 `PaperBroker` 在最后五个交易日运行并保存状态。

监控比较动量因子的参考段和当前段 PSI，同时检查净值最大回撤：

\[
PSI=\sum_j(q_j-p_j)\ln(q_j/p_j).
\]

输出 `monitor_should_stop` 只是本次离线规则决策，不代表真实生产监控已经部署。

## 阅读顺序

先用周根指针锁定唯一 `run_NNN`，再按数据与因子、组合与绩效、风险与验证、ML、执行与模拟盘、监控与治理的证据链阅读。完成运行级审计后再读复现协议、毕业报告和答辩清单，避免报告叙事先入为主。

## 实验步骤（实验与独立复现顺序）

1. 运行课程，记录新生成的 `run_NNN`，不要复用旧目录。
2. 从周根 `manifest.json` 找 GUIDE 入口，再以 `summary.csv.run_directory` 交叉确认。
3. 读取运行级 `run_manifest.json`，冻结其 `config`、数据声明、日期范围、资产数和 seed。
4. 按“数据/因子 → 组合/绩效 → 风险/压力 → 验证/ML → 执行/模拟盘 → 监控”顺序审阅。
5. 补全 `graduation_report.md`，不得改写原始 CSV/JSON 来迎合结论。
6. 第三方在新的输出目录使用相同配置和 seed 重跑。
7. 比较文件集合、行列模式、日期边界、核心指标和停止决策；记录差异而不是覆盖第一次结果。
8. 逐项完成答辩清单，保留质询、无法回答项和修改记录。

## GUIDE：周根 manifest 的可导航映射

周根 `manifest.json` 由课程 runner 生成。它声明的核心研究入口必须能映射到以下 GUIDE；`run_*` 是文档通配说明，实际路径必须替换为本次 `summary.csv.run_directory`（例如 `runs/run_003`）：

- manifest 入口 `runs/run_NNN/run_manifest.json` → GUIDE“运行身份、配置与核心指标”。
- manifest 入口 `runs/run_NNN/graduation_report.md` → GUIDE“毕业报告与结论边界”。
- manifest 入口 `reproduction.md` → GUIDE“独立复现协议”。
- manifest 入口 `defense_checklist.md` → GUIDE“答辩门槛”。
- runner 追加的 `summary.csv` → GUIDE“周级运行指针与摘要”。
- runner 追加的 `homework.md` → GUIDE“待补研究任务”。
- runner 追加的 `acceptance.json` → GUIDE“机器可读验收条件”。

因此，通配符只用于讲义描述；验收时必须证明每个 manifest 根产物都能落到一个具体文件，尤其不能让 `runs/run_*/...` 模糊指向多个运行。

## 逐文件与字段解释（主要 28 类产物与字段）

下面按审计用途归为 28 类。组合类会包含多个真实文件；YAML frontmatter 则逐路径列出，以便直接发现文件。

### 1. 周根运行清单：`manifest.json`

记录周数、quick 模式及 runner 声明的产物路径。它是课程级导航，不等于运行级研究 manifest。重点检查其运行路径与 `summary.csv.run_directory` 指向同一 `run_NNN`。

### 2. 周级摘要：`summary.csv`

- `run_directory`：相对周根的唯一运行目录。
- `assets`：运行级 manifest 报告的资产数。
- `strategy_sharpe`：策略 Sharpe。
- `monitor_should_stop`：监控停止决策。
- `seed`：固定为 202407。

### 3. 作业与验收：`homework.md`、`acceptance.json`

前者要求补全报告、第三方复现和答辩；后者记录第 24 周验收条件。它们是流程证据，不是性能证据。

### 4. 独立复现协议：`reproduction.md`

包含本次只读产物目录、固定 seed、配置/数据/环境核对和新目录重跑要求。第三方应追加环境版本、运行命令、开始结束时间、差异摘要和签名。

### 5. 答辩入口：`defense_checklist.md`

检查经济逻辑、PIT 与标签隔离、失败试验与 DSR、压力与容量、停止降级恢复以及第三方复现。勾选必须附证据路径，不能只改成 `[x]`。

### 6. 运行身份与配置：`runs/run_*/run_manifest.json`

- `course_week`：24。
- `data`：`synthetic_for_process_validation_only`。
- `config`：完整 `ResearchConfig` 嵌套字典。
- `date_range`：价格日期最小值、最大值。
- `assets`：价格矩阵资产列数。
- `mean_composite_rank_ic`、`mean_ml_rank_ic`：复合因子与 ML 平均 Rank IC。
- `strategy_sharpe`：绩效摘要中的 Sharpe。
- `final_turnover`：最后两日目标权重换手。
- `monitor_should_stop`：监控决策。

`config` 内含起止日期、seed 及数据、因子、组合、验证、回测、执行、监控等配置，是复现的首要输入。

### 7. 毕业报告：`runs/run_*/graduation_report.md`

初始报告含合成数据免责声明、策略 Sharpe、复合 Rank IC、ML Rank IC、监控停止状态，并要求补充经济逻辑、PIT 审计、稳健证据、失败实验和实盘边界。

### 8. 因子摘要：`factor_summary.csv`

索引为因子名；字段 `mean_rank_ic`、`icir`、`observations`。检查方向、稳定性和有效样本，不以单个高 IC 决策。

### 9. 因子日度 IC：`factor_daily_ic.csv`

`date` 加每个标准化因子一列，值为当日 Rank IC。用于重算均值、波动、ICIR和时序稳定性。

### 10. 时间稳定与衰减：`composite_yearly_ic.csv`、`factor_ic_decay.csv`

前者按年汇总复合因子 IC；后者保存不同预测滞后下的 IC 衰减序列。字段命名来自相应 Series/DataFrame 输出，审阅时以文件表头为准，并核对期限是否与经济逻辑一致。

### 11. 因子冗余：`factor_correlation.csv`

因子相关矩阵，行列均为因子名。检查对称性、对角线及高相关簇；相关不等于完全冗余，还要结合稳定性和交易成本。

### 12. 绩效摘要：`performance_summary.csv`

由 `performance_summary` 以 Series 形式写出，包含策略绩效指标；`strategy_sharpe` 从其中取值。答辩时须以文件实际行名逐项解释，不能从本讲义猜测未显式代码字段。

### 13. 日度绩效：`daily_performance.csv`

- `date`：交易日索引。
- `strategy_return`、`benchmark_return`：策略和等权基准日收益。
- `strategy_nav`：策略财富指数。
- `turnover`：组合换手。
- `cost`：回测交易成本。

它是复算收益、Sharpe、回撤和成本的底表。

### 14. 资产风险分解：`asset_risk_decomposition.csv`

按最终权重和收缩协方差输出资产层风险贡献。具体列由风险函数生成，应检查贡献加总与组合风险的一致性。

### 15. 主动风险归因：`active_risk_attribution.csv`

比较最终组合与等权基准，输出主动风险归因。审阅重点是主动权重、边际/贡献口径及加总关系，实际字段以表头为准。

### 16. 因子风险分解：`factor_risk_decomposition.csv`

以 Series 形式输出因子模型下组合风险分解。检查因子风险与特异风险口径、资产交集以及最终权重重索引造成的遗漏。

### 17. 三组压力：`stress_costs.csv`、`stress_subsamples.csv`、`stress_market_regimes.csv`

- 成本压力索引 `cost_multiplier`，字段 `observations`、`annualized_return`、`sharpe`、`max_drawdown`。
- 子样本压力索引 `subsample`，字段同上。
- 状态压力索引 `regime`，字段同上。

它们分别回答成本敏感性、时间稳定性和牛熊适应性，不能互相替代。

### 18. 验证协议：`validation_protocol.json`

键为 `train`、`validation`、`final_test`；每个值是 `[最早日期, 最晚日期, 日期数]`。检查时间顺序、集合非空及 purge/embargo 后的空档。该文件不保存空档参数本身，需回到运行 manifest 的 `config.validation`。

### 19. 试验注册：`experiment_registry.csv`

- `name`：`baseline`、`double_cost`。
- `sharpe`：年化 Sharpe。
- `observations`：有效收益数。

任何流水线外尝试也必须披露，否则登记数低估选择偏差。

### 20. Deflated Sharpe：`deflated_sharpe.json`

字段为 `probability`、`observed_sharpe`、`benchmark_sharpe`、`n_trials`、`observations`、`skewness`、`kurtosis`。正确说法是“观察 Sharpe 超过多试验门槛的概率近似”，不是盈利概率。

### 21. ML 日度 Rank IC：`ml_daily_rank_ic.csv`

日期索引和 `ml_rank_ic` 值。用于复算 `mean_ml_rank_ic`，并观察模型信号随时间是否失效。

### 22. ML 折边界：`ml_folds.csv`

字段 `fold`、`train_start`、`train_end`、`prediction_start`、`prediction_end`、`n_train_dates`、`n_train_samples`、`model`。逐折证明训练截止早于预测并留足标签实现期。

### 23. ML 逐折解释：`ml_feature_importance.csv`

字段 `fold`、`feature`、`importance`、`kind`、`train_end`、`prediction_start`。比较跨折方向和排序，不能混用不同 `kind` 的尺度。

### 24. 理论订单：`theoretical_orders.csv`

- `symbol`、`side`。
- `requested_shares`、`reference_price`、`target_shares`。

检查非负权重、100 股整数手和权重到股数的舍入。

### 25. 模拟成交：`simulated_fills.csv`

- `symbol`、`side`、`requested_shares`。
- `filled_shares`、`unfilled_shares`。
- `reference_price`、`execution_price`、`volume`。
- `participation_rate`、`impact_cost`、`status`。

`status` 为 `FILLED`、`PARTIALLY_FILLED` 或 `UNFILLED`。

### 26. 执行对账：`execution_reconciliation.csv`

- `symbol`、`side`。
- `theoretical_shares`、`simulated_shares`。
- `share_difference`、`matched`。

默认股数容差为 0；部分成交会造成不匹配，这不是文件错误，而是执行约束证据。

### 27. 模拟盘状态：`paper_state/**`

该目录由 `PaperBroker.save_state` 写入，保存最后五日模拟运行状态。`pipeline.py` 没有显式展开其内部文件与字段，因此讲义只把它作为目录级产物，不臆造文件名。验收时应递归列出实际内容，核对现金、持仓、订单/成交或状态文件能否被对应版本加载。

### 28. 监控决策：`monitor_decision.json`

- `should_stop`：是否停止。
- `reasons`：结构化原因列表。
- `metrics`：至少包括 `max_drawdown`，提供 PSI 时还包括 `psi`。

其阈值来自 `run_manifest.json.config.monitor`；恢复决策不在该文件中，不能把 `should_stop=false` 等同于获得上线批准。

## 图表解读（无预生成图时的建议）

毕业包不要求固定图片，若运行目录没有图，应从底表生成并把脚本、输入路径和运行编号写入报告。最低建议包括：因子日度/年度 IC 与衰减图、策略和基准净值及回撤图、成本与状态压力图、ML Rank IC 与逐折重要性图、理论请求与模拟成交对比图、监控 PSI 分箱贡献图。所有图标题必须标注具体 `run_NNN`、样本区间和口径；图上的均值、Sharpe 或回撤应能回到 CSV 字段复算，不能跨运行拼接。解读顺序是先看样本与边界，再看稳定性和尾部，最后才看平均绩效。

## 动态指标判断

- 因子层持续跟踪滚动 Rank IC、ICIR、符号一致性、衰减和相关性；短期抬升但年度稳定性下降时，不应提高结论等级。
- 组合层联合跟踪滚动 Sharpe、相对收益、回撤、换手和成本占毛收益比例；高收益若伴随成本或集中风险上升，应触发复核。
- 验证与 ML 层监控试验登记数、DSR、折边界、样本外 Rank IC、重要性翻转和 PSI；任何泄漏都使后续动态指标失效。
- 执行与模拟盘层监控成交率、参与率、冲击、未成交量、现金与持仓差异；回测指标不能覆盖执行或对账红线。
- 采用预注册的绿/黄/红阈值：黄色进入调查与影子观察，红色停止新增风险；从红色恢复必须满足根因关闭、独立复算和人工批准，不能因单期指标反弹自动恢复。

## 复现判断标准

独立复现应分层比较：

1. **结构一致**：28 类产物齐全，CSV/JSON 可解析，日期和索引唯一。
2. **配置一致**：seed、数据规模、标签期限、purge/embargo、成本、执行和监控阈值一致。
3. **边界一致**：日期范围、资产数、折边界、情景数量一致。
4. **数值一致**：同环境与固定 seed 下核心指标应在预先声明的浮点容差内。
5. **治理一致**：停止决策、失败试验披露、报告免责声明和恢复边界一致。

若第三方只复制原目录并重算摘要，不叫独立复现。若重跑结果不同，应先保存双方产物，再比较环境、依赖、排序、随机种子和输入哈希；禁止覆盖原运行。

## 答辩叙事顺序

1. 研究问题、经济机制和预注册假设。
2. 数据何时可得、股票池如何避免幸存者偏差。
3. 因子为什么可能获得补偿，何时会失效。
4. 组合约束、成本、停牌涨跌停和执行滞后。
5. 风险来源与最差压力情景。
6. 验证边界、全部试验、DSR 和 final-test 纪律。
7. ML 相对规则模型带来的增量及漂移降级。
8. 容量、部分成交、模拟盘和账户对账。
9. 停止、回滚、人工恢复和实盘不可逾越边界。
10. 第三方复现结果、差异与尚未解决的问题。

## 常见误区

1. 用合成数据 Sharpe 宣称真实 alpha。
2. 只交 `graduation_report.md`，没有底层 CSV/JSON。
3. 从多个 `run_NNN` 挑最好指标拼报告。
4. 把固定 seed 等同于完全可复现，忽略依赖和排序。
5. 只登记 baseline 与 double_cost，隐藏人工调参历史。
6. 把 final-test 反复用于修改策略。
7. 将部分成交对账不匹配当作程序错误删除。
8. 把 `monitor_should_stop=false` 当作上线批准。
9. 在讲义中臆造 `paper_state` 内部字段，而不检查实际保存内容。
10. 勾完答辩清单却没有证据路径和第三方签字。

## 思考题

1. `run_manifest.json` 已含 config，为什么还需要周根 `manifest.json` 与 `reproduction.md`？
2. 固定 seed 后仍可能出现哪些跨环境差异？
3. 如果 baseline DSR 很高但 double_cost Sharpe 为负，答辩结论应如何调整？
4. 若执行对账大量不匹配，而回测 Sharpe 很高，哪个证据优先？
5. 如何证明 final-test 只查看一次？代码之外需要什么流程记录？

## 作业提示（毕业作业）

1. 补全运行目录中的毕业报告，覆盖经济逻辑、PIT 审计、稳健证据、失败试验、容量与实盘边界。
2. 请第三方依据 `reproduction.md` 在新目录重跑，提交环境、命令、文件集合、核心指标差异和签名。
3. 为 28 类产物建立逐项证据索引，每项写“路径—字段—结论—限制—答辩页码”。
4. 完成一次 20 分钟答辩和 10 分钟质询；保留无法回答项及修订记录。
5. 设计上线前否决条件：任何一个条件失败都不得以高 Sharpe 豁免。

## 验收标准（最终验收）

- 新运行位于唯一 `week24/runs/run_NNN`，没有覆盖或混用旧运行。
- 周根 manifest 的每个产物均通过 GUIDE 映射到具体路径，`summary.csv.run_directory` 与之相符。
- 28 类主要产物均被审阅，实际字段与本讲义或文件表头一致；`paper_state` 不作无依据推断。
- 第三方在独立目录固定 seed 重跑，并提交可审计差异。
- 能解释 PIT、purge/embargo、DSR、压力、PSI 降级、容量和故障治理。
- 报告明确合成数据边界、失败试验、最终测试纪律和实盘否决条件。
- 答辩清单逐项附证据，恢复与上线均保留人工批准。
