# Output Spec

`liangqin-contract-pricing` 的输出分为两类：

- 给人看的审核摘要
- 给程序继续处理的结构化结果

## 标准输出位置

```text
runtime-root/
  jobs/
    <job-id>/
      output/
        review.md
        review.json
        pricing-precheck.json
        pricing-compare.json
        product-split.json
        template-profile.json
        review-feedback.json
```

## 核心输出文件

### `review.md`

人工快速查看审核结论的第一入口。

建议至少包含：

- 合同总价
- 报价系统回放总价
- 最佳匹配目标
- 差额
- 主要差异项
- 人工复核提示

### `review.json`

结构化审单输出。

建议至少包含：

- `issues`
- `review_card`
- `review_analysis`
- `template_profile`

### `pricing-precheck.json`

记录合同字段映射到 `liangqin-pricing` 前的预检结果。

### `pricing-compare.json`

记录合同金额与报价回放结果的逐单对比。

### `product-split.json`

记录多产品合同的拆单回放结果，用于定位主要差额来源。

### `template-profile.json`

记录模板指纹、模板画像、模板信任分和常见冲突。

### `review-feedback.json`

记录人工确认结果，供模板学习层回写。

建议至少包含：

- `job_id`
- `template_id`
- `issue_code`
- `human_decision`
- `corrected_fields`
- `confirmed_root_cause`
- `template_profile_update`

### `batch-dashboard.json`

批次级首页输出。

建议至少包含：

- `template_learning_overview`
- `template_learning_false_positive_breakdown`
- `template_learning_top_templates`

其中 `template_learning_top_templates` 建议包含：

- `recommended_action`
- `recommended_reason`
- `suggested_feedback_command`
- `quick_actions`
