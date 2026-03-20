# 投放区说明

以后如果有新的报价资料，直接把文件放在这个目录：

- 新产品目录：`xlsx`
- 新定制规则：`docx`

放好以后运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/update_release.py
```

默认会自动选择这个目录里最新的：

- 一个 `.xlsx`
- 一个 `.docx`

如果你想指定文件，也可以手动带参数运行：

```bash
python3 ~/.openclaw/skills/liangqin-pricing/scripts/update_release.py --price-book "/path/to/产品目录.xlsx" --rules-docx "/path/to/定制规则.docx"
```
