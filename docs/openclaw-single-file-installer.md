# 良禽佳木 Skill 单文件安装器说明

## 1. 这是什么

这是把整个良禽佳木报价 skill 打成 `一个文件` 的安装方案。

生成后你会得到一个文件，例如：

```bash
liangqin-pricing-installer-YYYYMMDD.sh
```

这个文件本身就已经包含：

- skill 本体
- 当前价格索引
- 当前规则
- 安装逻辑
- 发布逻辑

## 2. 适合什么场景

适合你以后想做到这件事：

`只发 1 个文件，再给 OpenClaw 一段话，让它自己安装。`

## 3. 生成命令

在当前项目目录执行：

```bash
bash scripts/build_single_file_installer.sh
```

默认会在：

```bash
./dist/
```

生成一个单文件安装器。

## 4. OpenClaw 可以怎么安装这个文件

如果对方环境允许 OpenClaw 执行本地 shell 命令，你可以直接对 OpenClaw 说：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木报价 skill 安装到 shared skills，并同步到 workspace。安装完成后再做一次 fresh 测试。
```

如果你想让它安装后用指定问题测试，可以说：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，并用“我要做个北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，多少钱？”做一次 fresh 测试。
```

如果你担心对方环境开了联网搜索，更推荐直接用这版：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木报价 skill 安装到 shared skills，并同步到 workspace。安装完成后，良禽相关问题只能按 liangqin-pricing 当前资料回答；资料没明确写到，就直接说“现有良禽资料未明确”或“当前不能替你确认”，不要把联网搜索结果和行业常识写成良禽资料。然后用“良禽佳木可以选国产五金和进口五金吗？良禽有BLUM的五金，是什么啊？”做一次 fresh 测试，并把完整结果告诉我。
```

## 5. 这个单文件安装器默认会做什么

默认会自动完成：

1. 解出 skill 文件
2. 安装到 `~/.openclaw/skills/liangqin-pricing`
3. 发布到 `~/.openclaw/workspace/skills/liangqin-pricing`
4. 跑一次 fresh 测试

如果你要专门验收“是否混入外部五金知识”，安装后建议再手动补测一次：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --preset hardware-boundary
```

## 6. 如果不想自动测试

可以执行：

```bash
sh liangqin-pricing-installer-YYYYMMDD.sh --skip-test
```

## 7. 如果云端路径不是默认目录

可以带参数：

```bash
sh liangqin-pricing-installer-YYYYMMDD.sh --skills-root /你的skills根目录 --workspace-dest /你的workspace技能目录/liangqin-pricing --skip-test
```

所以它也可以兼容一部分云端环境。

## 8. 最重要的提醒

这个方案的前提是：

- OpenClaw 有权限访问这个安装器文件
- OpenClaw 有权限执行 shell / python3
- OpenClaw 有权限写目标 skill 目录

如果这些权限都具备，你就真的可以做到：

`发 1 个文件 + 给 1 段话 = 完成安装`
