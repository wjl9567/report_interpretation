"""报告解读核心服务

整合数据适配器、Prompt引擎、LLM推理，完成报告解读的完整链路。
"""

import re
import logging
from typing import Optional

from app.adapters.base import BaseLISAdapter
from app.services.llm_service import LLMService, llm_service
from app.prompts.templates import (
    get_system_prompt,
    build_report_user_message,
    get_multi_report_system_prompt,
    build_multi_report_user_message,
)
from app.schemas.report import (
    ReportData,
    InterpretResponse,
    InterpretMultiResponse,
    AbnormalItemResult,
    PatientInfo,
)

logger = logging.getLogger(__name__)

LEVEL_CONFIG = {
    "critical": {"label": "危急值", "color": "#FF0000"},
    "severe":   {"label": "重度异常", "color": "#FF6600"},
    "moderate": {"label": "中度异常", "color": "#FFAA00"},
    "mild":     {"label": "轻度异常", "color": "#FFDD66"},
    "normal":   {"label": "正常", "color": "#52C41A"},
}

LEVEL_ORDER = {"critical": 0, "severe": 1, "moderate": 2, "mild": 3, "normal": 4}


class InterpretationService:
    """报告解读核心服务"""

    def __init__(self, lis_adapter: BaseLISAdapter, llm: Optional[LLMService] = None):
        self.lis = lis_adapter
        self.llm = llm or llm_service

    async def interpret_by_patient(
        self,
        patient_id: str,
        report_no: Optional[str] = None,
        department_code: str = "general",
        report_type: str = "lab",
    ) -> InterpretResponse:
        """通过住院号获取报告并解读"""
        if report_no:
            report = await self.lis.get_report_detail(patient_id, report_no)
        else:
            report = await self.lis.get_latest_report(patient_id)

        return await self.interpret_report(report, department_code, report_type)

    async def interpret_report(
        self,
        report: ReportData,
        department_code: str = "general",
        report_type: str = "lab",
    ) -> InterpretResponse:
        """对给定报告数据进行AI解读"""
        system_prompt = get_system_prompt(department_code, report, report_type)
        user_message = build_report_user_message(report)

        logger.info(f"开始解读报告 {report.report_no}，科室: {department_code}")

        llm_response = await self.llm.chat(
            system_prompt=system_prompt,
            user_message=user_message,
        )

        abnormal_summary, clinical_significance, clinical_suggestion = self._parse_response(
            llm_response.content
        )

        abnormal_items = self._extract_abnormal_items(report)

        confidence = self._assess_confidence(llm_response.content, report)

        return InterpretResponse(
            report_no=report.report_no,
            patient=report.patient,
            report_title=report.report_title,
            report_date=report.report_date,
            items=report.items,
            abnormal_items=abnormal_items,
            abnormal_summary=abnormal_summary,
            clinical_significance=clinical_significance,
            clinical_suggestion=clinical_suggestion,
            confidence=confidence,
            model_name=llm_response.model,
            latency_ms=llm_response.latency_ms,
        )

    async def interpret_multi_reports(
        self,
        reports: list[ReportData],
        report_title: str = "",
    ) -> InterpretMultiResponse:
        """对多份同类报告做对比与趋势解读"""
        if not reports or len(reports) < 2:
            return InterpretMultiResponse(
                report_title=report_title,
                report_nos=[r.report_no for r in reports] if reports else [],
                summary="",
                suggestion="至少需要 2 份报告才能进行对比解读。",
            )
        system_prompt = get_multi_report_system_prompt()
        user_message = build_multi_report_user_message(reports)
        logger.info(f"开始多份报告对比解读，共 {len(reports)} 份")
        llm_response = await self.llm.chat(
            system_prompt=system_prompt,
            user_message=user_message,
        )
        summary, suggestion = self._parse_multi_response(llm_response.content)
        return InterpretMultiResponse(
            report_title=report_title or (reports[0].report_title if reports else ""),
            report_nos=[r.report_no for r in reports],
            summary=summary,
            suggestion=suggestion,
            model_name=llm_response.model,
            latency_ms=llm_response.latency_ms,
        )

    @staticmethod
    def _parse_multi_response(content: str) -> tuple[str, str]:
        """从多份报告解读输出中提取【对比与趋势总结】和【临床建议】"""
        summary = ""
        suggestion = ""
        if not content:
            return summary, suggestion
        sum_match = re.search(r"【对比与趋势总结】\s*(.*?)(?=【临床建议】|$)", content, re.DOTALL)
        if sum_match:
            summary = sum_match.group(1).strip()
        sug_match = re.search(r"【临床建议】\s*(.*?)$", content, re.DOTALL)
        if sug_match:
            suggestion = sug_match.group(1).strip()
        return summary, suggestion

    @staticmethod
    def _parse_response(content: str) -> tuple[str, str, str]:
        """解析模型输出，提取三个模块"""
        abnormal_summary = ""
        clinical_significance = ""
        clinical_suggestion = ""

        patterns = [
            (r"【异常总结】(.*?)(?=【临床意义】|$)", "summary"),
            (r"【临床意义】(.*?)(?=【临床建议】|$)", "significance"),
            (r"【临床建议】(.*?)$", "suggestion"),
        ]

        for pattern, key in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                text = match.group(1).strip()
                if key == "summary":
                    abnormal_summary = text
                elif key == "significance":
                    clinical_significance = text
                elif key == "suggestion":
                    clinical_suggestion = text

        if not abnormal_summary and not clinical_significance:
            abnormal_summary = content

        return abnormal_summary, clinical_significance, clinical_suggestion

    @staticmethod
    def _extract_abnormal_items(report: ReportData) -> list[AbnormalItemResult]:
        """提取并排序异常项"""
        items = []
        for item in report.items:
            level = item.abnormal_level or "normal"
            config = LEVEL_CONFIG.get(level, LEVEL_CONFIG["normal"])
            items.append(AbnormalItemResult(
                name=item.name,
                value=item.value,
                unit=item.unit,
                reference_range=item.reference_range,
                abnormal_level=level,
                level_label=config["label"],
                color=config["color"],
            ))

        items.sort(key=lambda x: LEVEL_ORDER.get(x.abnormal_level, 4))
        return items

    @staticmethod
    def _assess_confidence(content: str, report: ReportData) -> str:
        """评估解读可信度"""
        has_critical = any(i.abnormal_level == "critical" for i in report.items)
        if has_critical:
            return "high"

        report_item_names = {i.name for i in report.items}
        mentioned_count = sum(1 for name in report_item_names if name in content)
        coverage = mentioned_count / len(report_item_names) if report_item_names else 0

        if coverage >= 0.6:
            return "high"
        elif coverage >= 0.3:
            return "medium"
        return "low"
