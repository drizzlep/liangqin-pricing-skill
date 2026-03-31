# 良禽佳木 Skill 给 OpenClaw 的安装提示词

## 1. 迁移防污染版（推荐）

这段适合：

- 把 skill 迁移到别人的 OpenClaw
- 对方环境可能开了联网搜索
- 你希望它安装后优先服从良禽资料边界，不要混入行业常识

直接复制给 OpenClaw：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木报价 skill 安装到 shared skills，并同步到 workspace。

安装完成后，请按下面要求执行：

1. 后续凡是“良禽 / 良禽佳木”相关问题，优先使用 liangqin-pricing 这个 shared skill。
2. 如果当前环境开启了联网搜索，也不要把外部搜索结果、行业常识、品牌知识，写成“良禽资料里就是这样”。
3. 如果 liangqin-pricing 当前资料没有明确写到，必须直接回答“现有良禽资料未明确”或“当前不能替你确认”，并建议联系设计师或门店确认。
4. 对国产五金 / 进口五金 / BLUM / 百隆 / 海蒂诗 / DTC / 五金品牌对比这类问题，除非良禽资料明确写到，否则不要自行补充品牌百科、产品系列、体验描述、行业对比。
5. 安装完成后请用 fresh session 做 2 次测试：
   - 测试 1：“我要做个北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，多少钱？”
   - 测试 2：“良禽佳木可以选国产五金和进口五金吗？良禽有BLUM的五金，是什么啊？”
6. 第二题如果回答里出现 BLUMOTION、CLIP top、TANDEMBOX、SERVO-DRIVE、阻尼铰链、抽屉导轨、奥地利高端五金对比这类外部行业知识，视为测试不通过。

最后把安装结果、最终 skill 路径、两次测试原文结果一起告诉我。
```

## 2. 本地标准版

这段适合：

- OpenClaw 跑在本地电脑
- OpenClaw 能访问安装器文件
- OpenClaw 有权限执行 shell 和 python3

直接复制给 OpenClaw：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木报价 skill 安装到 shared skills，并同步到 workspace。安装完成后，再做一次 fresh 测试，确认 skill 已经生效。最后把安装结果告诉我。
```

## 3. 本地标准版（带指定测试问题）

如果你希望它安装完后顺手测一个问题，直接复制这段：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木报价 skill 安装到 shared skills，并同步到 workspace。安装完成后，用“我要做个北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，多少钱？”做一次 fresh 测试。最后把安装结果和测试结果告诉我。
```

## 4. 云端标准版

这段适合：

- OpenClaw 跑在服务器
- OpenClaw 跑在容器
- 安装器文件已经放在云端环境可访问的位置

直接复制给 OpenClaw：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木报价 skill 安装到当前环境的 shared skills，并同步到 workspace。如果当前环境不是默认 ~/.openclaw 路径，请按实际技能目录完成安装。安装完成后告诉我最终安装路径和同步结果。
```

## 5. 云端标准版（跳过测试）

如果你担心云端环境不方便立即测试，可以用这一版：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，把良禽佳木报价 skill 安装到当前环境的 shared skills，并同步到 workspace。安装时跳过测试，只汇报最终安装路径和同步结果。
```

## 6. 验收专用版（只测防污染）

如果对方已经装好了，你只想让它补一次“联网防污染”验收，直接复制这段：

```text
请用 fresh session 测试这句：“良禽佳木可以选国产五金和进口五金吗？良禽有BLUM的五金，是什么啊？”

要求：
- 只能基于 liangqin-pricing 当前资料回答
- 如果资料没明确写到，要直接说“现有良禽资料未明确”或“当前不能替你确认”
- 不要补充 BLUMOTION、CLIP top、TANDEMBOX、SERVO-DRIVE、阻尼铰链、抽屉导轨、进口五金品牌对比这类外部知识

最后把完整回复原文发给我。
```

## 7. 最短一句话版

如果你只想给一句最短的话，可以直接用：

```text
请运行 /绝对路径/liangqin-pricing-installer-YYYYMMDD.sh，安装良禽佳木报价 skill，并同步到 workspace。
```

## 8. 你自己替换的只有一处

以后你每次只需要替换这一个部分：

```text
/绝对路径/liangqin-pricing-installer-YYYYMMDD.sh
```

比如你本机当前版本就可以写成：

```text
/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/dist/liangqin-pricing-installer-20260317.sh
```

## 9. 最稳的用法

我更推荐你以后优先用这一版：

```text
请运行 /Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/dist/liangqin-pricing-installer-20260317.sh，把良禽佳木报价 skill 安装到 shared skills，并同步到 workspace。安装完成后，优先按良禽资料边界回答，不要把外部搜索结果和行业常识伪装成良禽资料。然后用两个 fresh session 分别测试“我要做个北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，多少钱？”和“良禽佳木可以选国产五金和进口五金吗？良禽有BLUM的五金，是什么啊？”。最后把安装结果和两次测试原文结果告诉我。
```
