# 美股大盘：长期收益与持有风险

[阅读交互报告](https://ickma2311.github.io/FinRunbook/sp500-20year-return-risk/report/)

研究截止：2026-09-04。主区间为 2006–2025 年；1993–2026 年辅助样本用于比较不同买入时点。

报告涵盖名义与实际收益、年度回报、回撤与恢复时间、滚动持有窗口、提款顺序情景，以及可展开的证据和计算。发布版的模型、数字、图表数据和财务结论与原运行一致。

## 证据与验证范围

`research-record.json` 是报告使用的证据摘录，包含 20 条事实、16 条证据、9 项来源和 8 项计算，不是完整的原运行账本。原始提问、研究计划和完成状态作为历史记录保留，其中的“仅本地”限制描述原运行；后续发布范围单独记录在 `publication` 字段中。

`validation.json`、`model-audit.json`、`semantic-validation.json`、`editorial-review.json` 和 `browser-tests.json` 保留原运行的时间和检查范围。原始验证为 **PASS_WITH_WARNINGS**：两项 Yahoo 二手来源警告，以及一项公司行动和复权口径警告。没有把这些警告改成无条件通过，也没有重新宣称独立审计。

`publication-review.json` 单独记录公开包的内容一致性、引用完整性及浏览器测试，不提供数据许可或金融审计保证。

## 数据使用边界

Yahoo Adjusted Close 仅用作含分配复投回报的代理，并非独立重建的总回报指数。价格指数、通胀调整、月末滚动窗口和未完整年度的口径分别标注。

本公开示例按项目所有者的明确要求发布研究结果；这不等于 Yahoo、指数公司或其他来源提供了再分发许可。第三方来源仍受各自条款约束，FinRunbook 不提供商业行情再分发许可。来源目录保留原采集时的使用限制。

公开包不含原始行情快照、缓存、完整源文件或批量逐日价格事实。它保留分析所需的派生时间序列、少量计算端点、引用、公式及原始文件哈希。未附原始文件的路径只用于追溯，不是可下载附件。独立重算需另行取得适用权限下的原始数据与原运行计算脚本。

## Limitations

This is an attributed analytical example, not a live data feed or personalized investment recommendation. Publishing it does not grant a third-party data license. Historical returns, recovery periods and overlapping rolling windows do not establish future returns or loss probabilities. Original validation receipts cover the full local run; the public ledger is an excerpt.
