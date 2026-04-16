# 合同审核发布验收

这份文档只服务一个目标：

- 把 `contract-review` 收成“正式合同发出前的二次校验器”

不再继续扩展平台能力，不再继续发散模板工作台玩法。

当前发布前，重点只验证三件事：

1. 合同自己有没有算错
2. 合同金额和报价系统有没有明显冲突
3. 当系统发现问题时，是否能明确指出“先核对什么”

## 验收样本建议

建议至少准备 `30-50` 份真实历史合同，按下面三类分布：

- `正常合同`
  - 合同金额与报价系统一致
  - 合同内计算自洽
- `合同内计算错误`
  - 数量乘法错误
  - 折扣计算错误
  - 增项汇总错误
  - 总价不自洽
- `合同与报价系统冲突`
  - 差额明显大于 `300 元`
  - 差额明显大于 `3%`
  - 折扣口径不一致
  - 数量漏算
  - 增项漏算

如果样本数量不够，最低也要保证：

- 正常合同：`10`
- 合同内计算错误：`10`
- 合同与报价系统冲突：`10`

## 样本目录规范

推荐直接建一个验收批次目录，例如：

```text
acceptance-batch-2026-04-16/
  manifest.json
  raw/
    case-001-normal/
      合同.docx
    case-002-calc-error/
      合同.pdf
      图纸.png
    case-003-quote-conflict/
      合同.docx
```

同时建议在批次目录旁边准备一份人工标注表：

```text
acceptance-batch-2026-04-16/
acceptance-ground-truth.csv
```

推荐直接使用仓库里的模板：

```text
apps/contract-review/templates/acceptance-ground-truth.example.csv
```

## 人工标注字段

每份样本至少标这几列：

- `case_key`
  - 对应 `raw/` 下的 case 目录名
- `expected_bucket`
  - `normal`
  - `calc_error`
  - `quote_conflict`
- `expected_verdict`
  - `recommended_release`
  - `manual_review_required`
- `expected_issue_codes`
  - 例如：`calculation_error`
  - 或：`quote_conflict|discount_mismatch`
- `expected_primary_check`
  - 例如：`核对折扣`
  - 例如：`核对数量`
  - 例如：`核对增项`
- `notes`
  - 人工备注

## 运行命令

先准备好批次目录，然后执行：

```bash
bash apps/contract-review/scripts/run_acceptance_batch.sh \
  --batch-dir /absolute/path/to/acceptance-batch-2026-04-16
```

如果当前机器还没装 OCR，先只验文字合同，可临时关闭 OCR：

```bash
bash apps/contract-review/scripts/run_acceptance_batch.sh \
  --batch-dir /absolute/path/to/acceptance-batch-2026-04-16 \
  --ocr-backend disabled
```

## 重点看什么

跑完之后，先只看这几个文件：

- `runtime/batches/<batch-id>/batch-dashboard.md`
  - 先看总量、风险结构、重点模板
- `runtime/batches/<batch-id>/manual-review-queue.md`
  - 看高风险合同排序是否合理
- `runtime/batches/<batch-id>/pricing-compare-diagnosis.md`
  - 看系统给的差异归因是否像人话
- `runtime/jobs/<job-id>/output/review.md`
  - 抽查单份合同的审单卡

## 验收标准

发布前建议至少达到下面标准：

1. 漏报
- `合同内计算错误` 样本里，不能出现明显漏报
- `合同与报价系统冲突` 样本里，不能漏掉“大差额”合同

2. 误报
- `正常合同` 样本里，误报率尽量控制在可接受范围
- 如果误报存在，必须能通过人工快速判掉，不能让人看不懂

3. 输出可用性
- 每份高风险合同都必须明确告诉人“先核对什么”
- 不接受只说“请人工复核”但没有方向

4. 风险规则稳定
- 合同内算术不自洽：必须高风险
- 差额 `> 300 元` 或 `> 3%`：必须高风险
- OCR 低置信 / 关键字段冲突：必须进入人工核对

## 是否可以发布

满足下面条件时，可以认为已经达到当前目标：

- 高风险合同基本不漏报
- 正常合同误报率在团队可接受范围内
- 审单卡已经足够让设计师或复核人立即知道下一步该查什么
- 报价系统仍然是唯一价格真相源，审核系统没有自动改价

到这一步，产品目标就已经成立了：

- 不是替代设计师报价
- 也不是自动批价
- 而是在正式合同发出前，多一层稳定的安全兜底
