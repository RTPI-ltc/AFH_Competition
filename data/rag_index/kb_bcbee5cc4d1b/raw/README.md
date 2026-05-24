# 规则解析骨架库（Rule Parsing Library）

> 本目录是 **赛题方向 C "执行辅助 Agent"** 的核心骨架库。
> 目标：把"规则文本 → 结构化检查清单 + 风险点 + 澄清问题" 这条链路上的**通用模式 / 模板 / 矩阵**沉淀下来，让 Agent 在 `rule_parser`、`checklist_builder`、`product_verifier` 节点能更稳定地输出。

## 文件索引

| 文件 | 内容 | Agent 调用节点 |
|------|------|----------------|
| `ambiguity_patterns.md` | 高频规则歧义模式 + 对应标准澄清问句 | `rule_parser` |
| `risk_severity_rubric.md` | 风险点 high/medium/low 的判定准则 | `rule_parser` + `checklist_builder` |
| `mutual_exclusion_matrix.md` | 活动间的互斥 / 叠加关系矩阵 | `rule_parser`（互斥规则识别） |
| `checklist_templates.md` | 按规则类型分类的检查项模板 | `checklist_builder` |
| `audit_rejection_cases.md` | 平台报名审核驳回的典型原因 + 整改路径 | `risk_points` 增补 |

## 设计原则

1. **本目录与具体平台无关**——平台规则在 `../platform/`；本目录是"规则解析方法论"。
2. **本目录与具体品类无关**——品类术语在 `../jewelry_industry/`；本目录是"歧义模式 / 互斥关系 / 检查清单结构"。
3. **本目录与企业 SKU 无关**——企业数据在 `../chow_tai_fook/`；本目录用于 Agent 推理时引用。

## 与 Agent 节点的对应关系

```
[rule_parser] ── 引用 ambiguity_patterns + risk_severity_rubric + mutual_exclusion_matrix
                  ↓
[checklist_builder] ── 引用 checklist_templates + audit_rejection_cases
                  ↓
[product_verifier] ── 引用 checklist_templates 中的"核查模板"
```
