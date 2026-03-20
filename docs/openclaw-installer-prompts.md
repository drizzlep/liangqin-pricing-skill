# 良禽佳木 Skill 给 OpenClaw 的安装提示词

## 1. 本地标准版

这段适合：

- OpenClaw 跑在本地电脑
- OpenClaw 能访问安装器文件
- OpenClaw 有权限执行 shell 和 python3

直接复制给 OpenClaw：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木报价 skill 安装到 shared skills，并同步到 workspace。安装完成后，再做一次 fresh 测试，确认 skill 已经生效。最后把安装结果告诉我。
```

## 2. 本地标准版（带指定测试问题）

如果你希望它安装完后顺手测一个问题，直接复制这段：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木报价 skill 安装到 shared skills，并同步到 workspace。安装完成后，用“我要做个北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，多少钱？”做一次 fresh 测试。最后把安装结果和测试结果告诉我。
```

## 3. 云端标准版

这段适合：

- OpenClaw 跑在服务器
- OpenClaw 跑在容器
- 安装器文件已经放在云端环境可访问的位置

直接复制给 OpenClaw：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木报价 skill 安装到当前环境的 shared skills，并同步到 workspace。如果当前环境不是默认 ~/.openclaw 路径，请按实际技能目录完成安装。安装完成后告诉我最终安装路径和同步结果。
```

## 4. 云端标准版（跳过测试）

如果你担心云端环境不方便立即测试，可以用这一版：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木报价 skill 安装到当前环境的 shared skills，并同步到 workspace。安装时跳过测试，只汇报最终安装路径和同步结果。
```

## 5. 最短一句话版

如果你只想给一句最短的话，可以直接用：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，安装良禽佳木报价 skill，并同步到 workspace。
```

## 6. 你自己替换的只有一处

以后你每次只需要替换这一个部分：

```text
/绝对路径/liangqin-pricing-installer-YYYYMMDD.sh
```

比如你本机当前版本就可以写成：

```text
/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/dist/liangqin-pricing-installer-20260317.sh
```

## 7. 最稳的用法

我更推荐你以后优先用这一版：

```text
请运行 /Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/dist/liangqin-pricing-installer-20260317.sh，把良禽佳木报价 skill 安装到 shared skills，并同步到 workspace。安装完成后，再做一次 fresh 测试，确认 skill 已经生效。最后把安装结果告诉我。
```
