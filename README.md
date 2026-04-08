# liangqin-pricing-skill

良禽佳木 OpenClaw 报价 skill 源码仓库。

这个仓库面向两类用途：

- 安装当前可直接使用的报价 skill
- 维护价格索引、规则、打包脚本和安装器

## 快速迁移到另一个 OpenClaw

如果你只是想把这个报价 skill 安装到另一个 OpenClaw，按下面做就行：

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
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木报价 skill 安装到 shared skills，并同步到 workspace。安装完成后，再做一次 fresh 测试，确认 skill 已经生效。最后把安装结果告诉我。
```

### 关键说明

这个仓库里的 skill 已经带了当前可用的：

- 价格索引
- 报价规则
- 设计师追加规则 layer
- 安装和发布脚本

所以就算目标环境没有最初的产品目录 Excel 和定制规则 Doc，也可以直接报价。

## 目录结构

- `skill/liangqin-pricing/`
  当前 shared skill 源码快照
- `scripts/`
  打包 zip、生成单文件安装器等仓库级脚本
- `docs/`
  安装说明、迁移说明、交付话术、小白版 FAQ

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
3. 安装完成后先运行 `check_runtime_health.py`
4. 自检通过后再运行 `refresh_and_test.py`

相关文档：

- `docs/openclaw-single-file-installer.md`
- `docs/openclaw-installer-prompts.md`
- `docs/github-release-workflow.md`
- `docs/openclaw-skill-one-page-faq.md`
- `docs/openclaw-skill-delivery-kit.md`
