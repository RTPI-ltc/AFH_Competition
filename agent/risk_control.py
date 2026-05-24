from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent import database


RISK_EVENT_DIR = Path(os.getenv("AFH_RISK_EVENT_DIR", "data/risk_events"))

FORBIDDEN_CLAIMS = (
    "100%保真",
    "百分百保真",
    "全网最低",
    "最低价",
    "绝对最低",
    "稳赚",
    "保本",
    "保证升值",
    "闭眼买",
)

PROMISE_PATTERNS = (
    r"保证.{0,8}(升值|赚钱|回本|转化|销量)",
    r"一定.{0,8}(爆单|卖爆|赚钱|回本)",
    r"(零风险|无风险)",
)

PRICE_PATTERN = re.compile(r"(?:¥|￥)?\s*(\d[\d,]*(?:\.\d{1,2})?)\s*(?:元|块|RMB|rmb)")


@dataclass
class RiskFinding:
    code: str
    description: str
    severity: str = "medium"
    suggestion: str = ""
    source: str = "risk_control"
    product_name: str | None = None
    sku_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_risk_item(self) -> dict[str, str]:
        text = self.description
        if self.suggestion:
            text = f"{text} 建议：{self.suggestion}"
        return {"description": text, "severity": "high" if self.severity == "high" else "medium"}


@dataclass
class RiskAuditResult:
    findings: list[RiskFinding]
    should_block_actions: bool = False

    @property
    def high_count(self) -> int:
        return sum(1 for item in self.findings if item.severity == "high")

    def to_metadata(self) -> dict[str, Any]:
        return {
            "findings": [
                {
                    "code": item.code,
                    "description": item.description,
                    "severity": item.severity,
                    "suggestion": item.suggestion,
                    "source": item.source,
                    "product_name": item.product_name,
                    "sku_id": item.sku_id,
                    "metadata": item.metadata,
                }
                for item in self.findings
            ],
            "should_block_actions": self.should_block_actions,
            "high_count": self.high_count,
        }


def _safe_float(value: Any, default: float = 0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _catalog_indices() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_sku: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for product in database.list_catalog_products(limit=2000):
        sku = str(product.get("sku_id") or "").upper()
        name = str(product.get("product_name") or "")
        if sku:
            by_sku[sku] = product
        if name:
            by_name[name] = product
    return by_sku, by_name


def _match_product(item: dict[str, Any], by_sku: dict[str, dict[str, Any]], by_name: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    details = item.get("details") if isinstance(item.get("details"), dict) else {}
    sku = str(item.get("sku_id") or details.get("sku_id") or "").upper()
    if sku and sku in by_sku:
        return by_sku[sku]
    name = str(item.get("product_name") or "").strip()
    if name and name in by_name:
        return by_name[name]
    return None


def _price_candidates(product: dict[str, Any]) -> set[float]:
    keys = (
        "tag_price_rmb",
        "list_price_rmb",
        "last_30d_min_price",
        "last_90d_min_price",
        "last_365d_min_price",
    )
    values = {_safe_float(product.get(key)) for key in keys}
    weight = _safe_float(product.get("weight_g"))
    tag_price = _safe_float(product.get("tag_price_rmb"))
    if weight and tag_price:
        values.add(round(weight * tag_price, 2))
    return {round(value, 2) for value in values if value > 0}


def _collect_referenced_products(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    by_sku, by_name = _catalog_indices()
    products: dict[str, dict[str, Any]] = {}
    for key in ("recommendations", "actions"):
        value = parsed.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            product = _match_product(item, by_sku, by_name)
            if product and product.get("sku_id"):
                products[str(product["sku_id"])] = product
    return list(products.values())


def _audit_reply_claims(reply: str) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    for word in FORBIDDEN_CLAIMS:
        if word in reply:
            findings.append(RiskFinding(
                code="forbidden_claim",
                description=f"回复中包含高风险承诺或极限表述：{word}",
                severity="high",
                suggestion="改为基于库存、价格、销量等事实的审慎表达，并保留人工确认。",
                metadata={"matched": word},
            ))
    for pattern in PROMISE_PATTERNS:
        if re.search(pattern, reply):
            findings.append(RiskFinding(
                code="promise_pattern",
                description="回复中包含确定性收益、销量或零风险承诺。",
                severity="high",
                suggestion="删除承诺式表达，改为概率性判断和风险提示。",
                metadata={"pattern": pattern},
            ))
    return findings


def _audit_price_consistency(reply: str, products: list[dict[str, Any]]) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    mentioned_prices = {round(float(item.replace(",", "")), 2) for item in PRICE_PATTERN.findall(reply)}
    if not mentioned_prices or not products:
        return findings
    valid_prices: set[float] = set()
    for product in products:
        valid_prices.update(_price_candidates(product))
    if not valid_prices:
        return findings
    for price in sorted(mentioned_prices):
        if price not in valid_prices:
            findings.append(RiskFinding(
                code="price_mismatch",
                description=f"回复中出现价格 {price:g} 元，但未匹配到被引用商品的数据库价格。",
                severity="high",
                suggestion="以商品库价格为准，人工确认后再对外使用。",
                metadata={"mentioned_price": price, "valid_prices": sorted(valid_prices)},
            ))
    return findings


def _audit_product(product: dict[str, Any]) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    name = str(product.get("product_name") or "")
    sku = str(product.get("sku_id") or "")
    active_campaigns = product.get("active_campaigns") or []
    if active_campaigns:
        findings.append(RiskFinding(
            code="campaign_conflict",
            description=f"{name} 已关联活动 {', '.join(active_campaigns)}，可能与本次报名互斥。",
            severity="high",
            suggestion="确认活动互斥规则和退出/叠加条件。",
            product_name=name,
            sku_id=sku,
        ))
    list_price = _safe_float(product.get("list_price_rmb"))
    for key, label in (("last_30d_min_price", "近30天最低价"), ("last_90d_min_price", "近90天最低价")):
        min_price = _safe_float(product.get(key))
        if list_price and min_price and list_price > min_price:
            findings.append(RiskFinding(
                code="price_protection",
                description=f"{name} 当前标价高于{label}，存在价格保护口径风险。",
                severity="high",
                suggestion="确认活动价、券后价、会员价是否满足平台最低价规则。",
                product_name=name,
                sku_id=sku,
                metadata={"list_price_rmb": list_price, key: min_price},
            ))
    stock = int(_safe_float(product.get("stock")))
    sales = int(_safe_float(product.get("last_90d_sales")))
    if stock < max(20, int(sales * 0.3)):
        findings.append(RiskFinding(
            code="stock_shortage",
            description=f"{name} 库存相对近90天销量偏低，活动期间可能缺货。",
            severity="medium",
            suggestion="确认可售库存、补货周期和活动锁库策略。",
            product_name=name,
            sku_id=sku,
            metadata={"stock": stock, "last_90d_sales": sales},
        ))
    review_rate = _safe_float(product.get("review_rate"))
    if review_rate and review_rate < 95:
        findings.append(RiskFinding(
            code="review_rate_low",
            description=f"{name} 好评率低于95%，转化和审核存在风险。",
            severity="medium",
            suggestion="复核差评原因、详情页承诺和售后说明。",
            product_name=name,
            sku_id=sku,
            metadata={"review_rate": review_rate},
        ))
    return_rate = _safe_float(product.get("return_rate"))
    if return_rate >= 3:
        findings.append(RiskFinding(
            code="return_rate_high",
            description=f"{name} 退货率偏高，可能影响活动表现。",
            severity="medium",
            suggestion="复核尺码/材质描述、发货质检和售后预期。",
            product_name=name,
            sku_id=sku,
            metadata={"return_rate": return_rate},
        ))
    if not product.get("certificate_ids"):
        findings.append(RiskFinding(
            code="certificate_missing",
            description=f"{name} 缺少证书编号或质检信息。",
            severity="medium",
            suggestion="补齐材质、成色、宝石证书或质检证明后再确认。",
            product_name=name,
            sku_id=sku,
        ))
    return findings


def _dedupe_findings(findings: list[RiskFinding]) -> list[RiskFinding]:
    seen: set[tuple[str, str, str | None]] = set()
    result: list[RiskFinding] = []
    for item in findings:
        key = (item.code, item.description, item.sku_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def audit_chat_result(project_id: str, message: str, parsed: dict[str, Any]) -> RiskAuditResult:
    reply = str(parsed.get("reply") or "")
    products = _collect_referenced_products(parsed)
    findings: list[RiskFinding] = []
    findings.extend(_audit_reply_claims(reply))
    findings.extend(_audit_price_consistency(reply, products))
    for product in products:
        findings.extend(_audit_product(product))

    action_count = len(parsed.get("actions") or []) if isinstance(parsed.get("actions"), list) else 0
    high_policy_findings = [item for item in findings if item.severity == "high" and item.code in {
        "forbidden_claim",
        "promise_pattern",
        "price_mismatch",
        "campaign_conflict",
        "price_protection",
    }]
    should_block_actions = bool(action_count and high_policy_findings)
    result = RiskAuditResult(_dedupe_findings(findings), should_block_actions)
    record_risk_event(
        "chat_risk_audit",
        project_id=project_id,
        severity="high" if result.high_count else ("medium" if result.findings else "low"),
        status="blocked" if result.should_block_actions else "passed",
        detail=f"message={message[:80]}",
        payload=result.to_metadata(),
    )
    return result


def apply_risk_audit(parsed: dict[str, Any], audit: RiskAuditResult) -> dict[str, Any]:
    if not audit.findings:
        parsed["risk_control"] = audit.to_metadata()
        return parsed
    cleaned = dict(parsed)
    existing_risks = cleaned.get("risks") if isinstance(cleaned.get("risks"), list) else []
    existing_clarifications = cleaned.get("needs_clarification") if isinstance(cleaned.get("needs_clarification"), list) else []
    cleaned["risks"] = [*existing_risks, *[item.to_risk_item() for item in audit.findings]]
    if audit.should_block_actions:
        cleaned["actions"] = []
        existing_clarifications = [
            *existing_clarifications,
            "风控发现高风险项，本轮未执行上架/移除动作。请人工确认风险后再提交。",
        ]
    else:
        existing_clarifications = [
            *existing_clarifications,
            *[
                f"{item.product_name or '当前方案'}：{item.suggestion}"
                for item in audit.findings
                if item.suggestion and item.severity == "high"
            ],
        ]
    cleaned["needs_clarification"] = list(dict.fromkeys(str(item) for item in existing_clarifications if item))
    cleaned["risk_control"] = audit.to_metadata()
    return cleaned


def record_risk_event(
    event_name: str,
    *,
    project_id: str,
    severity: str,
    status: str,
    detail: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    event = {
        "event_id": str(uuid.uuid4()),
        "event_name": event_name,
        "project_id": project_id,
        "severity": severity,
        "status": status,
        "detail": detail,
        "payload": payload or {},
        "created_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    try:
        RISK_EVENT_DIR.mkdir(parents=True, exist_ok=True)
        path = RISK_EVENT_DIR / f"{datetime.now(UTC).date().isoformat()}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        return
