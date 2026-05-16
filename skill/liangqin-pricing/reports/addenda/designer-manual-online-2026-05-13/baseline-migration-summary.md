# 新版设计师手册机器迁移台账摘要

目标：以 `designer-manual-online-2026-05-13` 作为良禽报价系统的新基准，使用机器证据、自动测试和 shadow 验证推进，不要求人工逐条确认。

## 总览
- 新版候选规则：147
- 旧版运行规则：91
- 可自动接入 precheck 队列：82

## 机器状态
- active_new_baseline_candidate: 82
- conflict_paused: 5
- paused_unverified: 60

## 冲突状态
- no_old_overlap: 35
- money_rule_paused: 20
- old_overlap_shadow_required: 47
- paused_quality_or_ocr: 45

## 执行规则
- 机器无法验证的规则暂停，不进入正式报价。
- 金额规则先暂停，补齐公式字段和金额回归测试后再激活。
- 旧版相近规则只作为冲突证据，不作为新版运行兜底。
