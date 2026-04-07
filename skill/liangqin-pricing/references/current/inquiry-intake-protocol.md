# 通用客户询盘分诊层 v1 协议

这份文档描述当前已落地的 `平台无关售前询盘分诊层`。

建议和下面几份一起看：

- `references/current/quote-flow-role-routing.md`
- `references/current/quote-flow-frontend-mapping.md`
- `references/current/conversation-policy.md`

这份文档只说明三件事：

- 上游应该传什么
- 分诊层当前会返回什么
- 6 类核心售前问题分别怎么走

## 0. 事实来源边界

这层分诊的训练样本里可以参考真实聊天记录的“客户提问方式”，但不能把历史客服回复当成事实真相。

当前回答依据仍然以 skill 内已有资料和脚本为准，优先包括：

- `references/current/rules.md` 及各拆分规则文档
- `references/current/conversation-policy.md`
- `data/current/price-index.json`
- `scripts/precheck_quote.py`
- `scripts/query_addendum_guidance.py`
- `scripts/handle_quote_message.py`

所以：

- 聊天记录主要用于识别“客户会怎么问”
- 具体事实回答、报价边界、服务边界仍以仓库内资料为准
- 资料不明确时，要走安全收口，不做业务承诺

## 1. 目标范围

v1 只覆盖 6 类核心售前问题：

- `quote_flow`
- `size_spec`
- `measurement_installation`
- `lead_time_service`
- `material_config`
- `purchase_mode`

当前不覆盖：

- 订单
- 支付
- 活动
- 售后

## 2. 入口位置

当前链路里，这层分诊主要落在两个脚本里：

- `scripts/route_quote_request.py`
  - 负责做前置路由
  - 返回 `inquiry_family / preferred_next_tool / preferred_next_stage`
- `scripts/handle_quote_message.py`
  - 负责把分诊结果继续执行下去
  - 对非报价问题生成最终回复

底层分类规则集中在：

- `scripts/inquiry_intake.py`

## 3. 上游输入协议

当前推荐上游至少传这几个字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `text` | 是 | 用户本轮原始消息 |
| `context_json` | 否 | 会话上下文，用于生成 `conversation_id` 和复用状态 |
| `channel` | 否 | 渠道标识，如 `feishu` |
| `product_context` | 否 | 商品上下文，用于补足商品识别和目录尺寸回答 |

`product_context` 当前建议支持这些字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `product_name` | 否 | 商品名 |
| `product_code` | 否 | 商品编号 |
| `product_url` | 否 | 商品链接 |
| `product_ref` | 否 | 上游自己的商品引用 id |
| `recent_catalog_candidates` | 否 | 最近候选目录记录列表 |
| `source_channel_item_text` | 否 | 渠道侧商品文本 |

当前实现里的使用原则：

- 分诊首先看本轮 `text`
- `product_context` 主要用于补产品识别，不做强猜
- 如果 `recent_catalog_candidates` 能唯一收敛，会优先拿它回答目录尺寸
- 如果没有稳定商品上下文，就退回单一追问，不伪造规格

## 4. 路由结果协议

`scripts/route_quote_request.py` 当前会额外返回下面这些分诊字段：

| 字段 | 说明 |
| --- | --- |
| `inquiry_family` | 当前识别到的询盘大类 |
| `inquiry_confidence` | 当前规则命中的置信度 |
| `preferred_next_stage` | 建议下一阶段，当前主要是 `quote_flow` 或 `inquiry_reply` |
| `preferred_next_tool` | 建议下一脚本 |
| `can_answer_directly` | 是否可以先直接回答事实 |
| `needs_product_context` | 是否缺商品识别上下文 |
| `resolved_product_context` | 当前已收敛出的商品上下文 |

当前 `preferred_next_tool` 的典型映射是：

| `inquiry_family` | 当前典型下游 |
| --- | --- |
| `quote_flow` | `precheck_quote` 或规则类脚本 |
| `size_spec` | `inquiry_reply` |
| `measurement_installation` | `inquiry_reply` |
| `lead_time_service` | `inquiry_reply` |
| `purchase_mode` | `inquiry_reply` |
| `material_config` | `query_addendum_guidance` |

说明：

- `material_config` 当前仍优先走资料查询边界，不在 `inquiry_reply` 里补一套新事实源
- 规则咨询、结构咨询、复杂正式报价，会优先保留在 `quote_flow`

## 5. 回复结果协议

当 `preferred_next_tool=inquiry_reply` 时，`scripts/handle_quote_message.py` 当前会产出一组统一字段。

核心字段如下：

| 字段 | 说明 |
| --- | --- |
| `reply_text` | 当前这一轮默认展示给用户的话 |
| `internal_summary` | 内部版摘要 |
| `customer_forward_text` | 可直接转客户的文本 |
| `next_best_question` | 下一步唯一关键追问 |
| `source_basis` | 本轮回答依据类型 |
| `safe_boundary_reason` | 为什么只能做安全口径 |
| `handoff_needed` | 是否建议人工接力 |
| `missing_fields` | 当前仍缺什么 |
| `route_result` | 上游路由结果 |

`inquiry_reply` 下游的内部结果对象里，当前固定会包含：

| 字段 | 说明 |
| --- | --- |
| `reply_text` | 同上 |
| `next_question` | 同 `next_best_question` |
| `source_basis` | 当前依据，如 `catalog_dimensions` |
| `can_answer_directly` | 是否已先答事实 |
| `safe_boundary_reason` | 安全边界原因 |
| `handoff_needed` | 是否需要人工接力 |
| `missing_fields` | 仍缺的关键字段 |
| `resolved_product_context` | 当前命中的商品上下文 |

## 6. 会话状态扩展

为了支持“先问非报价问题，再顺滑回到报价流”，当前 `scripts/quote_flow_state.py` 已补了 4 个轻量字段：

| 字段 | 作用 |
| --- | --- |
| `active_inquiry_family` | 当前处于哪类售前询盘 |
| `captured_product_context` | 最近一次识别出的商品上下文 |
| `last_non_quote_reply` | 最近一次非报价回复 |
| `last_safe_boundary_reason` | 最近一次安全边界原因 |

这几个字段不会替代原有报价状态，原来的这些字段仍然保留：

- `confirmed_fields`
- `missing_fields`
- `last_formal_payload`

## 7. 六类询盘的当前行为

### `quote_flow`

适用情况：

- 明显在要价格、参考价、正式报价
- 已经给出较完整的尺寸、材质、产品信息
- 结构化规则咨询、设计规则咨询

当前行为：

- 直接进入原有报价流
- 不再让泛化的普通用户引导兜底吞掉
- 继续复用现有 `precheck / 正式报价 / 报价卡`

### `size_spec`

适用情况：

- 用户在问“这款多大”“什么尺寸”“规格是多少”
- 重点是对目录规格，不是直接要正式报价

当前行为：

- 如果已能唯一识别商品，直接回答目录尺寸
- 如果无法稳定识别商品，只追一个识别问题

当前典型 `source_basis`：

- `catalog_dimensions`
- `product_identity_required`

### `measurement_installation`

适用情况：

- 用户在问“怎么量尺寸”“量哪里”“怎么预留”

当前行为：

- 先给通用量尺指引
- 如果能识别到大类，就把追问收敛到该类最关键的一组尺寸
- 每轮只追一个问题
- 不在这一层承诺上门覆盖

当前典型 `source_basis`：

- `generic_measurement_guidance`

### `lead_time_service`

适用情况：

- 用户在问“多久”“周期”“交期”“发货”“什么时候装”
- 尤其是同时提到“上门测量 / 设计 / 制作 / 安装”

当前行为：

- 统一先走安全口径
- 只说明需要结合城市、排产、设计确认
- 不自动承诺固定天数、发货时间或覆盖范围
- 然后只追一个最关键的报价条件

当前典型 `source_basis`：

- `safe_service_boundary`

当前典型 `safe_boundary_reason`：

- `service_facts_not_loaded`

### `material_config`

适用情况：

- 用户在问五金、环保、木蜡油、纯实木、进口/国产等配置问题

当前行为：

- 继续遵守现有资料边界
- 当前主要走 `query_addendum_guidance`
- 资料明确的按资料答
- 资料未明确的，保持“现有资料未明确”的安全口径

### `purchase_mode`

适用情况：

- 用户在问“定制还是成品”“有没有现货”“可以做标准品吗”

当前行为：

- 先解释目录成品/标准品和按尺寸定制是两条不同路径
- 再只追一个决定后续路径的问题

当前典型 `source_basis`：

- `purchase_mode_overview`

## 8. 当前分诊规则的保护原则

这一版不是“看见关键词就分进去”，而是先做保护，再做分诊。

当前已经特别加了两类保护：

### A. 结构化报价保护

如果同时命中：

- 价格词，如 `多少钱 / 报价 / 正式报价`
- 和产品 / 材质 / 尺寸等强报价信号

就优先留在 `quote_flow`，不让 `size_spec` 抢走。

### B. 规则咨询保护

如果命中：

- `规则 / 工艺 / 结构 / 节点 / 默认做 / 允许范围`

就优先留给原有规则路径，不进非报价问答层。

## 9. 典型样例

下面这组样例更适合拿给上游或前端联调。

| 用户输入 | 期望 `inquiry_family` | 期望行为 |
| --- | --- | --- |
| `这款没有尺寸吗` | `size_spec` | 无上下文时追商品识别；有稳定商品上下文时直接回目录尺寸 |
| `怎么量尺寸` | `measurement_installation` | 先给量尺指引，再只追一个关键量尺问题 |
| `这个4980的是什么尺寸的柜子` | `size_spec` | 若已命中目录候选，优先解释价格对应规格 |
| `半高床定制的话上门测量，设计，制作安装大概要多久，什么价格` | `lead_time_service` | 先给安全口径，再追一个决定报价路径的关键条件 |
| `良禽佳木可以选国产五金和进口五金吗` | `material_config` | 走资料边界，不混行业常识 |
| `我想定个书柜` | `quote_flow` | 继续走原有报价/引导路径，不回到尺寸问答层 |

再补两条容易误判、现在已经被保护的样例：

| 用户输入 | 期望 `inquiry_family` | 原因 |
| --- | --- | --- |
| `常规拆装柜体高度1700以内默认做顶盖侧还是侧盖顶？` | `quote_flow` | 这是规则咨询，不是规格问答 |
| `一张半高梯柜上铺床...床垫尺寸的...直接正式报价` | `quote_flow` | 这是结构化正式报价，不是因为出现“尺寸”就变成 `size_spec` |

## 10. 给前端或上游的最低接入建议

如果上游第一版只想轻接，可以先只接下面这些字段：

- 输入：
  - `text`
  - `context_json`
  - `channel`
  - `product_context`
- 路由结果：
  - `inquiry_family`
  - `preferred_next_tool`
  - `preferred_next_stage`
  - `can_answer_directly`
  - `needs_product_context`
- 执行结果：
  - `reply_text`
  - `next_best_question`
  - `missing_fields`
  - `source_basis`
  - `safe_boundary_reason`

这样已经足够实现：

- 先分清是不是报价
- 非报价时先答事实
- 每轮最多只追一个问题
- 客户从非报价问题平滑切回正式报价
