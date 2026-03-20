# 良禽佳木 Skill 本地部署安装说明

## 1. 适用对象

这份说明只给下面这类用户用：

- OpenClaw 跑在自己电脑上
- 可以直接打开终端
- 可以直接操作 `~/.openclaw/`

如果对方是服务器、云主机、容器、远程平台环境，不要用这份，改看：

- [openclaw-skill-cloud-deploy.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-cloud-deploy.md)

## 2. 收到什么文件

你发给对方一个 zip 包就够了，例如：

```bash
liangqin-pricing-openclaw-20260317.zip
```

## 3. 安装步骤

### 第一步：准备目录

```bash
mkdir -p ~/.openclaw/skills
```

### 第二步：解压到 shared skills 目录

```bash
unzip liangqin-pricing-openclaw-20260317.zip -d ~/.openclaw/skills
```

解压后应该看到：

```bash
~/.openclaw/skills/liangqin-pricing
```

### 第三步：发布到 workspace

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/publish_skill.py
```

这一步很关键。

因为：

- `~/.openclaw/skills/liangqin-pricing`
  是 shared skill 母版
- `~/.openclaw/workspace/skills/liangqin-pricing`
  才是 OpenClaw 实际运行时吃到的副本

### 第四步：做一次 fresh 测试

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py
```

如果要换成自己的测试问题：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --message "我要做个北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，多少钱？"
```

## 4. 升级时怎么做

如果你收到的是新版本 zip，不需要手改内部文件。

直接按这套流程：

```bash
rm -rf ~/.openclaw/skills/liangqin-pricing
unzip liangqin-pricing-openclaw-YYYYMMDD.zip -d ~/.openclaw/skills
python3 ~/.openclaw/skills/liangqin-pricing/scripts/publish_skill.py
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py
```

## 5. 常见判断

如果你满足下面 3 条，基本就属于本地部署：

- OpenClaw 在你的电脑上运行
- 你能直接操作自己的用户目录
- 你能直接运行 `python3 ~/.openclaw/...`

只要满足这 3 条，就优先按本地版安装。
