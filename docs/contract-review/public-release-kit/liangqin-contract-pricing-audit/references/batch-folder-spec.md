# Batch Folder Spec

批次目录用于向 `liangqin-contract-pricing` 投递一组待审核合同文件。

## 最小目录结构

```text
batch-dir/
  raw/
    合同1.pdf
```

最小可运行条件：

- 存在 `raw/`
- `raw/` 下至少有一个主合同文件

## 推荐目录结构

```text
batch-dir/
  manifest.json
  raw/
    contract-demo-001-main.pdf
```

## 支持的文件类型

- `.pdf`
- `.docx`
- `.png`
- `.jpg`
- `.jpeg`

## manifest.json 示例

```json
{
  "source_type": "manual_batch",
  "source_channel": "manual",
  "requested_actions": ["audit", "replay"],
  "operator": "demo-user",
  "received_at": "2026-04-15T10:00:00+08:00",
  "notes": "正式合同报价审核批次",
  "source_batch_id": "batch-2026-04-15-001"
}
```

## 当前拆分规则

- `raw/` 下每个主合同文件生成一个 job
- 每个 job 独立输出审核结果
- 如果合同中存在附件报价清单，则在 job 内继续拆 line item
