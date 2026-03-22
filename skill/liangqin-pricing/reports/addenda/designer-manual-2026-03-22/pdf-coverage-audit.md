# PDF 新增规则覆盖审计表

- source_file: /Users/admin/Downloads/设计标准手册-AI测试.pdf
- page_count: 427
- entry_count: 304
- included_runtime: 83
- manual_review: 157
- excluded_non_pricing: 64

## Status 说明

- `included_runtime`: 已进入当前追加规则运行时逻辑
- `manual_review`: 有报价相关信号，但当前未进入运行时，建议人工确认
- `excluded_non_pricing`: 当前判断为背景说明/弱相关内容，暂不进入报价逻辑

## included_runtime

### p11 · 4英寸宽2英尺长。净划面数量根据板材的尺寸而定，

- status: included_runtime
- domain: material
- rule_type: formula
- relevance_score: 9
- pricing_relevant: True
- tags: 材质, 尺寸阈值
- runtime_title: 英寸宽2英尺长。净划面数量根据板材的尺寸而定，
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

4英寸宽2英尺长。净划面数量根据板材的尺寸而定， NHLA分等规则 了解NHLA分等规则 普2A级中最小的板面规格为3英寸宽4英尺长，净划面的出材率的比例范围是 。最小允许净划面的 尺寸是3英寸宽2英尺长，数量因板面大小而异。如果最差面达到普2A级的最低要求，较好面所属的等级就无关紧要了。 NHLA分等规则 了解NHLA分等规则 以下图片描述了美国硬木的一些。其中有些是特定材种本身固有的特征，另一些是为一般材种所共有的。这些特征是木材自然生成的或是在 干燥过程中形成的。正如前

### p21 · 2分别连续。该情况需提前与客户沟通确认。无备注时，默认从分段处断开连纹。

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 8
- pricing_relevant: True
- tags: 柜体, 材质, 尺寸阈值
- runtime_title: 分别连续。该情况需提前与客户沟通确认。无备注时，默认从分段处断开连纹。
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

2分别连续。该情况需提前与客户沟通确认。无备注时，默认从分段处断开连纹。 •竖向纹理门板连续：纹理方向长度≤2400mm时，同一个产品中相邻门板默认上下纹理连续（上下门板之间无横板或只有一个横板时为相邻门 板），上下门板之间有两个及以上横板时无需连纹；纹理方向＞2400mm时，上下门板纹理不连续；当同一个柜子中左右相邻门板一侧上下门板 高度和≤2400，一侧上下门板高度和＞2400，同一视角范围内视觉不统一更容易突出差异，因此默认统一采取所有门板上下均不连续的做法， 该情况需

### p31 · 20mm圆边切角

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 新现代边角-侧边平齐 本 工 + IMS Tw ol PATER CEE QP ds 3k 抽屉间空隙为18mm新现代边角 -侧边平齐 MIST ey RE 由二
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

20mm圆边切角 •整装柜体的柜体结构为顶板盖侧板时，使用圆边切 角，顶板、底板以及两侧侧板均无切角，只有内部 横竖板有切角。 •如上图，黄色圆圈处无切角。 •柜体通长落地立板上下均无切角 •图示为顶盖侧结构，该样式边角不可做侧盖顶结构。新现代边角-侧边平齐 本 工 + IMS Tw ol PATER CEE QP ds 3k 抽屉间空隙为18mm新现代边角 -侧边平齐 MIST ey RE 由二 •图示为顶盖侧结构，该样式边角不可做侧盖顶结构。新现代边角-侧边飘出

### p34 · © RSIS? EEC BY BD TSE T°

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 为方便查看尺寸，尺寸图中边角为直边，实物为圆边，可参考下页实物图与渲染图
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

8 00 Ww = { © RSIS? EEC BY BD TSE T° SLANE SHS aot A 柜体 新现代边角-侧边飘出 SLE EH eS i •为方便查看尺寸，尺寸图中边角为直边，实物为圆边，可参考下页实物图与渲染图。 •图示为顶盖侧结构，该边角风格柜体默认为顶盖侧结构，侧盖顶结构需特殊备注。 •外直角常用于组合柜体。 A B 外直角新古典圆边 A B 2626 26 26 一 | iia a A 0 0 | | Vo) •图示为顶盖侧结构，该边角风格柜体默认

### p40 · 30'0 山山 Te'0 山山

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 当高柜使用海棠角斜边时，顶底板为直角平边，门板盖顶底板
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

30'0 山山 Te'0 山山 he $10 山 + EAM Ave. PERERA’ ISIC a E° BINT WBMWD •图示为侧盖顶结构，该样式边角不可做顶盖侧结构。 •当高柜使用海棠角斜边时，顶底板为直角平边，门板盖顶底板。海棠边角-海棠角斜边-高柜 •图示为45°拼接结构，该样式边角不可做其他结构。 •使用该样式边角设计有门板的柜体时只能为普通门板的内嵌门。海棠边角-海棠角平边 窄边框柜体 o）圆角圆边-窄边p）直角平边-窄边 矮柜 高柜 q）圆角平边-窄边 

### p55 · 80mm，其他特殊情况可调整牙称高度，牙称高度范围50≤ H ≤250mm。

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 其他特殊情况可调整牙称高度
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

80mm，其他特殊情况可调整牙称高度，牙称高度范围50≤ H ≤250mm。 •以下介绍常见的拆装柜体结构，分别为：侧盖顶与顶盖侧柜体结构示例、超高柜体分段示例、超长柜体分段示例、超长\超高柜体分段示例。 可由此学习常规拆装柜体各种样式的具体结构。 高度＞1700mm侧盖顶拆装柜体 高度≤1700mm顶盖侧拆装柜体常规拆装柜体-侧盖顶与顶盖侧柜体结构示例1 以衣柜为例 以电视柜为例 上下进深不一致拆装柜体 多组拆装组合柜常规拆装柜体-侧盖顶与顶盖侧柜体结构示例2 卡座书柜，非

### p59 · 5情况开放格区域层板内凹，层板外沿与门板不齐平。为提高家具结构稳定性及保

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 8
- pricing_relevant: True
- tags: 柜体, 超深, 投影面积, 尺寸阈值
- runtime_title: 情况开放格区域层板内凹，层板外沿与门板不齐平。为提高家具结构稳定性及保
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

5情况开放格区域层板内凹，层板外沿与门板不齐平。为提高家具结构稳定性及保 证全屋家具结构统一，推荐图1、图2设计方法，非必要不进行图3、4、5设计。 图6 分段缝对齐层板上方 层板外沿与门板不齐平 门板与层板之间漏缝 图2 分段缝对齐层板上方 层板外沿与门板齐平图3 分段缝对齐层板下方 层板外沿与门板齐平 图4 分段缝对齐层板下方 层板外沿与门板不齐平图5 分段缝对齐层板下方 层板外沿与门板不齐平 P.S. 其他相似情况此处不做列举，请在设计时根据实际情况判断 a）立板上下通

### p78 · 1-15045 25 150 40DG-02 DG-06 DG-10

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 8
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 15045 25 150 40DG-02 DG-06 DG-10 DSG-03 CTG-01 CTG-03 CBG-04 DSG-08 CBG-07 XSG-04 DG-08 DSG-02 CJ-01 YG-06 YG-09 YG-17 SG-13 YG-11 DSG-01 XSG-02 DSG-04 a）正视图 b）左视图 c）俯视图 d）支腿俯视图 圆直腿1-150 圆直腿1-200 圆直腿1-220 圆直腿1-240 圆直腿2-200 圆直腿2-150 圆斜腿1-1
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

1-15045 25 150 40DG-02 DG-06 DG-10 DSG-03 CTG-01 CTG-03 CBG-04 DSG-08 CBG-07 XSG-04 DG-08 DSG-02 CJ-01 YG-06 YG-09 YG-17 SG-13 YG-11 DSG-01 XSG-02 DSG-04 a）正视图 b）左视图 c）俯视图 d）支腿俯视图 圆直腿1-150 圆直腿1-200 圆直腿1-220 圆直腿1-240 圆直腿2-200 圆直腿2-150 圆斜腿1-1

### p85 · 1. 遇见书柜-上柜顶底包侧；下柜顶盖侧，侧包底；单独下柜高度≤1700mm，顶盖侧，侧包底；高度＞1700mm（不建议，非必要不设计），

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 遇见书柜-上柜顶底包侧
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

1. 遇见书柜-上柜顶底包侧；下柜顶盖侧，侧包底；单独下柜高度≤1700mm，顶盖侧，侧包底；高度＞1700mm（不建议，非必要不设计）， 侧包顶底 高度＞1700mm （不建议，非必要不设计）

### p89 · 2个独立柜体 开放分组转角柜转角柜

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 8
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: L型层板后方均为背板
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

2个独立柜体 开放分组转角柜转角柜 开放整体转角柜 衣柜：≤1100mm 其他柜体：≤900mm衣柜：≤1100mm其他柜体：≤900mm ≤200衣柜：≤1100mm 其他柜体：≤900mm衣柜：≤1100mm其他柜体：≤900mm•开放整体转角柜是指转角部分是一个整体，不可拆分。可做直边/圆边。 •转角处使用L型层板，内侧转角可设计为直角或圆角，圆角半径≤200mm，设计时应注意L型层板的尺寸限制。 •L型层板后方均为背板。 开放整体转角柜 L型层板任一边≤600mm时，

### p97 · •柜体圆边时，书梯滑轨安装板上下层板外侧圆边

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 8
- pricing_relevant: True
- tags: 柜体, 超深, 投影面积, 门型, 公式, 尺寸阈值
- runtime_title: 注意轨道
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

450—500mm •柜体圆边时，书梯滑轨安装板上下层板外侧圆边 外侧圆边 •爬梯滑轨安装板默认平板无造型，可做造型设计，选择增加造型时 需备注 •造型尺寸默认如右侧俯视图，槽间距默认6，可根据实际情况适当调 整，需要备注在合同中以及附有修改后的尺寸图纸 •注意轨道支架处需留白不做造型，便于轨道安装平板无造型 造型挡板 •遇见书柜柜体为整装结构，整体由多个单体柜组合而成，设 计柜体尺寸时应考虑单组柜体能否通过电梯搬运，以及客户 家空间布局是否影响搬运。 •柜体整体为遇见边角，

### p111 · 123：指层板或立板的板件进深柜内组件避让原则

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 10
- pricing_relevant: True
- tags: 柜体, 表格, 尺寸阈值
- runtime_title: 123：指层板或立板的板件进深柜内组件避让原则
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

123：指层板或立板的板件进深柜内组件避让原则 图2-63 柜内搁板长度 a）衣柜内搁板 b）其他柜体柜内搁板a) b)•衣柜单块搁板长度须≤1000mm，如图2-63；其他柜体如书柜、储物柜、玄关柜等搁板长度须≤900mm。 图2-61 柜体结构•柜体横竖板连接的关系统一先竖后横，如图2-61。固定层板 空区不在柜体一侧，且邻区有固层 衣柜：≤1700mm 书柜：≤1000mm 储物柜：≤1700mm两空区相邻 衣柜：≤1500mm 书柜： ≤1000mm 储物柜：≤150

### p127 · 2000＜L≤2200/ H＜900 前托称*1前托称*1

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 表格, 尺寸阈值
- runtime_title: 榻榻米组合柜空区适用于该托称添加规则，但添加托称的组合柜需配合 固定上墙
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

2000＜L≤2200/ H＜900 前托称*1前托称*1 后托称*180*26（木质托称）表2-6 空区托称添加规则 注：有背板空区，空区处背板需为单块独立背板，不与其他区域共用背板 LDH 钢管托称 木质托称 •进门柜底部空区请勿添加托称，请根据“3.2.4 无牙称柜体”章节内容 按规则添加暗支腿； •榻榻米组合柜空区适用于该托称添加规则，但添加托称的组合柜需配合 固定上墙； •钢管托称及木质托称安装位置见图。3 3 3 3

### p128 · 称前托称 后托称

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 层板 层板 层板 层板前 托 称后 托 称 前 托 称后 托 称前托称 后托称 前托称 后托称 走线圆口
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

33层板 层板 层板 层板前 托 称后 托 称 前 托 称后 托 称前托称 后托称 前托称 后托称 走线圆口 •走线圆口可应用于书桌、书柜等家具用于穿线。 •走线圆口直径规格为50/60/80mm，无标注默认50mm。 •书桌上的走线圆口默认配一个盖板。 •柜体中的走线口因需避让三合一孔位，需距边≥50mm •检修口需距边≥50mm •到顶柜体，顶板有可拆卸式检修口盖板的，封 边条尺寸需≥30mm，以便打开盖板。 •开口位置不可与立板重叠可拆卸式顶板检修口盖板孔洞 柜侧前开口

### p130 · 方剩余板件宽度不小于侧板宽度的1

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 参考铰链
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

3，即后 方剩余板件宽度不小于侧板宽度的1 3 •开口高度≤700mm •两侧开口时，上柜需固定上墙柜侧前缺口 柜侧闭合缺口 WW WW •柜体侧板闭合形开口，用于取 放柜内物品等 •开口宽度不超过侧板宽度的2 3 •开口高度≤650mm •开口距后方≥50mm；前方无铰 链安装时≥50；有铰链安装时 参考铰链称宽度 拱形玄关挡板 •档板厚度20mm；分为平板和斜拼两种造型； •拱形玄关挡板下方有挡条结构，单独挡条厚度12mm，宽度约为50mm； •平板拱形玄关挡板：造型顶部

### p130 · 方剩余板件宽度不小于侧板宽度的1

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 方剩余板件宽度不小于侧板宽度的1
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

3，即后 方剩余板件宽度不小于侧板宽度的1 3 •开口高度≤250mm•柜体侧板开放形前缺口，高度较大， 侧板作支承部件 •开口宽度不超过侧板宽度的2

### p135 · •背板宽度应控制在1100mm以内，高度2300mm以内；芯板任意一边长应≤500mm，特殊情

- status: included_runtime
- domain: cabinet
- rule_type: material_mapping
- relevance_score: 8
- pricing_relevant: True
- tags: 柜体, 门型, 尺寸阈值
- runtime_title: •背板宽度应控制在1100mm以内，高度2300mm以内；芯板任意一边长应≤500mm，特殊情
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

11mm。 •背板宽度应控制在1100mm以内，高度2300mm以内；芯板任意一边长应≤500mm，特殊情 况可进行特殊处理（如电视柜背板）。 •背板纹理方向默认为竖纹，特殊情况可为横纹 （同一件家具所有的背板纹理方向必须 保持一致）。 •开放柜体或玻璃门等能直接看到背板的情况，背板横称需要与层板保持对齐。 •进门柜、餐边柜等中间操作台空区处的外露背板默认为平装背板，其他区域如需平装须 备注；无背板柜体或特定区域无背板须备注，以免图纸不明显导致的错误。 •外露背板为特殊背板，

### p137 · 9mm竖纹平板背板

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 10
- pricing_relevant: True
- tags: 柜体, 门型, 材质, 尺寸阈值
- runtime_title: 背板和层板需要自攻螺丝固定
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

9mm竖纹平板背板 （整装柜体）H＞800mmH≤800mmH＞800 横撑平板背板 H WL•15mm竖纹平板背板(拆装柜体) •背板可通顶或者分段使用 •分段背板承重性更好，与层板之间不容易漏缝 •背板和层板需要自攻螺丝固定 •尺寸限制： 内空高度H≤2400mm； 当内空宽度W≤360mm时为一整块背板； 当W＞360mm时需要断开，且单块背板宽度L≤260mm；平板背板 内退尺寸9mm 立 板15mm背板 正面咬口5mm 俯视图 背板通顶,层板之间的距离＞1700， 

### p156 · 100mm≤抽面高度≤350mm

- status: included_runtime
- domain: accessory
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 可使用扣手、明装拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

100mm≤抽面高度≤350mm 抽面上沿与抽侧上沿高差需≤60mm；抽屉下盖时，抽面下沿与抽侧下沿高差需≤60mm •开启方式：可使用扣手、明装拉手、按弹开启；使用明装拉手时，抽面长度＞600mm建议使用双孔长拉手或2个单孔拉手； •适用轨道：所有轨道；默认海蒂诗阻尼托底轨 抽屉长度＞600mm底称，两侧圆弧 ≤1040mm100mm≤H≤350mm ≤60mm≤60mm 骨骼线抽屉 •骨骼线抽屉属于平板抽屉的一种，抽面厚度：22mm， •尺寸限制：抽面长度≤1040mm；

### p158 · 120mm≤抽面高度≤350mm；抽面高度＜150mm时，抽面框架宽度为40mm

- status: included_runtime
- domain: accessory
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 可使用明装拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

120mm≤抽面高度≤350mm；抽面高度＜150mm时，抽面框架宽度为40mm 抽面上沿与抽侧上沿高差需≤60mm；抽屉下盖时，抽面下沿与抽侧下沿高差需≤60mm •开启方式：可使用明装拉手、按弹开启；使用明装拉手时，抽面长度＞600mm建议使用双孔长拉手或2个单孔拉手； •适用轨道：所有轨道；默认海蒂诗阻尼托底轨 ≤1040mm120mm≤H≤350mm ≤60mm≤60mm 玻璃抽屉 •玻璃抽屉为玻璃+木质平板组合抽面抽屉；长虹玻璃不可以做玻璃抽屉； •抽面厚度：有扣手

### p159 · 150mm≤抽面高度≤350mm；木抽面高度需≥80mm；

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 9
- pricing_relevant: True
- tags: 柜体, 门型, 公式, 尺寸阈值
- runtime_title: 可使用扣手、明装拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

150mm≤抽面高度≤350mm；木抽面高度需≥80mm； •开启方式：可使用扣手、明装拉手、按弹开启；使用明装拉手时，抽面长度＞600mm建议使用双孔长拉手或2个单孔拉手； •适用轨道：所有轨道；默认海蒂诗阻尼托底轨 ≤1040mm150mm≤H≤350mm ≥80mm147 307 5 26≥80mm8.5 8.5 30 5 22 无扣手抽面侧视图≥80mm 有扣手抽面侧视图 •以上3类抽屉默认使用海蒂诗阻尼托底轨： •海蒂诗阻尼托底轨规格最小250mm，最大500mm 

### p167 · 50*20mm，默认门盖拉条，如需抽屉盖拉条须备注，注意会影响抽盒高度。

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 50*20mm，默认门盖拉条，如需抽屉盖拉条须备注，注意会影响抽盒高度。
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

50*20mm，默认门盖拉条，如需抽屉盖拉条须备注，注意会影响抽盒高度。 （以2个抽屉悬空为例） •外置抽屉下方如果是开放区域（没有柜门），则使 用层板 开放柜体 加层板抽屉悬空方案 黑鸟抽屉 •黑鸟抽屉为黑鸟柜体专用抽屉； •抽面厚度：26mm •尺寸限制： 抽面长度≤1040mm；抽面长度≤600mm时无底称，＞600mm时中间需加底称

### p168 · 150mm≤抽面高度≤350mm

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 可使用明装拉手
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

150mm≤抽面高度≤350mm 抽面上沿与抽侧上沿高差需≤60mm；抽屉下盖时，抽面下沿与抽侧下沿高差需≤60mm •开启方式：可使用明装拉手、按弹开启；使用明装拉手时，抽面长度＞600mm建议使用双孔长拉手或2个单孔拉手； •适用轨道：所有轨道；默认海蒂诗推弹阻尼回收托底轨 •使用海蒂诗推弹阻尼回收托底轨的内嵌黑鸟抽屉尺寸： ①抽屉总进深 = 滑轨规格 + 26mm ②抽屉内使用空间进深 = 滑轨规格 – 25mm ③抽屉内使用空间长度 = 抽屉总长 – 40mm ④抽屉

### p170 · 4只承重45kg；6只承重65kg

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 可使用扣手、明装拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

4只承重45kg；6只承重65kg 托盘抽 •托盘抽主要用于书桌键盘抽、储物柜/餐边柜拉出平台等； •抽面厚度：22mm •尺寸限制：66mm≤抽面高度H≤128mm；抽面上沿至托盘上沿高差20mm≤C≤60mm；抽面长度L≤1050mm •承重：30Kg •开启方式：可使用扣手、明装拉手；使用明装拉手时，抽面长度＞600mm建议使用双孔长拉手或2个单孔拉手； •适用轨道：海蒂诗全拉出阻尼托底轨，规格250-500mm

### p171 · 反弹踢脚抽

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 平板与层板之间的放鞋空区处，需根据客户家鞋类的具体情况自行判断，需在图纸上标注尺寸. 贴纸粘贴在中间位置，脚踢贴纸位置，弹出使用H W侧视尺寸图抽 面 穿带平板静音条 背 板
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

20≤C≤60mm 反弹踢脚抽 •尺寸限制：H=60mm，500mm≤W≤1000mm，踢脚抽后端距墙或柜体需留有8mm(5mm按弹余量+3mm静音棉）距离； •平板与层板之间的放鞋空区处，需根据客户家鞋类的具体情况自行判断，需在图纸上标注尺寸. 贴纸粘贴在中间位置，脚踢贴纸位置，弹出使用H W侧视尺寸图抽 面 穿带平板静音条 背 板 •尺寸限制：台面长度L≤2400mm；台面深度400mm≤D≤800mm;可移动台面高度H=80mm； •飘窗滑轨台面结构为整装，滑轨最大承重

### p174 · 780≤D≤800 750mm轨道长度与桌面尺寸关系表

- status: included_runtime
- domain: table
- rule_type: material_mapping
- relevance_score: 7
- pricing_relevant: True
- tags: 门型, 尺寸阈值
- runtime_title: 不同尺寸轨道
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

780≤D≤800 750mm轨道长度与桌面尺寸关系表 不同尺寸轨道拉出长度示例 台面宽度 •可拉出台面当作书桌使用 使用场景 。 HPHASAAERS EH poy) wes 本节介绍平开门，平开门按安装方式不同可分为全盖、半盖和内嵌。 平开门的主要种类有：平板门、铝框门、拼框门，将在后续小节中分别展开讲解。 a) 嵌门 (内嵌门)b) 盖门 (全盖门)c) 半盖门

### p177 · 1.门板长宽比例不易过大，比例过大时，会使铰链负荷过大而造成铰链螺丝脱落或门板下沉。示例图及公式可见图3-2。

- status: included_runtime
- domain: door_panel
- rule_type: formula
- relevance_score: 6
- pricing_relevant: True
- tags: 公式
- runtime_title: 会使铰链负荷过大而造成铰链
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

1.门板长宽比例不易过大，比例过大时，会使铰链负荷过大而造成铰链螺丝脱落或门板下沉。示例图及公式可见图3-2。

### p177 · 3.除已说明的默认开启方式（如流云门默认为按弹开启），其他无把手、无抠手柜门，除说明开启方向外，须明确备注开启方式。

- status: included_runtime
- domain: door_panel
- rule_type: material_mapping
- relevance_score: 7
- pricing_relevant: True
- tags: 门型
- runtime_title: 除已说明的默认开启方式（如流云门默认为按弹开启），其他无把手、无抠手柜门，除说明开启方向外，须明确备注开启方式。
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

3.除已说明的默认开启方式（如流云门默认为按弹开启），其他无把手、无抠手柜门，除说明开启方向外，须明确备注开启方式。 柜门开启示例图：右上门板从空区 处开启，无需把手或抠手。 图3-2 平板门 平板门指门板无框架结构的门板，包括横纹门板和竖纹门板。 平板门后均有穿带结构，因此以下平板门门型均不可做推拉门。 平板门目前包括流云门（横纹平板门）、飞瀑门（竖纹平板门）、拉线门（横向/竖向）、月亮门4类门型，将在后续小节详述。 为保证家具稳定性及后续正常使用，设计时应考虑各门型尺寸限

### p180 · 外观无中缝

- status: included_runtime
- domain: door_panel
- rule_type: material_mapping
- relevance_score: 8
- pricing_relevant: True
- tags: 门型, 尺寸阈值
- runtime_title: 可推弹开启、抠手开启、拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

60mm≤深≤100mm W≤450mm 外观无中缝 •尺寸限制：300mm≤单小块门板长度≤500mm，单小块门板宽度 ≤450mm，柜门高度≤2200mm •门板厚度：20mm •穿带避让尺寸*：30mm/50mm •开启方式：可推弹开启、抠手开启、拉手开启。无备注无标注时 默认为推弹开启，其他开启方式需标注及备注。此门型不可设计 跨越门板间插槽空隙的长抠手，否则将有榫接合外露的情况发生。 •适用铰链：所有铰链均适用；内嵌门铰链称宽度需≥100mm，外 盖门铰链称需≥80

### p183 · 10的整数倍，此时差值最小。

- status: included_runtime
- domain: door_panel
- rule_type: dimension_threshold
- relevance_score: 8
- pricing_relevant: True
- tags: 门型, 尺寸阈值
- runtime_title: 可推弹开启、抠手开启、拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

10的整数倍，此时差值最小。 单小块门板长度 单 小 块 门 板 宽 度 柜 门 高 度横向拉线门 •横向拉线门是在流云门基础上铣型而成的柜门 •尺寸限制：300mm≤单小块门板长度≤500mm，单小块门板宽度 ≤450mm，为避免小门板抽涨造成的拉线间隙问题，柜门高度≤900mm •门板厚度：20mm •穿带避让尺寸：30mm •开启方式：可推弹开启、抠手开启、拉手开启。当门板为两块拼接时， 不可设计跨越门板间插槽空隙的竖向长抠手，否则将有榫接合外露的 情况发生。 •特殊要

### p185 · 230/270/310/350/390/430/470/510mm。圆环内为镂空状，无法

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 可推弹开启、拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

230/270/310/350/390/430/470/510mm。圆环内为镂空状，无法 安装玻璃；圆环位置上下可调，圆环上下距边要求≥160mm •适用铰链：所有铰链均适用。内嵌门铰链称宽度需≥100mm，外 盖门铰链称需≥80mm ；柜内拉篮等避让铰链宽度至少80mm. •尺寸限制：单扇门宽≤450mm，高度≤2300mm •门板厚度：20mm •穿带避让尺寸*：20mm/30mm •开启方式：可推弹开启、拉手开启；拉手尺寸：40*20 •特殊要求：拉手不可安装在上下，只

### p188 · 上方右侧图 下方右侧图

- status: included_runtime
- domain: door_panel
- rule_type: dimension_threshold
- relevance_score: 8
- pricing_relevant: True
- tags: 门型, 尺寸阈值
- runtime_title: 铝框门、天地铰链铝框门和、针式铰链
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

60mm≤柜深≤100mm 上方右侧图 下方右侧图 金属条位置左侧图 •应用场景 a i 全 ae 一 m0 | a §38 56 |e Nl 铝框门指门板框架为铝框的门板。 铝框门目前包括常规铰链铝框门、天地铰链铝框门和、针式铰链铝框门、铝框岩板门4种门型。 设计时，如使用天地铰链铝框门或针式铰链铝框门、铝框岩板门需备注，无备注默认为常规铰链铝框门。 为保证家具稳定性及后续正常使用，设计时应考虑各门型尺寸限制，请勿超出规定的柜门尺寸限制。铝框门 铝框平开门尺寸限制快速检索表

### p193 · 常规铰链铝框门

- status: included_runtime
- domain: door_panel
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 长拉手长度1100mm，可靠下安装，距边30mm，不可安装于其他位置
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

300≤h≤2700 常规铰链铝框门 •尺寸限制：305mm≤高度≤2700mm，180mm≤宽度≤560mm •门板厚度：22mm •门边框宽度：22mm •门边框颜色：黑色\金色，需备注；可定制银色\白色\红色，需提前询 问工厂 •开启方式：拉手开启 •特殊要求： 铝框门拉手分为长拉手、短拉手与通长拉手，使用时应备注； 长拉手长度1100mm，可靠下安装，距边30mm，不可安装于其他位置； 短拉手长度200mm，可居中、靠上或靠下安装，靠上或靠下均距边

### p194 · 30mm，不可安装于其他位置。

- status: included_runtime
- domain: door_panel
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 30mm，不可安装于其他位置。
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

30mm，不可安装于其他位置。 •适用铰链：天地铰链、90°平行铰链不可用。内嵌门铰链称宽度需 ≥100mm，外盖门铰链称需≥80mm ；柜内拉篮等避让铰链宽度至少80mm. 天地铰链铝框门 •尺寸限制：305mm≤高度≤2200mm，180mm≤宽度≤500mm •门板厚度：26mm •门边框宽度：26mm •门边框颜色：黑色\金色，需备注；可定制银色\白色\红色，需提前询问工厂 •开启方式：拉手开启 •特殊要求： 铝框门拉手分为长拉手、短拉手与通长拉手 长拉手长度1100

### p195 · 20mm，抽屉盖6mm，抽屉面板厚度为26mm，如图3-52-c.

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 10
- pricing_relevant: True
- tags: 柜体, 门型, 材质, 尺寸阈值
- runtime_title: 只适用天地铰链
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

20mm，抽屉盖6mm，抽屉面板厚度为26mm，如图3-52-c. 因门厚不一，设计类似于图3-53结构的铝框门使用天地铰链时，其他门型 需对齐门厚，平板门纹理连续超过0.9m时需加价，详见《报价原则》 天地铰链铝框门柜体如长度超长，断开形式只能立板通断； 使用天地铰链的柜体，顶板不可做检修口等的避让开口； •适用铰链：只适用天地铰链 图3-52 天地铰链铝框门 a)天地铰链铝框门 b)天地铰链铝框门 c)柜门与抽屉交接处层板b) a) c) 图3-53a) b) 针式铰链铝

### p201 · 3.有 26 厚门板和抽屉都是外盖的情况，抽面改为 26 厚

- status: included_runtime
- domain: door_panel
- rule_type: material_mapping
- relevance_score: 5
- pricing_relevant: True
- tags: 门型
- runtime_title: 有 26 厚门板和抽屉都是外盖的情况，抽面改为 26 厚
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

3.有 26 厚门板和抽屉都是外盖的情况，抽面改为 26 厚 拼框木门 拼框玻璃门 真格栅门 新古典格栅门 经 典 木 门拱 形 木 门胶 囊 木 门 门厚 规格 门边框宽度 门厚 规格 门边框宽度 门厚规格门边框 宽度

### p209 · 26 60 26 60300≤W≤560300≤W≤560 300≤W≤560 300≤W≤560

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 8
- pricing_relevant: True
- tags: 柜体, 门型, 公式, 尺寸阈值
- runtime_title: 可推弹开启、抠手开启、拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

26 60 26 60300≤W≤560300≤W≤560 300≤W≤560 300≤W≤560 ≤1700 ≤2300 ≤2200 ≤2300拼框平开门尺寸限制快速检索表-a 单位：mm 经典木门/拱形木门/胶囊木门 •尺寸限制：单扇门宽≤560mm；无中横门高≤2200mm；带中横门高 ≤2300mm。 •门板厚度：门高≤1500mm，门厚22mm；门高＞1500mm，门厚26mm。 •门边框宽度：60mm（含斜切边） •开启方式：可推弹开启、抠手开启、拉手开启。带中横

### p213 · 7 OE NT AE BX TORI IS NIRS, Mls ELON TSE. DEAS CCT LC CEES I RS LS PSS SE NEVO NOT SRN

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 门型, 公式, 尺寸阈值
- runtime_title: 7 OE NT AE BX TORI IS NIRS, Mls ELON TSE. DEAS CCT LC CEES I RS LS PSS SE NEVO NOT SRN
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

7 OE NT AE BX TORI IS NIRS, Mls ELON TSE. DEAS CCT LC CEES I RS LS PSS SE NEVO NOT SRN ESS NI ICN Ms WY, ADEA SOO SS ONG, CGI, GEIS NY IE NB OR NOSIS VE SRE SION RASS OORR RBS i AG Wye NA KURI SOAS I” MIP EO, Meso LN ee Ee PS Se a ee Nee en

### p218 · 新古典格栅门

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 门型, 公式, 尺寸阈值
- runtime_title: 可推弹开启、抠手开启、拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

2300＜H≤2600 新古典格栅门 •尺寸限制：单扇门宽≤560mm，门高≤2300mm •门板厚度：门高≤1500mm且无玻璃，门厚22mm；门高＞1500mm或有玻璃， 门厚26mm •门边框宽度：60mm（含斜切边） •竖格栅条：无斜切边，宽度15mm, 竖格栅条之间间距为15-20mm，默认均 分，有特殊要求需标注及备注。 •横格栅条：无斜切边，宽度20mm •开启方式：可推弹开启、抠手开启、拉手开启。 •特殊要求：竖向格栅条高度＞800mm需有横格栅条固定，两横格

### p222 · 3.避免暴露在直射阳光下，因为太阳的热量和紫外线可能对藤材产生损害。

- status: included_runtime
- domain: door_panel
- rule_type: material_mapping
- relevance_score: 9
- pricing_relevant: True
- tags: 门型, 尺寸阈值
- runtime_title: 可推弹开启、扣手开启、拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

3.避免暴露在直射阳光下，因为太阳的热量和紫外线可能对藤材产生损害。 虽然经过处理的藤面可能会出现毛刺，但通过适当的保养和合理的使用，可以延缓其出现并保持家具的美观。 在设计藤编家具时应注意藤面的天然属性并向客户详细说明使其知悉产品特性。藤编制品说明 美式木门 •尺寸限制：300mm＜单扇门宽≤560mm，无中横门高≤1700mm ，带中横 门高≤2300mm •门板厚度：26mm •门边框宽度：60mm •开启方式：可推弹开启、扣手开启、拉手开启。 •特殊要求：门板芯板凸面

### p225 · 10mm；边框可选择无斜边，默认有，无斜边需要备注；

- status: included_runtime
- domain: general
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 10mm；边框可选择无斜边，默认有，无斜边需要备注；
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

10mm；边框可选择无斜边，默认有，无斜边需要备注； •尺寸限制：单门宽度W：W≤500mm；单门高度H：H≤2200mm；木框边宽60mm；设计上下翻门时：长L≤1040mm；木框边宽度W：

### p225 · 40mm≤W≤60mm，默认40mm，有其他临近平开门边框为60mm时可调为60mm；

- status: included_runtime
- domain: door_panel
- rule_type: formula
- relevance_score: 6
- pricing_relevant: True
- tags: 门型, 尺寸阈值
- runtime_title: 40mm≤W≤60mm，默认40mm，有其他临近平开门边框为60mm时可调为60mm；
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

40mm≤W≤60mm，默认40mm，有其他临近平开门边框为60mm时可调为60mm； •开启方式：可推弹开启、抠手开启、拉手开启； •黑板品牌：美国Polyvision哑光黑色搪瓷珐琅板:金属板材，零甲醛、可磁吸（可自主搭配带磁吸效果的配件使用）、可书写、 抗划痕、硬度高。 W≤500mm L≤1040mm边框斜边40mm≤W≤60mm 黑板门 实物图 H≤2200mm W≤500mm xh ba ae a se00uu | | | | 工 入 区 | 2 Ee i= ma

### p227 · 2. 推拉门门厚

- status: included_runtime
- domain: cabinet
- rule_type: material_mapping
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 门型, 尺寸阈值
- runtime_title: 使用五金轨道
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

2. 推拉门门厚 使用五金轨道，门厚统一26mm； 使用木轨道，除带格栅条玻璃门、美式门、窄边框斜边玻璃推拉门 门厚26mm，其他常规门门厚22mm。3. 层板内缩（相对于柜体外沿）： 木轨道

### p227 · 26厚门板：直边、圆边内缩70mm，内斜边内缩75mm

- status: included_runtime
- domain: door_panel
- rule_type: material_mapping
- relevance_score: 6
- pricing_relevant: True
- tags: 门型, 尺寸阈值
- runtime_title: 五金轨道
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

26厚门板：直边、圆边内缩70mm，内斜边内缩75mm 玻璃门：直边、圆边内缩40mm，内斜边内缩45mm 五金轨道 双轨道：直边内缩70mm，圆边内缩75mm 单轨道：直边内缩40mm，圆边内缩45mm

### p227 · 4.当柜体上下柜门均为推拉门时，中间的间隔层板根据使用的

- status: included_runtime
- domain: cabinet
- rule_type: material_mapping
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 门型, 尺寸阈值
- runtime_title: 也可以使用拉手
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

4.当柜体上下柜门均为推拉门时，中间的间隔层板根据使用的 滑轨不同有所变化，具体要求可见表 上门 下门 隔层要求 五金轨道 五金轨道 20mm层板2块 木轨道 木轨道 20mm层板1块 木轨道 五金轨道 26mm层板1块推拉门 推拉门拉手 •拼框推拉门多使用扣手，也可以使用拉手，使用拉手时注意拉手在外侧门板上，内侧门板可做扣手或无扣手； •带阻尼的推拉门默认带居中全圆扣手，尺寸200×22mm，不要扣手或特殊扣手需备注及标注； •使用木轨道的推拉门因扣手尽头有缺口，请勿设计通

### p230 · 3门推拉 4门推拉 4门位置调换导致的门边错开示例

- status: included_runtime
- domain: door_panel
- rule_type: material_mapping
- relevance_score: 7
- pricing_relevant: True
- tags: 门型, 尺寸阈值
- runtime_title: 门宽＞650mm需加竖撑单扇门
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

3门推拉 4门推拉 4门位置调换导致的门边错开示例 拼框木推拉门 拼框玻璃推拉门 真格栅推拉门 藤编推拉门 新古典格栅推拉门美式推拉门 单扇门宽≤1200mm 门宽＞650mm需加竖撑单扇门宽≤780mm 单扇门宽≤1200mm 门宽＞765mm需加竖撑单扇门宽≤1200mm 门宽＞650mm需加竖撑单扇门宽≤780mm 单扇门宽≤1200mm，门 宽＞650mm需加竖撑 此表仅展示基础样式，其他衍生样式此处不再罗列，可参考平开门样式。 门高、是否带中横等尺寸限制继承平开门数

### p234 · 铝框推拉门

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 投影面积, 门型, 尺寸阈值
- runtime_title: 默认双边居中内扣拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

4 1 四| ss SSS eos een — | 上 | |) sii ia - | | | s 铝框推拉门 •尺寸限制：600mm≤门宽≤1200mm，1200mm≤门高≤2600mm，且1 ㎡≤单门面积≤2.5㎡ •层板内缩： •门边宽度：26mm •门厚：26mm •轨道：铝框推拉门均使用五金轨道，不可用木轨道 •拉手：默认双边居中内扣拉手，可选择单边拉手，单边拉手时应 备注左右边；拉手尺寸不可调整，位置可调，上下距门边最小 50mm 拉手尺寸 日式障子门 •该门型常

### p249 · 60mm以下不能做居中圆扣手。

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 60mm以下不能做居中圆扣手。
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

60mm以下不能做居中圆扣手。 上翻回收展板门 平板上翻门 拼框上翻门 上翻回收展板门 •上翻回收展板门包括平板上翻回收展板门和简美上翻回收展板门；两门各尺寸限制信息一致，区别在于前挡条样式； •简美上翻回收展板门可见参考模型，常与美式书柜、美式卡座书柜等搭配 平板上翻回收展板门 简美上翻回收展板门 简美上翻回收展板门 回收状态 上翻回收门回收状态

### p251 · 下翻门（安全阻尼器）

- status: included_runtime
- domain: door_panel
- rule_type: material_mapping
- relevance_score: 6
- pricing_relevant: True
- tags: 投影面积, 门型, 尺寸阈值
- runtime_title: 可抠手开启、五金拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

4 Mad 下翻门（安全阻尼器） •门板面积（㎡）*门高H≤0.2 •开启方式：可抠手开启、五金拉手开启 •尺寸限制：门长度≤1040mm，真格栅下翻门门长度＞765mm时需加竖撑 拼框门高度≤560mm；横纹平板下翻门高度≤500mm，门高＞450mm时需要加中缝，内空深D≥150mm 拼框下翻门（含拼框玻璃），边框宽度：40mm≤W≤60mm（含斜切边；默认40mm，有其他临近平开门边框为60mm时可 调为60mm）；60mm以下不能做居中圆扣手 注意：请勿设计半盖下翻门

### p253 · 7.8 小型折叠门

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 可铣型拉手开启、五金拉手
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

7.8 小型折叠门 •单扇门重量需≤15kg •开启方式：可铣型拉手开启、五金拉手开启 •尺寸限制：250mm≤门宽≤500mm，门高≤1500mm •注意提醒客户关门时手不要放在中间门缝处，容易夹手 •小型折叠门柜体有内置抽屉时，开门方向需预留滑道架宽度150mm •设计小型折叠门时应在图纸中说明门板的开启方向（下图所示为左开门） 预留滑道架尺寸，防止抽屉碰撞门板 关门时 手不可 放置此 处 选用扣手开启时，只能选择上 下扣手，不能使用左右扣手 拉手示意图 门板无下轨道 层

### p255 · •额外收费的金属拉手在其信息说明中列出，未列

- status: included_runtime
- domain: accessory
- rule_type: dimension_threshold
- relevance_score: 6
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 额外收费的金属拉手
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

2个。 •额外收费的金属拉手在其信息说明中列出，未列 出的金属拉手无需额外收费；已列出的标准木拉 手无需额外收费，本册中未列出的其他样式木拉 手需收费，收费标准见报价原则。木质拉手 •型号：M-YB •名称：元宝拉手 •规格尺寸：37*17mm •型号：M-TG •名称：糖果拉手 •规格尺寸： 长度 120 150

### p257 · 80儿童木质拉手-用于儿童房家具

- status: included_runtime
- domain: accessory
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 儿童木质拉手
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

80儿童木质拉手-用于儿童房家具 •型号：JS-FX •名称：方形金属拉手 •规格尺寸： 长度31mm 宽度30mm 高度20mm •型号：JS-YX •名称：圆形金属拉手 •规格尺寸： 直径32mm 高度25mm •型号：JS-YZ •名称：圆珠金属拉手 •规格尺寸： 直径19mm 高度20mm •型号：JS-ZT •名称：锥台金属拉手 •规格尺寸： 直径上20下13mm 高度25mm •型号：JS-BK •名称：贝壳金属拉手 •规格尺寸： 直径25mm 高度23mm •型

### p262 · 140/160/180/200/220/240等20的整数倍数值；在抽屉上使用该3种

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 门型, 材质, 尺寸阈值
- runtime_title: 样式凹槽拉手
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

140/160/180/200/220/240等20的整数倍数值；在抽屉上使用该3种 样式凹槽拉手时，为方便使用，扣手长度需≥80mm。 •抽屉上使用半圆凹槽拉手、半圆对凹槽拉手时，设计时应注意扣手 长度应超过抽屉长度的一半。 半圆凹槽拉手半圆居中凹槽拉手全圆居中凹槽拉手全圆居中对凹槽拉手 半圆对凹槽拉手 扣手长度＞1/2抽屉长度 图4-32 单边扣手设计的拼框 对开门，无扣手门默 认在侧边加隐藏扣手20 Sy SEO NAR: pewesnd MLL aL ae a SOU

### p273 · 1" ii bl | tae mL th 册 ll il | aa | | Im fag eh = i | | il 几

- status: included_runtime
- domain: material
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 材质, 尺寸阈值
- runtime_title: 品牌：德利丰
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

1" ii bl | tae mL th 册 ll il | aa | | Im fag eh = i | | il 几 | a [seat | 欧茶 | | = i> 4 a a ff i, 3 by 4 金茶 i i] # 欧灰 上 8 埃 <a EX my 、 XY sis —e UA ss \—— | — GE me Ey lease 4 Se eS a ee | - e By •品牌：德利丰 •厚度：12mm •尺寸限制：最大3200*1600mm，建议长度≤240

### p289 · 24v驱动款可隔门板手扫雷达开关

- status: included_runtime
- domain: door_panel
- rule_type: material_mapping
- relevance_score: 8
- pricing_relevant: True
- tags: 材质, 尺寸阈值
- runtime_title: 适用于所有型号的单色温灯带
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

24v驱动款可隔门板手扫雷达开关 •产品编号：05.640.0011 •该开关为有线开关，控制方式为暗装手扫或者明装触摸； •可隔门板/石材板，将感应头隐藏在柜子内部，手在外端扫即可控制灯光开启和关闭； •适用材质及厚度：≤约25mm的木材、玻璃、石材、亚克力，不适用金属材质板材及金属材质包覆板； •可通过开关上的调节按钮进行三档感应距离调节，不同档位亮度与感应距离不一样； •适用于所有型号的单色温灯带;不可调节色温和亮度。 •产品颜色：灰色 •产品尺寸： 53.9*16*8

### p291 · 12mm集控触模感应开关(插拔头)05.65.0012；

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 12mm集控触模感应开关(插拔头)05.65.0012；
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

12mm集控触模感应开关(插拔头)05.65.0012； •可选明装（底座）/暗装（开孔嵌入）； •适用于所有型号的单色温灯带;不可调节色温；手扫和触摸开关可以调节亮度，人体红外开关不可调节亮度。 •产品颜色：太狼灰 •产品尺寸：12*24mm •产品特点： 此系列感应头正向和反向驱动均可使用，12V和24V驱动通用； 集控感应头不用区分正负极，正向和反向驱动均可使用； 感应头尾部带快插接口，感应头可与接线分离，方便检修替换； 集控感应开关，插入驱动专用控制接口上，可控制整个

### p297 · 1.打开米家APP，

- status: included_runtime
- domain: accessory
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 制灯带开关
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

1.打开米家APP， 点击首页右上角“+” 选择添加设备2.完成，创建好房间后 3.下一步，进入连接状态 4.界面显示连接中 5.连接成功后就可以手动控 制灯带开关灯/色温/亮度等 无线单面板动能开关 •产品编号： 白色：05.637.0011；灰色：05.637.0013 •该开关为无线开关，控制方式为单击灯亮，单击灯灭，长按调节亮度; •适用于所有型号的单色温灯带，可调节光的亮度，不能调节光的色温； •产品颜色：白色/灰色 •产品尺寸： 86*86*13mm 无线双门碰开

### p299 · ww LiL) anaemia | | :

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 适用于所有型号灯带
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

5 LOBSIINE ‘ ww LiL) anaemia | | : —= | ) + - SIS “ie SCRE ee BEDE 3S : BOA RE 无线下手扫开关 •产品编号： 05.629.0011 •该开关为无线开关，控制方式为手扫灯亮，再扫灯灭； •安装位置：装于层板下方 •手扫感应距离：5-8cm； •适用于所有型号灯带:选用单色温灯带时可调节光的亮度，不能 调节光的色温；选用双色温灯带时均可调节。 •产品颜色：黑色 •产品尺寸： 78.9*33.3*10.

### p310 · 3种进线方式,涵盖大部分安装场景

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 门型, 尺寸阈值
- runtime_title: 导致轨道
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

3种进线方式,涵盖大部分安装场景 有效避免因进线位置不同，导致轨道无法安装 逆时针旋转 灯灭断电 顺时针旋转灯亮通电 25.4mm 18.4mm 整体薄至43.8mm 图4-132 悍高旋转推拉镜900mm（703561）图4-133 悍高旋转推拉镜1100mm（703562）图4-134 苏柏瑞旋转推拉镜1200mm（1604） 柜体净内空进深≥推拉镜长度+10mm 例如：悍高旋转推拉镜90cm（703561）所需柜体净内空进深为350mm 含挂衣杆的内部空间高度≥推拉镜高

### p318 · 162) BETA TUBES AA TSI) =

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 无背板柜体需要安装拉条用膨胀螺丝与墙体固定
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

162) BETA TUBES AA TSI) = EWI! ENGITCOOUNRIEBIER (GIETNE’ HN’ RIG’ RAB’ BEMIE’ see RRA Se ES —— 3S 32 (2 ee CERES) •无背板柜体需要安装拉条用膨胀螺丝与墙体固定 •拉条尺寸：50*20mm 拉条拉条 L＞1200mmL≤1200mm防倾倒装置——无背板柜体 抽屉锁 •抽屉可使用指纹锁或普通锁；带锁抽屉上方必须要有层板或≥50mm宽的拉条； •下图为指纹锁基本信息，

### p326 · 海蒂诗大角度铰链

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 抽屉应距离门板至少60mm特殊铰链
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

95° 95° 海蒂诗大角度铰链 全盖、半盖、内嵌 开启角度：165°/120° 适用于20/22/26mm厚度木门 常用于转角柜、单开门钻石柜 常规柜体使用该大角度铰链，有柜内 抽屉时，抽屉应距离门板至少60mm特殊铰链 钻石柜只能做 平边/内嵌门 海蒂诗45°铰链 内嵌 开启角度：95° 适用于20/22/26mm厚度木门 常用于对开门钻石柜 钻石柜只能做 平边/内嵌门165°120°

### p329 · 165°铰链开启 默认铰链开启柜体离床铺很近，柜门单开一侧衣服拿取不太方便

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 10
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 165°铰链开启 默认铰链开启柜体离床铺很近，柜门单开一侧衣服拿取不太方便
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

165°铰链开启 默认铰链开启柜体离床铺很近，柜门单开一侧衣服拿取不太方便 默认铰链开启 165°铰链开启 aly tee 有 1e2. RUE as SO SY POP Ra Pe ge NE See a Sing < = <a DP ack Reh, ee oa Sg 人 OE ee ee Sz 和 CBE AO, a5 ES St =. See ees ea SS 和Ce ee ee ee Se EZ ee Se eS I Et Rt SS Ss 一人Er NE — e

### p341 · a)除标准模块中已有的围栏、孔洞、开口设计，请勿随意设计其他样式，如有需求请填写至需求表格；

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: a)除标准模块中已有的围栏、孔洞、开口设计，请勿随意设计其他样式，如有需求请填写至需求表格；
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

3.围栏 a)除标准模块中已有的围栏、孔洞、开口设计，请勿随意设计其他样式，如有需求请填写至需求表格； b)请勿设计可开启的围栏及其他部件，所有部件需满足在使用工具的情况下，产品及其零部件才能被拆卸； c)定制尺寸，围栏栏杆间隙应满足：不小于60mm且小于75mm，多个间隙值可用时，取根数最少； d)上床常规样式安全栏板高度限制为300-600mm，平板围栏≤450mm，特殊围栏高度＞600mm时，应添加横称保证结构稳定； e)上层床出入缺口（挂梯或梯柜入口）宽度W=400m

### p344 · 标准尺寸使用标准挂梯，定制尺寸时，应满足以下要求：

- status: included_runtime
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 标准尺寸使用标准挂梯，定制尺寸时，应满足以下要求：
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

4.1 挂梯 标准尺寸使用标准挂梯，定制尺寸时，应满足以下要求： a)应与床架相连，垂直或向上层床倾斜安装； b)地面到第一级踏脚板上表面的距离应不大于400mm； ≤400mm c)两连续踏脚板上表面的间距应为250mm±50mm； 200-300mm d)所有踏脚板上表面间的距离应均匀，允差为±5mm； abcdee)连续两踏脚板间净空距离应不小于200mm； 净空距离≥200mm f)踏脚板的使用宽度应不小于300mm； 使用宽度≥300mm g)所有踏脚板上表面的前边

### p348 · 600mm需分为2个抽屉；

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 600mm需分为2个抽屉；
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

600mm需分为2个抽屉； 450-600mm f)踏脚板的上表面前边缘应在一直线上，允差为±20mm； g)步深应不小于200mm，不大于475mm，最上层进出平台深 度475mm； 475mm ≥200mm 一一 日 TAA 床铺 a)产品相邻上床铺面与下床铺面之间的净空距离1000-1200mm；双层床及高架床设计时应注意上床距离屋顶空间，防止上床后无法起身， 离顶高度建议大于900mm； b)床铺面组件间（排骨条）的间隙应小于75mm；请勿随意修改标准排骨架排骨条间隙

### p355 · 25mm 或 60≤L＜75mm 或 L≥200mm；挂梯落地、错落差值变化时，挂梯始终位于上床右侧，位置变动时，上床床腿距离下床床腿的距离L

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 设计时应注意上床距离房顶高度，以免无法起身，使用不便
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

25mm 或 60≤L＜75mm 或 L≥200mm；挂梯落地、错落差值变化时，挂梯始终位于上床右侧，位置变动时，上床床腿距离下床床腿的距离L 应满足同上要求； 挂梯落于下床 挂梯落地L L 床底无支撑 床底有部分柜体支撑床底有等宽等长柜体支撑•所有高架床及错层床上床底部无柜体时，上床离地高度h≤1450mm，床底有部分柜体支撑时，离地高度h≤1600mm，床底有床体等长等宽柜体 支撑时，离地高度h≤1800mm；设计时应注意上床距离房顶高度，以免无法起身，使用不便； 儿童房

### p358 · 1.6 稳定性

- status: included_runtime
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 7
- pricing_relevant: True
- tags: 门型, 尺寸阈值
- runtime_title: 床榻包括箱体床、架式床、儿童床、榻榻米
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

1.6 稳定性 高桌台（产品总高度超过1000mm，配有书架或类似结构的桌台类产品，如书桌柜）及高度大于600mm的柜架类产品，需要添加防倾倒装置； 上表面离地高度不小于 600 mm床铺声明 上下床/高架床，上铺宽度均不能超过1.2M，为单人床尺寸，超过1.2M宽的高层产品定仅允许定制置物架，且置物架不提供休息功能，儿童 成人均不可在置物架上住宿。 √ •床榻包括箱体床、架式床、儿童床、榻榻米。 •床类产品作为成品标准款出售时无法对床的外观尺寸进行修改；若为标准款产品，可直

### p363 · 50*80*260mm（黑色）；尾翻箱体床限位器安装于床头方向，

- status: included_runtime
- domain: bed
- rule_type: formula
- relevance_score: 10
- pricing_relevant: True
- tags: 材质, 公式, 尺寸阈值
- runtime_title: 尾翻箱体床限位器安装于床头方向， 尾翻床床垫宽度＜1500mm时安装1个，床垫宽度≥1500mm时 安装2个
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

50*80*260mm（黑色）；尾翻箱体床限位器安装于床头方向， 尾翻床床垫宽度＜1500mm时安装1个，床垫宽度≥1500mm时 安装2个；侧翻箱体床限位器安装于侧面（与锁扣相反方 向），安装2个。 尾翻床安装于床头 侧翻床安装于锁扣相反方向侧面 床垫限位器床垫限位器 | | PA: j ] < ie 本 | 人 | | 二一 下， TET: =>) a ole ig | = 由 a Ss ara QNEKRE—-G BARE Wuoww wer Fig v OAVRMUV

### p366 · 1.尺寸

- status: included_runtime
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 尺寸 双层床上床及高架床床宽应≤1200mm（床垫尺寸） *高架床指床铺面（排骨架）的上表面离地高度≥600mm的床类产品 双层床上下床铺面之间净空距离建议不小于1100mm 双层床及高架床设计时应注意上床距离屋顶空间，防止上床后无法起身，离顶高度建议不小于900mm ≤1200mm 离地高度 离地高度
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

1.尺寸 双层床上床及高架床床宽应≤1200mm（床垫尺寸） *高架床指床铺面（排骨架）的上表面离地高度≥600mm的床类产品 双层床上下床铺面之间净空距离建议不小于1100mm 双层床及高架床设计时应注意上床距离屋顶空间，防止上床后无法起身，离顶高度建议不小于900mm ≤1200mm 离地高度 离地高度

### p367 · 3.安全栏板

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: b）上层床出入缺口宽度W范围应符合：300mm≤W≤400mm
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

3.安全栏板 a）独立双层床/高架床的上层铺面应设置安全栏板，仅允许在进出床铺面一侧留有进出缺口，其余部分应全部封闭。当特殊定制与其他柜体组合 的双层床/高架床，与柜体连接的一侧可无安全栏板，其他三面应设置安全栏板，床体应与柜体固定。 特殊定制一侧靠墙的双层床/高架床，与墙体连接的一侧可无安全栏板，其他三面应设置安全栏板，床体应与承重墙面固定。 b）上层床出入缺口宽度W范围应符合：300mm≤W≤400mm。与柜体固定 三面围栏与墙面固定 三面围栏 c）无专用工具时，安全栏板

### p369 · 2.床垫重量应≤50kg，设计时需考虑客户家床垫重量，如床垫超重可使用两套750N举升器，下单时需备注。

- status: included_runtime
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 6
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 床垫重量应≤50kg，设计时需考虑客户家床垫重量，如床垫超重可使用两套750N举升器，下单时需备注。
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

2.床垫重量应≤50kg，设计时需考虑客户家床垫重量，如床垫超重可使用两套750N举升器，下单时需备注。 床垫尺寸限制W≤1800、L≤2000，当W＞1800时默认使用两套750N举升器，需要单独收费，详见报价原则。

### p370 · 750N举升器，下单时需备注床垫重量以及举升器数量。

- status: included_runtime
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 6
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 750N举升器，下单时需备注床垫重量以及举升器数量。
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

750N举升器，下单时需备注床垫重量以及举升器数量。 床垫尺寸限制W≤1800、L≤2000，当W＞1800时默认使用两套750N举升器，需要单独收费，详见报价原则。

### p374 · 3.排骨架间隙为15-25mm

- status: included_runtime
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 7
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 排骨架间隙为15-25mm 主要适用于尾翻箱体床等排骨架 榻榻米结构
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

3.排骨架间隙为15-25mm 主要适用于尾翻箱体床等排骨架 榻榻米结构 •榻榻米（无屉版） •外框架前后盖左右，板件 厚度20mm •盖板尺寸规范参见《榻榻 米盖板及其撑杆》 •榻榻米（带屉内嵌版） •外框架前后盖左右 •前框厚度22mm，其他20mm •前框边框宽度≥60mm •抽屉上为固定盖板，盖板尺寸规范参见 《榻榻米盖板及其撑杆》•榻榻米（排骨架带屉版） •外框架前后盖左右 •前框厚度22mm，其他20mm •上边宽≥60mm+排骨架下嵌尺寸 •两侧及下边宽≥60m

### p378 · 30/30mm，如中边框宽度90mm，则分段缝左右边宽45/45mm。榻榻米超长解决方案

- status: included_runtime
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 榻榻米超长解决方案
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

30/30mm，如中边框宽度90mm，则分段缝左右边宽45/45mm。榻榻米超长解决方案 榻榻米盖板 •榻榻米盖板边框厚度26mm，芯板平装11mm •边框宽度50mm •格子拼框结构，格子芯板大小应控制在300-500mm之间 A：可开启盖板 B：不可开启盖板 盖板统一为外平装；可开启盖板芯板上有Φ30mm通孔扣手，左右居中； 不可开启盖板不开扣手孔。 *可开启盖板支持带阻尼撑杆开启或无撑杆手动开启两种方式，默 认带撑杆，无撑杆需备注。L＜210mm，H＜150mm时无法安

### p390 · 8 I a ¥ we Nu’ & by LOX gum

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 以上产品下单图纸进行尺寸标注时，应标注桌面/凳面尺寸，请勿标注支腿尺寸
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

8 I a ¥ we Nu’ & by LOX gum 二 一- Z I TOQUI 上 Cs-04 BHSM\eN-0) 合肝书谨\CS-08 BHLESSHSEY SO BEWE 罗胖系列产品说明 罗胖系列桌类，包括CZ-01 罗胖餐桌、CZ-08 罗胖带屉餐桌、CZ-09 罗胖高屉餐桌、SZ-01 罗胖书桌； 罗胖系列凳类，包括TD-01 罗胖条凳； 以上产品下单图纸进行尺寸标注时，应标注桌面/凳面尺寸，请勿标注支腿尺寸； 罗胖系列产品支腿尺寸比桌面尺寸默认大10mm，

### p394 · 1800*900*780订制款：

- status: included_runtime
- domain: general
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 1800*900*780订制款： 长度≤2100mm 宽度≤900mm L尺寸要求 S上腿径X下腿径ZS左右上边距ZX左右下边距QS前后上边距QX前后下边距H横称高度
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

1800*900*780订制款： 长度≤2100mm 宽度≤900mm L尺寸要求 S上腿径X下腿径ZS左右上边距ZX左右下边距QS前后上边距QX前后下边距H横称高度

### p399 · 2400*1000*780SZ-17 长滩岛/长滩岛Y

- status: included_runtime
- domain: cabinet
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 材质, 尺寸阈值
- runtime_title: 整体变化：边角样式均可做平边或圆边
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

2400*1000*780SZ-17 长滩岛/长滩岛Y 仅可做樱桃木/黑胡桃木 桌面及桌腿厚度均为45mm 支腿可选木支腿/亚克力支腿 标准支腿间间距不可调整 漂流岛样式定制 •整体结构不变，桌面与桌腿样式可变； •整体变化：边角样式均可做平边或圆边； •桌面要求：四周圆角范围为R2.5～R100mm；桌面底部开槽尺寸不变，与标品相同； •桌腿要求：整体长度、宽度、厚度不变，可参考以下给定款式，在结构不变的前提下做样式修改； •注意：定制时需标注样式细节及尺寸，选用以下模型时

### p399 · 超长定制款：桌长超过2400可进行分段定制，分段处需增加支腿，支腿尺寸不变；中支腿位于分缝处中心，左右支腿参照标准品左右距边SZ-14 漂流岛/漂流岛Y

- status: included_runtime
- domain: table
- rule_type: dimension_threshold
- relevance_score: 7
- pricing_relevant: True
- tags: 材质, 尺寸阈值
- runtime_title: 超长定制款：桌长超过2400可进行分段定制，分段处需增加支腿，支腿尺寸不变；中支腿位于分缝处中心，左右支腿参照标准品左右距边SZ-14 漂流岛/漂流岛Y
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

2400*1000*780 超长定制款：桌长超过2400可进行分段定制，分段处需增加支腿，支腿尺寸不变；中支腿位于分缝处中心，左右支腿参照标准品左右距边SZ-14 漂流岛/漂流岛Y 仅可做樱桃木/黑胡桃木 桌面及桌腿厚度均为45mm 支腿可选木支腿/亚克力支腿 标准支腿间间距不可调整漂流岛&长滩岛 SZ-17 长滩岛 SZ-17 长滩岛Y 标准款：

### p403 · 订制款：

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 2000*900*780 订制款： 长度≤2000mm 宽度≤900mm其他桌 该类书桌必须固定在承重墙上;无需与其他柜体固定订制注意事项：
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

2000*900*780 订制款： 长度≤2000mm 宽度≤900mm其他桌 该类书桌必须固定在承重墙上;无需与其他柜体固定订制注意事项：

### p404 · 1200*400*146 1600*400*146

- status: included_runtime
- domain: table
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 使用时需在图纸 中标注并备注
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

1200*400*146 1600*400*146 高度调节脚，可用于支腿高度不一的订制桌类。使用时需在图纸 中标注并备注。 调节脚安装后底部有胶垫，调节脚尺寸： 在图纸中标注尺寸时，标注支腿实际尺寸即可， 无需考虑调节脚高度，调节脚可在图纸中标注并 在合同中备注使用调节脚。 桌类高度调节脚 440mm 400mm 550mm 430mm

### p404 · 2.桌面厚度不可更改，仅可调整抽屉尺寸，抽屉高度最小110mm；

- status: included_runtime
- domain: table
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 桌面厚度不可更改，仅可调整抽屉尺寸，抽屉高度最小110mm；
- runtime_action: constraint
- reason: 已进入运行时追加规则，action_type=constraint

2.桌面厚度不可更改，仅可调整抽屉尺寸，抽屉高度最小110mm；

### p404 · 3.若作为书桌或梳妆台等需考虑桌下容腿空间，柜体下沿距地建

- status: included_runtime
- domain: cabinet
- rule_type: dimension_threshold
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 若作为书桌或梳妆台等需考虑桌下容腿空间，柜体下沿距地建
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

3.若作为书桌或梳妆台等需考虑桌下容腿空间，柜体下沿距地建 议≥580mm。 订制款： 长度：400≤L≤2400 进深：400≤D≤500 高度：146≤H≤386 挂墙桌 配件注意事项： 此支架为隐藏支架； 悬空支架个数要求:两支架间距≤1000mm； 两个支架的承重为60kg，设计时请注意柜体重量。悬空支架 支架安装位置展示 标准款：

### p417 · 450mm786mm160mmYZ-14 吧椅

- status: included_runtime
- domain: table
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 门型, 尺寸阈值
- runtime_title: 备注示例：标准三人位沙 发垫，布艺-RHO-502 原野
- runtime_action: adjustment
- reason: 已进入运行时追加规则，action_type=adjustment

450mm786mm160mmYZ-14 吧椅 YZ-15 新罗胖椅 465mm 465mm 440mm440mm 820mm148mm •注意： •橙色数据为外径尺寸； •所有椅子尺寸均为手动测量有误差， 同款椅子尺寸也会存在轻微差别； •标准款沙发请勿进行尺寸及样式调整；订制款沙发仅3人位以上可做订制，只订制长度，其它尺寸不做订制。 •三款沙发沙发垫可通用，设计时应在合同中备注沙发垫名称及颜色，并截图手册附于合同中。备注示例：标准三人位沙 发垫，布艺-RHO-502 原野

## manual_review

### p1 · 良禽佳木设计师标准手册

- status: manual_review
- domain: material
- rule_type: formula
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

前言 良禽佳木设计师标准手册 版本20260322 ES SENG HE SE 原木定制三大误区 实木 = 原木？ 木材小知识 均属于木质人造板(wood-based panel) GB/T 28202-2020 《家具工业术语》中，对于实木家具的定义： 由此可见，实木家具并不是我们印象中的“全部使用原切木材”制成的家具，像薄木贴面、指接材、集成材家具，都可以称为实木家具。而 指接材、集成材这类材料，均属于木质人造板，不属于原木。因此，实木家具并不等同于原木家具。树木伐倒后除

### p20 · N Ne i 5 —— Se A dare le |

- status: manual_review
- domain: door_panel
- rule_type: formula
- relevance_score: 5
- pricing_relevant: True
- tags: 门型, 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2s —— — Mb Tr N Ne i 5 —— Se A dare le | Ts eae Sa. Was monies oe | Tin 不吗 和 96 as | ia bes, ST) Pe 弄虽 ea: ia a 也 ea) = mie ee e ‘ 2 = — = u lee We |@) a — wen : ane ES — a —— Eee ==, A 虽 于 < > 一 加 ne paar = = a (es oa <= EASES BAB yak ST w

### p30 · REUSE WIAD’ Mc A MTSE IM SET °

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1 | 55 Luw 1 REUSE WIAD’ Mc A MTSE IM SET ° Be hE

### p49 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: formula
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

4 ] ‘| | = mt My | | inl |一|

### p49 · 窄边风格——拆装注意事项

- status: manual_review
- domain: cabinet
- rule_type: formula
- relevance_score: 6
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

8 | a“ ; ii BwEY-wy St 窄边风格——拆装注意事项 门盖牙称与顶挡条时最少需要留出15mm | TSE wD Be To 中 shi —_H ee teem 场景—— 整装斗柜示例 pa a a4 | ta - 场景—— 整装斗柜示例 — cli a 中 cdg ; FTE ~ { CF a al i ba oe ie 4 i 柜体结构 柜体结构示例（拆装为例）： Jew wee et Bly SS ee EE == we pa 四 cS kt sousw

### p86 · 3. 顶板飞檐-顶盖侧，侧包底

- status: manual_review
- domain: cabinet
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 柜体
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

3. 顶板飞檐-顶盖侧，侧包底 二、燕尾榫：除以上3种外的整装家具 顶底包侧（吊柜；常规支腿柜） / 顶盖侧，侧包底（落地柜） 特殊情况： 当如下电视柜组合高矮柜搭配时，需要和矮柜匹配，做顶盖侧， 侧包底（落地柜）/顶底包侧（支腿柜），燕尾榫。 单独整装柜体高度大于1700时，侧包顶底，单肩榫； 特殊整装美式柜框（左/右不出沿），顶底包侧，不出沿 部分连接使用单肩榫 特殊整装美式柜框 左不出沿 右不出沿 左右不出沿 单体组合柜说明 由多个单体柜组合成一个整柜时，为方便生产，通

### p127 · 1200＜L≤1600D≤300 H＜900 无托称后托称*1

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1200＜L≤1600D≤300 H＜900 无托称后托称*1 D≤300 H≥900 前托称*1前托称*1 后托称*1D＞300 /

### p127 · 1600＜L≤1800/ H＜900 60*26（木质托称）

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1600＜L≤1800/ H＜900 60*26（木质托称）

### p127 · 1800＜L≤2000/ H＜900 前托称*1前托称*1

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1800＜L≤2000/ H＜900 前托称*1前托称*1 后托称*170*26（木质托称）

### p174 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

400≤D≤480 350m

### p174 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

480≤D≤580 450mm

### p174 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

580≤D≤680 550mm

### p174 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

680≤D≤780 650mm

### p176 · 7.2 平开门

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

7.2 平开门 铰 链 所 在 边铰 链 所 在 边上门 边上门 边 上门边 ≤1.5 铰链所在边进行平开门的设计时，需注意一些特殊要求，分列如下：

### p177 · 2.柜门数量为单数的柜体，需附图说明柜门开启方向，以便生产。

- status: manual_review
- domain: cabinet
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 柜体
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2.柜门数量为单数的柜体，需附图说明柜门开启方向，以便生产。

### p179 · 平板平开门尺寸限制快速检索表

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

510单位：mm ≤2300 ≤2300≤2300 平板平开门尺寸限制快速检索表 骨 骼 线 门 板零 食 柜 门单位：mm ≤2300 ≤450 ≤2300

### p180 · 外观有中缝

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

450＜W≤600mm 外观有中缝

### p191 · 305≤h≤2700 305≤h≤2200180≤W≤500

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

305≤h≤2700 305≤h≤2200180≤W≤500 铝框平开门尺寸限制快速检索表 针 式 铰 链 铝 框 门门厚 门边框宽度 扣手及铰链处厚度36 其余厚度22上下门框宽31 左右门框宽29单位：mm

### p191 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

22 22 26 26单位：mm

### p191 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

180≤W≤560

### p192 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

180≤W≤500

### p192 · 铝框平开门尺寸限制快速检索表

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

305≤h≤3000 36mm 36mm22mm 铝框平开门尺寸限制快速检索表 铝 框 岩 板 门 门厚 门边框宽度

### p193 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

22 55单位：mm

### p193 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

300≤W≤500

### p201 · 1.抽屉上下左右都是内嵌的情况，抽面 22 厚(美式抽屉除外)

- status: manual_review
- domain: accessory
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.抽屉上下左右都是内嵌的情况，抽面 22 厚(美式抽屉除外)

### p201 · 2.有 26 厚门板和 22mm 抽屉的情况，抽面全盖层板

- status: manual_review
- domain: door_panel
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2.有 26 厚门板和 22mm 抽屉的情况，抽面全盖层板

### p202 · 1500拼框平开门尺寸限制快速检索表-a

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1500拼框平开门尺寸限制快速检索表-a 单位：mm ≤560 ≤2200 ≤560 ≤2300≤560 ≤2200≤560 ≤2300≤560 ≤2200≤560 ≤2300 超 高 拼 框 木 门 门厚 门边框宽度

### p202 · 26 门高＞1500 26门高＞150026门高＞

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

26 门高＞1500 26门高＞150026门高＞

### p202 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

22 门高≤1500

### p202 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

6022门高≤1500

### p202 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

6022门高 ≤1500 60

### p203 · 26 60拼框平开门尺寸限制快速检索表-a

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

26 60拼框平开门尺寸限制快速检索表-a 单位：mm ≤560

### p203 · 门厚 规格 门边框宽度 门厚 门边框宽度 门厚 规格门边框宽

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2300＜H≤2600 经 典 玻 璃 门拱 形 玻 璃 门 门厚 规格 门边框宽度 门厚 门边框宽度 门厚 规格门边框宽 度

### p204 · 1500拼框平开门尺寸限制快速检索表-a

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1500拼框平开门尺寸限制快速检索表-a 单位：mm ≤560 ≤2200≤560 ≤2300≤560 ≤2300 ≤560 ≤2200 拱 形 玻 璃 门胶 囊 玻 璃 门 门厚规格门边框 宽度门厚 门边框宽度 门厚规格门边框 宽度门厚 规格门边框宽度

### p204 · 26 门高＞1500 26门高＞

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

26 门高＞1500 26门高＞

### p204 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

22 门高≤1500

### p204 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

60 26 6022门高 ≤1500 60

### p205 · 1500拼框平开门尺寸限制快速检索表-a

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1500拼框平开门尺寸限制快速检索表-a 单位：mm ≤560 ≤2300≤560 ≤2300≤560 ≤2200≤560 ≤2300 超 高 拼 框 玻 璃 门 门厚 门边框宽度

### p205 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

22门高 ≤1500

### p205 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

60 26 6022门高 ≤1500

### p205 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

6022门高 ≤1500 60

### p205 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

26门高＞

### p205 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

150026门高＞

### p205 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1500 26门高＞

### p206 · 26 60拼框平开门尺寸限制快速检索表-a

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

26 60拼框平开门尺寸限制快速检索表-a 单位：mm ≤560

### p206 · 门厚 规格 门边框宽度 门厚 规格 门边框宽度

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2300＜H≤2600 新 古 典 格 栅 门真 格 栅 门 门厚 规格 门边框宽度 门厚 规格 门边框宽度

### p207 · 22门高≤1500且无

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

22门高≤1500且无 玻璃

### p207 · 26门高＞1500或

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

26门高＞1500或 带有玻璃26 门高＞1500≤560 ≤2300≤560 ≤2300 拼框平开门尺寸限制快速检索表-a 单位：mm 藤 编 门拱 形 藤 编 门 门厚 门边框宽度 门厚 门边框宽度

### p207 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

6022 门高≤1500 60

### p208 · 22 60（外露30） 22 60（外露30）≤560

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 5
- pricing_relevant: True
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

22 60（外露30） 22 60（外露30）≤560 ≤2300 ≤560 ≤2300拼框平开门尺寸限制快速检索表-a 单位：mm 美 式 木 门美 式 玻 璃 门 门厚 门边框宽度 门厚 门边框宽度

### p222 · 1.经年累月的使用和磨损：即使经过处理的藤编家具表面一开始是光滑的，随着时间的推移和频繁的使用，表面可能会受到摩擦和磨损，

- status: manual_review
- domain: general
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 门型
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.经年累月的使用和磨损：即使经过处理的藤编家具表面一开始是光滑的，随着时间的推移和频繁的使用，表面可能会受到摩擦和磨损， 从而导致毛刺的出现。

### p222 · 3.温度变化：温度的变化也可能影响藤编家具的表面。较大的温度变化也可能导致藤材料收缩或膨胀，进而产生毛刺。

- status: manual_review
- domain: general
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 门型
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

3.温度变化：温度的变化也可能影响藤编家具的表面。较大的温度变化也可能导致藤材料收缩或膨胀，进而产生毛刺。 为了尽量避免藤编家具表面出现毛刺，可以采取以下措施：

### p227 · 1. 木轨道及五金轨道使用规则见表

- status: manual_review
- domain: general
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1. 木轨道及五金轨道使用规则见表 木轨道五金轨道 五金无阻尼轨道五金带阻尼轨道

### p227 · 22厚门板：直边、圆边内缩60mm，内斜边内缩65mm

- status: manual_review
- domain: door_panel
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

22厚门板：直边、圆边内缩60mm，内斜边内缩65mm

### p227 · 门高≤1200300≤门宽＜450

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

300≤门宽＜800 门高≤1200300≤门宽＜450 门高＞1200门宽≥450

### p232 · 300≤W≤12001200＜H≤2300单块小门板W≤600mm

- status: manual_review
- domain: door_panel
- rule_type: formula
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

300≤W≤12001200＜H≤2300单块小门板W≤600mm — SSS SSeS = oa Saas — = —~ aa — —=5 一 es SS 本 — 有 = 一 ， ny NUL/ =

### p233 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1 ~ ———— oa Be ya al Fy | Ri Wh | | he | | : 有 ee il la | ta ; N | | Hi | a :

### p251 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

3e0 um

### p251 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

50 ww abu \T wu F 8 el RCL] eZ

### p256 · 180儿童木质拉手-用于儿童房家具

- status: manual_review
- domain: accessory
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

180儿童木质拉手-用于儿童房家具 •型号：M-TTQ •名称：甜甜圈拉手 •规格尺寸： 直径 120 150 180 •型号：M-TZ •名称：兔子拉手 •规格尺寸： 长度-高度 60-80 90-120

### p256 · •名称：云朵拉手

- status: manual_review
- domain: accessory
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

120-160•型号：M-YD •名称：云朵拉手 •规格尺寸： 长度 60 90

### p256 · •名称：四叶草拉手

- status: manual_review
- domain: accessory
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

120•型号：M-SYC •名称：四叶草拉手 •规格尺寸： 长度 60 90 120 •型号：M-YN •名称：圆纽拉手 •规格尺寸： 直径 40 60

### p257 · •名称：圆形拉手

- status: manual_review
- domain: accessory
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

80•型号：M-YX •名称：圆形拉手 •规格尺寸： 直径 40 60 80 •型号：M-JY •名称：鲸鱼拉手 •规格尺寸： 长度 60

### p257 · •名称：小熊拉手

- status: manual_review
- domain: accessory
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

80•型号：M-XX •名称：小熊拉手 •规格尺寸： 长度 60

### p257 · •名称：小鱼拉手

- status: manual_review
- domain: accessory
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

80•型号：M-XY •名称：小鱼拉手 •规格尺寸： 长度 60

### p282 · 20 GIA Wee IUfGUW69A6' 92 GAYS 92 QIUCWG WOOUPE LOMIUa ILO | | Dig ae why

- status: manual_review
- domain: general
- rule_type: formula
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

20 GIA Wee IUfGUW69A6' 92 GAYS 92 QIUCWG WOOUPE LOMIUa ILO | | Dig ae why Chauulua PESCpE2 S|OUA (WE BISCK Cosar Ie PLES—U;SKIUG’ 1he PUALE Suq | ke as cnlintsl cys Fh6 mundns eceusiA pow pS Basu bese po pus SS ‘ enti (V6 BIIKSU bsuluanle I

### p282 · SUQ GAe-Carcuiud' : 1

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2bECIEICVLION , SUQ GAe-Carcuiud' : 1 bre wiviwwaes ebscee’ jpe G9 esse me Bnlasu9u zfou6 12 biecione i 3

### p283 · 6xbkeazz6z (UG [LNG PESNFA AMAIFP LUIVILUS] PISCK AAG pellsAs FUSE SI] KIUG2 P |

- status: manual_review
- domain: general
- rule_type: formula
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

6xbkeazz6z (UG [LNG PESNFA AMAIFP LUIVILUS] PISCK AAG pellsAs FUSE SI] KIUG2 P | Ifa blelu' pag fbe Moulq ceu cowubere MIfb LOL pegnfX Ynkokg BISCK | | VARA SS EES TL ww BDB Ae” i (Eta) HWY LISI S SI MIRE WED Soy MEAD BL | WK as 人 二 = < a e

### p284 · 2onj2 QGWwouztisf2 [Pe Lwgl]e2fIcG' UGIGELIC SUG GXfLIOLGIUSLA . i —e re ZZ ] | - A

- status: manual_review
- domain: cabinet
- rule_type: formula
- relevance_score: 7
- pricing_relevant: True
- tags: 柜体, 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2onj2 QGWwouztisf2 [Pe Lwgl]e2fIcG' UGIGELIC SUG GXfLIOLGIUSLA . i —e re ZZ ] | - A Uu6f9lIIC PEXENLG2 LG Clhiz2-cLozzeq ‘ |¢ cabinie2 beobjs pesise guq / . ast ~ => if | | 一 日 人 FIK6 9 LSA OL q9MU 9ckozz (UG zkKN zf9lu6q MIFH IUK ue MDIF6 

### p290 · 24v驱动款可隔门板手扫雷达开关

- status: manual_review
- domain: door_panel
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

24v驱动款可隔门板手扫雷达开关 •安装位置及使用方式指引 可底装放置在岩板或台面 下方上从上方手扫开启 可侧装 放置在 侧板里 面，隔 侧板手 扫开启 正面明装可做触摸开关

### p291 · 12mm集控人体红外感应开关(插拔头)05.63.0012；

- status: manual_review
- domain: accessory
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

12mm集控人体红外感应开关(插拔头)05.63.0012；

### p291 · 12mm集控感应开关（插拔头）系列：共三款

- status: manual_review
- domain: accessory
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

12mm集控感应开关（插拔头）系列：共三款 •产品编号：12mm集控手扫感应开关(插头)05.62.0012；

### p296 · 1.小爱音箱：灯带接到电源上后，呼叫小爱同学，通过与小爱同学对话发出指令，实现灯带的配对，

- status: manual_review
- domain: accessory
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.小爱音箱：灯带接到电源上后，呼叫小爱同学，通过与小爱同学对话发出指令，实现灯带的配对， 以下是对话过程，红色字体为需要下达的指令，白色字体为小爱同学回答

### p296 · 2.发现设备

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2.发现设备 回答：稍等一下，正在帮你发现设备 发现一个设备情景mesh三色灯VRS系列， 是否需要连接3.连接 回答：稍等一会儿，设备连接中

### p296 · 5.弹出设置界面，设置好即可通过语音

- status: manual_review
- domain: accessory
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

5.弹出设置界面，设置好即可通过语音 进行操控：开关灯/色温/亮度等（在连接的过程中灯带灯光会闪烁提醒） 米家控制盒灯带开关:配对教程

### p297 · 2.手机米家APP：音箱连接后，手机APP会直接显示该设备，下面演示如何直接用米家APP配对灯带设备，通过手机操控灯带数值。

- status: manual_review
- domain: accessory
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2.手机米家APP：音箱连接后，手机APP会直接显示该设备，下面演示如何直接用米家APP配对灯带设备，通过手机操控灯带数值。

### p316 · 39mm30mm33mm24mm•无刹车

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

39mm30mm33mm24mm•无刹车 1.5mm 25mm 25mm •安装面板 防倾倒装置——安装使用说明(贴纸标识） Wek eVS Wt eLS WEIR SYS Le ER e\e ie LL eee PRUE E LIE oe © WWERBLELANERMWEYELESSETR SESECR ERE TS ° SUMUMN_XRW MEE S SER SEE KERE: a Ome © TL AL EREY CRUE RATAN BHER MURR Rune 

### p324 · 3 SYEUM SVREBVSMLTS SVB BML

- status: manual_review
- domain: accessory
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

3 SYEUM SVREBVSMLTS SVB BML y SYP AVREMEP SL BVM T BPS S (Vv) BA: 。 (Cp Stee 。 eam 。 FB Hy: 机械抽屉锁 •普通锁使用钥匙开启，颜色可选黑色、镍色，使用时应备注及附图； •注意使用普通锁时抽屉无法使用通长扣手；可选择靠左、靠右、居中安装； •带锁抽屉上方必须要有层板或≥50宽的拉条； •普通锁仅可用于锁住一个抽屉，不可联排锁定； •抽屉锁芯直径20mm，靠左或靠右安装时中心距边100mm

### p327 · 海蒂诗铝框门铰链

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

95° 海蒂诗铝框门铰链 全盖、半盖、内嵌 开启角度：95° 适用于常规开启铝框门 海蒂诗铝框门大角度铰链 全盖、半盖、内嵌 开启角度：165°/120° 适用于常规开启铝框门 海蒂诗平门铰链 内嵌 开启角度：95° 适用于20/22/26mm厚度木门 常用于L型转角柜

### p328 · 特殊情况：根据门板情况会使用默认铰链，若想使用海蒂诗165°铰链需要上传图纸并备注：柜体的安装位置图纸以及备注哪扇门需要更换大角度铰链

- status: manual_review
- domain: cabinet
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 柜体
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

95° 特殊情况：根据门板情况会使用默认铰链，若想使用海蒂诗165°铰链需要上传图纸并备注：柜体的安装位置图纸以及备注哪扇门需要更换大角度铰链

### p341 · 1. 通用要求

- status: manual_review
- domain: bed
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 门型
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1. 通用要求 a)设计儿童床时，所有外露边角应为圆边圆角； b)儿童床上涉及的抽屉，设计时优先使用扣手，如使用其他拉手，应选择“儿童拉手”分类内产品； c)床体任何部位请勿设计挂钩、装饰图形等突出物体； d)请勿将藤编、网布等网织物应用于儿童床任何可触及区域；

### p341 · 2.注意事项

- status: manual_review
- domain: bed
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2.注意事项 应告知客户以下注意事项： a)上层床不适合6岁及以下的人群使用，因有跌伤的危险。 b)请勿在产品的任何部分附加或悬挂任何不适合用于床的物品，例如，但不限于绳索、绳子、钩子、皮带和袋子。因使用不当，产品可 能导致勒死的严重危险。 c)注意防止从进出缺口处掉落。 d)上层床仅允许1人使用。 e)如果产品有任何结构部件损坏或缺失，请勿使用。

### p344 · 4.进出通道

- status: manual_review
- domain: bed
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

4.进出通道 a)上层床应有进出通道（如梯子、楼梯等） b)梯子最上层脚踏板或者楼梯最上层梯柜上表面与围栏出入口或限制床褥最大厚度的永久性标记线（选两者中较高者）间的距离应不大于

### p344 · 500mm，或者与没有缺口的安全栏板顶部距离不大于500mm。

- status: manual_review
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

500mm，或者与没有缺口的安全栏板顶部距离不大于500mm。 c)进出通道与相邻床架刚性部件间的距离应：小于7mm；或不小于12mm，小于25mm；或不小于60mm，小于75mm；或不小于200mm。

### p357 · 1.1 边缘、尖端及外角

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.1 边缘、尖端及外角 设计儿童房家具时，外露边角应为圆边圆角。 不应有危险外角，其角的圆半径应不小于10mm，或圆弧长不小于15mm，尤其注意桌类、柜类产品四角圆弧设计； 家具危险外角示意图

### p358 · 1.2 突出物

- status: manual_review
- domain: accessory
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.2 突出物 设计儿童家具时优先使用扣手，使用其他拉手，应选择“儿童拉手”分类内产品；

### p358 · 1.3 孔、间隙及开口

- status: manual_review
- domain: general
- rule_type: narrative_rule
- relevance_score: 3
- pricing_relevant: False
- tags: 门型
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.3 孔、间隙及开口 请勿将藤编、网布等网织物应用于家具任何可触及区域；

### p358 · 1.4 垂直开启的翻门、翻板

- status: manual_review
- domain: general
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.4 垂直开启的翻门、翻板 请勿在儿童家具中设计可回收上下翻门、随意停上下翻门；

### p358 · 1.5 玻璃部件

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.5 玻璃部件 除距离地面高度和其他站立面高度1600mm以上的区域外，儿童家具不应使用玻璃部件；

### p362 · •带举升器的箱体床默认安装床垫限位器，限位器规格为：

- status: manual_review
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

60mm≤L≤75mm。 •带举升器的箱体床默认安装床垫限位器，限位器规格为：

### p366 · 2.进出通道

- status: manual_review
- domain: child_room
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2.进出通道 进出通道要求同儿童家具要求，见3.6《儿童房家具设计要求》

### p369 · 1.内空要求H≥196mm；内空长度L≥950mm；内空长度L≤600mm时可使用榻榻米盖板；内空长度600＜L＜950mm

- status: manual_review
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.内空要求H≥196mm；内空长度L≥950mm；内空长度L≤600mm时可使用榻榻米盖板；内空长度600＜L＜950mm 时不可做可开启床屉板。

### p369 · 3.床不得空载(不放床垫)关闭时间过长。

- status: manual_review
- domain: bed
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

3.床不得空载(不放床垫)关闭时间过长。

### p369 · 4.不同力值气弹簧使用规范寄对应挡位见下表，出厂默认挡位：500N-1挡、750N-2挡、950N-3挡小蜻蜓举升器

- status: manual_review
- domain: bed
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

4.不同力值气弹簧使用规范寄对应挡位见下表，出厂默认挡位：500N-1挡、750N-2挡、950N-3挡小蜻蜓举升器 所有箱体床，包括符合安装要求的侧翻床、儿童床，均使用SUSPA小蜻蜓举升器 注意事项：

### p370 · 1.内空要求H≥196mm；内空长度L≥950mm；内空长度L≤600mm时可使用榻榻米盖板；内空长度600＜L＜950mm

- status: manual_review
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.内空要求H≥196mm；内空长度L≥950mm；内空长度L≤600mm时可使用榻榻米盖板；内空长度600＜L＜950mm 时不可做可开启床屉板。

### p370 · 2.使用一套举升器时床垫重量应≤50kg，设计时需考虑客户家床垫重量，当床垫重量＞50kg时，应使用两套

- status: manual_review
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2.使用一套举升器时床垫重量应≤50kg，设计时需考虑客户家床垫重量，当床垫重量＞50kg时，应使用两套

### p370 · 3.床不得空载(不放床垫)关闭时间过长。

- status: manual_review
- domain: bed
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

3.床不得空载(不放床垫)关闭时间过长。

### p370 · 4.不同力值气弹簧使用规范寄对应挡位见下表，出厂默认挡位：500N-1挡、750N-2挡、950N-3挡小蜻蜓举升器

- status: manual_review
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

4.不同力值气弹簧使用规范寄对应挡位见下表，出厂默认挡位：500N-1挡、750N-2挡、950N-3挡小蜻蜓举升器 安装位置1：适用于箱体内部有两块隔板的情况； 安装位置2：适用于箱体内部只有1块隔板或没有隔板的； ≥450mm 安装位置1 安装位置2 SUSPA小蜻蜓安装位置说明 ≥196mm ≥950mm 电动举升器 床垫重量应≤25kg，设计时需考虑客户家床垫重量。 电动举升器完全打开后可达27°大开角，取放方便。 安装空间要求：内空长度≥1350mm 内空高度≥20

### p374 · 1.宽度≤1450mm时，排骨架数量为单

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.宽度≤1450mm时，排骨架数量为单 块。

### p374 · 1.宽度＞1450mm时，排骨架数量为双

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.宽度＞1450mm时，排骨架数量为双 块。

### p374 · 1.宽度＞1450mm时，排骨架数量为双

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.宽度＞1450mm时，排骨架数量为双 块。

### p374 · 2.排骨条均为80mm宽

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2.排骨条均为80mm宽

### p374 · 2.排骨条均为80mm宽

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2.排骨条均为80mm宽

### p374 · 2.排骨条均为80mm宽

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2.排骨条均为80mm宽

### p374 · 3.排骨架间隙为15-25mm

- status: manual_review
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

3.排骨架间隙为15-25mm 主要适用于架式床、儿童床、侧翻床、 尾翻床等双块排骨架

### p374 · 3.排骨架间隙为15-25mm

- status: manual_review
- domain: bed
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

3.排骨架间隙为15-25mm 主要适用于架式床和侧翻床等双块排骨架

### p389 · 700≤W≤900600标准屉柜高度=300mm罗胖桌系列

- status: manual_review
- domain: table
- rule_type: formula
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

700≤W≤900600标准屉柜高度=300mm罗胖桌系列 CZ-01 罗胖餐桌/SZ-01 罗胖书桌/CZ-08 罗胖带屉餐桌桌腿及桌面厚度规格

### p389 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1200≤L＜1400400

### p389 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1400≤L＜1600450

### p389 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1600≤L＜1800500

### p389 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

600≤W＜700520

### p389 · 屉柜宽度屉柜深度屉柜高度

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1100＜L＜1800L-180 L≥1800 L-220 屉柜宽度屉柜深度屉柜高度 桌面长度L屉柜宽度

### p389 · 桌面宽度W屉柜深度

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1800≤L≤2000600 桌面宽度W屉柜深度

### p389 · 订制款：

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2000*900*780 订制款： 长度≤2000mm 宽度≤900mmSZ-01 罗胖书桌 单面抽屉 标准款：

### p389 · 订制款：

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2000*800*780 订制款： 长度≤2000mm 宽度≤900mm 设计订制款时应注意桌下容腿空间 CZ-08 罗胖带屉餐桌 双面抽屉 标准款：

### p389 · 订制款：

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2000*900*780 订制款： 长度≤2000mm 宽度≤900mm 设计订制款时应注意桌下容腿空间 xL 桌面长度L 屉柜总长X ≤1100 L-160

### p390 · Ps es, ¥ B\e E 20uu’ ¥ be TOOK TOoWM

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

40 如 (| ERS ARE OW Ps es, ¥ B\e E 20uu’ ¥ be TOOK TOoWM 一 LE STgoomm a | |

### p390 · ° ___ b*~| ] ¥ eK wr ¥ pRsoxsoum

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

4800 ‘ss -一 fu 2 | K 十 EDSARE: HE ° ___ b*~| ] ¥ eK wr ¥ pRsoxsoum a TTOQMM< XE <Tg0OUMN __& 200 品

### p390 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

7 c || BOSARE: 3将

### p394 · 1200≤L＜140060 35 150 70 90 10 70

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1200≤L＜140060 35 150 70 90 10 70

### p394 · 1400≤L≤160060 35 170 90 90 10 80

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1400≤L≤160060 35 170 90 90 10 80

### p394 · 1600＜L≤210070 40 200 120 90 10 902000*900*780

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1600＜L≤210070 40 200 120 90 10 902000*900*780

### p394 · 2100*900*780斜腿桌系列

- status: manual_review
- domain: table
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2100*900*780斜腿桌系列 CZ-06 简美大桌 标准款：

### p395 · 订制款：

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2100*900*780 订制款： 长度≤2100mm 宽度≤900mm 简美大桌 SZ-02 经典双屉书桌 标准款：

### p396 · 2100＜L≤2200100经典双屉书桌

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2100＜L≤2200100经典双屉书桌 前屉板；桌长＜800时可取消 SZ-05 经典儿童多屉书桌 标准款：

### p396 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1200≤L＜140070

### p396 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1400≤L≤160080

### p396 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1600＜L≤210090

### p396 · 带抽屉桌桌长≥1400mm时，桌面下有钢管，桌下抽屉内部使用空间减少25mm

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1600*700*780 带抽屉桌桌长≥1400mm时，桌面下有钢管，桌下抽屉内部使用空间减少25mm 订制款： 长度≤1600mm，宽度≤800mm 桌下无抽屉有横称时，长度 ≤2200mm， 桌长与横称高度关系见表 桌台长L 横称高度H L＜1200 50

### p397 · 2100＜T≤2200100经典儿童多屉书桌

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2100＜T≤2200100经典儿童多屉书桌 H T SZ-07 定制并立书桌 桌长≤2400mm可不分段，桌长＞2000mm需考虑能否搬运及进入入户门，如不能， 则需在订单中注明此桌为拆装结构。 桌长＞2400mm为拆装结构，且需分段，在屉柜左右两侧做分段结构带屉定制款： 桌台长L≤1600mm 宽度≤600mm 桌台长L≥1400mm时，桌面下有钢管， 桌下抽屉内部使用空间减少25mm 无屉定制款： 桌台长L≤2200mm 宽度≤600mm 桌长L与横称高度H关系见表L 

### p397 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1200≤T＜140070

### p397 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1400≤T≤160080

### p397 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1600＜T≤210090

### p397 · 带屉订制款：

- status: manual_review
- domain: table
- rule_type: formula
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1800*600*780 带屉订制款： T=桌长L-屉柜宽度W≤1600mm 宽度≤600mm T=桌长L-屉柜宽度W≥1400mm时，桌面下有 钢管，桌下抽屉内部使用空间减少25mmW L W L无屉订制款： T=桌长L-屉柜宽度W≤2200mm 宽度≤600mm T=桌长L-屉柜宽度W与横称高 度H关系见图 桌长L-屉柜宽度W ＜1400mm，下拉称宽度30mm，距地150mm 桌长L-屉柜宽度W ≥1400mm，下拉称宽度50mm，距地130mm 桌台长T=L-W横称高

### p398 · 2100＜L≤2200100定制并立书桌

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2100＜L≤2200100定制并立书桌 SZ-14 漂流岛 SZ-14 漂流岛Y 标准款：

### p398 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1200≤L＜140070

### p398 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1400≤L≤160080

### p398 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1600＜L≤210090

### p401 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1200≤L＜140070

### p401 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1400≤L≤160080

### p401 · 尺寸阈值 规则

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1600＜L≤210090

### p401 · 无屉定制款：

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2100＜L≤2200100 无屉定制款： 桌台长L≤2200mm 宽度≤600mm 桌长L与横称高度H关系见表无屉定制款 带屉定制款 定制无腿书桌 L SZ-15 升降桌 SZ-16 带屉升降桌 桌面宽度＜800mm使用RMT200mm阻尼托底轨，桌面宽度≥800mm使用海蒂诗 阻尼托底轨

### p402 · 5.升降桌需使用电源，设计时需考虑电源，控制盒带有3.3m长（弹簧拉伸

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

5.升降桌需使用电源，设计时需考虑电源，控制盒带有3.3m长（弹簧拉伸 后）弹簧电源线，黑色，插头为10A三孔。 为保证使用安全，设计阶段请明确告知客户预留插座，如客户家中插座与 家具位置相距较远，务必与客户沟通并建议其自购插线板。不可做任何现 场接线的承诺，禁止私自剪断电线或者取下插头对接电线。 升降桌弹簧电源线及插头 升降桌

### p402 · CZ-09 罗胖高屉餐桌

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

55mm1040≤L≤2240 CZ-09 罗胖高屉餐桌 双面抽屉 标准款：

### p403 · 双面抽屉标准款：

- status: manual_review
- domain: accessory
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2000*800*780 双面抽屉标准款：

### p403 · 订制款：

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

2000*900*780 订制款： 长度≤2000mm 宽度≤900mm CZ-05 经典圆餐桌 标准款：

### p403 · 订制款：

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1400*1400*780 订制款： 桌面直径≤1400mmSZ-10 简美书桌 标准款：

### p403 · 订制款：

- status: manual_review
- domain: table
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1600*700*780 订制款： 长度≤1600mm 桌长≥1400mm时， 桌面下有钢管， 桌下抽屉内部使 用空间减少25mm SZ-13 漂浮书桌 单面抽屉标准款：

### p404 · 1.订制可改桌面边角;

- status: manual_review
- domain: table
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

1.订制可改桌面边角;

### p406 · 445mm400mmYZ-01 罗胖椅

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

445mm400mmYZ-01 罗胖椅 450mm750mm 一 — ; «a Pa AS-01 BERS 430mm770mm 530mm510mm

### p407 · 668mm480mm500mm550mmYZ-02 新Y椅

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

668mm480mm500mm550mmYZ-02 新Y椅 580mm 470mm 450mm 430mm 500mm770mm400mm

### p408 · 470mmYZ-03 高背罗胖椅

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

470mmYZ-03 高背罗胖椅 545mm 600mm 430mm 545mm810mm 665mm675mm495mm 525mm

### p409 · 585mmYZ-05 广岛椅

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

585mmYZ-05 广岛椅 580mm 520mm 470mm780mm 680mm 100mm150mm465mm 550mm515mm

### p410 · 500mm180mmYZ-06 主咖大座

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 4
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

500mm180mmYZ-06 主咖大座 YZ-07 主咖巨大座 860mm 600mm685mm 50mm90mm630mm 890mm847mm587mm 280mm

### p412 · 655mmYZ-08 江口椅

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

655mmYZ-08 江口椅 620mm 1120mm 480mm 450mm QS Quy ooouu yd80u “ eT Os | | | | : / TOTT

### p413 · 562mmYZ-09 蝙蝠椅

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

562mmYZ-09 蝙蝠椅 450mm 1084mm 480mm 433mm442mm ye0uu ery 4 . | «30 aw 有 AX-00 #HRz ye) YZ-10 新夏克椅 580mm1112mm609mm 560mm517mm 640mm 424mm675mm YZ-11 长滩n椅 476mm480mm420mm 120mm 528mm 430mm790mm ydAQUU | Su | 5 多 : 人AS- 长准u捍 YZ-12 长滩h椅 476mm480

### p416 · YZ-13 金属靠背椅

- status: manual_review
- domain: general
- rule_type: dimension_threshold
- relevance_score: 3
- pricing_relevant: False
- tags: 尺寸阈值
- runtime_title: 
- runtime_action: 
- reason: 含报价/尺寸/门型/材质等信号，但当前未进入 runtime，建议人工复核

3, ! As- FEMEM HL YZ-13 金属靠背椅 460mm 455mm 440mm507mm

## excluded_non_pricing

### p30 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1 50 WWW |

### p40 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

50'0 山山

### p47 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

8 Ts 加

### p47 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

8 TS:

### p47 · 直角圆边-窄边矮柜

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1 — 三| HwWay-sy 直角圆边-窄边矮柜 凹 槽 内 退 尺 寸

### p48 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

4 | | 1 li

### p48 · 直角圆边-窄边高柜

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

8 | BHEEMY-ByEe 直角圆边-窄边高柜 凹 槽 内 退 尺 寸

### p86 · 2. 新现代风格-顶盖侧，侧包底

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

2. 新现代风格-顶盖侧，侧包底

### p127 · 50*26（钢管托称）

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

50*26（钢管托称）

### p222 · 1.定期清洁和保养家具，避免灰尘和污垢的积累。

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1.定期清洁和保养家具，避免灰尘和污垢的积累。

### p222 · 2.控制室内湿度和温度，尽量维持稳定的环境条件。

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

2.控制室内湿度和温度，尽量维持稳定的环境条件。

### p222 · 2.湿度变化：如果环境湿度经常波动，例如干燥的季节或潮湿的气候，藤材料会收缩或膨胀，这可能导致表面出现毛刺。

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

2.湿度变化：如果环境湿度经常波动，例如干燥的季节或潮湿的气候，藤材料会收缩或膨胀，这可能导致表面出现毛刺。

### p233 · | liga i hy he halt | |

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

7 \ : i wit we | . i | | | ka | | ||轩 ; | | | | | | | | | | | | J ‘ w # | SSS ae 村 元 4 | i | 上 < i | : “一 ] | | | 和 | | | | E | | liga i hy he halt | | uit | A \ ay 7 fr fated 1 wt 1 |

### p251 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

372 un slaw 5ag ww | |

### p251 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

310 wu a | se

### p251 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

32 ws TS ww SOU - q5 ww

### p284 · 2bECIEICV LIOU / wis — ks |

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

2bECIEICV LIOU / wis — ks |

### p284 · DBSWAOBC-A-$E iw Ma sw | .

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

3 VA X . ™ 人/ / DBSWAOBC-A-$E iw Ma sw | .

### p296 · 1.呼叫小爱同学

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1.呼叫小爱同学 回答：在

### p296 · 4.连接成功，现在可以前往米家设置设备

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

4.连接成功，现在可以前往米家设置设备 所在房间和名字啦

### p326 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

110° 110°

### p328 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

120°165°

### p328 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

95° 95°

### p329 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

165°

### p329 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

95°

### p389 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1200*700*780

### p389 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1400*750*780

### p389 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1600*800*780

### p389 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1800*900*780

### p389 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1200*600*780

### p389 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1400*600*780

### p389 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1600*700*780

### p389 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1800*800*780

### p389 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1600*800*780

### p389 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1800*900*780

### p394 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1600*800*780

### p395 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1600*800*780

### p395 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1800*900*780

### p395 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

2000*900*780

### p396 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1200*600*780

### p396 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1400*600*780

### p397 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1200*600*780

### p397 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1400*600*780

### p397 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1600*600*780

### p399 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

2000*900*780

### p399 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

2200*900*780

### p399 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

2400*900*780

### p399 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

2000*900*780

### p399 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

2200*900*780

### p399 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

2400*900*780

### p403 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1600*800*780

### p403 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1800*900*780

### p403 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1000*1000*780

### p403 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1200*1200*780

### p403 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1200*600*780

### p403 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1400*600*780

### p403 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1400*600*780

### p403 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1600*700*780

### p403 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1800*800*780

### p403 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1600*800*780

### p403 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

1800*900*780

### p404 · 600*400*146 1000*400*146

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 2
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

600*400*146 1000*400*146

### p412 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

230U册 AX-08 STO

### p416 · 待分类 规则

- status: excluded_non_pricing
- domain: general
- rule_type: narrative_rule
- relevance_score: 1
- pricing_relevant: False
- tags: 待分类
- runtime_title: 
- runtime_action: 
- reason: 当前更像背景介绍、知识说明或弱相关内容，暂不进入报价逻辑

3, 名
