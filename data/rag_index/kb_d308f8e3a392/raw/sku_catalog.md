# SKU 数据库样例（SKU Catalog）

> 演示用 SKU 数据，覆盖周大福主要品类。字段结构贴近真实 ERP 输出，可直接驱动 Agent `product_verifier` 节点端到端跑通。
> 重点字段：`active_campaigns`（当前在售 / 在报活动）+ `campaign_history`（近 365 天活动参与历史）—— 用于赛题示例规则"已参加品牌日不可重复报名"的互斥校验。

---

## 1. 数据字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `sku_id` | string | 周大福内部 SKU 编码 |
| `product_name` | string | 商品名称 |
| `brand` | string | 品牌（CTF / T MARK / SOINLOVE / MONOLOGUE / CTF 传承） |
| `category_l1` | string | 一级类目（黄金、镶嵌、铂金、银饰、玉石、珍珠） |
| `category_l2` | string | 二级类目（足金、古法金、5G 黄金、K 金、钻石、翡翠、珍珠 等） |
| `pricing_model` | string | "weight"（计重）/ "fixed"（一口价） |
| `weight_g` | float | 克重（克），仅 weight 模式必填 |
| `purity` | string | 成色（999 / 999.9 / 999.99 / Au750 / Pt950 等） |
| `gem_carat` | float \| null | 主石克拉数（镶嵌类） |
| `gem_color` | string \| null | 钻石颜色（D-Z） |
| `gem_clarity` | string \| null | 钻石净度（FL / IF / VVS1 / VVS2 / VS1 / VS2 / SI1 / SI2 / I1 / I2 / I3） |
| `gem_cut` | string \| null | 钻石切工（EX / VG / G / F / P） |
| `tag_price_rmb` | float | 吊牌价（人民币） |
| `list_price_rmb` | float | 划线价（人民币）|
| `last_14d_min_price` | float | 近 14 天店内最低成交价（京东口径） |
| `last_30d_min_price` | float | 近 30 天店内最低成交价（天猫口径） |
| `last_90d_min_price` | float | 近 90 天店内最低成交价（百补口径） |
| `last_365d_min_price` | float | 近 365 天店内最低成交价（双 11 双重校验口径） |
| `stock` | int | 当前可用库存 |
| `last_30d_sales` | int | 近 30 天销量 |
| `last_90d_sales` | int | 近 90 天销量 |
| `review_rate` | float | 近 30 天好评率 |
| `return_rate` | float | 近 30 天退货率 |
| `new_product` | bool | 是否近 90 天上新 |
| `certificate_ids` | array | 关联证书编号 |
| `factory_id` | string | 生产工厂代码 |
| `lead_time_days` | int | 补货周期 |
| **`active_campaigns`** | array | **当前正在参与的活动 ID 列表（核心：用于互斥检测）** |
| **`campaign_history`** | array | **近 365 天活动参与历史（用于"已参加 X 不可再报"判定）** |

### 1.1 活动 ID 命名规则

格式：`{platform}:{campaign_type}:{year}_{period}`

| 平台 | campaign_type | 示例 |
|------|---------------|------|
| tmall | super_brand_day | `tmall:super_brand_day:2025_q4` |
| tmall | brand_day | `tmall:brand_day:2025_07` |
| tmall | category_day | `tmall:category_day:2025_09_gold` |
| tmall | 618 | `tmall:618:2025` |
| tmall | double_eleven | `tmall:double_eleven:2025` |
| tmall | juhuasuan | `tmall:juhuasuan:2025_q3` |
| tmall | baiyibutie | `tmall:baiyibutie:rolling` |
| jd | super_brand_day | `jd:super_brand_day:2025_q4` |
| jd | baiyibutie | `jd:baiyibutie:rolling` |
| jd | plus_day | `jd:plus_day:2025_06` |
| douyin | livestream | `douyin:livestream:2025_08_15` |
| internal | member_day | `internal:member_day:2025_09` |
| internal | anniversary | `internal:anniversary:2025` |

---

## 2. SKU 样例（30 条多品类，含 active_campaigns + campaign_history）

### 2.1 足金 / 千足金（黄金计重）

| sku_id | 名称 | 品牌 | 类目 | 定价 | 克重 | 成色 | 划线 | 14d 最低 | 30d 最低 | 90d 最低 | 365d 最低 | 库存 | 30d 销量 | 90d 销量 | 好评 | 退货 | 新品 | 工厂 | active_campaigns | campaign_history（近 365 天）|
|--------|------|------|------|------|------|------|------|----------|----------|----------|------------|------|----------|----------|------|------|------|------|------------------|------------------------------|
| CTF-FJ-999-001 | 足金古法金手镯 25g | 传承 | 黄金/古法金 | weight | 25.00 | 999 | 18800 | 18500 | 18200 | 17800 | 16500 | 320 | 52 | 158 | 98.5% | 1.2% | false | F-SZ-001 | [`tmall:618:2025`] | [`tmall:brand_day:2024_09`, `tmall:double_eleven:2024`] |
| CTF-FJ-999-002 | 足金 999 福字吊坠 3.5g | CTF | 黄金/足金 | weight | 3.50 | 999 | 2680 | 2620 | 2580 | 2480 | 2350 | 1800 | 342 | 1024 | 97.8% | 2.5% | false | F-SZ-002 | [] | [`tmall:juhuasuan:2025_q2`, `internal:member_day:2025_03`] |
| CTF-FJ-999-003 | 足金 999.9 婚嫁三件套 18g | CTF | 黄金/千足金 | weight | 18.00 | 999.9 | 14000 | 13800 | 13500 | 13200 | 12800 | 280 | 32 | 95 | 98.0% | 1.8% | false | F-SZ-001 | [`tmall:super_brand_day:2025_q4`] | [`tmall:brand_day:2024_12`] |
| CTF-FJ-999-004 | 足金 999 婴儿手镯 5.5g | CTF | 黄金/足金 | weight | 5.50 | 999 | 4180 | 4150 | 4080 | 3980 | 3850 | 600 | 104 | 312 | 99.0% | 0.5% | false | F-SZ-002 | [] | [`internal:member_day:2025_05`] |
| CTF-FJ-9999-001 | 万足金 999.99 投资金条 50g | CTF | 黄金/万足金 | weight | 50.00 | 999.99 | — | — | — | — | — | 120 | 15 | 45 | 99.5% | 0.2% | false | F-SH-003 | [] | [] |

### 2.2 5G 黄金 / 硬足金（一口价 / 工艺类）

| sku_id | 名称 | 品牌 | 类目 | 定价 | 克重 | 成色 | 划线 | 14d 最低 | 30d 最低 | 90d 最低 | 365d 最低 | 库存 | 30d 销量 | 90d 销量 | 好评 | 退货 | 新品 | 工厂 | active_campaigns | campaign_history |
|--------|------|------|------|------|------|------|------|----------|----------|----------|------------|------|----------|----------|------|------|------|------|------------------|------------------|
| CTF-5G-001 | 5G 黄金小蛮腰耳钉 1.2g | CTF | 黄金/5G | fixed | 1.20 | 999 | 1280 | 1230 | 1180 | 1080 | 980 | 2400 | 617 | 1850 | 98.2% | 1.5% | true | F-SZ-002 | [`tmall:juhuasuan:2025_q3`] | [`tmall:juhuasuan:2025_q2`, `douyin:livestream:2025_05_20`] |
| CTF-5G-002 | 5G 黄金转运珠手链 2.8g | CTF | 黄金/5G | fixed | 2.80 | 999 | 2480 | 2420 | 2380 | 2280 | 2180 | 1800 | 307 | 920 | 97.5% | 2.8% | true | F-SZ-002 | [`tmall:618:2025`, `tmall:juhuasuan:2025_q3`] | [`tmall:brand_day:2024_11`] |
| CTF-HG-001 | 硬足金"福"字吊坠 1.5g | CTF | 黄金/硬足金 | fixed | 1.50 | 999 | 1480 | 1430 | 1380 | 1280 | 1180 | 1500 | 260 | 780 | 98.8% | 1.1% | false | F-SZ-002 | [] | [] |
| CTF-GFJ-001 | 古法金"传承福"手镯 22g | 传承 | 黄金/古法金 | fixed | 22.00 | 999 | 22800 | 22500 | 22000 | 21500 | 20800 | 220 | 25 | 75 | 99.1% | 0.8% | true | F-SZ-001 | [`tmall:super_brand_day:2025_q4`, `tmall:category_day:2025_09_gold`] | [`internal:anniversary:2024`] |

### 2.3 K 金 / 镶嵌钻饰

| sku_id | 名称 | 品牌 | 类目 | 定价 | 克重 | 成色 | 主石ct | 颜色 | 净度 | 切工 | 划线 | 14d 最低 | 30d 最低 | 90d 最低 | 365d 最低 | 库存 | 30d 销量 | 90d 销量 | 好评 | 退货 | 新品 | 工厂 | active_campaigns | campaign_history |
|--------|------|------|------|------|------|------|--------|------|------|------|------|----------|----------|----------|------------|------|----------|----------|------|------|------|------|------------------|------------------|
| CTF-G18K-NL-001 | 18K 金项链 0.50ct | CTF | 镶嵌/K金 | fixed | 6.50 | Au750 | 0.50 | F | VS1 | EX | 27800 | 27400 | 26800 | 26000 | 25500 | 60 | 11 | 32 | 98.0% | 2.0% | false | F-SH-002 | [] | [`jd:super_brand_day:2024_q4`] |
| CTF-G18K-NL-002 | 18K 金项链 0.30ct | CTF | 镶嵌/K金 | fixed | 5.20 | Au750 | 0.30 | G | VS2 | EX | 17800 | 17200 | 16800 | 16000 | 15500 | 80 | 16 | 48 | 97.8% | 1.8% | false | F-SH-002 | [`tmall:super_brand_day:2025_q4`] | [`tmall:category_day:2024_05_diamond`] |
| CTF-G18K-RG-001 | 18K 金钻戒 0.20ct | SOINLOVE | 镶嵌/求婚钻戒 | fixed | 3.50 | Au750 | 0.20 | H | SI1 | VG | 9380 | 9100 | 8980 | 8780 | 8580 | 150 | 32 | 96 | 98.2% | 1.5% | true | F-SH-002 | [`jd:super_brand_day:2025_q4`] | [] |
| CTF-G18K-RG-002 | T MARK 30 分钻戒（3EX 切工） | T MARK | 镶嵌/求婚钻戒 | fixed | 3.80 | Au750 | 0.30 | F | VVS2 | EX | 21800 | 21200 | 20800 | 20200 | 19800 | 80 | 17 | 52 | 99.0% | 1.0% | true | F-SH-002 | [`tmall:brand_day:2025_07`] | [`tmall:double_eleven:2024`] |
| CTF-PT950-RG-001 | 铂金 Pt950 50 分钻戒 | CTF | 镶嵌/求婚钻戒 | fixed | 4.20 | Pt950 | 0.50 | E | VVS1 | EX | 36800 | 36000 | 35800 | 34800 | 33800 | 40 | 6 | 18 | 98.5% | 1.2% | false | F-SH-002 | [] | [] |
| CTF-G18K-EAR-001 | 18K 金钻石耳钉 0.10ct（一对） | CTF | 镶嵌/耳饰 | fixed | 1.80 | Au750 | 0.10 | G | VS2 | EX | 4680 | 4520 | 4480 | 4280 | 4180 | 320 | 65 | 195 | 98.0% | 1.8% | false | F-SH-002 | [`tmall:juhuasuan:2025_q3`] | [`tmall:juhuasuan:2025_q1`] |

### 2.4 翡翠 / 玉石

| sku_id | 名称 | 品牌 | 类目 | 定价 | 划线 | 14d 最低 | 30d 最低 | 90d 最低 | 365d 最低 | 库存 | 30d 销量 | 90d 销量 | 好评 | 退货 | 新品 | 工厂 | active_campaigns | campaign_history |
|--------|------|------|------|------|------|----------|----------|----------|------------|------|----------|----------|------|------|------|------|------------------|------------------|
| CTF-JADE-001 | 翡翠 A 货平安无事牌 | CTF | 玉石/翡翠 | fixed | 17800 | 17500 | 17000 | 16500 | 16000 | 30 | 4 | 12 | 97.0% | 3.5% | false | F-GZ-001 | [] | [] |
| CTF-JADE-002 | 翡翠 A 货福豆挂坠 | CTF | 玉石/翡翠 | fixed | 5580 | 5450 | 5380 | 5180 | 4980 | 80 | 13 | 38 | 97.5% | 2.8% | true | F-GZ-001 | [] | [`tmall:category_day:2025_03_jade`] |

### 2.5 珍珠

| sku_id | 名称 | 品牌 | 类目 | 定价 | 划线 | 14d 最低 | 30d 最低 | 90d 最低 | 365d 最低 | 库存 | 30d 销量 | 90d 销量 | 好评 | 退货 | 新品 | 工厂 | active_campaigns | campaign_history |
|--------|------|------|------|------|------|----------|----------|----------|------------|------|----------|----------|------|------|------|------|------------------|------------------|
| CTF-PEARL-001 | Akoya 海水珍珠项链 7-8mm | MONOLOGUE | 珍珠/海水 | fixed | 6580 | 6380 | 6280 | 6080 | 5880 | 120 | 22 | 65 | 98.0% | 2.0% | false | F-SH-004 | [`tmall:brand_day:2025_07`] | [] |
| CTF-PEARL-002 | 大溪地黑珍珠吊坠 9-10mm | MONOLOGUE | 珍珠/海水 | fixed | 12000 | 11800 | 11500 | 11200 | 10800 | 50 | 7 | 22 | 98.5% | 1.5% | true | F-SH-004 | [] | [] |

### 2.6 铂金 / 银饰

| sku_id | 名称 | 品牌 | 类目 | 定价 | 克重 | 成色 | 划线 | 14d 最低 | 30d 最低 | 90d 最低 | 365d 最低 | 库存 | 30d 销量 | 90d 销量 | 好评 | 退货 | 新品 | 工厂 | active_campaigns | campaign_history |
|--------|------|------|------|------|------|------|------|----------|----------|----------|------------|------|----------|----------|------|------|------|------|------------------|------------------|
| CTF-PT-NL-001 | 铂金 Pt950 项链 5.5g | CTF | 铂金/项链 | weight | 5.50 | Pt950 | 5380 | 5300 | 5180 | 4980 | 4780 | 240 | 44 | 132 | 98.2% | 1.8% | false | F-SH-001 | [] | [] |
| CTF-PT-RG-001 | 铂金 Pt950 素圈对戒 | CTF | 铂金/戒指 | weight | 3.20 | Pt950 | 6480 | 6380 | 6280 | 6080 | 5880 | 180 | 30 | 88 | 98.0% | 2.2% | false | F-SH-001 | [`tmall:category_day:2025_06_wedding`] | [] |
| CTF-SLV-001 | 925 银转运珠手链 | CTF | 银饰/手链 | fixed | 4.50 | 925 | 480 | 420 | 380 | 350 | 320 | 1500 | 293 | 880 | 97.5% | 3.0% | true | F-SZ-003 | [`tmall:juhuasuan:2025_q3`, `douyin:livestream:2025_08_15`] | [] |

### 2.7 投资金 / 摆件

| sku_id | 名称 | 品牌 | 类目 | 定价 | 克重 | 成色 | 库存 | 30d 销量 | 90d 销量 | 好评 | 退货 | 新品 | 工厂 | active_campaigns | campaign_history |
|--------|------|------|------|------|------|------|------|----------|----------|------|------|------|------|------------------|------------------|
| CTF-INV-001 | Au999.9 投资金条 100g | CTF | 黄金/投资金 | weight | 100.00 | 999.9 | 60 | 9 | 28 | 99.5% | 0.1% | false | F-SH-003 | [] | [] |
| CTF-INV-002 | Au999.9 投资金条 20g | CTF | 黄金/投资金 | weight | 20.00 | 999.9 | 200 | 44 | 132 | 99.5% | 0.1% | false | F-SH-003 | [] | [] |

### 2.8 子品牌 / 国潮款（新品集中）

| sku_id | 名称 | 品牌 | 类目 | 定价 | 克重 | 成色 | 主石ct | 划线 | 14d 最低 | 30d 最低 | 90d 最低 | 365d 最低 | 库存 | 30d 销量 | 90d 销量 | 好评 | 退货 | 新品 | 工厂 | active_campaigns | campaign_history |
|--------|------|------|------|------|------|------|--------|------|----------|----------|----------|------------|------|----------|----------|------|------|------|------|------------------|------------------|
| CTF-SL-RG-001 | SOINLOVE 双心钻戒 0.20ct | SOINLOVE | 镶嵌/求婚钻戒 | fixed | 3.50 | Au750 | 0.20 | 11800 | 11400 | 11000 | 10500 | 10000 | 200 | 53 | 158 | 98.5% | 1.5% | true | F-SH-002 | [`jd:super_brand_day:2025_q4`] | [] |
| CTF-ML-NL-001 | MONOLOGUE 月光石锁骨链 | MONOLOGUE | 镶嵌/项链 | fixed | 1.80 | Au750 | — | 2680 | 2580 | 2480 | 2380 | 2280 | 480 | 84 | 252 | 97.8% | 2.5% | true | F-SH-002 | [] | [] |
| CTF-IP-001 | 国潮"长安"金吊坠 | 传承 | 黄金/古法金 | fixed | 4.50 | 999 | — | 4580 | 4450 | 4380 | 4280 | 4180 | 320 | 63 | 188 | 98.2% | 1.8% | true | F-SZ-001 | [`tmall:super_brand_day:2025_q4`, `tmall:category_day:2025_09_gold`] | [] |

---

## 3. 互斥检测样例（对应赛题示例规则）

### 3.1 赛题示例规则触发场景

```text
[活动规则] 天猫 618 大促规则第 4 条："已参加'品牌日'活动的商品不可重复报名"
[当前活动] tmall:618:2025
[Agent 行为] 扫描所有报名 618 的 SKU，检查 active_campaigns 和 campaign_history 是否包含 brand_day 或 super_brand_day
```

### 3.2 扫描结果（基于上述 SKU 样例）

| SKU | active_campaigns 含品牌日? | campaign_history 含品牌日? | 判定 |
|-----|----------------------------|-----------------------------|------|
| CTF-FJ-999-001 | ✅ 已在 618 | ✅ `tmall:brand_day:2024_09` | ⚠ **历史曾参与品牌日**，需澄清规则是否回溯到去年 |
| CTF-FJ-999-003 | ✅ 已在超品日 | ✅ `tmall:brand_day:2024_12` | ⚠ 同上 + 当前已在超品日，**双重冲突** |
| CTF-G18K-RG-002 | ✅ 当前在品牌日 2025_07 | ✅ 历史在双 11 | ❌ **直接互斥**（当前在品牌日） |
| CTF-PEARL-001 | ✅ 当前在品牌日 2025_07 | 否 | ❌ **直接互斥** |
| CTF-FJ-999-002 | 否 | 否 | ✅ 可报 |
| CTF-IP-001 | ✅ 超品日 + 品类日 | 否 | ⚠ **超品日属于品牌日范畴吗？澄清** |

### 3.3 Agent 期望输出

```json
{
  "exclusion_check_results": [
    {"sku_id": "CTF-G18K-RG-002", "decision": "reject", "severity": "high", "reason": "当前已在 tmall:brand_day:2025_07，与 tmall:618:2025 互斥"},
    {"sku_id": "CTF-PEARL-001", "decision": "reject", "severity": "high", "reason": "当前已在 tmall:brand_day:2025_07，与 tmall:618:2025 互斥"},
    {"sku_id": "CTF-IP-001", "decision": "review", "severity": "medium", "reason": "tmall:super_brand_day 是否属于'品牌日'范畴需澄清"},
    {"sku_id": "CTF-FJ-999-001", "decision": "review", "severity": "medium", "reason": "campaign_history 含品牌日，互斥规则是否回溯到去年需澄清"},
    {"sku_id": "CTF-FJ-999-002", "decision": "approve", "severity": "low", "reason": "无互斥冲突"}
  ],
  "clarification_questions": [
    "互斥规则中'品牌日'是仅指 brand_day，还是包括 super_brand_day？",
    "互斥回溯时窗是仅本期次（当前 active_campaigns），还是包含历史（campaign_history 近 365 天）？"
  ]
}
```

---

## 4. 维护说明

- 字段 `active_campaigns` 和 `campaign_history` 在真实 ERP 中通过订阅平台报名接口同步，黑客松版本静态写死。
- `campaign_history` 仅保留近 365 天记录，超过自动归档。
- 同 SKU 同一活动重复出现只计一次。
