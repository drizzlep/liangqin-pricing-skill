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
