# 良禽佳木 Skill 交付目录建议

## 1. 这份清单是干什么的

这份清单专门解决一个问题：

`我以后要把这个 skill 发给别人时，到底该发哪几个文件？`

你不用每次重新想，直接按下面发就行。

## 2. 永远要发的核心文件

无论对方是本地部署还是云端部署，这 1 个文件都要发：

- [liangqin-pricing-openclaw-20260317.zip](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/dist/liangqin-pricing-openclaw-20260317.zip)

这就是 skill 本体包。

如果你想进一步简化成“1 个文件 + 1 段话让 OpenClaw 自己装”，也可以改发：

- [openclaw-single-file-installer.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-single-file-installer.md)
- [openclaw-installer-prompts.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-installer-prompts.md)

## 3. 如果对方是本地部署，要发什么

建议你发这 3 样：

1. zip 安装包
2. 本地部署说明
3. 小白版 1 页说明

对应文件：

- [liangqin-pricing-openclaw-20260317.zip](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/dist/liangqin-pricing-openclaw-20260317.zip)
- [openclaw-skill-local-install.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-local-install.md)
- [openclaw-skill-one-page-faq.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-one-page-faq.md)

如果你想再省事一点，还可以额外附上：

- [openclaw-skill-delivery-message-templates.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-delivery-message-templates.md)

## 4. 如果对方是云端部署，要发什么

建议你发这 3 样：

1. zip 安装包
2. 云端部署说明
3. 小白版 1 页说明

对应文件：

- [liangqin-pricing-openclaw-20260317.zip](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/dist/liangqin-pricing-openclaw-20260317.zip)
- [openclaw-skill-cloud-deploy.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-cloud-deploy.md)
- [openclaw-skill-one-page-faq.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-one-page-faq.md)

如果对方是技术同事，也可以再补一份：

- [openclaw-skill-zip-delivery.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-zip-delivery.md)

## 5. 如果是老用户升级，要发什么

建议你发这 2 样就够：

1. 新版 zip 安装包
2. 升级通知话术

对应文件：

- [liangqin-pricing-openclaw-20260317.zip](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/dist/liangqin-pricing-openclaw-20260317.zip)
- [openclaw-skill-delivery-message-templates.md](/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/docs/openclaw-skill-delivery-message-templates.md)

## 6. 最简单的发法

如果你完全不想判断太多，直接按下面发：

### 给普通用户

- zip 安装包
- 小白版 1 页说明

### 给技术同事

- zip 安装包
- 本地部署说明 或 云端部署说明
- 标准交付话术

## 7. 以后你自己怎么维护这套交付目录

以后每次出新版本，只需要做两件事：

1. 重新打一个新的 zip
2. 把这里面引用的 zip 名称换成新版文件名

打包命令：

```bash
bash scripts/package_openclaw_skill.sh
```

## 8. 一句话记忆版

你以后可以这样记：

- `skill 本体` 永远发 zip
- `怎么安装` 看本地版还是云端版
- `给小白看` 发 1 页 FAQ
- `给同事发消息` 用标准话术模板
