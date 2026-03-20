# 良禽佳木报价 Skill

这个 skill 分成两层：

- 运行层：给小龙虾日常报价用
- 维护层：给内部更新价格和规则用

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
   只负责把结果排成正式报价。

## 后续调价怎么维护

如果后面有人给你新的：

- 产品目录 `xlsx`
- 定制规则 `docx`

不需要手改 Python，也不需要分步跑一堆脚本。

只要：

1. 把两个文件放进 `sources/inbox/`
2. 运行下面这一个命令

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/update_release.py
```

这个命令会自动完成：

- 识别最新的 `xlsx` 和 `docx`
- 生成新的价格索引
- 提取新的规则候选
- 构建版本
- 校验版本
- 激活到 `data/current`
- 同步到 OpenClaw workspace

## 最傻瓜的刷新 + 测试

如果你只是想：

- 让小龙虾吃到你刚改过的版本
- 然后马上用一个干净的新会话测试

直接运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py
```

它会自动做两件事：

1. 如果 `sources/inbox/` 里有新的 `xlsx + docx`，先更新当前版本
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
  新版 `xlsx/docx` 投放区。
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
