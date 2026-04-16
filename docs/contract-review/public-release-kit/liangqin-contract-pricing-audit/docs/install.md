# Install Guide

## 目标

安装 `liangqin-contract-pricing`，并确保它能正确联动 `liangqin-pricing`。

## 前置要求

- Python 3
- `liangqin-pricing`
- PaddleOCR

## 安装步骤

1. 获取仓库：

```bash
git clone <your-repo-url> liangqin-contract-pricing
cd liangqin-contract-pricing
```

2. 配置依赖路径：

```bash
export LIANGQIN_PRICING_SKILL_DIR="/path/to/liangqin-pricing"
export LIANGQIN_CONTRACT_AUDIT_APP_DIR="/path/to/liangqin-contract-pricing/apps/contract-review"
export LIANGQIN_CONTRACT_AUDIT_PADDLE_PYTHON="/path/to/python"
```

3. 检查依赖：

```bash
bash scripts/check_dependencies.sh
```

4. 执行审核：

```bash
bash scripts/run_contract_pricing_audit.sh "/path/to/batch-dir"
```

## 重点提醒

- 本项目不是法律合同审查
- 本项目不能脱离 `liangqin-pricing` 独立运行
- 公开仓库不要提交真实合同和敏感数据
