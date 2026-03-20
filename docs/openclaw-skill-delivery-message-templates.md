# 良禽佳木 Skill 标准交付话术

## 1. 本地部署版

这段适合直接发给“本地电脑上运行 OpenClaw”的同事。

```text
我发你一个良禽佳木报价 skill 的安装包。

你如果是本地部署的小龙虾，直接按下面 4 步装：

1. mkdir -p ~/.openclaw/skills
2. unzip liangqin-pricing-openclaw-YYYYMMDD.zip -d ~/.openclaw/skills
3. python3 ~/.openclaw/skills/liangqin-pricing/scripts/publish_skill.py
4. python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py

如果你想用自己的问题测试，可以执行：

python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --message "你的测试问题"

如果你是云端部署，不要直接照搬这套命令，改看云端部署说明。
```

## 2. 云端部署版

这段适合直接发给“服务器 / Docker / 容器 / 云主机”的同事。

```text
我发你一个良禽佳木报价 skill 的 zip 包。

这个 zip 本体和本地版是一样的，但云端不要直接照搬本地安装步骤。

云端这边你只要做这几件事：

1. 把 zip 上传到服务器或镜像构建环境
2. 解压后把 liangqin-pricing 目录放进 OpenClaw 的 shared skills 路径
3. 执行一次 publish_skill.py，把 skill 同步到 workspace
4. 必要时重启 OpenClaw 服务
5. 最后用 fresh session 做一次测试

如果你那边也是标准 ~/.openclaw 目录结构，可以参考：

mkdir -p ~/.openclaw/skills
unzip liangqin-pricing-openclaw-YYYYMMDD.zip -d ~/.openclaw/skills
python3 ~/.openclaw/skills/liangqin-pricing/scripts/publish_skill.py

如果是容器或镜像部署，优先把 liangqin-pricing 整个目录直接打进镜像或挂到持久卷里。
```

## 3. 升级通知版

这段适合你后面发新版 skill 给已经装过的人。

```text
这是良禽佳木报价 skill 的新版安装包。

如果你之前已经装过，直接覆盖原来的 liangqin-pricing 目录，然后重新执行一次发布就可以。

本地版最简单的更新方式：

rm -rf ~/.openclaw/skills/liangqin-pricing
unzip liangqin-pricing-openclaw-YYYYMMDD.zip -d ~/.openclaw/skills
python3 ~/.openclaw/skills/liangqin-pricing/scripts/publish_skill.py
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py

如果你是云端版，不要直接照搬本地路径，还是按你们云端的 shared skills 路径覆盖后再执行 publish_skill.py。
```

## 4. 判断对方属于哪一种

你自己发消息前，可以先用这句判断：

```text
你这边的小龙虾是跑在你自己电脑本地，还是跑在服务器 / Docker / 云端环境里？
```

如果对方回答：

- `我自己电脑上跑的`
  就发“本地部署版”
- `服务器 / Docker / 容器 / 云主机`
  就发“云端部署版”

## 5. 最短口径

如果你懒得发很长内容，可以只发这一句：

```text
这个 zip 本地版和云端版内容一样，但安装方法不一样。本地版直接解压到 ~/.openclaw/skills 后执行 publish_skill.py；云端版要先放进 shared skills 路径，再同步到 workspace。
```
