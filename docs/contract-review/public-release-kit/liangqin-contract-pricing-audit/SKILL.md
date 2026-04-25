---
name: liangqin-contract-pricing
description: 良禽佳木正式合同报价审核。用于从合同、PDF、附件图纸中提取报价相关字段，联动 liangqin-pricing 做报价回放、金额比对和差异诊断；仅适用于良禽佳木内部报价体系，不提供法律合同审查。
---

# Liangqin Contract Pricing Audit

本 skill 仅用于良禽佳木正式合同阶段的报价审核。

它负责：

- 读取合同批次文件夹
- 抽取合同正文、附件清单、图纸图片中的报价相关信息
- 归一化类目、材质、尺寸、数量等字段
- 联动 `liangqin-pricing` 做预检、报价回放和金额比对
- 输出审核结论、差异项和人工复核提示

它不负责：

- 法律条款审核
- 合同主体风险判断
- 通用合同理解
- 脱离 `liangqin-pricing` 的独立报价

## 运行前检查

先执行：

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/check_dependencies.sh"
```

如果依赖缺失，停止流程并明确提示先安装 `liangqin-pricing`。

## 输入约定

输入应为一个批次文件夹。

目录协议见：

- `references/batch-folder-spec.md`

## 标准执行流程

1. 检查依赖
2. 确认输入目录符合批次协议
3. 执行本地审核脚本
4. 读取输出结果
5. 优先汇报：
   - 合同总价
   - 报价系统回放总价
   - 最佳匹配目标
   - 差额
   - 主要差异项
6. 如果存在低置信字段，明确标记人工复核点

## 执行命令

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/run_contract_pricing_audit.sh" "/path/to/batch-dir"
```

## 输出要求

默认先给简洁结论：

- 是否基本匹配
- 差额是多少
- 哪几个品项最可疑
- 是否建议人工复核

再补：

- 关键拆单结果
- 命中的报价候选
- 失败或低置信原因
