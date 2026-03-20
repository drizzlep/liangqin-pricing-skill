# 良禽佳木 Skill 云端部署说明

## 1. 适用对象

这份说明只给下面这类情况用：

- OpenClaw 跑在云服务器
- OpenClaw 跑在 Docker / 容器环境
- OpenClaw 跑在远程 Linux 主机
- OpenClaw 不是运行在使用者自己的本地电脑上

如果对方是在自己电脑本地跑 OpenClaw，不要用这份，改看：

- [openclaw-skill-local-install.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-local-install.md)

## 2. 先说结论

云端部署和本地部署，`skill 包本体可以一样`，也就是同一个 zip 可以共用。

但下面这些通常不一样：

- 解压路径
- 运行用户
- 文件权限
- 是否允许直接写 `~/.openclaw/`
- 是否需要在镜像构建阶段就把 skill 放进去
- 是否需要重启 OpenClaw 服务

所以：

- 可以共用同一个 zip
- 不要共用同一份安装步骤

## 3. 云端最稳的交付原则

云端环境里，建议统一按下面这个原则处理：

1. 先把 zip 上传到服务器或镜像构建环境
2. 解压到 OpenClaw 实际运行账户可访问的位置
3. 确保 skill 最终落到 shared skill 目录
4. 再执行 `publish_skill.py`
5. 必要时重启 OpenClaw 服务
6. 最后再做 fresh 测试

## 4. 推荐目录口径

如果你的云端 OpenClaw 也是标准用户目录结构，推荐仍然落到：

```bash
~/.openclaw/skills/liangqin-pricing
```

如果不是标准用户目录，就要以云端那台机器的实际 OpenClaw skill 根目录为准。

关键不是路径长什么样，而是最终要满足这两件事：

- shared skill 被正确放进去
- `publish_skill.py` 能把它同步到 workspace

## 5. 云端部署的两种常见方式

### 方式 A：服务器上直接安装

适合：

- 你能登录服务器
- 服务器文件系统可写
- OpenClaw 以某个固定用户运行

做法：

```bash
mkdir -p ~/.openclaw/skills
unzip liangqin-pricing-openclaw-YYYYMMDD.zip -d ~/.openclaw/skills
python3 ~/.openclaw/skills/liangqin-pricing/scripts/publish_skill.py
python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --message "我要做个北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，多少钱？"
```

如果云端 OpenClaw 有 service 管理，发布后建议补一次重启。

### 方式 B：打进镜像或挂载卷

适合：

- OpenClaw 跑在 Docker
- OpenClaw 跑在容器平台
- 环境是镜像部署，不适合上线后手工改文件

做法原则：

1. 在镜像构建阶段，把 `liangqin-pricing` 整个目录复制进去
2. 让它落到容器里的 shared skills 路径
3. 启动后执行一次：

```bash
python3 /实际路径/liangqin-pricing/scripts/publish_skill.py
```

4. 再执行一次 fresh 测试

如果是挂载卷模式，也可以把解压后的 `liangqin-pricing` 目录直接挂进去。

## 6. 云端要特别注意的 4 个点

### 第一：运行用户

你执行脚本的用户，最好和 OpenClaw 实际运行用户一致。

否则常见问题是：

- 你装进了 A 用户目录
- OpenClaw 实际跑在 B 用户目录
- 最终技能看起来“装了”，其实没生效

### 第二：权限

要确认下面两个目录可写：

- shared skills 目录
- workspace skills 目录

否则 `publish_skill.py` 会失败，或者表面成功、实际没同步进去。

### 第三：持久化

如果容器重建就丢文件，那不要靠手工安装。

应该改成：

- 镜像内置
  或
- 挂载持久卷

### 第四：重启

有些云端 OpenClaw 环境会缓存技能列表。

如果你已经发布了 skill，但前台还是旧版本，优先检查：

- 有没有重启服务
- 有没有复用旧 session
- workspace 里是不是还是旧副本

## 7. 你给云端同事时最推荐的话术

你可以直接这么说：

“这个 zip 是 skill 本体，本地版和云端版内容一样，但云端不要直接照搬本地安装步骤。云端只要把 `liangqin-pricing` 目录放进 OpenClaw 的 shared skills 路径，再执行一次 `publish_skill.py` 同步到 workspace，然后用 fresh session 验证就可以。”  

## 8. 最简判断口径

如果对方问你一句：

“我拿到这个 zip，能不能直接照着本地命令装？”

你可以这样判断：

- 能直接操作自己的 `~/.openclaw/`，按本地版
- 是远程服务器 / 容器 / 平台环境，按云端版
