# OCR / Markdown 策略

## 结论

复杂合同、混合排版、图纸说明场景下：

- **强 OCR / 文档视觉提取是必要能力**
- 但 **不能把 OCR 当全部系统**
- 也 **不能把 Markdown 当最终真相层**

当前仓库 V1 已先选定：

- **OCR 后端：PaddleOCR**
- **接入方式：`apps/contract-review/core/extraction_router.py` 可插拔路由**
- **默认策略：有文字层先走原生提取，图片 / 扫描件再走 PaddleOCR**

## 推荐分层

### 1. Source Layer

保留原始文件：

- `docx`
- `pdf`
- `png/jpg`

### 2. Extraction Layer

按文档类型路由：

- `docx_native_extractor`
- `pdf_text_extractor`
- `ocr_layout_extractor`
- `vision_drawing_extractor`

### 3. Evidence Layer

输出可回链证据：

- `page_no`
- `block_id`
- `bbox`
- `raw_text`
- `confidence`

### 4. Projection Layer

把提取结果投影成更适合模型消费的表示：

- `plain_text`
- `markdown`
- `table_rows`
- `normalized_fields`

### 5. Audit Layer

真正的审核、回放、规则匹配，只读：

- `normalized_fields`
- `evidence refs`

而不是直接读 Markdown 原文。

## 为什么不能只靠 Markdown

Markdown 解决的是：

- 让模型更容易读
- 把复杂文档变成线性文本

但它解决不了：

- 这句话来自哪一页
- 这是正文、备注还是图纸标注
- 这个尺寸来自 OCR 猜测还是文字层
- 表格结构是否丢失
- 同一页多个图片区块之间的关联

所以：

- Markdown 很有价值
- 但只能是派生层

## 对当前仓库的落地要求

当前 `apps/contract-review/` 应持续遵循：

- 发现图片/扫描件 -> 明确打 `ocr_or_vision_required`
- PaddleOCR 已成功落盘 -> 可进入 `ocr_evidence_ready`
- 存在图纸附件 -> 明确打风险提示
- 没有 OCR/视觉证据前，不进入可靠报价回放
- 即使后续接入 `markitdown` 一类工具，也只作为 projection 层，不替代 evidence 层
