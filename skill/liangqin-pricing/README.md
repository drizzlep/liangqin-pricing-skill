# 良禽佳木报价 Skill

这个 skill 分成两层：

- 运行层：给小龙虾日常报价用
- 维护层：给内部更新价格和规则用

## GitHub 公开版说明

为了让其他 OpenClaw 安装时仓库更轻，GitHub 公开版默认：

- 保留可直接运行的 `rules-index.json`、`runtime-rules.json`、规则草稿和审阅稿
- 不提交 `sources/archived/addenda/` 里的原始大 PDF

也就是说：

- 公开仓库可以直接用于安装和运行报价
- 如果你只是使用这套 skill，不需要原始 PDF
- 如果你要重新从 PDF 生成 addendum，请把你自己的原始文件放进 `sources/inbox/`，再运行更新脚本

## OpenClaw 安装

如果其他 OpenClaw 想直接使用这个版本，优先使用 GitHub Releases 里的 zip 或 installer 附件。

如果你确实要从仓库源码安装，再按 release 对应 tag 拉取：

```bash
git clone --branch <release-tag> --depth 1 https://github.com/drizzlep/liangqin-pricing-skill.git
```

然后把 `skill/liangqin-pricing` 同步到 OpenClaw workspace 即可。

## 日常只需要看这几个文件

- `SKILL.md`
- `data/current/price-index.json`
- `data/current/modular-child-bed-price.json`
- `references/current/rules.md`
- `references/current/examples.md`
- `references/current/quote-flow-role-routing.md`
- `references/current/quote-flow-frontend-mapping.md`
- `references/current/inquiry-intake-protocol.md`

如果后面要接前端工作台，或者想快速看“角色路由层 / 会话状态 / 新报价清理规则”，优先看：

- `references/current/quote-flow-role-routing.md`
- `references/current/inquiry-intake-protocol.md`

## 日常报价怎么运行

运行链路先分三种：

- 目录标准价路径：`precheck -> query_price_index -> format_quote_reply`
- 模块化儿童床路径：`precheck -> calculate_modular_child_bed_quote -> format_quote_reply`
- 模块化儿童床 + 床下柜路径：`precheck -> calculate_modular_child_bed_combo_quote -> format_quote_reply`

目录标准价链路：

1. `scripts/precheck_quote.py`
   先判断缺什么参数、该先问什么，以及当前该走哪条报价路径。
2. `scripts/query_price_index.py`
   只查询当前版本里的目录基础价格。
3. `scripts/format_quote_reply.py`
   默认会在排版前尝试套用活跃 addendum layer，再统一输出成一段正式报价；如需跳过可用 `--disable-addenda`。
   如果同时传入当前消息的 `Conversation info JSON + channel`，还会额外缓存会话级 bundle，并在尾部补一句“如需生成图片，回复生成图片即可”。

模块化儿童床链路：

1. `scripts/precheck_quote.py`
   如果返回 `pricing_route=modular_child_bed`，说明应走模块化儿童床路径。
2. `scripts/calculate_modular_child_bed_quote.py`
   按 `床形态 + 上层出入方式 + 床架/围栏/梯子模块` 做组合计价。
3. `scripts/format_quote_reply.py`
   统一输出正式报价。

模块化儿童床 + 床下柜链路：

1. `scripts/precheck_quote.py`
   如果返回 `pricing_route=modular_child_bed_combo`，说明应走半高床/高架床床下组合柜路径。
2. `scripts/calculate_modular_child_bed_combo_quote.py`
   先算床体模块价，再叠加床下前后柜体投影面积价。
3. `scripts/format_quote_reply.py`
   统一输出正式报价。

## 分角色统一入口

如果你现在希望先走“一层统一入口”，再决定后面该进哪条报价链路，可以先运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/route_quote_request.py --text "用户当前这句话" --context-json '{...}' --channel feishu
```

这个入口会先做四件事：

- 识别当前更像 `普通用户 / 设计师 / 咨询顾问`
- 普通用户对外统一落到一个公开入口：`entry_mode=customer_guided_discovery`
- 再在后端内部用 `customer_strategy` 区分是“需求较明确 / 装修逛看 / 模糊探索”
- 给出建议输出 profile：`customer_simple / designer_full / consultant_dual`
- 判断下一步优先该走哪个脚本，例如：
  - `generate_quote_card_reply`
  - `query_bed_weight_guidance`
  - `query_addendum_guidance`
  - `detect_special_cabinet_rule`
  - `precheck_quote`
- 如果当前明显是“新开一单”，还会提示是否该清掉上一条报价残留上下文

如果你只是想单独看角色识别结果，也可以直接运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/classify_quote_role.py --text "用户当前这句话" --context-json '{...}' --channel feishu
```

你会看到：

- `audience_role`
- `entry_mode`
- `customer_strategy`

这里要特别注意：

- `entry_mode` 是对外公开流程入口
- `customer_strategy` 是普通用户内部引导策略
- 前端一般只需要展示前者，后者用于解释当前为什么这样追问

## 另一个机器人排障自检

如果你在另一个机器人环境里看到“当前版本没有价格数据”这类提示，先不要直接相信它。

先跑这个命令：

```bash
python3 ~/.openclaw/workspace/skills/liangqin-pricing/scripts/check_runtime_health.py
```

这个自检会直接告诉你：

- 当前加载的是哪份 skill 目录
- `release.json` 是否存在
- `price-index.json` 是否存在
- 当前版本实际有多少条记录、多少条可查询记录
- 是安装不完整，还是数据正常但机器人把“没查到匹配记录”误判成了“整份价格索引为空”

如果你想让另一个机器人读取结构化结果，也可以改成：

```bash
python3 ~/.openclaw/workspace/skills/liangqin-pricing/scripts/check_runtime_health.py --output-mode json
```

如果你希望直接用一个脚本把“角色识别 + 路由 + 下游执行 + 角色化输出”串起来，可以运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/handle_quote_message.py --text "用户当前这句话" --context-json '{...}' --channel feishu
```

这个统一编排入口目前优先覆盖四类安全路径：

- 图片请求：命中“生成图片”时，直接复用当前会话最近一次完整报价 bundle 生成报价卡
- 规则咨询：命中床垫重量、设计师追加规则、特殊柜体规则时，直接返回结构化结果和分角色文案
- 预检追问：当你同时传入 `--precheck-args-json '{...}'` 时，会直接执行 `precheck_quote` 并返回统一结构
- 正式输出：当你同时传入 `--quote-payload-json '{...}'` 时，会直接走 `format_quote_reply`，并自动写入会话级 bundle/state
- 专项报价：当你同时传入 `--special-quote-json '{...}'` 时，会直接执行专项价/专项折减，再统一走正式输出

如果你已经有结构化预检参数，并且希望在“预检通过后继续直接出正式报价”，可以再加：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/handle_quote_message.py \
  --text "用户当前这句话" \
  --context-json '{...}' \
  --channel feishu \
  --precheck-args-json '{...}' \
  --execute-quote-when-ready
```

当前这一步已经接通两类正式报价执行：

- 默认投影面积柜体路径：例如常规衣柜、书柜、玄关柜等默认 profile 柜体
- 模块化儿童床路径：`modular_child_bed / modular_child_bed_combo`

继续往下已经补通的路径：

- 成人床标准价路径：`bed_standard`，会继续走成人床标准规则计算
- 目录标准品单位价路径：会命中唯一标准目录记录后直接出正式报价，例如部分书桌、餐桌、标准目录款

专项价入口当前已经补通：

- 岩板专项价：`rock_slab_countertop / rock_slab_backboard / rock_slab_aluminum_frame_door`
- 双面门专项价：`double_sided_door`
- 操作空区专项价：`operation_gap`
- 非见光玫瑰木折减：`hidden_rosewood_discount`

例如：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/handle_quote_message.py \
  --text "这个岩板台面专项价直接算进去" \
  --context-json '{...}' \
  --channel feishu \
  --quote-payload-json '{...}' \
  --special-quote-json '{"special_rule":"rock_slab_countertop","slab_length":"1.8"}'
```

现在还支持一层更轻的“会话接力”：

- 如果当前会话里已经有上一轮正式报价 bundle / flow state
- 这轮消息只是补一句专项条件，例如“这组柜子加岩板台面，岩板长度1.8，直接给新版报价”

那么 `handle_quote_message.py` 会优先尝试：

- 复用上一轮正式报价 payload
- 从当前新消息里抽取专项参数
- 直接生成新版正式报价

当前会话接力已覆盖：

- 岩板台面专项价
- 双面门专项价
- 操作空区专项价
- 非见光玫瑰木折减

当前这层仍然不改底层计价职责：

- 没有 `quote_payload_json` 时，不会假装已经算完价
- 没有 `precheck_args_json` 时，也不会伪造预检参数
- 真正的价格计算仍然继续由 `query_price_index / calculate_modular_child_bed_quote / calculate_modular_child_bed_combo_quote` 负责

如果后面要专门微调“普通用户首轮引导话术”，优先看：

- `scripts/customer_guidance_templates.py`

这里集中维护：

- 普通用户首轮追问问题模板
- 普通用户第二轮续问口径
- `precise_need / renovation_browse / guided_discovery / default` 四类首轮回复文案
- 首轮回复里的预算区间 / 接近参考报价提示

模块化儿童床运行时数据来自：

- `data/current/modular-child-bed-price.json`

这份数据目前由下面的脚本从 `模块儿童上下床报价.xls` 抽取生成：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/extract_modular_child_bed_data.py --input "/path/to/模块儿童上下床报价.xls" --output "~/.openclaw/skills/liangqin-pricing/data/current/modular-child-bed-price.json" --pretty
```

## 后续调价怎么维护

如果后面有人给你新的：

- 产品目录 `xlsx`
- 定制规则 `docx / pdf`

不需要手改 Python，也不需要分步跑一堆脚本。

只要：

1. 把两个文件放进 `sources/inbox/`
2. 运行下面这一个命令

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/update_release.py
```

这个命令会自动完成：

- 识别最新的 `xlsx` 和规则文件（优先 `docx`，没有时回退 `pdf`）
- 生成新的价格索引
- 提取新的规则候选
- 生成一份规则审阅稿 `Markdown`
- 生成一份高信号规则索引 `JSON + Markdown`
- 生成一组分域规则草稿 `Markdown`
- 构建版本
- 校验版本
- 激活到 `data/current`
- 同步到 OpenClaw workspace

## 设计师追加规则怎么维护

如果后面你拿到的是单独的设计师补充规则文件，不希望污染主规则：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/update_addendum_layer.py --rules-source "/path/to/设计师补充规则.pdf" --layer-id "designer-manual-a" --layer-name "设计师追加规则 A"
```

这条链路会：

- 保持 `references/current/*` 主规则不变
- 单独生成一个 addendum layer
- 单独生成候选、索引、分域草稿
- 额外生成一份 `knowledge-layer.json` 作为“可回答但暂不程序化”的知识层
- 额外生成一份 `coverage-ledger.json` 作为整本 PDF 的统一覆盖台账
- 供后续报价在主规则之后做二次判断

## 最傻瓜的刷新 + 测试

如果你只是想：

- 让小龙虾吃到你刚改过的版本
- 然后马上用一个干净的新会话测试

直接运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py
```

它会自动做两件事：

1. 如果 `sources/inbox/` 里有新的 `xlsx + 规则文件`，先更新当前版本
2. 用 fresh session 跑一轮测试，避免掉回旧会话逻辑

如果你想换成自己的测试问题：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --message "你的测试问题"
```

如果你想专门验证“是否会把五金行业知识混进良禽口径”，直接运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --preset hardware-boundary
```

如果你发现小龙虾、钉钉还像在回答旧版本，通常不是规则没改成功，而是旧会话还在复用上下文。

先执行这一条：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/reset_quote_sessions.py --apply
```

它只会定向清理这几类旧报价会话：

- 本机默认主会话 `agent:main:main`
- 钉钉旧直聊/群聊会话
- `dingtalk-connector` 产生的用户会话

如果你还在飞书里用了这套 skill，建议改用这一条，把飞书旧报价会话也一起清掉：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/reset_quote_sessions.py --apply --include-feishu
```

这里的 `--include-feishu` 不区分私聊/群聊，会一并清理命中的飞书报价会话；钉钉这边默认已经覆盖私聊和群聊。

如果你想一条命令同时完成“刷新版本 + 清理旧会话 + fresh session 测试”，直接运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --reset-quote-sessions
```

如果你要确保钉钉、飞书、私聊、群聊都尽快切到新版本，建议直接运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --reset-quote-sessions --include-feishu
```

## 批量真实题测试

如果你想把一批固定题目反复回归，而不是一次只测一题：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/run_openclaw_prompt_suite.py --publish-skill --reset-quote-sessions
```

如果你想在回归前把飞书旧报价会话也一起清掉：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/run_openclaw_prompt_suite.py --publish-skill --reset-quote-sessions --include-feishu
```

默认题库在：

- `references/current/openclaw-prompt-suite.json`

输出结果会落到：

- `reports/validation/openclaw-prompt-suite-时间戳.json`

如果只想跑某几题：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/run_openclaw_prompt_suite.py --case-id opening-method-follow-up --case-id bed-mattress-weight-follow-up
```

如果你想把整套题目默认重复多跑几次，检查 OpenClaw 是否存在随机漂移：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/run_openclaw_prompt_suite.py --repeat-each 3
```

如果只是想盯住“外部五金知识会不会混进良禽口径”这一题，直接运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/run_openclaw_prompt_suite.py --publish-skill --reset-quote-sessions --case-id hardware-brand-boundary-no-pollution --max-retries 0
```

这题在题库里已经默认 `repeat_count=3`，只要 3 次里有 1 次出现 `BLUMOTION / CLIP top / TANDEMBOX / SERVO-DRIVE / 阻尼铰链 / 抽屉导轨`，就算没通过。

## 报价图联动 v1

现在这套 skill 支持：

- 先正常输出完整文字报价
- 再提示用户“回复生成图片”
- 用户明确回复后，读取当前会话最新 bundle，渲染 1 张 `1080 x 1920` JPG 并发回当前会话

日常用法：

1. 生成文字报价时，优先带上当前消息里的 `Conversation info` JSON 和当前渠道：

```bash
python3 ~/.openclaw/workspace/skills/liangqin-pricing/scripts/format_quote_reply.py --input-json '...' --context-json '{...}' --channel feishu
python3 ~/.openclaw/workspace/skills/liangqin-pricing/scripts/format_quote_reply.py --input-json '...' --context-json '{...}' --channel dingtalk-connector
```

2. 用户下一轮明确说“生成图片 / 发图 / 发报价卡”时：

```bash
python3 ~/.openclaw/workspace/skills/liangqin-pricing/scripts/generate_quote_card_reply.py --context-json '{...}' --channel feishu
python3 ~/.openclaw/workspace/skills/liangqin-pricing/scripts/generate_quote_card_reply.py --context-json '{...}' --channel dingtalk-connector
```

3. 如果用户已经开始新报价问题，先清掉旧 bundle：

```bash
python3 ~/.openclaw/workspace/skills/liangqin-pricing/scripts/clear_quote_result_bundle.py --context-json '{...}' --channel feishu
python3 ~/.openclaw/workspace/skills/liangqin-pricing/scripts/clear_quote_result_bundle.py --context-json '{...}' --channel dingtalk-connector
```

产物会落到：

- `~/.openclaw/media/quote-cards/<conversation-id>/<timestamp>/quote-card.html`
- `~/.openclaw/media/quote-cards/<conversation-id>/<timestamp>/quote-card.json`
- `~/.openclaw/media/quote-cards/<conversation-id>/<timestamp>/quote-result-bundle.json`
- `~/.openclaw/media/quote-cards/<conversation-id>/<timestamp>/quote-card.jpg`

## 目录说明

- `SKILL.md`
  对话规则和报价主流程。
- `references/current/rules.md`
  当前业务规则汇总。
- `references/current/examples.md`
  常见测试问法和预期行为。
- `data/current/`
  当前正在生效的数据。
- `data/versions/`
  历史版本。
- `sources/inbox/`
  新版 `xlsx + docx/pdf` 投放区。
- `sources/archived/`
  已归档的原始文件。
- `scripts/update_release.py`
  统一维护入口。
- `scripts/extract_modular_child_bed_data.py`
  模块化儿童床 `xls` 抽取入口。
- `scripts/calculate_modular_child_bed_quote.py`
  模块化儿童床组合计价入口。
- `scripts/calculate_modular_child_bed_combo_quote.py`
  模块化儿童床 + 床下柜组合计价入口。
- `scripts/refresh_and_test.py`
  一条命令完成“刷新 + fresh session 测试”。
- `scripts/generate_quote_card_reply.py`
  读取当前会话 bundle，输出图片回复。

## 内部工具

下面这些脚本还会保留，但默认当作内部工具，不要求日常维护者直接操作：

- `extract_price_index.py`
- `extract_rules_candidate.py`
- `build_release.py`
- `validate_release.py`
- `activate_release.py`
- `publish_skill.py`

如果没有特殊情况，优先只用 `update_release.py`。
