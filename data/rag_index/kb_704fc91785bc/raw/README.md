# 知识库总索引（Knowledge Base Index）

> 本目录是 **赛题方向 C "执行辅助 Agent"** 的所有上下文存放位置。Agent 在 `knowledge_base_loader` 节点把这些目录的 markdown 文件抽取为原文，并在 `rule_parser` / `checklist_builder` / `product_verifier` / `auto_decision_planner` 节点中作为 prompt context 注入。

## 与赛题 4 方向的边界

| 方向 | 范畴 | 本 KB 是否覆盖 |
|------|------|----------------|
| A 战略模拟（海外市场情报） | 公开信息抓取、每日简报 | ❌ 已剥离（GMV、流量包、PR 资源、跨品类拉新等战略数据不在本 KB） |
| B 协作沟通（多角色共识） | 跨角色视角解读、ROI 讨论 | ❌ 已剥离（组织架构、跨角色协作流程不在本 KB） |
| **C 执行辅助（规则解析）** | **解析规则 + 生成检查清单 + 提示风险点 + 标注澄清** | ✅ 本 KB 全部为 C 方向服务 |
| D 风控合规（合同 diff） | 合同 / 协议差异识别 | ❌ 已剥离（《广告法》《消费者权益保护法》《电子商务法》等法规罗列不在本 KB） |

---

## 1. 目录结构

```
knowledge_base/
├── README.md                                # 本文件（总索引）
├── platform/                                # 平台活动规则知识库
│   ├── README.md
│   ├── tmall_618.md                         # ⭐ 赛题示例规则对标
│   ├── double_eleven.md                     # 双 11 多波次 + 跨期价保
│   ├── tmall_super_brand_day.md             # 天猫超品日
│   ├── jd_super_brand_day.md                # 京东超品日（14 天 + PLUS 45 天）
│   ├── taobao_juhuasuan_baiyibutie.md       # 聚划算 / 百补（90 天 + 全网最低）
│   ├── category_day.md                      # 品类日（与品牌日互斥）
│   ├── livestream_campaign.md               # 抖音 / 淘宝 / 京东直播专场
│   ├── internal_marketing.md                # 周大福内部营销项目（赛题原文提及）
│   ├── price_terminology.md                 # 价格术语字典 + 近 X 天对照
│   ├── consumer_benefits.md                 # 商家执行视角的消费者规则 + 叠加矩阵
│   └── merchant_process_summary.md          # T-30 → T+30 全链路 SOP
├── rule_library/                            # ⭐ C 方向骨架库（新增目录）
│   ├── README.md
│   ├── ambiguity_patterns.md                # 高频歧义模式 + 标准澄清问句
│   ├── risk_severity_rubric.md              # 风险点 high/medium/low 判定准则
│   ├── mutual_exclusion_matrix.md           # 活动互斥矩阵（赛题第 4 条对应）
│   ├── checklist_templates.md               # 6 类检查清单模板
│   └── audit_rejection_cases.md             # 平台审核驳回原因 + 整改路径
├── chow_tai_fook/                           # 企业内部知识库
│   ├── README.md
│   ├── company_qualifications.md            # 企业资质（已精简，去 GMV / 佣金）
│   ├── product_certifications.md            # 商品资质（GIA / NGTC / CMA 对照）
│   ├── sku_catalog.md                       # 30 条 SKU 样例 + active_campaigns + campaign_history
│   ├── supply_chain.md                      # 工厂代码 + 补货周期 + 大促备货
│   └── human_review_routing.md              # 人工接管角色路由表
└── jewelry_industry/                        # 珠宝行业知识库
    ├── README.md
    ├── gold_basics.md                       # 黄金（足金 / 古法金 / 5G / 硬足金 / K 金 / 计重 vs 一口价）
    ├── diamond_basics.md                    # 钻石 4C + 证书 + 培育钻合规
    ├── platinum_silver.md                   # 铂金 vs 白 K 金 vs 925 银
    ├── jadeite_pearl_jade.md                # 翡翠 / 珍珠 / 和田玉
    ├── compliance_essentials.md             # 价格管控合规 + 商品标注国标
    └── industry_terminology.md              # 术语字典 + 高频歧义
```

---

## 2. 四大模块的协作模型

```
                          ┌───────────────────────────────────┐
                          │  rule_parser / checklist_builder /│
                          │  product_verifier / planner       │
                          └───────────────▲───────────────────┘
                                          │ prompt context 注入
                  ┌───────────────────────┼───────────────────────────────────┐
                  │                       │                                   │
       ┌──────────┴──────────┐  ┌─────────┴──────────┐  ┌──────────┴──────────────┐
       │ platform/           │  │ rule_library/      │  │ chow_tai_fook/          │
       │ "平台规则是什么"      │  │ "解析方法论"        │  │ "我们的状态是什么"        │
       └─────────────────────┘  └────────────────────┘  └─────────────────────────┘
                                          │
                                ┌─────────┴──────────┐
                                │ jewelry_industry/  │
                                │ "品类语义是什么"     │
                                └────────────────────┘
```

四大模块各司其职：

| 模块 | 职责 | 输出形态 |
|------|------|---------|
| `platform/` | 提供"规则文本来源" | 各平台 / 各活动的可解析规则条款 |
| `rule_library/` | 提供"解析方法论" | 歧义模式 / 风险分级 / 互斥矩阵 / 检查清单模板 / 驳回案例 |
| `chow_tai_fook/` | 提供"企业当前状态" | 资质、SKU、库存、活动参与记录 |
| `jewelry_industry/` | 提供"品类语义" | 黄金 / 钻石 / 翡翠等术语与国标 |

每一条规则的解析都需要四个模块联合作用。例如：

> **赛题示例规则：第 4 条"已参加'品牌日'活动的商品不可重复报名"**
>
> - `platform/category_day.md` 说明品牌日 vs 品类日的差异
> - `rule_library/mutual_exclusion_matrix.md` 提供互斥关系判定
> - `rule_library/ambiguity_patterns.md` 提示"品牌日"是同平台还是跨平台需澄清
> - `chow_tai_fook/sku_catalog.md` 提供每个 SKU 的 `active_campaigns` 和 `campaign_history`
> - `rule_library/checklist_templates.md` 给出互斥检测的标准输出格式

---

## 3. 知识库注入策略

详见 `../2026-05-23-execution-assistant-agent-design.md` 第 1 节。简要回顾：

1. 用户在前端上传或选择 `.md` / `.txt` / `.pdf` 文件，选择知识库类型。
2. 系统读取原文 → 存入 `knowledge_base_files`。
3. 每次调用 LLM 节点时，按知识库类型拼接到 prompt：
   ```
   [平台规则知识库]
   {{platform_rule_context}}

   [规则解析骨架库]
   {{rule_library_context}}

   [企业 X 内部知识库]
   {{chow_tai_fook_context}}

   [珠宝行业知识库]
   {{jewelry_industry_context}}

   [用户输入的活动规则]
   {{raw_rules}}
   ```
4. 截断策略：每类最大注入 8k–15k 字符。
5. 知识库只作为辅助上下文，**不能覆盖用户输入的活动规则原文**。

---

## 4. 知识库内容置信度

| 类型 | 置信度 | 说明 |
|------|--------|------|
| 平台公开规则 / 国家标准 | 高 | 引用自公开文档 |
| 平台佣金 / 流量包数值 | — | **已剥离**（属方向 A） |
| 周大福企业资质（编号、店铺 ID） | **演示模拟** | 真实场景需对接法务 |
| 周大福 SKU 数据 | **演示模拟** | 真实场景需对接 ERP |
| 周大福 active_campaigns / campaign_history | **演示模拟** | 真实场景需订阅平台报名接口 |
| 珠宝行业术语与国标 | 高 | GB 11887、GB/T 16554 等 |

---

## 5. 与赛题 manual.pdf 中示例规则的端到端映射

赛题原文给的标准示例规则：

```text
天猫 618 大促选品规则：
1. 参与商品必须满足：近 30 天销量 ≥ 100 件；好评率 ≥ 95%；库存 ≥ 500 件。
2. 价格要求：活动价不得高于近 30 天最低价；折扣力度 ≥ 7 折。
3. 品类限制：黄金类目单店最多 5 个 SKU；钻石类目单店最多 10 个 SKU。
4. 互斥规则：已参加"品牌日"活动的商品不可重复报名。
```

完整端到端解析样板见 `platform/tmall_618.md`。

| 规则条款 | Agent 解析所依赖的 KB |
|---------|----------------------|
| 销量 ≥ 100 件 | `rule_library/checklist_templates.md` §3.1 + `chow_tai_fook/sku_catalog.md` (last_30d_sales) |
| 好评率 ≥ 95% | `rule_library/ambiguity_patterns.md` §5.2 (统计时窗澄清) + sku_catalog |
| 库存 ≥ 500 件 | `chow_tai_fook/sku_catalog.md` (stock) + `chow_tai_fook/supply_chain.md` (补货周期) |
| 活动价 ≤ 近 30 天最低 | `platform/price_terminology.md` + `jewelry_industry/compliance_essentials.md` |
| 折扣力度 ≥ 7 折 | `rule_library/ambiguity_patterns.md` §2.3 (分母澄清) + `jewelry_industry/gold_basics.md` (计重款豁免) |
| SKU 数量限制 | `rule_library/checklist_templates.md` §4.1 |
| 互斥品牌日 | `platform/category_day.md` + `rule_library/mutual_exclusion_matrix.md` + sku_catalog (active_campaigns + campaign_history) |
