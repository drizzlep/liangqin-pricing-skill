# 良禽报价体新基准 shadow 验证报告

目标：用机器验证 `designer-manual-online-2026-05-13` 中与旧规则重叠的规则，避免新旧规则长期并行。

## 总览
- shadow 目标规则：47
- 可配置化覆盖旧规则：47
- 冲突暂停：0
- 仍需金额/OCR 阻塞：0
- 生成 runtime gate：47

## shadow 结果
- coverable_by_config_gate: 47

## 模块分布
- precheck_quote:safety_or_install_gate: 3
- precheck_quote:dimension_or_limit_gate: 32
- precheck_quote:required_note_or_confirmation_gate: 10
- precheck_quote:rule_gate: 2

## 机器护栏
- 只让高置信、非金额、非 OCR 风险的 precheck 规则配置化覆盖旧规则。
- 金额规则必须进入金额回归测试，不通过 shadow 自动覆盖。
- 配置化 gate 只负责正式报价前追问/确认，不直接改金额。
