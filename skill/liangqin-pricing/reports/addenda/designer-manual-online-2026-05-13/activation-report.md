# 良禽佳木设计师手册线上版激活报告

生成时间：2026-05-14 15:15:55 CST

## 结论

新版 `designer-manual-online-2026-05-13` 已切换为当前唯一 `ACTIVE` 标准。旧版 `designer-manual-2026-03-22` 已改为 `ARCHIVED`，仅保留为历史归档、审计证据和人工回滚参考，不再参与报价计算、报价前追问、自然语言咨询或运行时兜底。

本次切换遵循“新版设计师手册替换旧版手册”的口径：新版没有明确覆盖的旧版内容，不能再补成当前良禽标准回答；运行入口应返回“新版标准未明确”，并提示走新版复核或人工确认。

## 切换前后

切换前：

- `designer-manual-2026-03-22`：`ACTIVE`
- `designer-manual-online-2026-05-13`：`PAUSED`

切换后：

- `designer-manual-online-2026-05-13`：`ACTIVE`
- `designer-manual-2026-03-22`：`ARCHIVED`

旧版保留入口：

- `skill/liangqin-pricing/references/addenda/designer-manual-2026-03-22/manifest.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-2026-03-22/rules-index.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-2026-03-22/runtime-rules.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-2026-03-22/knowledge-layer.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-2026-03-22/coverage-ledger.json`

新版运行入口：

- `skill/liangqin-pricing/references/addenda/designer-manual-online-2026-05-13/manifest.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-13/rules-index.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-13/runtime-rules.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-13/knowledge-layer.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-13/coverage-ledger.json`
- `skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-13/full-document-data-certification.html`
- `skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-13/agent-validation-pack.html`

## 报价系统分层

新版全文数据认证仍保留 `1757` 个候选数据点：

- 可进入企业 Agent 数据点：`230`
- 需要人工复核：`240`
- 不适合自动回答：`1287`

按报价系统运行边界进一步拆分：

- 报价计算硬规则：`25`
- 报价前追问/拦截规则：`122`
- 设计师咨询知识：`83`
- 人工复核：`240`
- 不开放：`1287`

这意味着 `230` 条可进入 Agent 的点不会被一刀切进报价公式，而是先区分为“直接影响报价”“报价前追问/拦截”“只做设计师咨询回答”三层；`240` 条复核项优先看价格、尺寸、禁止项、合同备注和工厂确认类高价值风险。

## 本次代码保护

已新增或调整的保护：

- `query_addendum_guidance.py` 的 runtime/knowledge 查询只读取 `ACTIVE` manifest。
- 没有命中新版时返回 `addendum_guidance.current_standard_not_found`，不再读取旧版作为自然语言兜底。
- 旧版 manifest 状态从运行层退出，改为 `ARCHIVED`。
- `full-document-data-certification` 新增 `pricing_system_layer` 和 `pricing_system_layer_counts`，把候选数据点按报价系统边界分层。
- `agent-validation-pack` 文案改为“当前标准仅使用新版”，命中非当前标准的样例需要排除。
- 文档明确旧版只做历史归档、审计和回滚证据，不参与当前良禽标准回答。

## 验证结果

已通过：

- `python3 -m unittest skill/liangqin-pricing/tests/test_query_addendum_guidance.py skill/liangqin-pricing/tests/test_build_full_document_data_certification.py skill/liangqin-pricing/tests/test_build_agent_validation_pack.py`
  - 52 tests OK
- `python3 skill/liangqin-pricing/scripts/check_runtime_health.py`
  - 运行环境诊断：ok

已重新生成：

- `python3 skill/liangqin-pricing/scripts/build_full_document_data_certification.py --candidate-layer designer-manual-online-2026-05-13`
  - 输出 `1757` 个候选数据点
  - `230` 可进入企业 Agent
  - `240` 需人工复核
  - `1287` 不适合自动回答

## 已知风险

- 新版仍有 `240` 条需要人工复核的数据点，不能直接上线为自动报价或自动回答。
- 新版未覆盖的旧版规则现在会退出运行标准，短期内可能减少一部分旧口径咨询答案，但这是符合“新版替换旧版”的预期结果。
- 对齐报告中曾标记的冲突和暂缓主题仍应作为人工审核材料保留，不应自动合并成报价规则。

## 回滚步骤

如果需要人工回滚到旧版：

1. 将 `skill/liangqin-pricing/references/addenda/designer-manual-online-2026-05-13/manifest.json` 中的 `status` 从 `ACTIVE` 改回 `PAUSED` 或 `ARCHIVED`。
2. 将 `skill/liangqin-pricing/references/addenda/designer-manual-2026-03-22/manifest.json` 中的 `status` 从 `ARCHIVED` 改回 `ACTIVE`。
3. 运行 `python3 skill/liangqin-pricing/scripts/check_runtime_health.py`，确认只有旧版为 `ACTIVE`。
4. 重新运行本报告中的测试命令。

## 下一步建议

短期先按当前状态使用新版，让报价、追问、限制和咨询都只按线上版手册运行。下一阶段建议从 `240` 条人工复核项开始，优先处理价格、尺寸、禁止项、合同备注和工厂确认相关数据点，再逐步把它们提升到报价计算或 precheck 规则。
