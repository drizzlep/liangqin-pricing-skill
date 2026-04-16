# Dependency Contract

`liangqin-contract-pricing` 不是独立报价系统。

它负责：

- 提取正式合同中的报价相关字段
- 归一化类目、材质、尺寸、数量
- 调用 `liangqin-pricing` 做预检、报价回放和金额比对
- 输出审核结论与差异说明

因此：

- `liangqin-contract-pricing` 是 orchestration layer
- `liangqin-pricing` 是 pricing engine

## 最低依赖要求

- Python 3
- PaddleOCR
- `liangqin-pricing`
- `liangqin-pricing` 可用价格数据

建议运行前至少检查：

- `scripts/precheck_quote.py`
- `scripts/query_price_index.py`
- `data/current/price-index.json`

## 运行时建议

建议显式指定：

```bash
export LIANGQIN_PRICING_SKILL_DIR="/path/to/liangqin-pricing"
```

## 缺失依赖时

如果缺少 `liangqin-pricing`，应立即停止，不要生成伪结果。
