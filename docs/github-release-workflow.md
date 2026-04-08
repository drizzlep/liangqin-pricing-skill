# GitHub Release Workflow

这个仓库以后发布到 GitHub，统一走这条专用流程，不再手工拼命令。

## 默认发布命令

在仓库根目录执行：

```bash
python3 scripts/create_github_release.py
```

这个命令默认会做下面这些事：

1. `git fetch origin`
2. 校验当前分支必须是 `main`
3. 校验 `HEAD` 必须已经和 `origin/main` 对齐
4. 运行全量测试：

```bash
python3 -m unittest discover -s skill/liangqin-pricing/tests
```

5. 从当前 `HEAD` 生成干净快照
6. 打包 release 附件：
   - `liangqin-pricing-openclaw-YYYYMMDD.zip`
   - `liangqin-pricing-installer-YYYYMMDD.sh`
   - `liangqin-pricing-github-release-YYYYMMDD.patch`
7. 自动推断下一个 date-based tag，例如：
   - `v2026.03.30`
   - 同日再次发布则递增成 `v2026.03.30.1`
8. 生成基于真实 commit 的 release notes
9. 调用 `gh release create ...` 发布到 GitHub Releases

## 常用参数

只构建附件与说明，不真正创建 Release：

```bash
python3 scripts/create_github_release.py --dry-run
```

手动指定 tag 和标题：

```bash
python3 scripts/create_github_release.py --tag v2026.03.30.1 --title "v2026.03.30.1 - Hotfix release"
```

使用自定义 release notes：

```bash
python3 scripts/create_github_release.py --notes-file /absolute/path/to/release-notes.md
```

## 这次版本最推荐的发布顺序

如果这次发布的重点是：

- 材质简称归一化
- 特殊柜体自然说法识别
- `check_runtime_health.py` 运行环境自检
- `refresh_and_test.py` 先自检再 smoke test

建议统一按下面顺序发：

1. 先在本地确认工作区内容正确
2. 执行 dry run，先生成附件和说明：

```bash
python3 scripts/create_github_release.py --dry-run
```

3. 检查 `dist/` 里至少有这 3 个附件：
   - `liangqin-pricing-openclaw-YYYYMMDD.zip`
   - `liangqin-pricing-installer-YYYYMMDD.sh`
   - `liangqin-pricing-github-release-YYYYMMDD.patch`
4. 再正式执行：

```bash
python3 scripts/create_github_release.py
```

## 推荐 release notes 模板

如果你想手动指定说明，可以直接用这版：

```markdown
本次版本重点修复两类真实迁移问题：

- 扩大材质简称归一化，减少“北美黑胡桃 / 白橡 / 白蜡”这类输入在报价前丢失标准材质映射的情况
- 扩大特殊柜体自然说法识别，补齐“双面柜门 / 两面开门 / 无底板预留”等变体表达

同时补上运行环境自检链路：

- 新增 `check_runtime_health.py`，用于区分“技能没装完整”“价格索引文件缺失”“records 为空”“数据正常但筛选没命中”
- `refresh_and_test.py` 现在会在 fresh session 前先执行运行环境自检，环境异常时直接停止，不再误把坏环境当成 skill 逻辑问题

云端环境特别提醒：

- GitHub Release 能解决“把新能力发出去”的问题
- 但云端 OpenClaw 如果技能目录不固定，仍然需要显式指定实际 `skills root` 和 `workspace skill` 路径
- 安装后建议先运行 `check_runtime_health.py`，再运行 `refresh_and_test.py`
```

## 发给云端同事时的最短说明

如果对方是云端 OpenClaw，release 发出去后，最短建议说明不要只写“请安装最新版”，而是直接附这一句：

```text
这是 liangqin-pricing 的新 GitHub Release。请不要假设当前环境一定是默认 ~/.openclaw 路径。请先确认 OpenClaw 实际使用的 shared skills 目录和 workspace skills 目录，再安装 release 附件里的 zip 或单文件安装器。安装完成后，先运行 check_runtime_health.py，再运行 refresh_and_test.py，并把最终实际路径和结果回传给我。
```

## 正确发布顺序

推荐固定顺序：

1. 功能分支开发与提交
2. 分支上先跑针对性测试
3. 合并到 `main`
4. 在 `main` 上再跑全量测试
5. 推送 `main`
6. 执行 `python3 scripts/create_github_release.py`

不要跳过第 5 步。

这个脚本默认要求当前 `HEAD == origin/main`，就是为了避免从未推送提交或脏工作区直接发 release。

## 建议触发关键词

以后如果你想让我直接进入这条发布流，可以直接说这些句子：

- `发布这个技能`
- `发 GitHub Release`
- `把当前 main 发版`
- `按发布流程走`
- `给 liangqin-pricing-skill 发 release`
- `把这个仓库发布出去`

如果你还希望我顺带把分支合到 `main`，可以直接说：

- `合并到 main 并发布`
- `推 main 然后发 release`
- `按正式发布流程执行`
