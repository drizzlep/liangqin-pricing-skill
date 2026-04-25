# 良禽合同审核 Skill

这一层是 `apps/contract-review` 的聊天壳。

推荐入口：

```bash
python3 skill/liangqin-contract-review/scripts/handle_review_message.py \
  --text "审这份合同" \
  --batch-dir "/absolute/path/to/batch" \
  --runtime-root "apps/contract-review/runtime"
```

如果当前不是现成 batch，而是单个合同文件：

```bash
python3 skill/liangqin-contract-review/scripts/handle_review_message.py \
  --text "审这份合同" \
  --input-path "/absolute/path/to/合同.pdf" \
  --runtime-root "apps/contract-review/runtime"
```

如果是一整个新合同目录：

```bash
python3 skill/liangqin-contract-review/scripts/handle_review_message.py \
  --text "检查这批合同" \
  --input-path "/absolute/path/to/contracts-folder" \
  --runtime-root "apps/contract-review/runtime"
```

当前 `--input-path` 规则：

- 单个 `pdf/docx/图片`：默认一文件一合同
- 目录：递归收集目录里的 `pdf/docx/图片`，默认一文件一合同
- 自动生成临时 batch，再转交 `apps/contract-review/cli/review_chat.py`

如果走的是钉钉 OpenClaw，建议把当前消息上下文一起传进来：

```bash
python3 skill/liangqin-contract-review/scripts/handle_review_message.py \
  --text "审这份合同" \
  --input-path "/absolute/path/to/合同.docx" \
  --context-json '{...}' \
  --channel dingtalk-connector \
  --runtime-root "apps/contract-review/runtime"
```

这样 `看下一份高风险合同`、`展开证据` 等状态会按当前钉钉会话隔离保存。

继续处理上一批：

```bash
python3 skill/liangqin-contract-review/scripts/handle_review_message.py --text "看下一份高风险合同"
```
