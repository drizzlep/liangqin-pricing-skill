# 良禽佳木 Skill 压缩包交付说明

## 1. 目标

把当前这套 shared skill 打成一个可以直接发给其他 OpenClaw 用户使用的 zip 包。

压缩包方案的原则是：

- 对外只发一个 zip
- 对方不需要理解内部 Python 逻辑
- 对方只需要解压、发布、测试

## 2. 打包命令

在当前项目目录执行：

```bash
bash scripts/package_openclaw_skill.sh
```

默认会从下面这个 shared skill 目录取内容：

```bash
~/.openclaw/skills/liangqin-pricing
```

默认输出到：

```bash
./dist/liangqin-pricing-openclaw-YYYYMMDD.zip
```

如果你想改输出目录：

```bash
bash scripts/package_openclaw_skill.sh /你的输出目录
```

## 3. 压缩包里包含什么

这个 zip 会保留真正需要交付给别人的内容：

- `SKILL.md`
- `README.md`
- `data/current/`
- `references/current/`
- `scripts/`
- `sources/inbox/README.md`

同时会补齐这些后续维护会用到的目录：

- `data/versions/`
- `sources/archived/`
- `reports/validation/`
- `reports/diffs/`

不会打进包里的内容：

- `__pycache__/`
- `*.pyc`
- 本地缓存垃圾文件

## 4. 先分清是哪一种 OpenClaw

同一个 zip 包可以同时给这两类用户：

- 本地部署的小龙虾
- 云端部署的小龙虾

但两者的安装方式不要混用。

你对外发包时，建议永远同时附上下面两份文档：

- [openclaw-skill-local-install.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-local-install.md)
- [openclaw-skill-cloud-deploy.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-cloud-deploy.md)
- [openclaw-skill-delivery-message-templates.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-delivery-message-templates.md)
- [openclaw-skill-one-page-faq.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-one-page-faq.md)
- [openclaw-skill-delivery-kit.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-delivery-kit.md)

判断方式很简单：

- 如果对方能直接在自己的电脑终端里操作 `~/.openclaw/skills/`，就看“本地部署版”
- 如果对方是在服务器、容器、云主机、平台环境里运行 OpenClaw，就看“云端部署版”

## 5. 发给别人怎么安装

把 zip 发给对方后，让对方执行下面 4 步：

### 第一步：准备 skills 目录

```bash
mkdir -p ~/.openclaw/skills
```

### 第二步：解压

```bash
unzip liangqin-pricing-openclaw-YYYYMMDD.zip -d ~/.openclaw/skills
```

解压完成后，目录应该是：

```bash
~/.openclaw/skills/liangqin-pricing
```

### 第三步：发布到 OpenClaw workspace

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/publish_skill.py
```

### 第四步：做一次 fresh 测试

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py
```

如果想换成自己的测试问题：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --message "我要做个北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，多少钱？"
```

上面这一套，更适合“本地部署版”。

如果是“云端部署版”，不要直接照搬上面的终端路径写法，优先按云端部署文档操作。

## 6. 以后你升级版本怎么发

以后你只需要重复这套流程：

1. 先在你自己的机器上更新 shared skill
2. 再执行：

```bash
bash scripts/package_openclaw_skill.sh
```

3. 把新生成的 zip 发给对方
4. 对方覆盖原来的 `~/.openclaw/skills/liangqin-pricing`
5. 对方重新执行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/publish_skill.py
```

## 7. 最推荐的发包口径

你对外就发两样东西最合适：

- 一个 zip 包
- 一段安装命令

你可以直接把下面这段发给对方：

```bash
mkdir -p ~/.openclaw/skills
unzip liangqin-pricing-openclaw-YYYYMMDD.zip -d ~/.openclaw/skills
python3 ~/.openclaw/skills/liangqin-pricing/scripts/publish_skill.py
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py
```

## 8. 你自己内部怎么理解这件事

你可以把这套交付理解成两层：

- `~/.openclaw/skills/liangqin-pricing`
  这是 shared skill 母版
- `~/.openclaw/workspace/skills/liangqin-pricing`
  这是 OpenClaw 实际运行时吃到的副本

所以别人安装完 zip 以后，还必须执行一次：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/publish_skill.py
```

否则 shared skill 已经放进去了，但 workspace 里还是旧版本。
