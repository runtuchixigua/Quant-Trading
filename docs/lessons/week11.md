---
week: 11
title: "模拟盘与执行"
phase: "模拟盘"
reading_order:
  - "先复习目标权重与约束组合，理解信号不等于成交"
  - "再阅读本文的订单、容量、滑点、冲击、账本更新与对账"
  - "运行 python scripts/learn.py 11"
  - "按 orders→fills→reconciliation→daily_nav→holdings→PNG/report 顺序逐日审计"
artifacts:
  orders.csv:
    summary: "逐日保存由目标权重转换得到的整数手买卖订单。"
    columns:
      symbol: "订单对应的证券代码。"
      side: "订单方向，取 BUY 或 SELL。"
      requested_shares: "目标持仓与当前持仓之差对应的理论请求股数。"
      reference_price: "目标权重转换为目标股数时使用的当日参考价。"
      target_shares: "按目标权重、净值、参考价和整数手计算的目标持仓股数。"
      date: "订单生成对应的交易日期。"
  fills.csv:
    summary: "逐日保存容量、滑点和冲击约束下的模拟成交明细。"
    columns:
      symbol: "模拟成交对应的证券代码。"
      side: "模拟成交方向，取 BUY 或 SELL。"
      requested_shares: "对应订单原始请求成交的股数。"
      filled_shares: "应用成交量参与率上限后实际模拟成交的股数。"
      unfilled_shares: "请求股数减去模拟成交股数后的未成交数量。"
      reference_price: "计算执行价与价差成本所用的当日参考价。"
      execution_price: "加入方向性固定滑点与市场冲击后的模拟成交价。"
      volume: "容量计算使用的该证券当日市场成交量。"
      participation_rate: "模拟成交股数占当日市场成交量的比例。"
      impact_cost: "执行价与参考价的绝对价差乘成交股数，包含滑点与冲击。"
      status: "按成交数量划分的全成、部成或未成状态。"
      date: "模拟成交发生对应的交易日期。"
  reconciliation.csv:
    summary: "逐日按证券和方向对比理论订单数量与模拟成交数量。"
    columns:
      symbol: "订单与成交对账对应的证券代码。"
      side: "订单与成交对账对应的买卖方向。"
      theoretical_shares: "同日同证券同方向的理论订单股数合计。"
      simulated_shares: "同日同证券同方向的模拟成交股数合计。"
      share_difference: "模拟成交股数减去理论订单股数的差额。"
      matched: "股数差额绝对值是否在零股容差内。"
      date: "执行数量对账对应的交易日期。"
  daily_nav.csv:
    summary: "逐日保存执行后的现金、市值、净值和订单成交对账统计。"
    columns:
      date: "账户账本和净值对应的交易日期。"
      cash: "执行当日全部模拟成交后的现金余额。"
      market_value: "按当日参考价计算的日末持仓市值。"
      nav: "日末现金余额与持仓市值之和。"
      orders: "当日生成的订单记录行数。"
      filled_shares: "当日所有买卖模拟成交股数绝对值之和。"
      reconciled: "当日全部执行数量对账行是否均匹配。"
  holdings.csv:
    summary: "保存五个交易日模拟执行结束后的完整证券持仓股数。"
    columns:
      symbol: "证券代码，包括期末零持仓证券。"
      shares: "五日模拟执行结束后的持仓股数。"
  summary.csv:
    summary: "以指标名和 week11 数值列汇总交易天数、成交率、匹配率和期末净值。"
    columns:
      "Unnamed: 0": "CSV 中未显式命名的首列，保存天数、订单数、成交率、匹配率和期末净值等汇总指标名称。"
      week11: "第 11 周各汇总指标对应的数值。"
  paper_trading.png:
    summary: "展示五日日末净值路径与按日汇总的模拟执行价差成本。"
  report.md:
    summary: "摘要模拟交易天数、订单数、成交率、对账匹配率和离线边界。"
  homework.md:
    summary: "要求逐日对账订单、成交、现金和持仓并补充实盘安全控制。"
  acceptance.json:
    summary: "保存第 11 周机器可读的课程验收标准与完成状态。"
  acceptance_checklist.md:
    summary: "提供第 11 周模拟盘与执行流程的人工验收清单。"
  manifest.json:
    summary: "记录第 11 周运行元数据、产物清单及讲义字段释义。"
  run_manifest.json:
    summary: "与 manifest.json 同步保存本次第 11 周运行清单。"
---

# 第 11 周：模拟盘与执行

研究信号只有变成订单、成交、现金和持仓，才进入执行世界。本周连续五个交易日选择 5 日动量最高的三只股票，各设 30% 目标权重；系统将目标权重转换为 100 股整数手订单，按成交量参与率上限模拟成交，加入滑点和冲击，再逐日更新账本并对账。整个撮合器离线运行，不连接任何真实券商。

## 学习目标

1. 从目标权重、净值、价格和当前持仓复算目标股数与订单股数。
2. 解释整数手、成交量参与上限、部分成交、滑点和冲击成本。
3. 按订单—成交—现金—持仓—净值链路逐日对账。
4. 区分订单对账匹配、账户账本一致和经济执行质量。
5. 列出接入真实下单系统前仍缺失的安全控制。

## 前置知识与每日流程

本周初始现金 1,000,000，初始持仓为零。每日按以下顺序运行：

1. 用当日价格计算 5 日动量并选择前三名；
2. 为三只股票各设 30% 目标权重，其余为 0，保留约 10% 现金目标；
3. 用交易前现金和持仓按当日参考价计算 `nav_before`；
4. 将目标权重转换为目标股数与买卖订单；
5. 按当日价格、成交量和执行参数模拟成交；
6. 用实际成交股数和执行价更新持仓与现金；
7. 以当日参考价计算市值和日末净值；
8. 保存订单、成交和对账记录。

当前教学流程没有显式佣金、印花税、冻结资金、T+1 卖出限制、涨跌停、停牌或拒单理由；不能把它称为完整 A 股 OMS/EMS。

## 核心理论：从权重到订单

对股票 \(i\)，目标股数按整数手向下取整：

\[
q_i^*=
\left\lfloor\frac{w_iV}{P_iL}\right\rfloor L,
\]

其中 \(w_i\) 是目标权重，\(V\) 是交易前净值，\(P_i\) 是参考价，\(L=100\) 股。订单差额为 \(\Delta q_i=q_i^*-q_i\)。\(\Delta q_i\ge0\) 生成 BUY，负值生成 SELL；股数为绝对值。零差额不写入订单。

向下取整会带来现金残余和目标偏差。组合目标权重和不能超过 1，价格必须有限且为正，目标权重必须有限非负。本实现允许卖出已有持仓，但未验证 T+1 可卖数量。

## 成交容量、滑点与冲击

配置为：

- `lot_size=100`；
- `max_volume_participation=0.05`；
- `slippage=0.0005`；
- `impact_coefficient=0.02`；
- `impact_exponent=0.5`。

容量按成交量 5% 向下取整到 100 股：

\[
C_i=\left\lfloor\frac{0.05\,Volume_i}{100}\right\rfloor100,
\qquad
filled_i=\min(requested_i,C_i).
\]

参与率 \(p_i=filled_i/Volume_i\)，冲击率

\[
impact_i=0.02\,p_i^{0.5}.
\]

买入执行价为 \(P_i(1+slippage+impact_i)\)，卖出为
\(P_i(1-slippage-impact_i)\)。`impact_cost` 实际计算的是执行价与参考价差的绝对值乘成交股数，因此它包含固定滑点和模型冲击的总价差成本，字段名比经济含义更窄，解读时必须披露这一点。

状态分为 `FILLED`、`PARTIALLY_FILLED`、`UNFILLED`。部分或未成交不会自动跨日挂单；次日系统根据实际持仓和新目标重新生成订单。

## 账本更新与三层对账

每笔成交方向 \(d\) 对买入为 \(+1\)，卖出为 \(-1\)：

\[
q_i\leftarrow q_i+d\cdot filled_i,
\qquad
Cash\leftarrow Cash-d\cdot filled_i\cdot P_i^{exec}.
\]

日末市值按参考价计算，净值为现金加市值。执行价劣于参考价造成的损失自然进入现金和净值。

必须区分：

1. **订单—成交数量对账**：`reconciliation.csv` 比较同日同代码同方向的理论请求股数与模拟成交股数。
2. **账本滚动对账**：由前一日持仓现金加当日成交，复算当日持仓现金。
3. **外部账户对账**：策略账本与券商实际持仓、现金、费用和在途状态核对；本周没有外部账户。

当前 `matched` 仅在模拟成交股数与理论订单股数之差不超过 0 时为真。因此正常的部分成交会令 `matched=False`，它不是撮合器故障，却提示理论目标没有完全实现。反之，`matched=True` 只证明数量一致，不证明价格合理、现金充足、方向正确或外部账户一致。

## 阅读顺序

先理解目标权重到整数手订单的转换，再读容量、成交价和账本公式；运行后必须逐日沿 `orders.csv` → `fills.csv` → `reconciliation.csv` → `daily_nav.csv` → `holdings.csv` 追踪，之后才看 summary、PNG 和 report。不能从期末净值倒推过程正确。

## 实验步骤

1. 运行 `python scripts/learn.py 11`，确认输出恰有五个交易日。
2. 核对 manifest 后，从第一日开始，不要先看期末净值。
3. 用第一日 `nav_before`、参考价和目标 30% 手算目标股数，核对 `orders.csv`。
4. 用成交量 5% 上限复算 `filled_shares`，再复算参与率、执行价、未成交和状态。
5. 用 fills 逐笔滚动现金和持仓，核对 `daily_nav.csv`。
6. 对每一天、每个 `symbol, side` 检查 reconciliation。
7. 从最后一日滚动账本核对 `holdings.csv`。
8. 复算全期股数成交率与匹配率，核对 summary、PNG 和 report。

## 逐文件与字段解释（产物与字段字典）

### `orders.csv`

- `symbol`：证券代码。
- `side`：`BUY` 或 `SELL`。
- `requested_shares`：理论请求股数，正整数且为 100 的倍数。
- `reference_price`：订单转换使用的当日参考价。
- `target_shares`：按目标权重和整数手计算的目标持仓股数。
- `date`：runner 追加的交易日。

同一股票今天卖出、以后再买入是可能的；必须按日期排序分析。

### `fills.csv`

- `symbol`、`side`、`requested_shares`：对应订单键与请求数量。
- `filled_shares`：容量约束后的实际模拟成交股数。
- `unfilled_shares`：请求减成交。
- `reference_price`：当日模拟参考价。
- `execution_price`：含方向性滑点与冲击的成交价。
- `volume`：当日成交量输入。
- `participation_rate`：成交股数除以市场成交量。
- `impact_cost`：执行价与参考价绝对价差乘成交股数，实际包含滑点与冲击。
- `status`：全成、部成或未成。
- `date`：交易日。

### `reconciliation.csv`

- `symbol`、`side`：聚合对账键。
- `theoretical_shares`：同键理论订单合计。
- `simulated_shares`：同键模拟成交合计。
- `share_difference`：模拟减理论；部分成交通常为负。
- `matched`：差值绝对值是否不超过容差，本周容差为 0。
- `date`：交易日。

### `daily_nav.csv`

- `date`：交易日。
- `cash`：执行所有当日 fills 后的现金。
- `market_value`：日末持仓股数乘当日参考价之和。
- `nav`：`cash + market_value`。
- `orders`：当日订单行数，不是订单股数。
- `filled_shares`：当日所有成交股数绝对数量之和；买卖均为正数，不能直接用于净持仓变化。
- `reconciled`：当日 reconciliation 所有 `matched` 的逻辑与。

### `holdings.csv`

- `symbol`：完整股票列表。
- `shares`：五日结束后的持仓股数，包含零持仓。

### `summary.csv`

指标索引配 `week11` 值列：

- `trading_days`：不同交易日数。
- `orders`：订单总行数。
- `fill_rate`：总成交股数除以总请求股数。
- `reconciliation_match_rate`：所有对账行 `matched` 的均值。
- `ending_nav`：最后一天日末净值。

### 图表解读：`paper_trading.png`

左图为五日日末 NAV，样本太短，不能评价策略有效性；右图按日汇总 `impact_cost`，其实是滑点加冲击的总参考价差成本。柱高还受当日成交规模影响，不能直接当费率比较。

### `report.md` 与控制文件

报告汇报天数、订单数、股数成交率和匹配率，并声明不连接券商。它没有列出逐笔异常。作业、acceptance、checklist 与 manifest 用于学习和审计。

## 动态指标判断与结果边界

可以判断五日流水是否完整、订单转换和模拟成交公式是否一致、账本能否由 fills 滚动复算，以及理论请求是否完全成交。不能判断实盘成交质量、真实冲击、策略盈利能力、A 股规则合规或券商账户一致。

`ending_nav` 不是本周首要评分项。更重要的是：

- 五天订单、fills、reconciliation 日期集合一致；
- 每笔 `requested = filled + unfilled`；
- 状态与成交数量一致；
- 现金和持仓能逐笔复算；
- NAV 恒等式成立；
- 最终 holdings 与滚动账本一致。

## 常见误区（常见误读）

1. 把目标权重当已成交权重。
2. 把 `filled_shares` 日合计当净买入股数。
3. 把 `impact_cost` 解释为纯市场冲击；它还含固定滑点。
4. 把部分成交导致的 `matched=False` 当程序错误。
5. 把 `matched=True` 当完整账户和价格对账通过。
6. 忽略 100 股取整和残余现金。
7. 只核对最后 holdings，不滚动现金。
8. 用五日 NAV 判断策略有效或无效。

## 思考题

1. 若买单因容量只成交一半，第二天应追单、重算目标还是取消？取决于什么？
2. 为什么总成交率高仍可能有严重的单只股票未成交风险？
3. 如何将佣金、印花税、过户费和现金冻结加入账本？
4. 若卖出执行价低于参考价，现金更新公式为何仍使用统一方向变量？
5. 真实券商对账还需要哪些主键、订单状态和时间戳？

## 作业提示

选择一天提交完整工作底稿：目标股数、订单差额、容量、成交价、现金变化、持仓变化和 NAV。若出现部分成交，要解释 `matched=False` 是目标未完全实现，而非隐去该记录。安全控制至少考虑重复下单、价格保护、现金/可卖数量、停牌涨跌停、幂等、人工熔断、券商回报和灾备。

## 验收标准

- [ ] 连续五个交易日均有订单、成交、对账和 NAV。
- [ ] 能独立复算整数手订单、容量、执行价和未成交数量。
- [ ] 逐日滚动现金与持仓，最终与 `daily_nav.csv`、`holdings.csv` 一致。
- [ ] 能区分订单数量对账、策略账本对账和外部账户对账。
- [ ] 正确解释 `impact_cost` 和 `matched` 的实现口径。
- [ ] 明确模拟撮合不连接券商，五日结果不能证明策略有效。
