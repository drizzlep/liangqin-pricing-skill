# 良禽佳木 Skill 标准交付话术

## 1. 迁移防污染版（推荐优先发）

这段适合直接发给“你不确定对方有没有开联网搜索”的同事。

```text
我发你一个良禽佳木报价 skill 的安装包。

你安装完以后，良禽相关问题请优先按这个 skill 的资料回答，不要把联网搜索结果、行业常识、品牌百科，写成“良禽资料里就是这样”。

尤其是这类问题：
- 国产五金 / 进口五金
- BLUM / 百隆
- 海蒂诗 / DTC
- 五金品牌对比
- “这条是不是良禽资料”

如果当前良禽资料没明确写到，就直接回答“现有良禽资料未明确”或“当前不能替你确认”，再建议联系设计师或门店确认，不要自行扩展。

你安装完后请至少做两次 fresh 测试：
1. 我要做个北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，多少钱？
2. 良禽佳木可以选国产五金和进口五金吗？良禽有BLUM的五金，是什么啊？

第二题如果回答里出现 BLUMOTION、CLIP top、TANDEMBOX、SERVO-DRIVE、阻尼铰链、抽屉导轨、进口五金品牌对比这些内容，就说明还混进了外部知识，需要继续调。
```

## 2. 本地部署版

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

如果你想专门测“联网会不会把五金常识混进来”，可以执行：

python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --preset hardware-boundary

如果你是云端部署，不要直接照搬这套命令，改看云端部署说明。
```

## 3. 云端部署版

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

## 3A. GitHub Release + 云端未知路径版（推荐）

这段适合：

- 你准备把新版直接发到 GitHub Releases
- 对方是云端 OpenClaw
- 你不确定对方是不是默认 `~/.openclaw`

```text
我这边已经把 liangqin-pricing 的新版发到 GitHub Release。

这次版本除了报价规则增强，还补了两个排障能力：
1. `check_runtime_health.py`：先判断当前环境是不是装完整了
2. `refresh_and_test.py`：fresh session 前会先做运行环境自检

但请不要假设你那边一定是默认 ~/.openclaw 路径。

你那边请按下面顺序做：

1. 先确认当前 OpenClaw 实际使用的 shared skills 根目录和 workspace skills 根目录
2. 再安装 GitHub Release 里的 zip 或单文件安装器
3. 如果安装器支持自定义目录，请显式传入真实路径，不要靠默认值猜
4. 安装完成后，先运行：
   python3 /最终workspace技能目录/liangqin-pricing/scripts/check_runtime_health.py
5. 只有自检通过，再运行：
   python3 /最终workspace技能目录/liangqin-pricing/scripts/refresh_and_test.py --skill-dir /最终workspace技能目录/liangqin-pricing

如果自检失败，就不要继续报价测试，直接把：
- shared skills 实际目录
- workspace skills 实际目录
- 最终安装路径
- check_runtime_health.py 的完整输出

发给我。
```

## 4. 升级通知版

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

## 5. 验收结果回收版

这段适合你在对方装完以后，催他把“是否被联网污染”结果发回来。

```text
你那边麻烦再补一条 fresh session 测试：

“良禽佳木可以选国产五金和进口五金吗？良禽有BLUM的五金，是什么啊？”

这题正确口径应该是：
- 只按良禽当前资料回答
- 如果资料没明确写到，就明确说未明确
- 不能补外部品牌百科或行业对比

你把完整回复原文发我，我帮你看有没有混进外部知识。
```

## 6. 判断对方属于哪一种

你自己发消息前，可以先用这句判断：

```text
你这边的小龙虾是跑在你自己电脑本地，还是跑在服务器 / Docker / 云端环境里？
```

如果对方回答：

- `我自己电脑上跑的`
  就发“本地部署版”
- `服务器 / Docker / 容器 / 云主机`
  就发“云端部署版”

## 7. 最短口径

如果你懒得发很长内容，可以只发这一句：

```text
这个 zip 本地版和云端版内容一样，但安装完以后，良禽相关回答要优先按 skill 资料走；资料没写到就说未明确，不要用联网搜索和行业常识补成良禽结论。
```
