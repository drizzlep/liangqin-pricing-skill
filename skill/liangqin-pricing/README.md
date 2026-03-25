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

如果其他 OpenClaw 想直接使用这个版本，建议固定到 tag：

```bash
git clone --branch v2026.03.23.1 --depth 1 https://github.com/drizzlep/liangqin-pricing-skill.git
```

然后把 `skill/liangqin-pricing` 同步到 OpenClaw workspace 即可。

## 日常只需要看这几个文件

- `SKILL.md`
- `data/current/price-index.json`
- `references/current/rules.md`
- `references/current/examples.md`

## 日常报价怎么运行

运行链路固定为三步：

1. `scripts/precheck_quote.py`
   只判断缺什么参数、该先问什么。
2. `scripts/query_price_index.py`
   只查询当前版本里的基础价格。
3. `scripts/format_quote_reply.py`
   默认会在排版前尝试套用活跃 addendum layer，再统一输出成一段正式报价；如需跳过可用 `--disable-addenda`。

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

如果你发现小龙虾、钉钉还像在回答旧版本，通常不是规则没改成功，而是旧会话还在复用上下文。

先执行这一条：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/reset_quote_sessions.py --apply
```

它只会定向清理这几类旧报价会话：

- 本机默认主会话 `agent:main:main`
- 钉钉旧直聊/群聊会话
- `dingtalk-connector` 产生的用户会话

如果你想一条命令同时完成“刷新版本 + 清理旧会话 + fresh session 测试”，直接运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --reset-quote-sessions
```

## 批量真实题测试

如果你想把一批固定题目反复回归，而不是一次只测一题：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/run_openclaw_prompt_suite.py --publish-skill --reset-quote-sessions
```

默认题库在：

- `references/current/openclaw-prompt-suite.json`

输出结果会落到：

- `reports/validation/openclaw-prompt-suite-时间戳.json`

如果只想跑某几题：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/run_openclaw_prompt_suite.py --case-id opening-method-follow-up --case-id bed-mattress-weight-follow-up
```

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
- `scripts/refresh_and_test.py`
  一条命令完成“刷新 + fresh session 测试”。

## 内部工具

下面这些脚本还会保留，但默认当作内部工具，不要求日常维护者直接操作：

- `extract_price_index.py`
- `extract_rules_candidate.py`
- `build_release.py`
- `validate_release.py`
- `activate_release.py`
- `publish_skill.py`

如果没有特殊情况，优先只用 `update_release.py`。
