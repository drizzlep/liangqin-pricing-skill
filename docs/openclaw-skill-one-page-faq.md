# 良禽佳木报价 Skill 小白版 1 页说明

## 1. 这是什么

这是一个给 OpenClaw 用的“报价技能包”。

装好以后，用户可以直接问：

- `我要做个北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，多少钱？`
- `樱桃木罗胖餐桌 1.6 米多少钱？`
- `做个白橡木玄关柜 1.2*2.4*0.4，大概多少钱？`

## 2. 没有最初的 Excel 和 Doc，能不能直接报价

可以。

因为这个安装包里，已经带了当前可用的：

- 价格索引
- 报价规则
- Skill 运行脚本

所以对方就算没有最初那两个原始文件：

- 产品目录 `Excel`
- 定制规则 `Doc`

也可以直接用来报价。

## 3. 那什么时候才需要 Excel 和 Doc

只有一种情况需要：

- 以后你想自己更新价格或更新规则

也就是说：

- `直接使用当前报价`：不需要原始表格
- `以后自己维护新版`：需要新的 `Excel + Doc`

## 4. 如果是本地部署的小龙虾，怎么装

如果 OpenClaw 是跑在自己电脑上的，直接执行这 4 条：

```bash
mkdir -p ~/.openclaw/skills
unzip liangqin-pricing-openclaw-YYYYMMDD.zip -d ~/.openclaw/skills
python3 ~/.openclaw/skills/liangqin-pricing/scripts/publish_skill.py
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py
```

## 5. 如果是云端部署的小龙虾，怎么办

如果 OpenClaw 是跑在：

- 云服务器
- Docker
- 容器
- 远程 Linux

那就不要直接照搬本地安装命令。

云端版的原则只有一句话：

把 `liangqin-pricing` 这个目录放进 OpenClaw 的 shared skills 路径，再执行一次 `publish_skill.py`，必要时重启服务。

如果是云端环境，最好把安装包交给技术同事处理。

## 6. 我怎么判断自己是本地版还是云端版

你只要问自己一句：

`OpenClaw 是跑在我自己的电脑里，还是跑在服务器/容器里？`

判断方式：

- 在自己电脑里跑：按本地版装
- 在服务器或容器里跑：按云端版装

## 7. 以后收到新版安装包，怎么更新

如果你已经装过旧版，本地最简单的更新方式是：

```bash
rm -rf ~/.openclaw/skills/liangqin-pricing
unzip liangqin-pricing-openclaw-YYYYMMDD.zip -d ~/.openclaw/skills
python3 ~/.openclaw/skills/liangqin-pricing/scripts/publish_skill.py
```

## 8. 最后记住一句话

这个安装包本身已经带了当前可用的报价数据。

所以：

- `没有原始 Excel / Doc，也能直接报价`
- `只有以后要自己更新版本，才需要新的 Excel / Doc`
