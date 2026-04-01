# 前端状态字段对照表

这份文档给前端工作台直接使用。

它不解释底层计价规则，只回答三个问题：

- 前端应该读哪些字段
- 这些字段分别放在哪些界面区域
- 不同角色下，哪些内容该显示，哪些内容该隐藏

建议和下面这份一起看：

- `references/current/quote-flow-role-routing.md`

## 1. 会话级主对象

前端工作台建议把下面两份数据当成主输入：

- `QuoteFlowState`
  - 来自 `scripts/quote_flow_state.py`
  - 负责描述“当前这单进行到哪一步”
- 最新一次消息处理结果
  - 来自 `scripts/handle_quote_message.py`
  - 负责描述“这一轮应该怎么展示”

建议前端状态拆成三层：

- 会话层
  - 当前角色、当前路由、是否还有缺参、是否有人工覆盖
- 结果层
  - 当前回复文本、内部版、客户版、最新正式报价
- 控制层
  - 是否允许生成报价卡
  - 是否允许一键切换角色
  - 是否提示“这是新单，将清理旧上下文”

## 2. 字段到界面的映射

| 字段 | 来源 | 前端建议区域 | 用途 |
| --- | --- | --- | --- |
| `audience_role` | `handle_message` / `QuoteFlowState` | 顶部角色切换栏 | 决定当前角色标签和默认展示版本 |
| `output_profile` | `handle_message` | 顶部视图模式标签 | 区分 `customer_simple / designer_full / consultant_dual` |
| `manual_override_active` | `classify_quote_role` / `QuoteFlowState.role` | 角色切换栏 | 提示当前是否人工锁定角色 |
| `entry_mode` | `QuoteFlowState` | 会话信息抽屉 | 解释当前走的是哪种公开入口模式；普通用户当前统一为 `customer_guided_discovery` |
| `customer_strategy` | `handle_message` / `QuoteFlowState` | 会话信息抽屉 / 调试信息 | 标记普通用户内部引导策略，如 `precise_need / renovation_browse / guided_discovery`，不建议直接做成多个前端入口 |
| `active_route` | `QuoteFlowState` | 流程状态条 | 显示当前走的是柜体、组合床、专项调价等哪条路径 |
| `missing_fields` | `handle_message` / `QuoteFlowState` | 待补参数卡片 | 决定当前是否进入“继续追问”状态 |
| `confirmed_fields` | `QuoteFlowState` | 已确认参数面板 | 展示当前已收集到的关键报价条件 |
| `last_quote_kind` | `QuoteFlowState` | 流程状态条 | 区分“正式报价 / 参考报价 / 尚未产出完整结果” |
| `last_formal_payload` | `QuoteFlowState` | 调试面板 / 内部详情抽屉 | 供切角色后重渲染，不建议直接对外展示 |
| `reply_text` | `handle_message` | 主回复区 | 当前这一轮默认应展示给用户的文本 |
| `internal_summary` | `handle_message` / `QuoteFlowState` | 内部口径区 | 顾问和设计师模式下的完整内部视图 |
| `customer_forward_text` | `handle_message` / `QuoteFlowState` | 客户转发区 | 顾问模式下的一键复制内容 |
| `handoff_summary` | `QuoteFlowState` | 跟单摘要区 | 下一个接手人快速理解当前单据状态 |
| `pricing_route` | `handle_message` | 流程状态条 | 展示这一轮实际命中的计价路径 |
| `question_code` | `handle_message` | 待补参数卡片 | 给前端做更稳定的追问文案映射 |
| `constraint_code` | `handle_message` | 限制提示条 | 给前端做不可报价/需调整的结构化提醒 |
| `detail_level_hint` | `handle_message` | 视图策略层 | 决定当前更适合简版、完整版还是双栏版 |

## 3. 角色视图建议

补一条前端原则：

- `customer / designer / consultant` 才是前端角色维度
- 普通用户不要再拆多个入口
- 普通用户不同问法由后端 `customer_strategy` 决定
- 前端最多把 `customer_strategy` 当作解释性状态，不要把它做成额外角色

### customer

前端默认显示：

- `reply_text`
- `missing_fields`
- `下一步` 操作按钮

前端默认隐藏：

- `internal_summary`
- `last_formal_payload`
- 规则命中和追加来源明细

### designer

前端默认显示：

- `reply_text`
- `internal_summary`
- `confirmed_fields`
- `pricing_route`

前端可选显示：

- `last_formal_payload`
- 专项规则命中详情

### consultant

前端建议双栏显示：

- 左侧：`internal_summary`
- 右侧：`customer_forward_text`

前端建议提供：

- 一键复制客户版
- 一键切到客户视图预览
- 一键生成报价卡

## 4. 页面模块建议

如果做一个报价工作台，建议最少拆成下面 6 块：

### A. 顶部角色栏

读取字段：

- `audience_role`
- `output_profile`
- `manual_override_active`

动作：

- 切到 `customer`
- 切到 `designer`
- 切到 `consultant`
- 恢复自动识别

### B. 流程状态条

读取字段：

- `active_route`
- `pricing_route`
- `last_quote_kind`
- `missing_fields`

状态建议：

- `待补参数`
- `可正式报价`
- `已生成正式报价`
- `专项调价中`

### C. 已确认参数区

读取字段：

- `confirmed_fields`

用途：

- 避免跨人接力时重复确认
- 让顾问知道哪些条件已经可以直接回客户

### D. 待补参数区

读取字段：

- `missing_fields`
- `question_code`
- `constraint_code`

用途：

- 决定当前只追哪个关键问题
- 当命中限制条件时，替代普通追问卡片

### E. 输出展示区

读取字段：

- `reply_text`
- `internal_summary`
- `customer_forward_text`

展示建议：

- `customer` 单栏
- `designer` 单栏完整版
- `consultant` 双栏

### F. 会话摘要区

读取字段：

- `handoff_summary`
- `entry_mode`
- `customer_strategy`

用途：

- 方便客服交接
- 方便理解当前普通用户为什么走“需求优先 / 空间优先 / 目标优先”这一种追问策略
- 方便后续回查为什么当前走这条路径

## 5. 常见交互规则

### 切角色

前端只改角色，不改报价条件。

调用建议：

- 切角色时传 `role_override=customer|designer|consultant`
- 恢复自动识别时传 `role_override=auto`

预期结果：

- 已确认参数保留
- 金额不变
- 输出版本切换

### 新开一单

如果用户明确表达：

- `重新来一单`
- `重新报价`
- `新报价`

前端应提示：

- 当前会清掉旧会话待补状态
- 旧正式报价 bundle 不再作为本单上下文

### 继续上一单

如果当前 `missing_fields` 非空：

- 默认认为还是上一单
- 不自动弹“新建报价”

除非后端已经返回了新的路由并清理旧状态。

## 6. 前端最低接入方案

如果第一版工作台想先做轻一点，最少只接下面这些字段就够了：

- `audience_role`
- `output_profile`
- `missing_fields`
- `confirmed_fields`
- `reply_text`
- `internal_summary`
- `customer_forward_text`
- `active_route`
- `last_quote_kind`

如果希望把普通用户引导做得更稳，再额外接一个：

- `customer_strategy`

但它只是增强字段，不是新的角色入口。

这样已经足够做出：

- 角色切换
- 待补参数提示
- 客户版 / 内部版切换
- 顾问双栏转发

## 7. 推荐的前端判断顺序

每次收到新的 `handle_message` 结果后，前端建议按这个顺序更新界面：

1. 先更新 `audience_role` 和 `output_profile`
2. 再更新 `active_route`、`missing_fields`、`confirmed_fields`
3. 再更新 `reply_text / internal_summary / customer_forward_text`
4. 如果 `last_quote_kind=formal` 且 `missing_fields=[]`，将当前单标记为“已有正式报价”
5. 如果 `consultant_dual` 且 `customer_forward_text` 非空，默认激活客户转发标签

## 8. 一期暂不建议前端自己推断的内容

前端不要自己推断下面这些事情，避免和后端编排层冲突：

- 自己判断是 `customer / designer / consultant`
- 把普通用户再拆成多个前端入口模式
- 自己判断是否该清理旧上下文
- 自己推断正式报价是否可出
- 自己拼装客户版话术
- 自己从 `last_formal_payload` 直接生成展示文案

这些都应该以后端返回结果为准。
