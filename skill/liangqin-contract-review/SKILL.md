---
name: liangqin-contract-review
description: "合同审核、合同对账、报价冲突核对、批量审单、审单卡 => liangqin-contract-review。命中这类任务时，优先调用本地合同审核聊天入口，不要自由发挥。"
---

# 良禽合同审核助手

## 使用原则

- 这层是聊天壳，不负责自己发明审核逻辑。
- 真正的审核、对账、差异解释、模板学习，都走：

```bash
python3 ~/.openclaw/workspace/skills/liangqin-contract-review/scripts/handle_review_message.py --text "用户原话"
```

- 如果当前是本地文件批次入口，优先补 `--batch-dir`：

```bash
python3 ~/.openclaw/workspace/skills/liangqin-contract-review/scripts/handle_review_message.py \
  --text "审这份合同" \
  --batch-dir "/absolute/path/to/batch"
```

## 当前支持的交互

- 新审一批合同
  - `审这份合同`
  - `开始审核这个批次`
- 继续处理高风险队列
  - `看下一份高风险合同`
- 只看金额问题
  - `只看金额冲突`
- 展开证据
  - `展开证据`
- 标记人工已处理
  - `标记已核对`
  - `标记已核对 结论=确认问题 原因=template_alias_missing 字段=product_category:书柜,width:1500mm`
- 执行模板快捷动作
  - `执行模板快捷动作 tpl-001:feedback`

## 输出约束

- 默认输出“审单卡”：
  - 是否建议放行
  - 合同金额
  - 报价金额
  - 差额
  - 怀疑原因 Top 3
  - 请人工核对的 1-3 项
- 如果正式回放被缺字段阻塞：
  - 只追问一个关键字段
  - 不展开成长问卷
- 如果用户要求展开证据：
  - 只展示与当前 top issue 最相关的证据片段

## 本地脚本

- 入口脚本：
  - `scripts/handle_review_message.py`
- 真实实现：
  - `apps/contract-review/cli/review_chat.py`
