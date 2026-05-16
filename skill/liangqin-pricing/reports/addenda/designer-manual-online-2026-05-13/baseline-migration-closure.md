# 良禽报价体新基准机器迁移闭环报告

目标：以 `designer-manual-online-2026-05-13` 作为良禽报价系统的新基准，机器判断规则接入、暂停和验证状态，避免人工逐条确认。

## 合同状态
- T+1 小时合同：complete
- T+24 小时合同：complete
- 是否需要人工逐条审规则：否

## 当前进度
- 新规则总数：147
- precheck 候选规则：82
- 已进入 runtime gate：82
- precheck 尚未接入 runtime：0
- 需要 shadow 验证：47
- 已通过 runtime gate 覆盖的 shadow 规则：47
- 金额规则暂停：20
- OCR/质量暂停：45
- 冲突暂停：5

## 已接入 runtime gate
- landing-rule-0005
- landing-rule-0006
- landing-rule-0007
- landing-rule-0013
- landing-rule-0023
- landing-rule-0030
- landing-rule-0034
- landing-rule-0065
- landing-rule-0069
- landing-rule-0074
- landing-rule-0083
- landing-rule-0088
- landing-rule-0089
- landing-rule-0090
- landing-rule-0097
- landing-rule-0108
- landing-rule-0110
- landing-rule-0119
- landing-rule-0120
- landing-rule-0124
- landing-rule-0129
- landing-rule-0142
- landing-rule-0144
- landing-rule-0148
- landing-rule-0150
- landing-rule-0151
- landing-rule-0168
- landing-rule-0216
- landing-rule-0225
- landing-rule-0231
- landing-rule-0235
- landing-rule-0239
- landing-rule-0241
- landing-rule-0248
- landing-rule-0254
- landing-rule-0255
- landing-rule-0262
- landing-rule-0264
- landing-rule-0265
- landing-rule-0266
- landing-rule-0268
- landing-rule-0276
- landing-rule-0278
- landing-rule-0286
- landing-rule-0293
- landing-rule-0295
- landing-rule-0299
- landing-rule-0349
- landing-rule-0358
- landing-rule-0360
- landing-rule-0370
- landing-rule-0389
- landing-rule-0391
- landing-rule-0392
- landing-rule-0404
- landing-rule-0406
- landing-rule-0411
- landing-rule-0414
- landing-rule-0424
- landing-rule-0428
- landing-rule-0429
- landing-rule-0430
- landing-rule-0433
- landing-rule-0437
- landing-rule-0442
- landing-rule-0488
- landing-rule-0501
- landing-rule-0510
- landing-rule-0512
- landing-rule-0515
- landing-rule-0572
- landing-rule-0573
- landing-rule-0574
- landing-rule-0680
- landing-rule-0684
- landing-rule-0686
- landing-rule-0691
- landing-rule-0726
- landing-rule-0828
- landing-rule-0836
- landing-rule-0845
- landing-rule-0847

## 下一批机器工作
- precheck_runtime_expansion: 0
- shadow_verification: 0
- money_regression: 20
- quality_or_ocr_pause: 45

## 机器护栏
- 机器可验证规则进入 runtime gate；不可验证规则暂停。
- 金额规则没有公式字段和金额回归测试前不影响正式报价金额。
- 旧规则只作为 shadow 对照和冲突证据，不作为默认报价真相。
