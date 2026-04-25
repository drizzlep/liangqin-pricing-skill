# 合同审核模块说明

这份文档对应仓库里的并列应用模块：

- `apps/contract-review/`

当前定位：

- 给本地 AI Agent 调用
- 先做手工批次目录投递
- 不混入现有 `skill/liangqin-pricing/`
- 不把“文件夹路径”写死成最终接口

真正稳定的业务接口是：

- `batch`
- `job`

其中：

- 手工版：批次文件夹只是 `manual_batch adapter`
- 钉钉版：附件消息也会先落成一个 `batch/job`
- 飞书版：同理

## 为什么先做 app，不先做第二个 skill

因为当前第一批使用者是本地 AI Agent，而不是要立即分发给其他 OpenClaw。

这个阶段更需要：

- 批处理
- 任务状态机
- 运行时目录
- 批次汇总
- 渠道 adapter

这些都更像一个应用，而不是 skill 外壳。

所以当前结构是：

```text
apps/contract-review/
```

后续如果要分发给其他 OpenClaw，再补：

```text
skill/liangqin-contract-review/
```

让 skill 只负责“把 Agent 输入转成 app 调用”。

## 当前 CLI

```bash
python3 apps/contract-review/cli/manual_batch.py --batch-dir /absolute/path/to/batch
```

聊天入口：

```bash
python3 apps/contract-review/cli/review_chat.py \
  --text "审这份合同" \
  --batch-dir /absolute/path/to/batch
```

支持的轻命令：

- `看下一份高风险合同`
- `只看金额冲突`
- `展开证据`
- `标记已核对`

如果想把人工核对结果直接写回模板学习层，可以在同一条命令里补充：

```bash
python3 apps/contract-review/cli/review_chat.py \
  --text "标记已核对 结论=确认问题 原因=template_alias_missing 字段=product_category:书柜,width:1500mm"
```

当前默认 OCR 后端为 `PaddleOCR`。

如果本机准备正式吃图片 / 扫描件，先完成两步：

```bash
# 1. 先按官方说明安装适配你机器环境的 PaddlePaddle
# 2. 再安装 PaddleOCR 文档解析依赖
python -m pip install "paddleocr[doc-parser]"
```

如果当前只是想验证拆单、运行时目录和审阅骨架，可显式关闭 OCR：

```bash
python3 apps/contract-review/cli/manual_batch.py --batch-dir /absolute/path/to/batch --ocr-backend disabled
```

只看拆单计划，不写运行时：

```bash
python3 apps/contract-review/cli/manual_batch.py --batch-dir /absolute/path/to/batch --dry-run --output-mode json
```

如果你现在已经准备开始做“发布前真实验收”，直接看：

- `docs/contract-review/release-acceptance.md`
- `apps/contract-review/templates/acceptance-ground-truth.example.csv`

## 当前运行时输出

默认输出到：

```text
apps/contract-review/runtime/
```

内部结构：

```text
runtime/
  batches/<batch-id>/
    batch-dashboard.json
    batch-dashboard.md
    batch-summary.json
    batch-summary.md
    batch-summary.csv
    manual-review-queue.json
    manual-review-queue.md
  jobs/<job-id>/
    job.json
    input/
    normalized/source-assets.json
    normalized/extraction-results.json
    normalized/normalized-fields.json
    normalized/ocr/<asset-id>/
    output/pricing-precheck.json
    output/review.json
    output/review.md
    output/replay.json
    output/template-profile.json
    output/review-feedback.json
    status.json
```

## 当前 V1 已完成的能力

- 批次目录读取
- `manifest.json` 读取
- 自动拆单
- 单据任务 staging
- docx/pdf 的轻量文字预览
- PaddleOCR 可插拔 OCR 接入
- 合同字段结构化归一化（首批）
- 合同字段到 `liangqin-pricing precheck_args` 的独立桥接层
- 合同金额 / 增项 / 备注 / 特殊说明摘要
- 合同字段与报价预检之间的差异提示
- 统一 `issue` 输出与 `review_card`
- 差异签名库：折扣偏差 / 数量偏差 / 增项偏差 / OCR 风险 / 缺字段
- 模板指纹、模板画像、模板信任分
- 人工反馈回写模板档案
- ingest 级发现项
- 批次汇总
- 按 `p0/p1/p2/normal` 排序的人工复核队列

## 当前 V1 还没完成的能力

- 规则级审核
- 调用 `liangqin-pricing` 做正式报价回放
- 渠道 adapter

## 与 liangqin-pricing 的边界

当前桥接策略是：

- `apps/contract-review/` 负责 OCR 输出、字段归一化、字段置信度判断
- `apps/contract-review/core/pricing_bridge.py` 负责把高置信字段映射成 `precheck_args`
- `skill/liangqin-pricing/` 继续只负责预检、缺失项判断和正式报价规则

当前运行时里，推荐优先看两个文件：

- `normalized/normalized-fields.json`
  - 看合同里到底抽出了哪些结构化字段
- `output/pricing-precheck.json`
  - 看这些字段进入 `liangqin-pricing` 后，结果是可正式报价、还缺字段，还是必须人工确认

如果你是按批次先做人工筛单，建议优先看两个批次级文件：

- `batches/<batch-id>/batch-dashboard.md`
  - 批次首页，先看总量、优先级分布、OCR 阻塞量、模板学习成效
- `batches/<batch-id>/batch-dashboard.json`
  - 给 Agent 做批次级路由和任务分发
- `batches/<batch-id>/manual-review-queue.md`
  - 人工快速浏览的复核队列
- `batches/<batch-id>/manual-review-queue.json`
  - 给后续 Agent / 脚本消费的排序结果
- `batches/<batch-id>/batch-summary.json`
  - 更完整的批次汇总

当前字段归一化已优先覆盖两类高价值场景：

- 常规柜体
  - 类目、长宽高深、材质、是否带门、门型
- 模块化儿童床 / 上下床
  - `quote_kind`
  - `bed_form`
  - `access_style`
  - `lower_bed_type`
  - `guardrail_style`
  - `width`
  - `length`
  - `wood_material`
- 高架床 / 半高床 + 床下组合柜
  - `guardrail_length`
  - `guardrail_height`
  - `stair_width`
  - `stair_depth`
  - `underbed_cabinet_mode`
  - `front_cabinet_length`
  - `front_cabinet_height`
  - `front_cabinet_depth`
  - `front_cabinet_mode`
  - `rear_cabinet_length`
  - `rear_cabinet_height`
  - `rear_cabinet_depth`
  - `rear_cabinet_mode`
  - `interconnected_rows`

这意味着：

- 新增合同审核能力不会直接改写 `liangqin-pricing` 的报价核心
- 真正会影响报价结果的是“输入字段质量”，不是价格引擎本身
- 所以低置信字段必须先拦住，不能静默流入正式报价

## OCR 风险原则

如果合同里的关键尺寸、备注、开启方向、节点要求主要存在于：

- 图片
- 扫描 PDF
- 图纸截图
- 无文字层的嵌图文档

那么系统必须明确进入：

- `ocr_or_vision_required`

而不能假装“只要先转 Markdown 就已经看懂了”。

Markdown 在这里的正确位置是：

- 作为模型归纳的输入层

但真正的审计层还必须保留：

- 原始页码
- 图像块或文档块引用
- OCR / 视觉提取置信度
- 原始证据片段
