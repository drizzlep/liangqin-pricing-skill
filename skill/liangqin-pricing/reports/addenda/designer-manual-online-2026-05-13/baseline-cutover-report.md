# 良禽报价体新设计师手册基准 Cutover 报告

目标：将 `designer-manual-online-2026-05-13` 作为良禽报价体默认基准，旧版仅保留为 shadow/回归证据。

## Cutover 状态
- 状态：complete
- 维护状态：COMPLETED_MAINTENANCE
- 维护说明：迁移线已完成并进入维护状态。
- 新版层状态：ACTIVE
- 旧版层状态：ARCHIVED
- 旧版是否仍是默认运行真相：disabled

## 机器接入结果
- 新规则总数：147
- 机器可验证 precheck 规则：82
- 配置驱动 runtime gate：82
- 金额规则激活：20
- 金额规则暂停：0
- 历史 ledger 金额暂停记录：20（仅作 shadow/迁移证据）
- OCR/质量暂停：45
- 冲突暂停：5

## 金额 Cutover Guard
- 状态：passed
- 金额规则总数：20
- golden ready：20
- golden blocked：0
- zero-impact 规则：5
- 失败项：无

## precheck 模块分布
- precheck_quote:safety_or_install_gate: 11
- precheck_quote:dimension_or_limit_gate: 50
- precheck_quote:required_note_or_confirmation_gate: 15
- precheck_quote:rule_gate: 6

## 机器护栏
- 新版设计师手册是默认报价基准。
- 旧版设计师手册只保留为 shadow/回归证据，不作为默认运行真相。
- 金额规则必须满足 20/20 activated、0 paused、全部 runtime regression passed。
- zero-impact 结构规则只能输出 0 元，不得改变真实报价金额。
- OCR/质量风险规则保持暂停，不进入正式报价链路。
