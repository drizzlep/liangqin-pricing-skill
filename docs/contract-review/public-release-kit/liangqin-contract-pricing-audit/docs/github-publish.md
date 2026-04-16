# GitHub Publish Guide

目标仓库建议：

- `https://github.com/drizzlep/liangqin-contract-pricing`

## 发布前准备

在本地确认以下内容已经完成：

- 公开骨架文件已齐全
- `apps/contract-review` 公开版代码已放入仓库
- 不包含真实客户合同
- 不包含敏感价格数据
- `README.md`、`SKILL.md`、`docs/install.md` 已更新
- `bash scripts/check_dependencies.sh` 已验证
- 若本地有 `liangqin-pricing`，已执行一次测试回归

## 推荐发布步骤

### 1. 创建新目录

先把当前准备好的骨架目录单独拷到一个新工作目录，例如：

```bash
cp -R liangqin-contract-pricing /path/to/work/liangqin-contract-pricing
cd /path/to/work/liangqin-contract-pricing
```

### 2. 初始化 git

```bash
git init
git add .
git commit -m "chore: initialize public release skeleton"
```

### 3. 在 GitHub 创建公开仓库

如果你本机已安装 GitHub CLI，可直接：

```bash
gh repo create drizzlep/liangqin-contract-pricing --public --source=. --remote=origin --push
```

如果你想先在网页上创建仓库，也可以：

1. 打开 `https://github.com/drizzlep`
2. 新建 `liangqin-contract-pricing`
3. 创建空仓库
4. 回到本地执行：

```bash
git remote add origin git@github.com:drizzlep/liangqin-contract-pricing.git
git branch -M main
git push -u origin main
```

## 首次发布后的建议动作

1. 在 GitHub 仓库首页补：
   - Topics
   - Description
   - Website（如有）
2. 检查 GitHub Actions 是否正常触发
3. 在 README 第一屏再次确认：
   - 依赖 `liangqin-pricing`
   - 不是法律合同审核
4. 再准备第一版 Release Tag，例如：

```bash
git tag v0.1.0
git push origin v0.1.0
```

## 建议的仓库描述

可以直接用这句：

> Liangqin Ji Mu formal contract pricing audit companion skill. Extracts pricing fields from contracts and validates them against liangqin-pricing.

## 建议的 Topics

- `ocr`
- `contract-audit`
- `pricing-audit`
- `paddleocr`
- `ai-agent`
- `skill`
- `liangqin`

## 公开边界提醒

公开仓库前再次确认：

- 不要上传真实合同 PDF
- 不要上传客户个人信息
- 不要上传内部私有价格目录
- 不要上传未脱敏运行输出

如果某部分能力必须依赖私有资产，请在 README 里明确写成 dependency 或 private runtime requirement。
