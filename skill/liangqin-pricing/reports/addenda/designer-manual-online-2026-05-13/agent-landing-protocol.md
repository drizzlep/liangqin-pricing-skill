# 新版设计师手册报价规则 AI Agent 落地协议

## 目标
把新版设计师手册中已经被认证为 `报价计算硬规则` 和 `报价前追问/拦截规则` 的规则，分批接入良禽佳木报价系统。当前阶段不做人类逐条审核看板，不直接要求不懂规则的人确认每一条规则。

## 输入
- 规则包：`agent-rule-landing-pack.json`
- 规则表：`agent-rule-landing-pack.csv`
- 来源认证：`/Users/admin/Nutstore Files/我的坚果云/CODE/project/liangqin-skill/skill/liangqin-pricing/reports/addenda/designer-manual-online-2026-05-13/full-document-data-certification.json`

## 执行顺序
1. 只从 `first_batch` 开始，不要一次接入全部 `147` 条。
2. 每条规则先读 `source.title`、`source.page`、`rule_excerpt` 和 `expected_behavior`。
3. 先写或更新测试，再改 `suggested_module` 指向的代码。
4. 报价计算规则必须覆盖完整字段出价和缺字段 precheck 两条路径。
5. 追问/拦截规则必须证明不会被 `handle_quote_message` 路由绕过。

## 硬性边界
- 不使用旧版归档手册兜底。
- 不凭行业常识补规则。
- 不把 `人工复核`、`设计师咨询知识`、`不开放` 数据点混入第一批落地。
- 不在输出中暴露签名 URL、token、内部状态或旧版运行状态。

## 第一批推荐
| ID | 风险 | 动作 | 模块 | 主题 | 来源 |
| --- | --- | --- | --- | --- | --- |
| landing-rule-0034 | P0-影响安全/安装 | 接入报价前追问/拦截 | precheck_quote:safety_or_install_gate | •装有轨道插座的柜体，设计时需考虑轨道电源，电力轨道带有3m长电源线，线材规格3×1... | 轨道插座电源标准 第 1 页 |
| landing-rule-0009 | P0-影响金额 | 接入报价计算 | pricing_calculation:bed_or_soft_package_adjustment | •软包床设计要点: •华夫格软包床头：软包部分不可拆卸，软包内部结构固定板为18mm... | 软包床头 第 1 页 |
| landing-rule-0002 | P0-影响金额 | 接入报价计算 | pricing_calculation:cabinet_structure_adjustment | 天地铰链铝框门 •尺寸限制：305mm≤高度≤2200mm，180mm≤宽度≤500... | 天地铰链铝框门 第 1 页 |
| landing-rule-0155 | P0-影响金额 | 接入报价计算 | pricing_calculation:door_panel_adjustment | •隐形穿衣镜：安装于拼框门后，需另外收费，见《报价原则》 •穿衣镜距门边≥10mm，... | 穿衣镜 第 2 页 |
| landing-rule-0406 | P0-影响安全/安装 | 接入报价前追问/拦截 | precheck_quote:safety_or_install_gate | •设计时需考虑插座位置，建议插座面板放置于柜体背板后侧便于隐藏电源走线； •有插座面... | 轨道插座电源标准 第 2 页 |
| landing-rule-0099 | P0-影响金额 | 接入报价计算 | pricing_calculation:cabinet_structure_adjustment | •当有特殊需求时，可使用特殊抽屉滑轨，特殊抽屉滑轨有：海蒂诗侧 滑轨、海蒂诗全拉出托... | 特殊抽屉滑轨 第 1 页 |
| landing-rule-0027 | P0-影响金额 | 接入报价计算 | pricing_calculation:door_panel_adjustment | 极窄斜边拼框门 •该门型无法做玻璃门 •使用扣手开启时,需注意为对凹槽扣手形式，此时... | 极窄斜边拼框门 第 2 页 |
| landing-rule-0151 | P0-影响安全/安装 | 接入报价前追问/拦截 | precheck_quote:safety_or_install_gate | •装有轨道插座的柜体，设计时需考虑轨道电源，电力轨道带有3m长电源线，线材规格3×1... | 轨道插座电源标准 第 1 页 |
| landing-rule-0069 | P0-影响安全/安装 | 接入报价前追问/拦截 | precheck_quote:safety_or_install_gate | 悬空电视柜 悬空支架（隐藏支架） 内空高•尺寸限制：柜体无长度限制，单板件长度＞26... | 悬空电视柜 第 1 页 |
| landing-rule-0168 | P0-影响安全/安装 | 接入报价前追问/拦截 | precheck_quote:safety_or_install_gate | 该类书桌必须固定在承重墙上;无需与其他柜体固定订制注意事项： 1.订制可改桌面边角;... | 挂墙桌 第 1 页 |
| landing-rule-0144 | P0-影响安全/安装 | 接入报价前追问/拦截 | precheck_quote:safety_or_install_gate | 下翻门（安全阻尼器） •门板面积（㎡）*门高H≤0.2 •开启方式：可抠手开启、五金... | 下翻门 第 1 页 |
| landing-rule-0691 | P0-影响安全/安装 | 接入报价前追问/拦截 | precheck_quote:safety_or_install_gate | 电动举升器 床垫重量应≤50kg，设计时需考虑客户家床垫重量。 电动举升器完全打开后... | 电动举升器 第 1 页 |
| landing-rule-0074 | P0-影响安全/安装 | 接入报价前追问/拦截 | precheck_quote:safety_or_install_gate | •为避免活动层板挪开后的边角对接处外露产生的安全风险，圆边开放柜体中的活动层板 默认... | 活动层板 第 3 页 |
| landing-rule-0299 | P0-影响安全/安装 | 接入报价前追问/拦截 | precheck_quote:safety_or_install_gate | 栏板处开一个供进出床铺面的缺口;要么设置的进出缺口正对位置有一个符合本文件规定的 楼... | GB 28007-2024 婴幼儿及儿童家具安全技术规范 第 32 页 |
| landing-rule-0428 | P0-影响安全/安装 | 接入报价前追问/拦截 | precheck_quote:safety_or_install_gate | 面时,应将这些撑杆拆除。 | GB 28007-2024 婴幼儿及儿童家具安全技术规范 第 38 页 |
| landing-rule-0065 | P0-影响安全/安装 | 接入报价前追问/拦截 | precheck_quote:safety_or_install_gate | •岩板作为台面，边角默认为直边安全角，其他边角需备注；边 角详细尺寸见：“岩板” •... | 岩板柜 第 1 页 |
| landing-rule-0010 | P1-影响能否下单 | 接入报价计算 | pricing_calculation:cabinet_structure_adjustment | 高柜模块 高柜设计要求： •高柜宽度限制：单模块 W=700~900mm 双模块 W... | 模块卡座书柜定制设计指引 第 3 页 |
| landing-rule-0079 | P1-影响能否下单 | 接入报价计算 | pricing_calculation:cabinet_structure_adjustment | 圆弧侧板 •圆弧R=50mm不可做其他弧度；柜体高度≤2600mm时可自行分段或不分... | 圆弧侧板 第 1 页 |
| landing-rule-0122 | P1-影响能否下单 | 接入报价计算 | pricing_calculation:door_panel_adjustment | 藤编门/拱形藤编门 •尺寸限制：单扇门宽≤560mm，门高≤2300mm；藤面高度每... | 藤编门 第 1 页 |
| landing-rule-0369 | P1-影响能否下单 | 接入报价计算 | pricing_calculation:door_panel_adjustment | 针式铰链铝框门 •尺寸限制：305mm≤高度≤3000mm，180mm≤宽度≤500... | 针式铰链铝框门 第 1 页 |
