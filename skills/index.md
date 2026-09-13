# FinRunbook skill dictionary

This is the central index for maintained skills and pinned third-party references.
Read only the entries relevant to the question. Do not clone upstream repositories
or initialize submodules. The current first-party workflow remains in place during
the code refactor; the small single-skill plugin is the next phase.

Third-party financial entries are reference material, not certified local workflows.
Review dependencies before use. MCP services, proprietary terminals, nested routers
and required unavailable tools must be adapted before the method is advertised as
locally runnable. Read supporting documents at the same pinned revision. A link
does not grant data access or permission to run downloaded code. Record the selected
URL and commit; disclose unavailable instructions instead of claiming they ran.

| Skill | Description / when to use | Instructions |
| --- | --- | --- |
| Financial research | Current research workflow and evidence ledger. | [Read](finrunbook/SKILL.md) |
| Market-price analysis | Prices, volume, returns and benchmark comparisons; optional yfinance dependency. | [Read](finrunbook-market-data/SKILL.md) |
| Radar | Discover and qualify financial research topics, then manage child reports. | [Read](finrunbook-radar/SKILL.md) |
| Financial editorial review | Review prose while preserving claims, figures and citations. | [Read](finrunbook-tone-review/SKILL.md) |
| Validation | Check the current evidence and artifact contract; does not establish source truth. | [Read](finrunbook-validator/SKILL.md) |
| Company initiation | Business drivers, financial health and investment thesis. | [Read](https://github.com/anthropics/financial-services/blob/69cbc81467a5dced793eee03dec4658aa24ef856/plugins/vertical-plugins/equity-research/skills/initiating-coverage/SKILL.md) |
| Earnings analysis | Quarterly changes, beat/miss analysis and revised expectations. | [Read](https://github.com/anthropics/financial-services/blob/69cbc81467a5dced793eee03dec4658aa24ef856/plugins/agent-plugins/earnings-reviewer/skills/earnings-analysis/SKILL.md) |
| Sector overview | Industry structure, value chains and sector metrics. | [Read](https://github.com/anthropics/financial-services/blob/69cbc81467a5dced793eee03dec4658aa24ef856/plugins/agent-plugins/market-researcher/skills/sector-overview/SKILL.md) |
| Competitive analysis | Business models, competitive positioning and peer differences. | [Read](https://github.com/anthropics/financial-services/blob/69cbc81467a5dced793eee03dec4658aa24ef856/plugins/agent-plugins/market-researcher/skills/competitive-analysis/SKILL.md) |
| DCF model | Cash-flow valuation with explicit assumptions and sensitivities. | [Read](https://github.com/anthropics/financial-services/blob/69cbc81467a5dced793eee03dec4658aa24ef856/plugins/agent-plugins/model-builder/skills/dcf-model/SKILL.md) |
| Comparable valuation | Comparable companies and valuation multiples. | [Read](https://github.com/anthropics/financial-services/blob/69cbc81467a5dced793eee03dec4658aa24ef856/plugins/agent-plugins/model-builder/skills/comps-analysis/SKILL.md) |
| Earnings recap | Concise results, guidance and operating drivers. | [Read](https://github.com/himself65/finance-skills/blob/0a5759bca1ea273790cd45c17fad6a9aff76a7f5/plugins/market-analysis/skills/earnings-recap/SKILL.md) |
| Company valuation | Select valuation methods suited to a company. | [Read](https://github.com/himself65/finance-skills/blob/0a5759bca1ea273790cd45c17fad6a9aff76a7f5/plugins/market-analysis/skills/company-valuation/SKILL.md) |
| Financial analysis | Profitability, liquidity, leverage and accounting ratios. | [Read](https://github.com/GAJETOso/financeskills/blob/862774c15d83f58536d84973b42dbbffda5af7ae/skills/financial-analysis/SKILL.md) |
| Audit checklist | Financial reporting controls and audit questions. | [Read](https://github.com/GAJETOso/financeskills/blob/862774c15d83f58536d84973b42dbbffda5af7ae/skills/audit-checklist/SKILL.md) |
| Revenue recognition | Recognition timing, accounting policy and disclosure questions. | [Read](https://github.com/GAJETOso/financeskills/blob/862774c15d83f58536d84973b42dbbffda5af7ae/skills/revenue-recognition/SKILL.md) |
| Three-statement model | Connect income statement, balance sheet and cash flows. | [Read](https://github.com/GAJETOso/financeskills/blob/862774c15d83f58536d84973b42dbbffda5af7ae/skills/three-statement-modeling/SKILL.md) |
| sec-10k-analysis | Annual filings and business risks. Requires Octagon MCP/API; unavailable in the local workflow until adapted. | [Read](https://github.com/OctagonAI/skills/blob/51e938c4d086f658de8bdcf734e864d34637167e/skills/sec-10k-analysis/SKILL.md) |
| sec-10q-analysis | Interim filings and quarter versus YTD periods. Requires Octagon MCP/API; unavailable in the local workflow until adapted. | [Read](https://github.com/OctagonAI/skills/blob/51e938c4d086f658de8bdcf734e864d34637167e/skills/sec-10q-analysis/SKILL.md) |
| sec-8k-analysis | Material issuer events and disclosures. Requires Octagon MCP/API; unavailable in the local workflow until adapted. | [Read](https://github.com/OctagonAI/skills/blob/51e938c4d086f658de8bdcf734e864d34637167e/skills/sec-8k-analysis/SKILL.md) |
| sec-proxy-analysis | Governance, compensation and shareholder voting. Requires Octagon MCP/API; unavailable in the local workflow until adapted. | [Read](https://github.com/OctagonAI/skills/blob/51e938c4d086f658de8bdcf734e864d34637167e/skills/sec-proxy-analysis/SKILL.md) |
| income-statement | Revenue, margins and income statement trends. Requires Octagon MCP/API; unavailable in the local workflow until adapted. | [Read](https://github.com/OctagonAI/skills/blob/51e938c4d086f658de8bdcf734e864d34637167e/skills/income-statement/SKILL.md) |
| cash-flow-statement | Operating cash flow, capex and financing. Requires Octagon MCP/API; unavailable in the local workflow until adapted. | [Read](https://github.com/OctagonAI/skills/blob/51e938c4d086f658de8bdcf734e864d34637167e/skills/cash-flow-statement/SKILL.md) |
| balance-sheet | Assets, liabilities and capital structure. Requires Octagon MCP/API; unavailable in the local workflow until adapted. | [Read](https://github.com/OctagonAI/skills/blob/51e938c4d086f658de8bdcf734e864d34637167e/skills/balance-sheet/SKILL.md) |
| sec-segment-reporting | Segment definitions, reconciliations and trends. Requires Octagon MCP/API; unavailable in the local workflow until adapted. | [Read](https://github.com/OctagonAI/skills/blob/51e938c4d086f658de8bdcf734e864d34637167e/skills/sec-segment-reporting/SKILL.md) |
| analyst-estimates | Consensus estimates and their observation dates. Requires Octagon MCP/API; unavailable in the local workflow until adapted. | [Read](https://github.com/OctagonAI/skills/blob/51e938c4d086f658de8bdcf734e864d34637167e/skills/analyst-estimates/SKILL.md) |
| English editorial review | Clarity and concision; retain financial definitions and uncertainty. | [Read](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/writing-clearly-and-concisely/SKILL.md) |
| Chinese editorial review | Polish Chinese prose while preserving facts and financial structure. | [Read](https://github.com/KG3KAI/readable-human-writing/blob/cc669c7427ed921ffe15fae6fd91d8d4b9280676/SKILL.md) |
