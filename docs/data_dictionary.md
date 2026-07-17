# 数据字典与时点规范

## 1. 使用原则

本文件定义进阶课程的最低数据契约。正式研究可增加字段，但不得弱化以下要求。每个数据集必须记录：数据集 ID、供应商、许可范围、原始快照位置、获取时间、内容哈希、模式版本、转换版本、负责人和已知缺陷。

时间统一使用 `Asia/Shanghai`；日期采用 `YYYY-MM-DD`，时间采用带时区的 ISO 8601。空值必须保留为空并附原因码，不得用 0、空字符串或极端数值代替。

## 2. 时间语义

| 字段 | 含义 | 约束 |
|---|---|---|
| `event_time` | 现实事件发生时间 | 不代表市场已经知道 |
| `period_end` | 财务或统计报告期末 | 禁止作为财务信息可用日 |
| `publish_time` | 信息首次公开时间 | 需保留盘前、盘中、盘后精度 |
| `vendor_time` | 供应商接收或入库时间 | 用于识别供应商延迟 |
| `ingested_at` | 本系统获取时间 | 必须由系统写入且不可回填 |
| `valid_from/to` | 事实有效区间 | 表达现实状态变化 |
| `known_from/to` | 系统可知版本区间 | 表达修订历史 |
| `tradable_from` | 按课程成交规则最早可交易时间 | 由公开时间、日历和执行假设推导 |

默认规则：收盘后公开的信息最早在下一交易日使用；盘中信息若策略仅按日频运行，也在下一交易日使用。任何例外必须在 manifest 中声明。

## 3. 证券主数据

| 字段 | 类型 | 主键/单位 | 可用时点与质量规则 |
|---|---|---|---|
| `instrument_id` | string | 稳定内部 ID | 不随代码或交易所变化 |
| `symbol` | string | 交易代码 | 联合 `exchange`、有效区间唯一 |
| `exchange` | enum | SSE/SZSE/BSE | 不允许未知值静默进入 |
| `security_type` | enum | 股票/ETF/指数等 | 研究股票池需显式过滤 |
| `list_date` | date | 上市日 | 与交易日历交叉验证 |
| `delist_date` | date/null | 退市日 | 在市证券为空 |
| `board` | enum | 主板/科创板/创业板等 | 按历史有效区间保存 |
| `name` | string | 证券简称 | 不可作为关联主键 |
| `industry_code` | string | 分类代码 | 必须带分类体系与版本 |
| `industry_known_from` | datetime | 可知时间 | 禁止使用未来行业分类 |
| `st_status` | bool | ST 状态 | 保存生效和公开时间 |
| `suspension_status` | enum | 正常/停牌/临停 | 每交易日校验 |

## 4. 日行情与交易状态

日行情建议主键为 `instrument_id + trade_date + price_adjustment`。原始未复权行情必须永久保留，复权价格应由公司行动表可重建。

| 字段 | 类型 | 单位/口径 | 质量规则 |
|---|---|---|---|
| `trade_date` | date | 交易所交易日 | 不得含非交易日 |
| `open/high/low/close` | decimal | 元/股，未复权 | `high >= max(open, close, low)` |
| `prev_close` | decimal | 元/股，未复权 | 与前一有效收盘及公司行动核对 |
| `volume` | integer | 股 | 非负；不得混用手 |
| `amount` | decimal | 元 | 非负；量价关系异常需标记 |
| `vwap` | decimal/null | 元/股 | 口径必须说明是否含集合竞价 |
| `adj_factor` | decimal | 复权因子 | 正值；变更需对应公司行动 |
| `return` | decimal | 简单收益 | 明确价格口径和现金分红处理 |
| `turnover_rate` | decimal | 小数 | 分母股本口径必须可追溯 |
| `limit_up/down` | decimal | 元/股 | 按当日板块、ST 与规则计算 |
| `hit_limit_up/down` | bool | 触及状态 | 不等于不可成交 |
| `one_price_limit` | bool | 一字板 | 需由 OHLC 与限价联合判断 |
| `is_suspended` | bool | 是否停牌 | 停牌日价格填充不得产生收益 |
| `trade_status_reason` | enum | 状态原因 | 缺失时不得默认正常 |

## 5. 公司行动与股本

| 字段 | 类型 | 含义 | 时点要求 |
|---|---|---|---|
| `action_id` | string | 公司行动唯一 ID | 同一事件修订不得新建无关 ID |
| `action_type` | enum | 分红/送股/配股/拆并股等 | 类型枚举版本化 |
| `announce_time` | datetime | 首次公告时间 | 保留修订链 |
| `record_date` | date | 股权登记日 | 不作为首次可用时间 |
| `ex_date` | date | 除权除息日 | 与复权因子核对 |
| `pay_date` | date/null | 现金到账日 | 现金回测需使用 |
| `cash_dividend` | decimal | 每股现金 | 税前/税后口径明确 |
| `share_ratio` | decimal | 每股送转比例 | 与总股本变化核对 |
| `total_shares` | decimal | 总股本 | 保存历史有效区间 |
| `float_shares` | decimal | 流通股本 | 明确限售口径 |
| `free_float_shares` | decimal/null | 自由流通股本 | 供应商算法需记录 |

## 6. 财务与基本面

推荐主键：`instrument_id + statement_type + period_end + metric + known_from`。必须保留原始披露值、修订值和累计/单季口径。

| 字段 | 类型 | 含义 | 时点与校验 |
|---|---|---|---|
| `statement_type` | enum | 资产负债/利润/现金流 | 枚举固定 |
| `period_end` | date | 报告期末 | 仅描述归属期 |
| `report_type` | enum | 一季报/中报/三季报/年报 | 与报告期匹配 |
| `publish_time` | datetime | 实际公开时间 | 因子对齐核心字段 |
| `revision_no` | integer | 修订序号 | 单调递增 |
| `currency` | string | 币种 | 转换汇率也需 point-in-time |
| `revenue` | decimal | 营业收入 | 累计/单季口径明确 |
| `net_profit` | decimal | 归母净利润 | 不得与扣非混用 |
| `equity` | decimal | 归母权益 | 负值处理规则显式声明 |
| `total_assets` | decimal | 总资产 | 会计口径变化需标记 |
| `operating_cashflow` | decimal | 经营现金流 | 累计值转单季需保留公式 |
| `roe` | decimal/null | 净资产收益率 | 分子分母与年化规则记录 |
| `eps` | decimal/null | 每股收益 | 基本/稀释口径区分 |

## 7. 指数、行业与宏观数据

| 数据集 | 必备字段 | 关键时点 |
|---|---|---|
| 指数成分 | `index_id, instrument_id, announce_time, effective_from, effective_to, weight` | 研究资格按生效日，交易决策需同时考虑公告日 |
| 行业分类 | `instrument_id, taxonomy, version, industry_code, valid_from/to, known_from/to` | 禁止用最新分类覆盖历史 |
| 无风险利率 | `date, tenor, rate, convention, publish_time` | 收益年化与期限一致 |
| 宏观指标 | `period, value, publish_time, revision_no` | 保存初值与修订值 |
| 交易日历 | `exchange, date, session_open/close, is_trading_day` | 临时休市需版本化 |

## 8. 衍生特征、标签与预测

| 字段 | 含义 | 强制要求 |
|---|---|---|
| `feature_id/version` | 特征身份与版本 | 公式变化必须升级版本 |
| `as_of_time` | 特征计算截止时间 | 所有输入 `known_from <= as_of_time` |
| `lookback` | 回看窗口 | 明确交易日或自然日 |
| `universe_id/version` | 计算股票池 | 可重建当日成员 |
| `preprocess_fit_end` | 预处理拟合截止 | 不得晚于预测时点 |
| `label_start/end` | 标签收益区间 | 训练边界按标签结束日隔离 |
| `benchmark_id` | 超额收益基准 | 基准版本固定 |
| `model_id/version` | 模型身份 | 对应训练 manifest |
| `prediction_time` | 预测生成时间 | 早于计划执行时间 |
| `target_weight` | 目标权重 | 与优化配置绑定 |

## 9. 订单、成交、持仓与净值

| 字段 | 含义 | 对账规则 |
|---|---|---|
| `order_id/parent_order_id` | 订单及母单 ID | 全局唯一 |
| `decision_time` | 投资决策时间 | 不晚于下单时间 |
| `submit_time` | 报单时间 | 带时区且单调 |
| `side/order_type/limit_price` | 方向与类型 | 枚举合法 |
| `quantity/filled_quantity` | 委托与成交股数 | `0 <= filled <= quantity` |
| `fill_price/fill_time` | 成交信息 | 每笔成交可追溯 |
| `commission/tax/impact` | 成本分项 | 成本和现金变化一致 |
| `reject_reason` | 拒单原因 | 拒单必须非空 |
| `position_quantity` | 收盘持仓股数 | 昨日持仓加净成交对账 |
| `available_quantity` | T+1 可卖数量 | 不大于总持仓 |
| `cash` | 可用现金 | 与成交、费用、分红对账 |
| `nav` | 组合净值 | 持仓市值加现金一致 |

## 10. 质量规则与阈值

- 唯一性：主键重复率必须为 0。
- 完整性：关键时点、证券 ID、价格和版本字段缺失率必须为 0。
- 合法性：价格、成交量、股本非负；枚举值必须在模式内。
- 一致性：OHLC、复权因子、公司行动、持仓和现金必须通过跨表校验。
- 时点性：随机抽查 100 条用于特征的数据，未来可见违规必须为 0。
- 新鲜度：数据延迟阈值由策略频率确定；超阈值必须停止或显式降级。
- 漂移：每日记录行数、覆盖率、缺失率、分位点和 PSI；阈值在研究前确定。

质量检查失败不得静默删除记录后继续。处理动作只能是：阻断、隔离并降级、或经审批接受；动作及原因必须写入日志。

## 11. 版本与变更

模式版本采用语义化版本：破坏兼容性升级主版本，新增兼容字段升级次版本，规则说明或缺陷修复升级补丁版本。每次变更记录日期、发起人、原因、影响数据范围、迁移方法、回滚方法及受影响实验 ID。

建议快照身份由以下内容共同确定：

`dataset_id + schema_version + source_version + snapshot_time + content_hash`

任何一项变化都应产生新数据版本；旧版本不得覆盖，以保证历史实验可复现。
