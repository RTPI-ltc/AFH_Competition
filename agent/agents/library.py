from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentSpec:
    id: str
    name: str
    scenario: str
    description: str
    capabilities: tuple[str, ...]
    suggested_knowledge: tuple[str, ...]
    tools: tuple[str, ...]
    output_modes: tuple[str, ...]
    risk_controls: tuple[str, ...]
    orchestration_goal: str
    response_style: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "scenario": self.scenario,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "suggested_knowledge": list(self.suggested_knowledge),
            "tools": list(self.tools),
            "output_modes": list(self.output_modes),
            "risk_controls": list(self.risk_controls),
            "orchestration_goal": self.orchestration_goal,
            "response_style": self.response_style,
        }


_AGENT_SPECS: tuple[AgentSpec, ...] = (
    AgentSpec(
        id="hackathon-assistant",
        name="黑客松助手",
        scenario="赛事规则、提交材料与评审标准核对",
        description="面向参赛团队的知识库问答与材料核对 Agent，帮助梳理规则、截止时间、演示要求和待确认事项。",
        capabilities=(
            "解析赛事规则与任务说明",
            "生成提交材料检查清单",
            "标注评审标准对应证据",
            "识别缺失材料与模糊要求",
        ),
        suggested_knowledge=(
            "赛事通知",
            "评审规则",
            "提交模板",
            "常见问答",
        ),
        tools=(
            "知识库检索",
            "规则结构化",
            "清单生成",
            "人工确认",
        ),
        output_modes=(
            "规则摘要",
            "提交清单",
            "风险提示",
            "答辩准备要点",
        ),
        risk_controls=(
            "无法从知识库确认的要求必须标记为待核实",
            "涉及截止时间和评分口径时保留引用来源",
            "发现材料缺口时给出人工补充项",
        ),
        orchestration_goal="围绕赛事规则、提交材料、评审标准和待确认信息组织回答。",
        response_style="直接给出赛事相关结论、依据片段和下一步建议，不渲染固定检查清单模板。",
    ),
    AgentSpec(
        id="course-ta",
        name="课程助教",
        scenario="课程资料问答、复习提纲与练习反馈",
        description="面向通识课、培训课和内部学习资料的助教 Agent，基于课程知识库回答问题并生成复习路径。",
        capabilities=(
            "回答课程资料内的问题",
            "提炼章节知识点",
            "生成复习提纲与练习题",
            "提示超出资料范围的问题",
        ),
        suggested_knowledge=(
            "课程大纲",
            "讲义与阅读材料",
            "作业要求",
            "教师答疑记录",
        ),
        tools=(
            "知识库检索",
            "引用片段整理",
            "练习题生成",
            "薄弱点归纳",
        ),
        output_modes=(
            "问答回复",
            "知识点卡片",
            "复习计划",
            "练习题与参考要点",
        ),
        risk_controls=(
            "知识库外推断必须降置信度",
            "对评分或考试范围类问题提示以教师说明为准",
            "引用不足时建议补充章节或讲义页码",
        ),
        orchestration_goal="围绕课程资料问答、概念解释、复习建议和练习反馈组织回答。",
        response_style="用助教口吻解释知识点，区分课程资料证据和补充推断。",
    ),
    AgentSpec(
        id="project-application",
        name="项目申报助手",
        scenario="申报指南解读、材料完整性与附件核对",
        description="面向科研、大创、基金和商业计划等申报场景，帮助拆解指南要求并形成可执行材料清单。",
        capabilities=(
            "解读申报条件与限制",
            "梳理正文结构与附件要求",
            "核对材料完整性",
            "生成下一步行动清单",
        ),
        suggested_knowledge=(
            "申报指南",
            "模板文件",
            "评分细则",
            "往期问题记录",
        ),
        tools=(
            "指南条款抽取",
            "材料清单生成",
            "缺口分析",
            "版本对照",
        ),
        output_modes=(
            "申报条件摘要",
            "材料缺口表",
            "行动清单",
            "待人工确认问题",
        ),
        risk_controls=(
            "资格条件和截止日期必须保留来源",
            "政策口径不明确时要求人工确认",
            "附件缺失或版本冲突时标记高优先级",
        ),
        orchestration_goal="围绕申报条件、材料完整性、附件要求和政策边界组织回答。",
        response_style="输出申报视角的材料缺口、依据和行动建议，避免模板化任务卡。",
    ),
    AgentSpec(
        id="enterprise-knowledge",
        name="企业知识库助手",
        scenario="制度问答、流程核对与内部经验沉淀",
        description="面向企业内部制度、流程、培训和项目资料的知识库 Agent，提供可追溯的问答与流程辅助。",
        capabilities=(
            "回答内部制度与流程问题",
            "整理操作步骤与责任边界",
            "沉淀高频问答",
            "发现知识缺口与过期资料",
        ),
        suggested_knowledge=(
            "制度文件",
            "流程手册",
            "培训资料",
            "项目复盘记录",
        ),
        tools=(
            "权限内知识检索",
            "流程步骤抽取",
            "引用来源标注",
            "知识缺口记录",
        ),
        output_modes=(
            "制度问答",
            "流程步骤",
            "引用依据",
            "知识维护建议",
        ),
        risk_controls=(
            "敏感或权限不明内容不直接展开",
            "过期制度需提示复核发布日期",
            "跨部门责任边界不清时转人工确认",
        ),
        orchestration_goal="围绕内部制度、流程步骤、责任边界和知识维护建议组织回答。",
        response_style="保持企业知识库问答风格，强调来源、版本和权限边界。",
    ),
    AgentSpec(
        id="evidence-review",
        name="证据审阅助手",
        scenario="答案溯源、冲突识别与低置信结论复核",
        description="面向高可信问答和报告审阅，检查结论是否有足够证据支撑，并输出需要人工复核的清单。",
        capabilities=(
            "检查结论与证据的一致性",
            "识别资料冲突和引用缺口",
            "区分可确认结论与低置信结论",
            "生成复核问题清单",
        ),
        suggested_knowledge=(
            "原始资料",
            "引用片段",
            "审阅标准",
            "人工复核记录",
        ),
        tools=(
            "证据检索",
            "引用对照",
            "冲突检测",
            "置信度标注",
        ),
        output_modes=(
            "证据审阅表",
            "低置信结论",
            "冲突说明",
            "人工复核清单",
        ),
        risk_controls=(
            "没有来源支撑的结论不得标记为已确认",
            "相互矛盾的资料必须并列展示",
            "高影响结论需要人工复核后再输出最终口径",
        ),
        orchestration_goal="围绕证据充分性、冲突识别、低置信结论和复核问题组织回答。",
        response_style="以审阅者口吻输出证据判断，不替用户生成执行任务模板。",
    ),
)


def list_agent_specs() -> list[dict[str, Any]]:
    return [spec.to_dict() for spec in _AGENT_SPECS]


def get_agent_spec(agent_id: str | None) -> AgentSpec:
    if agent_id:
        for spec in _AGENT_SPECS:
            if spec.id == agent_id:
                return spec
    return _AGENT_SPECS[0]
