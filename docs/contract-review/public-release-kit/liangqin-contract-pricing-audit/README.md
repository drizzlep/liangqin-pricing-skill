# liangqin-contract-pricing

`liangqin-contract-pricing` 是良禽佳木专用的正式合同报价审核 skill。

它用于从合同、PDF、附件清单和图纸图片中提取报价相关字段，并联动 `liangqin-pricing` 对报价结果做回放、比对与差异诊断。

重要边界：

- 本项目不是法律合同审核工具
- 本项目不能脱离 `liangqin-pricing` 独立运行
- 本项目仅适用于良禽佳木内部报价体系

## 当前发布定位

当前公开仓库建议包含：

- skill 入口与说明文档
- 安装与依赖检查脚本
- CI 与 GitHub 模板
- 脱敏样例目录协议

不建议公开提交：

- 真实客户合同
- 客户姓名、电话、地址
- 敏感价格表和私有报价规则
- 任何未脱敏的运行输出

## 能力范围

- 合同正文与附件清单抽取
- OCR 图片文字识别
- 报价字段归一化
- 良禽报价体系映射
- 单品拆分与整单汇总比对
- 差异诊断与人工复核提示

## 依赖

运行前必须具备：

- Python 3
- `liangqin-pricing`
- PaddleOCR
- PyPDF2
- 本地可执行的合同审核脚本环境

依赖关系说明见：

- `references/dependency-contract.md`

## 快速开始

1. 先安装并配置 `liangqin-pricing`
2. 运行依赖检查：

```bash
bash scripts/check_dependencies.sh
```

3. 准备批次目录
4. 执行审核：

```bash
bash scripts/run_contract_pricing_audit.sh "/path/to/batch-dir"
```

如果你的 PaddleOCR 不在当前 python 环境里，也可以显式指定：

```bash
export LIANGQIN_CONTRACT_AUDIT_PADDLE_PYTHON="/path/to/python"
```

## 输入

批次目录通常包含：

- `raw/`
- `manifest.json`

详细协议见：

- `references/batch-folder-spec.md`

## 输出

典型输出包括：

- `review.md`
- `product-split.json`
- `pricing-compare.json`

详细格式见：

- `references/output-spec.md`

## 安装与发布

- 安装说明：`docs/install.md`
- 发布前检查：`docs/release-checklist.md`
- GitHub 发布步骤：`docs/github-publish.md`

## 仓库建议

如果发布到 `https://github.com/drizzlep`，建议：

- 先以 public repo 形式发布框架和说明
- 再通过私有依赖、私有数据目录或内部部署方式接入完整价格体系
