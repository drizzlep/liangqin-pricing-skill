# liangqin-pricing-skill

良禽佳木 OpenClaw 报价 skill 源码仓库。

这个仓库面向两类用途：

- 安装当前可直接使用的报价 skill
- 维护价格索引、规则、打包脚本和安装器

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

相关文档：

- `docs/openclaw-single-file-installer.md`
- `docs/openclaw-installer-prompts.md`
- `docs/openclaw-skill-one-page-faq.md`
