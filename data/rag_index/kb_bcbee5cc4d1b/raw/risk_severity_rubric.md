# 风险点分级判定准则（Risk Severity Rubric）

> Agent 在 `rule_parser` 与 `checklist_builder` 节点输出 `risk_points` 时，按本文档判定 `severity = high / medium / low`。

---

## 1. 三级分级判定准则

### 1.1 High（高风险，必须人工介入）

满足以下**任一**条件即标 `high`：

| 触发条件 | 典型场景 |
|---------|---------|
| 直接违反国家强制法规 | 划线价虚标违反《明码标价规定》 |
| 直接违反平台硬性规则导致下架 / 处罚 | 价格穿底、虚假宣传 |
| 数值型规则**穿底**（不满足且差距 > 5%） | 销量 50 件 < 100 件门槛 |
| 互斥规则**冲突命中** | 同 SKU 已在互斥活动报名 |
| 资质 / 证书**已过期** | 营业执照过期 |
| 库存**严重不足**（< 日均销量 × 3 天） | 报名承诺 500、实际 80 |
| 全网比价**穿底** | 抖音直播间价低于天猫活动价 |
| 触发可能立即下架 SKU 的事件 | DSR 跌破 4.0 |
| 涉及法律 / 媒体 / 公关层面的违规 | 翡翠 B/C 货当 A 货销售 |

**Agent 处置**：
- `requires_human=true`
- 路由到对应角色（见 `../chow_tai_fook/human_review_routing.md`）
- 30 分钟–4 小时 SLA
- 阻止 `auto_decision_executor` 继续执行

### 1.2 Medium（中风险，建议人工确认但 Agent 可附条件继续）

满足以下**任一**条件即标 `medium`：

| 触发条件 | 典型场景 |
|---------|---------|
| 数值型规则**接近阈值**（差距 ≤ 5%） | 销量 98 件接近 100 件门槛 |
| 资质 / 证书**临期**（≤ 6 个月） | 商标证还剩 4 个月到期 |
| 库存**预警**（< 日均销量 × 10 天但 ≥ 3 天） | 报名承诺 500、实际 200，可补货 |
| 让利幅度**勉强达标**（差距 ≤ 2 个百分点） | 让利 15.5% 接近 15% 门槛 |
| 规则**轻微歧义**（影响范围有限） | "好评率 ≥ 95%"统计时窗未明确 |
| 商品参数**不完整但不构成欺诈** | 钻石未填荧光等级 |
| 客服话术 / 商详页**配置错误**但可整改 | 价保规则未在商详页明示 |
| 渠道**部分穿底**（影响小） | PLUS 价低于全网，但仅个别 SKU |

**Agent 处置**：
- `requires_human=true`（建议人工确认，但可附"待补救动作"继续）
- 路由到对应角色，1–4 小时 SLA
- 允许 `auto_decision_executor` 在用户确认后执行

### 1.3 Low（低风险，仅提示，Agent 可自动决策）

满足以下**任一**条件即标 `low`：

| 触发条件 | 典型场景 |
|---------|---------|
| 数值型规则**显著满足**（超出门槛 ≥ 20%） | 销量 500 件远超 100 件门槛 |
| 资质 / 证书**长期有效** | 证书剩余有效期 > 1 年 |
| 库存**充足**（≥ 日均销量 × 30 天） | 备货完成 |
| 规则**清晰无歧义** | "活动价 199 元" 明确数值 |
| 风险**已有自动化兜底**（如自动退差） | 价保已配置自动跑批 |

**Agent 处置**：
- `requires_human=false`
- 自动通过，仅在最终报告中列出供事后审计

---

## 2. 各类规则的默认风险等级（速查表）

| 规则类型 | 默认 severity |
|---------|---------------|
| 资质 / 证书过期 | high |
| 资质 / 证书临期（≤ 6 个月） | medium |
| 价格穿底（活动价 > 近 X 天最低） | high |
| 价格临界（差距 ≤ 1%） | medium |
| 划线价虚高 | high |
| 让利不足门槛 | high |
| 让利接近门槛（差距 ≤ 2pp） | medium |
| 库存严重不足（< 日均 × 3 天） | high |
| 库存预警（< 日均 × 10 天） | medium |
| 库存充足 | low |
| 互斥活动冲突 | high |
| 销量 / 好评不足 | medium 或 high（视差距） |
| 商品参数不完整 | medium |
| 商品参数完整但不规范 | low |
| 商详页话术不合规 | medium |
| 假货 / 培育钻当天然钻 | high |

---

## 3. 跨规则置信度聚合（用于 `final_decision`）

`product_verifier` 节点最终判定按以下规则聚合：

```python
def final_decision(verification_results):
    """
    verification_results: [{"rule": str, "pass": bool, "confidence": float, "severity": str}]
    """
    if any(r["severity"] == "high" and not r["pass"] for r in verification_results):
        return "不通过"

    if any(r["severity"] == "high" and r.get("ambiguous") for r in verification_results):
        return "建议人工确认"

    if all(r["pass"] for r in verification_results):
        min_conf = min(r["confidence"] for r in verification_results)
        if min_conf < 0.7:
            return "建议人工确认"
        return "通过"

    # 有 medium / low 不通过
    if all(r["severity"] != "high" for r in verification_results):
        return "建议人工确认"  # medium 不通过仍建议人工

    return "不通过"
```

---

## 4. Agent 输出 `risk_points` 的标准格式

```json
{
  "description": "活动价 198 元 < 近 30 天最低价 188 元",
  "severity": "high",
  "trigger_rule_id": "R2.1",
  "suggestion": "调价至 ≥ 188 元 或退出报名",
  "requires_human": true,
  "routing_role": "价格管理 + 品类经理",
  "sla_minutes": 120
}
```
