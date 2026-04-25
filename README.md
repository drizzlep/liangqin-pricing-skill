# liangqin-pricing-skill

良禽佳木 OpenClaw 双 skill 源码仓库。

这个仓库面向两类用途：

- 安装当前可直接使用的报价 skill
- 维护价格索引、规则、打包脚本和安装器

## 快速迁移到另一个 OpenClaw

如果你只是想把这套良禽 skill 安装到另一个 OpenClaw，按下面做就行：

### 第一步：拉下仓库

```bash
git clone https://github.com/drizzlep/liangqin-pricing-skill.git
cd liangqin-pricing-skill
```

### 第二步：生成单文件安装器

```bash
bash scripts/build_single_file_installer.sh
```

生成后会得到一个文件，例如：

```bash
dist/liangqin-pricing-installer-YYYYMMDD.sh
```

### 第三步：交给 OpenClaw 安装

把下面这段话直接发给 OpenClaw：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木的 pricing + contract-review 两个 skill 一起安装到 shared skills，并同步到 workspace。安装完成后，再做一次 fresh 测试，确认 skill 已经生效。最后把安装结果告诉我。
```

### 关键说明

这个仓库里的安装包已经带了当前可用的：

- 价格索引
- 报价规则
- 设计师追加规则 layer
- 合同审核入口与运行时代码
- 安装和发布脚本

所以就算目标环境重建过 `workspace/skills`，也可以把 `报价 + 合同审核` 一起恢复。

## 目录结构

- `skill/liangqin-pricing/`
  当前 shared skill 源码快照
- `skill/liangqin-contract-review/`
  当前合同审核 shared skill 聊天壳
- `apps/contract-review/`
  合同审核并列应用模块，面向本地 AI Agent 和后续渠道 adapter
- `scripts/`
  打包 zip、生成单文件安装器等仓库级脚本
- `docs/`
  安装说明、迁移说明、交付话术、小白版 FAQ

## 合同审核模块

当前仓库已经补了一个并列应用模块：

- `apps/contract-review/`

它和 `skill/liangqin-pricing/` 的边界是：

- `skill/liangqin-pricing/` 继续只管报价 skill
- `apps/contract-review/` 负责手工批次投递、拆单、任务 staging、审阅骨架和后续渠道接入

快速试跑：

```bash
python3 apps/contract-review/cli/manual_batch.py --batch-dir /absolute/path/to/batch
```

说明：

- 默认会对图片和扫描件尝试走 `PaddleOCR`
- 如果当前机器还没装 OCR 依赖，可先加 `--ocr-backend disabled` 只跑 ingest 骨架

相关文档：

- `docs/contract-review/README.md`
- `docs/contract-review/batch-folder-spec.md`

## 最常用的两件事

### 1. 打包 zip

```bash
bash scripts/package_openclaw_skill.sh
```

### 2. 生成单文件安装器

```bash
bash scripts/build_single_file_installer.sh
```

## 当前推荐安装方式

如果你只是要把 skill 迁移到另一个 OpenClaw，优先使用单文件安装器。

如果对方是云端 OpenClaw，且你不确定它的技能目录是不是默认 `~/.openclaw`，不要让它直接猜默认路径。优先做法是：

1. 用 GitHub Release 附件里的 zip 或单文件安装器
2. 先确认云端实际 `shared skills` 和 `workspace skills` 路径
3. 安装完成后确认 `liangqin-pricing` 和 `liangqin-contract-review` 都已同步到 workspace
4. 再运行 `check_runtime_health.py`
5. 自检通过后再运行 `refresh_and_test.py`

相关文档：

- `docs/openclaw-single-file-installer.md`
- `docs/openclaw-installer-prompts.md`
- `docs/github-release-workflow.md`
- `docs/openclaw-skill-one-page-faq.md`
- `docs/openclaw-skill-delivery-kit.md`
