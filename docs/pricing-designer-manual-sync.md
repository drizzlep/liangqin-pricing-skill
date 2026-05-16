# 线上设计师标准手册同步流程

这份流程用于把钉钉线上版《良禽佳木设计师标准手册》接入报价 skill。

## 当前状态

- 迁移线状态：`COMPLETED_MAINTENANCE`，新版设计师手册替换旧报价基准的迁移主线已完成，后续进入机器 guard 和回归维护。
- 当前本地生效层：`designer-manual-online-2026-05-13`
- 当前本地源文件：`skill/liangqin-pricing/sources/inbox/designer-manual-online-2026-05-13`
- 当前层状态：`ACTIVE`
- 线上钉钉文档：作为最终权威源
- 旧 PDF：只作为历史归档、审计和回滚证据，不再参与报价或咨询兜底

## 原则

- 线上版优先。线上版和旧 PDF 冲突时，默认以线上版为准。
- 不直接覆盖当前 `ACTIVE` 层。线上导出后先生成 `PAUSED` 候选层。
- 一旦线上版被确认替换旧版，旧版 manifest 应改为 `ARCHIVED` 或 `REPLACED`，不得继续作为运行时兜底。
- 运行时只读取 `ACTIVE` 层；新版没有覆盖的旧版内容，不再作为当前良禽标准回答。
- 不实时依赖钉钉页面。钉钉页面有登录权限、结构变化和静默更新风险，应先导出成 PDF 或 DOCX 再入库。
- 高风险差异先人工确认。涉及计价、尺寸阈值、禁止项、默认结构、下单备注的差异，确认后再激活。
- 重要手册不能只靠 PDF 文字层。PDF 文字层只是第一路提取结果；扫描页、图片页、短文本页和图文混排页需要进入 OCR / 视觉抽取复核。

## 重要手册的提取准入

这类设计师标准手册会直接影响报价和设计口径，准入时按三层处理：

- 原始证据层：保留钉钉导出的 PDF / Markdown / 原始快照，不把派生文本当最终真相。
- 交叉提取层：PDF 先读可复制文字层；需要复核的页再走 PaddleOCR，输出页级证据和提取方式。
- 人工确认层：HTML 审核台只给人看“采用 / 暂缓 / 找设计师确认”等业务选择，JSON、Markdown、OCR 明细只作为证据层。

当前仓库可用的 OCR 后端优先使用 PaddleOCR。`apps/contract-review/` 已经沉淀了 PaddleOCR 路由和缓存；`liangqin-pricing` 的手册提取也支持在需要时通过同一套本地 PaddleOCR 环境复核 PDF 页。

本机 PaddleOCR 环境位于：

```text
.venv-paddleocr310-arm64/
```

如果要让 PDF 页触发 PaddleOCR 复核，可以在构建时设置阈值，例如：

```bash
python3 skill/liangqin-pricing/scripts/build_online_addendum_layer.py \
  --snapshot-dir skill/liangqin-pricing/sources/inbox/designer-manual-online-2026-05-13 \
  --layer-id designer-manual-online-2026-05-13 \
  --layer-name "设计师追加规则 线上版 2026-05-13" \
  --status PAUSED \
  --ocr-min-chars 80 \
  --ocr-backend paddleocr
```

如果只是复现上一版候选层、不跑 OCR，可以继续使用：

```bash
--ocr-min-chars -1
```

注意：审核台里的“平均可信度”是提取链路分数，不是人工逐字准确率。真正的 OCR 准确率需要做抽样标注，例如抽 50 到 100 条规则，人工标记“文字正确 / 规则正确 / 需要回看原文”，再计算通过率。

生成候选层后，先跑文字质量抽样看板。它不会激活规则，也不会改候选层，只用来回答“这批手册文字提取得靠不靠谱”：

```bash
python3 skill/liangqin-pricing/scripts/build_addendum_quality_sample.py \
  --candidate-layer designer-manual-online-2026-05-13 \
  --sample-size 36 \
  --ocr-sample-size 6 \
  --render-sample-size 12 \
  --run-ocr
```

输出位置：

```text
skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-13/quality-sample-board.html
```

看板只给人看关键结论：

- `没读到文字页`：PDF 文字层为空，必须先回看原文或 OCR。
- `图片较多页`：有图示、表格或尺寸标注，文字层可能漏读。
- `PaddleOCR 成功 / OCR 空结果 / OCR 失败`：抽样复核结果，不等同于全量准确率。

如果质量抽样结论是“需要先复核”，不要激活候选层；先处理空结果页、失败页和关键图示页。

## 导出与落地

从钉钉线上手册导出 PDF 或 DOCX 后，先放到：

```bash
skill/liangqin-pricing/sources/inbox/
```

建议命名：

```text
designer-manual-online-YYYY-MM-DD.pdf
```

例如：

```text
designer-manual-online-2026-05-12.pdf
```

## 生成候选层

先用 `PAUSED` 状态生成候选层，避免被报价链路自动套用：

```bash
python3 skill/liangqin-pricing/scripts/update_addendum_layer.py \
  --rules-source "skill/liangqin-pricing/sources/inbox/designer-manual-online-2026-05-12.pdf" \
  --layer-id "designer-manual-online-2026-05-12" \
  --layer-name "设计师追加规则 线上版 2026-05-12" \
  --status PAUSED
```

这一步会生成：

- `skill/liangqin-pricing/references/addenda/designer-manual-online-2026-05-12/manifest.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-12/rules-index.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-12/runtime-rules.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-12/knowledge-layer.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-12/coverage-ledger.json`

## 对比旧层

生成候选层后，先对比旧版和线上候选版：

```bash
python3 skill/liangqin-pricing/scripts/compare_addendum_layers.py \
  --base-layer designer-manual-2026-03-22 \
  --candidate-layer designer-manual-online-2026-05-12
```

如果需要机器可读结果：

```bash
python3 skill/liangqin-pricing/scripts/compare_addendum_layers.py \
  --base-layer designer-manual-2026-03-22 \
  --candidate-layer designer-manual-online-2026-05-12 \
  --output json
```

人类评审时优先打开 HTML 看板，不要直接从 Markdown diff 开始：

```bash
python3 skill/liangqin-pricing/scripts/build_addendum_review_board.py \
  --base-layer designer-manual-2026-03-22 \
  --candidate-layer designer-manual-online-2026-05-12
```

看板会生成在候选层报告目录：

```text
skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-12/review-board.html
```

它是人工确认入口；`layer-diff-vs-*.md`、`rules-index.json`、`coverage-ledger.json` 只作为证据层和机器输入。

重点看：

- `Rules Index`：线上版新增或删除了哪些候选规则
- `Runtime Rules`：会直接影响报价追问和规则判断的硬规则差异
- `Knowledge Layer`：可回答但暂不程序化的知识口径差异
- `Coverage Ledger`：整本手册覆盖状态是否明显异常

## 接入报价系统分层

全量数据认证包会把手册数据点拆成几类，作为报价系统后续接入依据：

- `报价计算硬规则`：尺寸阈值、加价、折减、材质补差、报价公式等，可进入正式报价候选。
- `报价前追问/拦截规则`：缺开启方式、尺寸超限、需备注、需工厂确认等，可接入 `precheck / handle_quote_message`。
- `设计师咨询知识`：可回答设计师问题，但不直接算价。
- `人工复核`：已提取但口径未稳，先进入审核看板。
- `不开放`：背景说明或非问答内容，不进入 Agent 自动回答。

生成全量数据认证包：

```bash
python3 skill/liangqin-pricing/scripts/build_full_document_data_certification.py \
  --candidate-layer designer-manual-online-2026-05-13
```

输出位置：

```text
skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-13/full-document-data-certification.html
skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-13/full-document-data-certification.json
```

## 激活前检查

只有满足以下条件，才把线上候选层从 `PAUSED` 改成 `ACTIVE`：

- 新层源文件确实来自钉钉线上手册导出
- `Runtime Rules` 的新增和删除都已过人工确认
- `Coverage Ledger` 没有异常少页、异常少规则或大量未解析内容
- 关键问答 smoke test 已通过
- 旧层已明确退出运行链路，只保留为归档或替换前快照

如果线上版要完全替代旧 PDF，建议操作顺序是：

1. 把 `designer-manual-online-YYYY-MM-DD` 改为 `ACTIVE`
2. 把 `designer-manual-2026-03-22` 改为 `ARCHIVED` 或 `REPLACED`
3. 生成全量数据认证包，确认报价系统分层统计
4. 运行规则问答和报价 smoke test
5. 同步到 OpenClaw workspace

## 关键注意

- 不要让两个互相冲突的设计师手册层同时 `ACTIVE`。
- 如果只是想检查线上版，不要改 `manifest.json` 的状态，保持 `PAUSED` 即可。
- 如果钉钉线上文档无法匿名抓取，这是正常情况；以导出的 PDF/DOCX 作为可审计源文件。
