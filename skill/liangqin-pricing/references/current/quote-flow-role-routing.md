# 分角色报价流程说明

这份说明对应一期已经落地的“角色路由层 + 会话级流程状态 + 分角色输出层”。

目标只有一句话：

- 同条件同价格
- 不同角色不同问法
- 不同角色不同输出版本

底层计价公式、特殊规则、追加规则都不在这里改，这一层只负责：

- 识别当前发起方更像谁
- 决定下一步优先走哪条脚本
- 记录当前会话已经确认到哪一步
- 用同一份报价结果重渲染成不同角色的展示版本

## 角色模型

当前一期只支持三类角色：

- `customer`
  - 普通定制用户
  - 更关注“能不能做、多少钱、下一步怎么办”
- `designer`
  - 设计师
  - 更关注结构、工艺、规则命中、专项加价来源
- `consultant`
  - 咨询顾问 / 客服 / 门店转译角色
  - 需要同时拿到内部完整口径和客户可转发版本

角色识别脚本：

- `scripts/classify_quote_role.py`

输出字段：

- `audience_role`
- `confidence`
- `reason_codes`
- `entry_mode`
- `customer_strategy`
- `manual_override_active`

其中普通用户当前的对外入口口径已经收敛成一个固定值：

- `entry_mode=customer_guided_discovery`

也就是说：

- 前端只需要提供一个“普通用户”入口
- 不需要再拆多个普通用户入口按钮

普通用户内部仍会继续细分策略，但这个细分只用于后端追问和话术控制，不作为前端入口暴露：

- `precise_need`
  - 用户虽然说法不专业，但已经表达出相对明确的需求方向，例如“想做个柜子/书柜/衣柜”
- `renovation_browse`
  - 用户还在装修或逛方案阶段，更像先看空间和预算范围
- `guided_discovery`
  - 用户只知道“想做点东西”或“想看看”，目标还比较模糊
- `default`
  - 默认兜底策略

## 输出 profile

角色和输出 profile 是一一对应的：

- `customer -> customer_simple`
- `designer -> designer_full`
- `consultant -> consultant_dual`

输出层脚本：

- `scripts/format_quote_reply.py`

三个 profile 的约束如下：

### customer_simple

- 优先给结论
- 只保留客户能理解的关键前提
- 不主动暴露内部工艺术语、追加规则命中细节
- 默认作为报价卡图片的文本来源

### designer_full

- 保留完整计算过程
- 保留规则命中、专项加价来源、结构化确认条件
- 适合复核、确认、下单前校验

### consultant_dual

- 同时生成两份文本
- `internal_summary` 给内部看
- `customer_forward_text` 给客户转发
- `reply_text` 默认回客户版，但内部版会落状态

## 会话状态模型

会话状态脚本：

- `scripts/quote_flow_state.py`

当前会话状态核心字段：

- `audience_role`
- `manual_override`
- `entry_mode`
- `customer_strategy`
- `confirmed_fields`
- `missing_fields`
- `active_route`
- `last_quote_kind`
- `last_formal_payload`
- `internal_summary`
- `customer_forward_text`
- `handoff_summary`

前端如果后面要做工作台，这一份状态就可以直接当作会话层的基础状态模型。

如果要继续往前接页面字段，可以再看：

- `references/current/quote-flow-frontend-mapping.md`

## 主编排入口

统一入口脚本：

- `scripts/handle_quote_message.py`

当前编排顺序大致是：

1. 读取当前会话已有 state 和 bundle
2. 走 `route_quote_request.py`
3. 确定当前角色、输出 profile，以及普通用户内部策略
4. 判断这轮是：
   - 图片请求
   - 规则咨询
   - 预检追问
   - 正式报价
   - 专项调价
   - 旧正式报价重渲染
5. 执行对应下游脚本
6. 回写最新 flow state 和 result bundle

## 角色切换规则

一期当前的设计原则是：

- 角色可以切
- 已确认参数不丢
- 只重算输出版本，不重算价格

具体行为：

- 如果当前还在预检补参阶段，本轮切角色后，仍然复用旧的 `confirmed_fields + missing_fields`
- 如果当前已经有上一条正式报价，本轮切角色时可以直接复用 `last_formal_payload`
- 这种场景下不会重新追问旧条件，也不会重新跑一遍人工补参

已落地的典型能力：

- 普通用户补参到一半，切成顾问模式后继续输出 `consultant_dual`
- 设计师正式报价完成后，切成顾问模式时直接重渲染出客户版

## manual override 规则

人工切角色时：

- `role_override=customer|designer|consultant`
- 当前会话会写入 `manual_override`
- 后续多轮默认沿用

人工取消覆盖时：

- `role_override=auto`
- 只清除人工覆盖
- 然后回到自动识别

这里有一个重要优先级：

- `auto` 清除覆盖的语义高于“低置信度继续沿用旧角色”
- 也就是显式恢复自动识别时，不会再被旧角色兜回去

## 新报价主题清理规则

一期现在支持两种“脱离旧会话”的触发方式。

### 1. 显式新单信号

命中这类强信号时，会直接清理旧上下文：

- `重新来一单`
- `重新报价`
- `新报价`
- `再来一单`

这类场景会清掉：

- 旧 `missing_fields`
- 旧 `confirmed_fields`
- 旧 `manual_override`
- 旧 result bundle

然后按新消息重新路由。

### 2. 宽泛新单，但路由族明显冲突

如果消息里没有显式说“重新来一单”，但满足下面两个条件，也会自动脱离旧会话：

- 当前消息自己就能独立推断出一套新报价骨架
- 这套骨架对应的路由族，和旧会话 `active_route` 明显冲突

例如：

- 旧会话还停在 `modular_child_bed_combo` 的待补参
- 当前消息已经是完整的衣柜正式报价请求

这时系统会直接丢掉旧组合床待补状态，按新的柜体路径重开。

### 当前不会自动清理的场景

为了避免误判，同一路由族内的自然续聊不会被自动清理，例如：

- 同一个衣柜改进深
- 同一个柜体改带门/不带门
- 同一个正式报价只切客户版 / 内部版
- 同一个组合床继续补后排柜体参数

## 路由族概念

当前实现里，会把具体 `pricing_route` 收敛成更稳定的“路由族”来判断是否冲突。

已使用的主要路由族：

- `cabinet`
- `modular_child_bed`
- `modular_child_bed_combo`
- `bed`
- `table`
- `special_adjustment`

这个抽象的作用是：

- 防止把同一路径里的局部调整误判成新单
- 也方便前端工作台做更稳定的流程分组

## 对前端工作台的建议映射

如果后面接前端，这里建议直接按下面这套映射：

- 当前角色：`audience_role`
- 当前展示版本：`output_profile`
- 是否人工锁定角色：`manual_override_active`
- 普通用户内部引导策略：`customer_strategy`
  - 仅用于前端理解当前为什么这样追问，不建议渲染成多个用户入口
- 当前报价阶段：
  - `missing_fields` 为空且已有 `last_formal_payload`，可视为“已有正式结果”
  - `missing_fields` 非空，视为“待补关键参数”
- 当前流程路径：`active_route`
- 内部展示区：`internal_summary`
- 客户转发区：`customer_forward_text`
- 一键继续跟单时的摘要：`handoff_summary`

如果要看更细的页面模块拆分和字段到组件的对照，继续看：

- `references/current/quote-flow-frontend-mapping.md`

## 当前一期边界

这份机制目前只负责“分角色对话编排”，不负责：

- 改底层计价公式
- 改价格索引结构
- 改专项规则算法
- 引入新的模型依赖

所以它更像一层稳定的 orchestration / presentation layer，而不是新的报价引擎。
