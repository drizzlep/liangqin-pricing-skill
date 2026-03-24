# PDF 图片 OCR 复盘结论

- source_file: /Users/admin/Downloads/设计标准手册-AI测试.pdf
- 总图块数: 2830
- 人工复核回灌图块数: 15
- remaining_high_risk: 0

## 回灌确认

- `p049-b04`: needs_manual_judgement / 直角圆边-窄边高柜
- `p049-b05`: needs_manual_judgement / 直角圆边-窄边高柜；凹槽内退尺寸；上节点可读20/8/12；下节点可读12/6/8
- `p050-b06`: covered_runtime / 窄边风格--拆装注意事项；门盖牙称与顶挡条时最少需要留出15mm
- `p050-b07`: covered_runtime / 窄边风格--拆装注意事项；门盖牙称与顶挡条时最少需要留出15mm

## 关键页面判断

- `p49`: 已升格为结构约束句草稿层，当前保持 `needs_manual_judgement`，继续不进 runtime。
- `p50`: 核心规则已确认并覆盖 runtime，`p050-b06/p050-b07` 当前均为 `covered_runtime` / `covered_runtime`。
- `p288`: 继续保持 `new_candidate_rule`，建议作为下一轮重点候选规则。
- `p148`: 当前文本以材质性能说明为主，建议作为说明性背景看待，不作为下一轮阻塞项。
- `p277`: 与现有“品牌：德利丰”运行时条目高度相关，但原始 runtime 文本质量较差；本轮视为已知问题，不阻塞全量测试，建议后续单独清洗。

## 剩余风险

- 当前没有剩余高风险块。

## 放行结论

- 结论: 现有扫描结果复盘无阻塞问题，可进入下一轮全面测试/复核。
