# 检查清单模板库（Checklist Templates）

> Agent 在 `checklist_builder` 节点把解析出的规则转化为可执行检查项时，按本文档的模板生成动作化语言。模板按"规则类型"分类，确保 Agent 输出格式稳定。

---

## 1. 规则类型分类

C 方向 Agent 解析出的规则可归为 **6 大类**：

| 类型 | 标识 | 典型规则关键词 |
|------|------|----------------|
| **R-资质类（Qualification）** | `qual` | 营业执照、商标证、贵金属许可、DSR、违规记录 |
| **R-数据类（Data）** | `data` | 销量、好评率、退货率、UV、转化率 |
| **R-数量类（Quantity）** | `qty` | SKU 数、品类数、库存数 |
| **R-价格类（Price）** | `price` | 活动价、划线价、近 X 天最低价、让利幅度、价保 |
| **R-参数类（Parameter）** | `param` | 克重精度、4C、成色、证书类型 |
| **R-互斥类（Exclusion）** | `excl` | 已参加 X 活动不可再报、二选一、跨店满减不叠加 |

---

## 2. 资质类（qual）检查项模板

### 2.1 单项资质核验

```text
[模板] 确认 {资质名称} 在有效期内（截止 {expiry_date}），且距离活动开始日 ≥ {threshold_days} 天

[示例] 确认营业执照在有效期内（截止 2099-12-31），且距离活动开始日 ≥ 30 天
[数据来源] ../chow_tai_fook/company_qualifications.md
[判定] 临期 ≤ 6 个月 → medium；已过期 → high
```

### 2.2 店铺等级核验

```text
[模板] 确认 {平台} 店铺 {评分维度} ≥ {threshold}

[示例] 确认天猫旗舰店 DSR 综合评分 ≥ 4.7
[数据来源] ../chow_tai_fook/company_qualifications.md §5
[判定] 未达 → high
```

### 2.3 违规记录核验

```text
[模板] 确认 {平台} 近 {days} 天无 {违规级别} 违规

[示例] 确认天猫旗舰店近 180 天无严重违规扣 12 分
[判定] 命中 → high
```

---

## 3. 数据类（data）检查项模板

### 3.1 销量门槛

```text
[模板] 确认 SKU {sku_id} 近 {window_days} 天销量 ≥ {threshold} 件

[示例] 确认 SKU CTF-FJ-999-002 近 30 天销量 ≥ 100 件
[数据来源] sku.last_30d_sales 或 sku.last_90d_sales / 3
[判定] 未达且差距 > 5% → high；差距 ≤ 5% → medium
[补充澄清] 若规则原文只说"销量"未指明时窗，主动澄清
```

### 3.2 好评率门槛

```text
[模板] 确认 SKU {sku_id} 近 {window_days} 天好评率 ≥ {threshold}%

[示例] 确认 SKU CTF-FJ-999-002 近 30 天好评率 ≥ 95%
[数据来源] sku.review_rate
[判定] 未达 → high
```

### 3.3 退货率上限

```text
[模板] 确认 SKU {sku_id} 近 {window_days} 天退货率 ≤ {threshold}%

[判定] 超过 → high
```

---

## 4. 数量类（qty）检查项模板

### 4.1 SKU 数门槛

```text
[模板] 确认报名 {category} 类目 SKU 数 {<= 或 >=} {threshold}

[示例 上限] 确认报名黄金类目 SKU 数 ≤ 5
[示例 下限] 确认报名总 SKU 数 ≥ 200
[判定] 不满足 → high
```

### 4.2 库存承诺

```text
[模板] 确认 SKU {sku_id} 库存承诺 ≥ {commit_stock} 件，且当前实际库存满足 {commit_stock} 件 或 补货周期 lead_time_days ≤ 距活动天数

[示例] 确认 SKU CTF-FJ-999-002 库存承诺 ≥ 500 件
[数据来源] sku.stock + sku.factory_id + factory.lead_time_days
[判定] 见 ../chow_tai_fook/supply_chain.md §4
```

### 4.3 新品占比

```text
[模板] 确认报名 SKU 中近 {days} 天上新 SKU 占比 ≥ {threshold}%

[示例] 确认报名 SKU 中近 90 天上新占比 ≥ 30%
[数据来源] sku.new_product == True 的占比
[判定] 未达 → medium
```

---

## 5. 价格类（price）检查项模板

### 5.1 活动价 ≤ 近 X 天最低

```text
[模板] 确认 SKU {sku_id} 活动价 ≤ 近 {window_days} 天店内最低成交价

[示例] 确认 SKU CTF-FJ-999-002 活动价 ≤ 近 30 天店内最低成交价
[数据来源] sku.list_price_rmb vs sku.last_30d_min_price（或 14d / 90d）
[判定] 穿底 → high
[平台口径] 天猫 30d / 京东 14d / 百补 90d
```

### 5.2 全网最低核验

```text
[模板] 确认 SKU {sku_id} 活动价 ≤ 全网同款最低价（含 {渠道列表}）

[示例] 确认 SKU CTF-FJ-999-002 活动价 ≤ 全网同款最低价（含京东、抖音、得物、品牌官网）
[数据来源] 比价工具
[判定] 穿底 → high
```

### 5.3 划线价合规

```text
[模板] 确认 SKU {sku_id} 划线价为近 {days} 天内有实际成交、未划线的销售价

[示例] 确认 SKU CTF-FJ-999-002 划线价（2880 元）为近 30 天内有实际成交的销售价
[数据来源] 订单库 / 商详页配置
[判定] 不合规 → high；引用《明码标价规定》
```

### 5.4 让利幅度

```text
[模板] 确认 SKU {sku_id} 让利幅度 ≥ {threshold}%

[计算公式] 让利 = (划线价 - 活动价) / 划线价 + 券补 + 平台补贴
[示例] 确认 SKU CTF-FJ-999-002 让利幅度 ≥ 15%
[判定] 接近门槛（差距 ≤ 2pp）→ medium；穿底 → high
```

### 5.5 价保配置

```text
[模板] 确认 SKU {sku_id} 商详页价保规则配置为 {days} 天

[示例] 确认天猫店 SKU 商详页价保 15 天 / 京东 PLUS SKU 价保 45 天
[判定] 未配置 → medium；配置错误 → high
```

---

## 6. 参数类（param）检查项模板

### 6.1 黄金成色

```text
[模板] 确认 SKU {sku_id} 商详页明示 {成色}，且印记包含 {印记}

[示例] 确认 SKU CTF-FJ-999-002 商详页明示 Au999，印记包含"足金 999"
[数据来源] sku.purity + 印记 QC 记录
[判定] 不符 → high；按 GB 11887-2012
```

### 6.2 钻石 4C

```text
[模板] 确认 SKU {sku_id}（30 分以上钻石）商详页明示完整 4C：克拉 / 颜色 / 净度 / 切工，且对应 {证书机构} 证书编号 {cert_no}

[示例] 确认 SKU CTF-G18K-NL-001 商详页明示 0.50ct/F/VS1/EX，且 GIA 证书编号 2400001234
[判定] 缺任一字段 → medium；证书机构不符 → high
```

### 6.3 翡翠 A 货

```text
[模板] 确认翡翠 SKU {sku_id} 商详页明示"A 货"，且有 NGTC A 货证书

[判定] 缺 A 货证书 → high
```

---

## 7. 互斥类（excl）检查项模板

### 7.1 单 SKU 互斥检测

```text
[模板] 确认 SKU {sku_id} 当前 active_campaigns 不包含与 {target_campaign} 互斥的活动

[示例] 确认 SKU CTF-FJ-999-002 当前 active_campaigns 不包含品牌日
[数据来源] sku.active_campaigns + ../rule_library/mutual_exclusion_matrix.md
[判定] 命中 → high
```

### 7.2 跨店互斥

```text
[模板] 确认同集团多店铺中，SKU {sku_id} 仅在 {target_store} 报名

[示例] 确认 CTF-FJ-999-002 仅在周大福官方旗舰店报名，不在 LOLA 旗舰店重复报名
[判定] 重复 → medium
```

### 7.3 跨平台穿底

```text
[模板] 确认 SKU {sku_id} 在 {target_platform} 的活动价 ≤ 其他平台同款近 X 天最低

[示例] 确认 CTF-FJ-999-002 在淘宝百亿补贴的价格 ≤ 京东百亿补贴近 90 天最低
[判定] 穿底 → high
```

---

## 8. Agent 生成 checklist 的标准输出格式

```json
[
  {
    "item_id": "C1",
    "category": "data",
    "template_id": "3.1",
    "item": "确认 SKU CTF-FJ-999-002 近 30 天销量 ≥ 100 件",
    "data_source": "sku.last_30d_sales",
    "expected": "≥ 100",
    "actual": "TBD（运行时取值）",
    "risk_level": "high",
    "requires_human": false,
    "trigger_rule_id": "R1.1"
  },
  {
    "item_id": "C2",
    "category": "price",
    "template_id": "5.1",
    "item": "确认 SKU CTF-FJ-999-002 活动价 ≤ 近 30 天店内最低成交价",
    "data_source": "sku.last_30d_min_price",
    "expected": "list_price_rmb ≤ last_30d_min_price",
    "actual": "TBD",
    "risk_level": "high",
    "requires_human": false,
    "trigger_rule_id": "R2.1"
  }
]
```
