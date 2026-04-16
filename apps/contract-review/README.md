# contract-review

良禽合同审核应用骨架。

当前阶段定位：

- 面向本地 AI Agent 调用
- 支持手工批次文件夹投递
- 将一批输入拆成多个单据任务
- 为每个任务生成标准化输入、审阅骨架和回放占位结果

当前阶段不做：

- 不直接混入 `skill/liangqin-pricing/`
- 不直接做 OpenClaw 可分发 skill
- 不直接接钉钉 / 飞书 / 微信

## 关于 OCR / Markdown

这条线默认按“混合文档”来设计，而不是假设合同都是纯文字：

- `docx`：优先原生解析
- `pdf` 且有文字层：优先直接抽文本
- `扫描 pdf / 图片 / 图纸截图`：必须进入 OCR 或文档视觉提取

这里有两个重要原则：

- OCR 是必要分支，但不是唯一主干
- Markdown 只是给模型读的派生层，不是最终证据层

也就是说，后续系统必须同时保留：

- 原始文件
- 块级或页级证据引用
- OCR / 提取置信度
- 派生后的 Markdown / 文本

## 目录

- `cli/`
  - 命令行入口
- `core/`
  - 任务模型、运行时目录、审阅流水线、报价桥接
- `adapters/`
  - 输入适配层，当前只实现 `manual_batch`
- `templates/`
  - 批次和任务示例
- `tests/`
  - 独立 unittest

## 快速运行

```bash
python3 apps/contract-review/cli/manual_batch.py --batch-dir /absolute/path/to/batch
```

如果想直接按“聊天式审单卡”使用，可以跑：

```bash
python3 apps/contract-review/cli/review_chat.py \
  --text "审这份合同" \
  --batch-dir /absolute/path/to/batch \
  --ocr-backend disabled
```

继续处理当前高风险队列：

```bash
python3 apps/contract-review/cli/review_chat.py --text "看下一份高风险合同"
```

人工核对后，如果想把根因和修正字段直接写回模板学习层，可以补成：

```bash
python3 apps/contract-review/cli/review_chat.py \
  --text "标记已核对 结论=确认问题 原因=template_alias_missing 字段=product_category:书柜,width:1500mm"
```

如果批次工作台已经给出模板快捷动作，也可以直接执行：

```bash
python3 apps/contract-review/cli/review_chat.py \
  --text "执行模板快捷动作 tpl-001:feedback"
```

当前默认 OCR 后端已经切到 `PaddleOCR`，用于处理：

- 图片附件
- 扫描版 PDF
- 无文字层 PDF

首次启用前，先按 PaddleOCR 官方文档安装对应环境：

```bash
# 先安装匹配你机器环境的 PaddlePaddle
# 再安装文档解析依赖组
python -m pip install "paddleocr[doc-parser]"
```

如果当前机器还没装 OCR 环境，只想先跑 ingest 骨架，可以临时关掉 OCR：

```bash
python3 apps/contract-review/cli/manual_batch.py --batch-dir /absolute/path/to/batch --ocr-backend disabled
```

如果只想先看会拆出哪些任务，不写任何运行时文件：

```bash
python3 apps/contract-review/cli/manual_batch.py --batch-dir /absolute/path/to/batch --dry-run --output-mode json
```

如果准备做发布前真实验收，建议直接跑：

```bash
bash apps/contract-review/scripts/run_acceptance_batch.sh \
  --batch-dir /absolute/path/to/acceptance-batch
```

验收说明见：

```text
docs/contract-review/release-acceptance.md
```

默认运行时输出会写到：

```text
apps/contract-review/runtime/
```

这个目录已在 `.gitignore` 中忽略。

PaddleOCR 结果还会额外做一层内容级缓存：

- macOS 默认写到 `~/Library/Caches/liangqin-contract-review/paddleocr/`
- Linux 默认写到 `~/.cache/liangqin-contract-review/paddleocr/`

同一份附件页内容再次复跑时，会优先命中缓存，避免重复 OCR。

当 OCR 成功执行后，每个任务还会额外生成：

```text
runtime/jobs/<job-id>/
  normalized/extraction-results.json
  normalized/normalized-fields.json
  normalized/ocr/<asset-id>/
    combined.md
    summary.json
    page-001/
    page-002/
  output/pricing-precheck.json
  output/formal-quote.json
  output/pricing-compare.json
  output/product-split.json
  output/template-profile.json
  output/review-feedback.json
```

其中：

- `combined.md`：给模型归纳用的派生文本
- `summary.json`：记录后端、页数和输出路径
- `page-xxx/`：逐页原始 OCR 结果落盘目录
- `normalized-fields.json`：合同侧归一化后的候选报价字段
- `pricing-precheck.json`：桥接到 `liangqin-pricing` 后的预检结果
- `formal-quote.json`：在预检满足条件时，调用现有报价系统做一次正式报价回放
- `pricing-compare.json`：合同金额与报价系统金额的逐单对比结果
- `product-split.json`：多产品合同的逐产品拆单候选、逐产品预检和逐产品报价对比结果
- `template-profile.json`：当前模板画像、模板指纹、模板信任分与常见冲突
- `review-feedback.json`：人工确认后的反馈写回记录

批次级还会额外生成：

```text
runtime/batches/<batch-id>/
  pricing-compare.json
  pricing-compare.csv
  pricing-compare.md
  pricing-compare-diagnosis.json
  pricing-compare-diagnosis.md
  workbench.html
```

用于快速查看：

- 哪些单据已经成功进入正式报价回放
- 哪些单据更接近合同最终价
- 哪些单据更接近折前价
- 哪些单据还因为字段不足或类目不可信而被跳过
- 哪些单据是多产品合同、正式报价失败、还缺字段，或需要人工确认类目
- 哪些单据可以直接在浏览器里按“概览 / 根因 / 模板 / 人工队列”工作台视角快速处理
- 哪些模板已经有人工反馈、哪些模板误报偏多、哪些模板已经沉淀出可复用字段记忆
- 哪些模板下一步应该“先补字段锚点”还是“先校准金额口径”
- 哪些模板已经能直接给出一条可复制的人工反馈命令模板

## 报价桥接原则

当前已经补了一层独立桥接：

- `apps/contract-review/core/pricing_bridge.py`

这层只负责：

- 把合同侧 `normalized_fields` 映射成 `liangqin-pricing` 可识别的 `precheck_args`
- 对低置信关键字段做拦截
- 调用现有报价系统的预检能力

当前桥接输出会给出三类状态：

- `ready_for_formal_quote`
  - 高置信字段已足够通过 `liangqin-pricing` 预检
- `needs_input`
  - 已成功进入预检，但还缺正式报价必需字段
- `manual_confirmation_required`
  - 关键字段置信度不够，先不允许进入报价

当前 `review.json` / `review.md` 也会额外输出一层合同审核摘要：

- `contract_total`
  - 合同里识别到的总金额
- `add_on_items`
  - 增项金额或另计项
- `special_notes`
  - 备注、特殊说明、安装/工艺说明
- `pricing_alignment`
  - 当前哪些字段已进入 `liangqin-pricing`
  - 还缺哪些字段才能继续正式报价
  - 哪些高置信合同字段还没被报价预检消费

当前第一批已支持的归一化字段包括：

- 基础柜体：`product_category`、`length`、`depth`、`height`、`wood_material`
- 柜体门路：`has_door`、`door_type`
- 基础报价意图：`quote_kind`
- 模块化儿童床：`bed_form`、`access_style`、`lower_bed_type`、`guardrail_style`、`width`、`length`、`wood_material`
- 模块化儿童床组合柜：`guardrail_length`、`guardrail_height`、`stair_width`、`stair_depth`
- 床下组合柜通用结构：`underbed_cabinet_mode`
- 床下组合柜前排：`front_cabinet_length`、`front_cabinet_height`、`front_cabinet_depth`、`front_cabinet_mode`
- 床下组合柜后排：`rear_cabinet_length`、`rear_cabinet_height`、`rear_cabinet_depth`、`rear_cabinet_mode`
- 双排关系：`interconnected_rows`

这层明确不负责：

- 不改 `skill/liangqin-pricing/` 里的价格规则
- 不改现有价格索引
- 不绕过预检直接生成正式报价

也就是说：

- 合同审核模块决定“哪些字段可信到可以进入报价预检”
- `liangqin-pricing` 继续只决定“这些字段在当前报价规则下是否可报、还缺什么、怎么报”
