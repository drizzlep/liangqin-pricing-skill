# 投放区说明

以后如果有新的报价资料，直接把文件放在这个目录：

- 新产品目录：`xlsx`
- 新定制规则：`docx / pdf`

放好以后运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/update_release.py
```

它会同时生成：

- 规则候选 `JSON`
- 规则审阅稿 `Markdown`
- 高信号规则索引 `JSON + Markdown`
- 分域规则草稿目录 `Markdown`

默认会自动选择这个目录里最新的：

- 一个 `.xlsx`
- 一个规则文件：优先最新 `.docx`，没有 `.docx` 时回退最新 `.pdf`

如果你想指定文件，也可以手动带参数运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/update_release.py --price-book "/path/to/产品目录.xlsx" --rules-source "/path/to/定制规则.pdf"
```
