# Medium Risk 条目处理建议

- 说明: 这里仅针对当前 `included_runtime` 中剩余的 6 条 `medium risk` 给出建议动作。
- 动作含义:
- `downgrade_to_manual_review`: 建议先从 runtime 降级，待人工确认后再决定是否回填。
- `keep_after_rewrite`: 建议保留业务含义，但需要先清洗/改写后再保留在 runtime。

## p78 · 15045 25 150 40DG-02 DG-06 DG-10 DSG-03 CTG-01 CTG-03 CBG-04 DSG-08 CBG-07 XSG-04 DG-08 DSG-02 CJ-01 YG-06 YG-09 YG-17 SG-13 YG-11 DSG-01 XSG-02 DSG-04 a）正视图 b）左视图 c）俯视图 d）支腿俯视图 圆直腿1-150 圆直腿1-200 圆直腿1-220 圆直腿1-240 圆直腿2-200 圆直腿2-150 圆斜腿1-1

- domain: cabinet
- recommended_action: downgrade_to_manual_review
- reason_flags: 标题更像表格/编号串；缺少明确报价信号
- rationale: 当前只有支腿编号/表格碎片，缺少清晰的计价或约束表达，直接进 runtime 风险高。

## p203 · 26 60拼框平开门尺寸限制快速检索表-a

- domain: general
- recommended_action: downgrade_to_manual_review
- reason_flags: domain偏弱；相关度低；标题更像表格/编号串
- rationale: 这是拼框平开门快速检索表的碎片页，信息可能有价值，但当前抽取不完整且高度重复，适合先人工整表后再入 runtime。

## p206 · 26 60拼框平开门尺寸限制快速检索表-a

- domain: general
- recommended_action: downgrade_to_manual_review
- reason_flags: domain偏弱；相关度低；标题更像表格/编号串
- rationale: 这是拼框平开门快速检索表的碎片页，信息可能有价值，但当前抽取不完整且高度重复，适合先人工整表后再入 runtime。

## p207 · 门高＞1500或

- domain: general
- recommended_action: downgrade_to_manual_review
- reason_flags: domain偏弱；相关度低；标题更像表格/编号串
- rationale: 这是拼框平开门快速检索表的碎片页，信息可能有价值，但当前抽取不完整且高度重复，适合先人工整表后再入 runtime。

## p208 · ≤2300拼框平开门

- domain: general
- recommended_action: downgrade_to_manual_review
- reason_flags: domain偏弱；相关度低；标题更像表格/编号串
- rationale: 这是拼框平开门快速检索表的碎片页，信息可能有价值，但当前抽取不完整且高度重复，适合先人工整表后再入 runtime。

## p297 · 无线单面板动能开关

- domain: accessory
- recommended_action: keep_after_rewrite
- reason_flags: 相关度低；包含背景/操作说明关键词
- rationale: 这条含有真实配件适用条件，当前 runtime 已按“无线单面板动能开关”完成清洗保留，建议人工抽检一次配网步骤是否已完全剥离。
