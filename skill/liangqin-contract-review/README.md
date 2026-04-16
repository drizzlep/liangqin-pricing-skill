# 良禽合同审核 Skill

这一层是 `apps/contract-review` 的聊天壳。

推荐入口：

```bash
python3 skill/liangqin-contract-review/scripts/handle_review_message.py \
  --text "审这份合同" \
  --batch-dir "/absolute/path/to/batch" \
  --runtime-root "apps/contract-review/runtime"
```

继续处理上一批：

```bash
python3 skill/liangqin-contract-review/scripts/handle_review_message.py --text "看下一份高风险合同"
```
