# 批次目录协议

## 推荐结构

```text
batch-2026-04-14-a/
  manifest.json
  raw/
    case-001/
      合同.docx
      图纸.pdf
    case-002/
      合同.pdf
      截图1.png
```

这是当前最推荐的模式：

- `raw/` 下每个一级子目录 = 一个 `job`
- 一个 job 里可以放合同、图纸、截图、补充说明

## 兼容的简化结构

如果 `raw/` 下直接是文件，没有子目录：

```text
batch-2026-04-14-b/
  raw/
    合同A.docx
    合同B.pdf
```

当前会按“每个直接文件一个 job”处理。

## `manifest.json`

最小可用示例：

```json
{
  "source_type": "manual_batch",
  "source_channel": "manual",
  "source_batch_id": "batch-2026-04-14-a",
  "requested_actions": ["audit", "replay"]
}
```

推荐完整示例见：

```text
apps/contract-review/templates/manifest.example.json
```

## 显式 jobs 映射

如果你不想依赖目录拆分，也可以在 `manifest.json` 里显式指定：

```json
{
  "source_type": "manual_batch",
  "source_channel": "manual",
  "source_batch_id": "batch-2026-04-14-a",
  "requested_actions": ["audit", "replay"],
  "jobs": [
    {
      "job_key": "case-001",
      "paths": [
        "raw/mixed/合同A.docx",
        "raw/mixed/合同A-图纸.pdf"
      ]
    }
  ]
}
```

当前逻辑：

- 如果 `manifest.json.jobs` 存在，就优先按显式 jobs 拆
- 否则回退到自动拆单

## 命名建议

为了给后续钉钉/飞书版留空间，建议现在就保持：

- `batch`：一次投递
- `job`：一单合同任务

也就是说：

- 你现在手工丢一批文件夹，是在创建一个 `batch`
- 系统内部会自动拆成多个 `job`

后面钉钉附件版，也只是把附件消息落成同样的 `batch/job`

## 当前批次输出重点

每次真实运行后，当前建议先看：

- `batches/<batch-id>/batch-dashboard.md`
  - 批次首页，先看总量和优先级结构
- `batches/<batch-id>/batch-dashboard.json`
  - 适合给本地 Agent 直接读取
- `batches/<batch-id>/manual-review-queue.md`
  - 人工快速浏览的复核队列
- `batches/<batch-id>/manual-review-queue.json`
  - 给后续 Agent / 脚本消费的排序结果
- `batches/<batch-id>/batch-summary.json`
  - 更完整的批次汇总

当前队列默认按下面顺序排序：

- `p0`
  - 关键字段冲突，必须优先人工复核
- `p1`
  - 高风险冲突，建议尽快人工确认
- `p2`
  - 中低风险冲突，可排在后面处理
- `normal`
  - 当前没有检测到明确冲突，但仍保留在批次结果里
