# 平台活动规则知识库（Platform Activity Rules KB）

> 本知识库面向"企业X电商运营执行辅助 Agent"，整理天猫、淘宝、京东等主流电商平台的活动规则。每份文档统一按 **商家侧 / 消费者侧 / 商家关注的流程与环节** 三段式组织，便于 Agent 解析规则、生成检查清单、提示风险点。

## 文件索引

| 文件 | 适用场景 | 核心内容 |
|------|----------|----------|
| **`tmall_618.md`** ⭐ | **天猫 618 大促（赛题示例对标）** | **直接对应 manual.pdf 给出的标准示例规则；含端到端解析样板** |
| `double_eleven.md` | 双 11 大促 | 多波次时间结构 + 跨期价保 30 天 + 近 30/365 天双重校验 |
| `tmall_super_brand_day.md` | 天猫超级品牌日 | 资质、价格管控、互斥、流程 |
| `jd_super_brand_day.md` | 京东超级品牌日 | 14 天口径、自营/POP 双轨、PLUS 价保 45 天 |
| `taobao_juhuasuan_baiyibutie.md` | 淘宝聚划算 / 百亿补贴 | 90 天口径、全网最低、限购 |
| `category_day.md` | 行业品类日 / 超级品类日 | **与品牌日互斥（赛题第 4 条对应）** |
| `livestream_campaign.md` | 抖音 / 淘宝 / 京东直播专场 | 直播间限时价、让利分摊、与货架电商口径差异 |
| `internal_marketing.md` | 周大福内部营销项目 | **赛题原文提及；与电商平台规则互斥风险** |
| `price_terminology.md` | 通用 | 划线价 / 活动价 / 到手价 / 近 14/30/90/365 天最低 口径对照 |
| `consumer_benefits.md` | 通用（商家执行视角） | 叠加矩阵 + 价保 + 客服话术口径 |
| `merchant_process_summary.md` | 通用（商家视角） | T-30 → T+30 全链路 SOP（检查清单骨架） |

## 平台规则知识库的使用原则

1. **本知识库只作为辅助上下文**：Agent 在解析活动规则文本时，以"用户输入的活动规则原文"为最高优先级，本知识库用于解释术语、补全口径和提示常见风险点，不能覆盖用户输入。
2. **以"商家是否能拿到福利"为视角**：所有规则都按"商家侧门槛 / 商家侧福利 / 消费者侧福利"三段式整理，方便 Agent 一次性产出"能否报名 / 报名后能拿到什么 / 消费者看到什么"。
3. **数值型条款标记高置信度**：例如"近 30 天最低价"、"满 300 减 50"、"店铺评分 ≥ 4.8"是可机器核查的数值条款，rule_parser 给出 confidence ≥ 0.9。
4. **定性条款标记低置信度**：例如"品牌力强"、"主推爆款"、"具备品牌调性"等模糊词，confidence < 0.7，由 human_review_gate 暂停等待人工确认。
5. **互斥与叠加规则单独提示**：跨店满减、品类日、品牌日之间往往互斥或部分叠加，必须在 Agent 输出的 `risk_points` 中显式提示。

## 与赛题对齐

- **赛题示例规则的端到端解析**：见 `tmall_618.md`，含 parsed_rules / decision_flow / counter_examples / clarification_questions 完整 demo。
- **商家流程总结**：见 `merchant_process_summary.md`，作为 `checklist_builder` 节点的输出骨架。
- **互斥规则识别**：本目录的 `category_day.md` + `internal_marketing.md` 提供"品牌日互斥对手方"语料，配合 `../rule_library/mutual_exclusion_matrix.md` 与 `../chow_tai_fook/sku_catalog.md` 的 `active_campaigns` 字段共同支撑赛题第 4 条规则的识别。
