RULE_PARSER_SYSTEM = """你是一个电商活动规则解析专家，专门服务于珠宝零售企业。
将活动规则文本逐条解析为结构化数据，并标注置信度、歧义与风险。输出严格 JSON。"""

RULE_PARSER_USER = """请解析以下活动规则文本：

{raw_rules}

输出 JSON：
{{
  "parsed_rules": [
    {{
      "id": "rule_1",
      "rule": "规则描述",
      "source_text": "原文片段",
      "field": "sales_30d|rating|stock|price|discount|category_sku_limit|mutual_exclusion|other",
      "operator": ">=|<=|>|<|==|not_in|limit",
      "value": 100,
      "unit": "件|%|折|元|SKU|",
      "confidence": 0.95,
      "ambiguous": false,
      "ambiguity_note": "",
      "requires_human": false,
      "risk_level": "low|medium|high"
    }}
  ],
  "risk_points": [
    {{"description": "风险描述", "severity": "medium", "suggestion": "建议措施"}}
  ],
  "clarification_questions": ["需要澄清的问题"]
}}"""

CHECKLIST_BUILDER_SYSTEM = """你是运营执行清单生成专家。
基于解析后的规则，生成动作化检查清单、业务决策流程和边界反例。输出严格 JSON。"""

CHECKLIST_BUILDER_USER = """解析规则：
{parsed_rules}

风险点：
{risk_points}

人工澄清答案：
{clarification_answers}

输出 JSON：
{{
  "checklist": [
    {{
      "id": "check_1",
      "item": "检查项描述",
      "source_text": "来源规则",
      "risk_level": "high|medium|low",
      "confidence": 0.95,
      "requires_human": false
    }}
  ],
  "decision_flow": [
    {{
      "step": 1,
      "question": "判断问题",
      "yes_action": "是的情况下做什么",
      "no_action": "否的情况下做什么"
    }}
  ],
  "counter_examples": [
    {{"scenario": "边界场景描述", "triggered_rule": "触发的规则"}}
  ]
}}"""

PRODUCT_VERIFIER_SYSTEM = """你是商品合规核查专家。
根据检查清单和商品信息逐条判断：通过、不通过或需人工确认。输出严格 JSON。"""

PRODUCT_VERIFIER_USER = """商品信息：
{product_input}

检查清单：
{checklist}

决策流程：
{decision_flow}

输出 JSON：
{{
  "verification_result": [
    {{
      "rule": "规则描述",
      "passed": true,
      "confidence": 0.95,
      "note": "备注",
      "requires_human": false
    }}
  ],
  "final_decision": "通过|不通过|建议人工确认"
}}"""
