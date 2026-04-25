# Release Checklist

## 公开发布前必须检查

- [ ] 已确认仓库名为 `liangqin-contract-pricing`
- [ ] 已确认对外边界写清楚：不是法律合同审核
- [ ] 已确认依赖写清楚：必须联动 `liangqin-pricing`
- [ ] 已检查未提交真实客户合同
- [ ] 已检查未提交客户姓名、电话、地址
- [ ] 已检查未提交敏感价格表
- [ ] 已检查 `.gitignore` 覆盖 runtime、cache、临时输出
- [ ] 已检查 `README.md`、`SKILL.md`、`docs/install.md`
- [ ] 已检查 `scripts/check_dependencies.sh` 与 `scripts/run_contract_pricing_audit.sh`
- [ ] 已准备脱敏样例目录
- [ ] 已确认 `LICENSE` 与公开策略一致
- [ ] 已确认 `VERSION` 已更新
- [ ] 已确认 GitHub Actions 可通过

## 建议发布顺序

1. 先创建 GitHub public repo
2. 先提交公开骨架、文档、脚本、CI
3. 再逐步补充脱敏样例和最终 app 代码
4. 最后补首个 GitHub Release
