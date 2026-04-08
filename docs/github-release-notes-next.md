# liangqin-pricing Release Notes

本次版本重点解决两类真实会影响对话成功率的问题，并补上运行环境自检链路，方便本地与云端 OpenClaw 更稳定地安装、排障和回归验证。

## 入口鲁棒性增强

- 扩大材质简称归一化，减少 `北美黑胡桃 / 黑胡桃 / 北美白橡 / 白橡 / 北美樱桃 / 樱桃 / 北美白蜡 / 白蜡 / 玫瑰木` 等常见输入在报价前丢失标准材质映射的情况
- 特殊柜体识别升级为受控同义词组，补齐 `双面柜门 / 双面开门 / 两面开门`、`冰箱位无底板 / 无底板预留` 等自然说法
- 玫瑰木折减规则收紧为“双重语义命中”才触发：只有同时出现“玫瑰木语义”和“非见光 / 内侧 / 背面语义”才会命中，避免把泛化表达误判成专项规则
- 保持底层计算器严格校验不变：缺参数、越界尺寸、无效枚举、未知材质仍会继续追问或明确报错，不改成自动猜测

## 运行环境自检与验证链路

- 新增 `skill/liangqin-pricing/scripts/check_runtime_health.py`，用于区分以下几类问题：
  - 技能安装不完整
  - `price-index.json` 缺失
  - 价格 records 为空
  - 数据正常但查询条件没有命中
- `skill/liangqin-pricing/scripts/refresh_and_test.py` 现在会在 fresh session smoke test 前先执行运行环境自检，环境异常时直接停止，避免把坏环境误判成 skill 逻辑问题
- 可选依赖缺失改为可跳过处理，减少验证报告被环境噪音污染

## 回归覆盖补强

- 新增材质简称输入回归用例
- 新增特殊柜体自然说法变体回归用例
- 显式覆盖应当拒绝、继续追问、或按业务边界拦截的负例，避免把预期拦截误记成 bug

## 云端 OpenClaw 使用提醒

- GitHub Release 能解决的是“把这次新能力和修复发出去”
- 但如果对方使用的是云端 OpenClaw，仍然不要假设一定存在默认 `~/.openclaw/...` 目录结构
- 安装前请先确认实际使用的 `shared skills` 目录和 `workspace skills` 目录，再选择 zip 包或单文件安装器
- 安装完成后，建议先运行 `check_runtime_health.py`，确认数据和索引完整，再运行 `refresh_and_test.py`

## 建议发布后转发给对接同事的一句话

这是 liangqin-pricing 的新 GitHub Release。请不要假设当前环境一定是默认 `~/.openclaw` 路径。请先确认 OpenClaw 实际使用的 shared skills 目录和 workspace skills 目录，再安装 release 附件里的 zip 或单文件安装器。安装完成后，先运行 `check_runtime_health.py`，再运行 `refresh_and_test.py`，并把最终实际路径和结果回传给我。
