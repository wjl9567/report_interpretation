"""报告解读 API 路由"""

import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.schemas.report import (
    InterpretRequest,
    InterpretDirectRequest,
    InterpretResponse,
    InterpretMultiRequest,
    InterpretMultiResponse,
    ReportListResponse,
    ReportData,
)
from app.services.interpretation import InterpretationService
from app.services.hid_resolver import resolve_pat_num_to_hid, resolve_pat_num_to_hid_list
from app.adapters import get_lis_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/report", tags=["报告解读"])

lis_adapter = get_lis_adapter()
interpret_service = InterpretationService(lis_adapter)


async def _resolve_to_hid(patient_id: str) -> str:
    """若配置了 SQL Server pat_num→xh，则用病历号/门诊卡号解析出 HID，否则原样作为 HID。"""
    hid = await resolve_pat_num_to_hid(patient_id)
    return (hid if hid else patient_id).strip()


async def _resolve_to_hid_list(patient_id: str) -> list[str]:
    """解析出 HID 列表：当配置 MSSQL_VIEW_REPORT_DAYS 时为近 N 天内多 HID，否则为单 HID 列表。未启用 MSSQL 时用 patient_id 作为唯一 HID。"""
    hids = await resolve_pat_num_to_hid_list(patient_id)
    if hids:
        return hids
    hid = await resolve_pat_num_to_hid(patient_id)
    if hid or patient_id:
        return [(hid or patient_id).strip()]
    return []


@router.get("/list/{patient_id}", response_model=ReportListResponse, summary="获取患者报告列表")
async def get_report_list(patient_id: str):
    """根据住院号/门诊号或病历号/门诊卡号获取报告列表。若配置 MSSQL_VIEW_REPORT_DAYS=7/14，则只取近一周或两周内门急诊/住院对应的多 HID，合并列表并去重。"""
    try:
        hid_list = await _resolve_to_hid_list(patient_id)
        if not hid_list:
            raise HTTPException(status_code=404, detail=f"未解析到患者: {patient_id}")
        seen_no: set[str] = set()
        reports_merged: list = []
        patient = None
        for hid in hid_list:
            try:
                reports_batch = await lis_adapter.get_patient_reports(hid)
                for r in reports_batch:
                    rno = getattr(r, "report_no", None)
                    if rno and rno not in seen_no:
                        seen_no.add(rno)
                        reports_merged.append(r)
                if patient is None and reports_batch:
                    patients = await lis_adapter.search_patient(hid)
                    if patients:
                        patient = patients[0]
            except Exception as e:
                logger.debug(f"合并报告列表时跳过 HID={hid}: {e}")
        if patient is None and hid_list:
            patients = await lis_adapter.search_patient(hid_list[0])
            patient = patients[0] if patients else None
        if not patient:
            raise HTTPException(status_code=404, detail=f"未找到患者: {patient_id}")
        reports_merged.sort(key=lambda r: getattr(r, "report_date", None) or datetime.min, reverse=True)
        return ReportListResponse(
            patient=patient,
            reports=reports_merged,
            total=len(reports_merged),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取报告列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interpret", response_model=InterpretResponse, summary="AI解读报告")
async def interpret_report(req: InterpretRequest):
    """通过住院号/门诊号或病历号/门诊卡号与报告编号触发AI解读。多 HID 时依次尝试直到该 report_no 命中。"""
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    try:
        hid_list = await _resolve_to_hid_list(req.patient_id)
        if not hid_list:
            raise HTTPException(status_code=404, detail=f"未解析到患者: {req.patient_id}")
        last_err = None
        for hid in hid_list:
            try:
                result = await interpret_service.interpret_by_patient(
                    patient_id=hid,
                    report_no=req.report_no,
                    department_code=req.department_code,
                    report_type=req.report_type,
                )
                logger.info(
                    "interpret_done request_id=%s patient_id=%s report_no=%s latency_ms=%.0f",
                    request_id, req.patient_id, req.report_no, (time.perf_counter() - start) * 1000,
                )
                return result
            except ValueError as e:
                last_err = e
                continue
        raise HTTPException(status_code=404, detail=str(last_err) if last_err else "未找到报告")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("interpret_failed request_id=%s error=%s", request_id, e)
        raise HTTPException(status_code=500, detail=f"解读服务异常: {str(e)}")


@router.post("/interpret/direct", response_model=InterpretResponse, summary="直接传入报告数据解读")
async def interpret_direct(req: InterpretDirectRequest):
    """直接传入报告数据进行AI解读（不经过LIS查询）"""
    try:
        result = await interpret_service.interpret_report(
            report=req.report,
            department_code=req.department_code,
            report_type=req.report_type,
        )
        return result
    except Exception as e:
        logger.error(f"报告解读失败: {e}")
        raise HTTPException(status_code=500, detail=f"解读服务异常: {str(e)}")


@router.post("/interpret-multi", response_model=InterpretMultiResponse, summary="多份同类报告对比解读")
async def interpret_multi(req: InterpretMultiRequest):
    """基于多份同类报告（≥2 份）做对比与趋势解读。用于「多份对比解读」页左侧选中同类报告≥2 后右侧展示。"""
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    report_nos = [n for n in (req.report_nos or []) if (n or "").strip()]
    if len(report_nos) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 份报告编号")
    try:
        hid_list = await _resolve_to_hid_list(req.patient_id)
        if not hid_list:
            raise HTTPException(status_code=404, detail=f"未解析到患者: {req.patient_id}")
        reports: list[ReportData] = []
        for report_no in report_nos:
            for hid in hid_list:
                try:
                    report = await lis_adapter.get_report_detail(hid, report_no)
                    reports.append(report)
                    break
                except (ValueError, Exception):
                    continue
        if len(reports) < 2:
            raise HTTPException(status_code=400, detail="未能获取至少 2 份报告详情，请确认报告编号与患者匹配")
        report_title = reports[0].report_title if reports else ""
        result = await interpret_service.interpret_multi_reports(reports, report_title=report_title)
        logger.info(
            "interpret_multi_done request_id=%s patient_id=%s reports=%s latency_ms=%.0f",
            request_id, req.patient_id, len(reports), (time.perf_counter() - start) * 1000,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("interpret_multi_failed request_id=%s error=%s", request_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patient/search", summary="搜索患者")
async def search_patient(keyword: str):
    """根据住院号、病历号/门诊卡号或姓名搜索患者；若配置 MSSQL 则先尝试将 keyword 解析为 HID 再查 LIS。"""
    try:
        hid = await _resolve_to_hid(keyword)
        patients = await lis_adapter.search_patient(hid)
        return {"data": patients, "total": len(patients)}
    except Exception as e:
        logger.error(f"搜索患者失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detail", response_model=ReportData, summary="获取报告详情（含项目列表，解读前可展示）")
async def get_report_detail(patient_id: str, report_no: str):
    """根据 patient_id（或病历号）与 report_no 返回报告完整数据。多 HID 时依次尝试直到命中。"""
    try:
        hid_list = await _resolve_to_hid_list(patient_id)
        if not hid_list:
            raise HTTPException(status_code=404, detail=f"未解析到患者: {patient_id}")
        last_err = None
        for hid in hid_list:
            try:
                report = await lis_adapter.get_report_detail(hid, report_no)
                return report
            except ValueError as e:
                last_err = e
                continue
        raise HTTPException(status_code=404, detail=str(last_err) if last_err else "未找到报告")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取报告详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdf", summary="报告 PDF 流（代理）")
async def get_report_pdf(
    patient_id: str,
    report_no: str,
    source: Optional[str] = None,
):
    """根据 patient_id（或病历号/门诊卡号）与 report_no 返回 PDF 字节流。多 HID 时依次尝试直到命中。source=lab 检验(8092)，source=exam 检查(8091)。"""
    get_pdf = getattr(lis_adapter, "get_report_pdf_bytes", None)
    if not get_pdf:
        raise HTTPException(status_code=501, detail="当前 LIS 适配器不支持 PDF 代理")
    try:
        hid_list = await _resolve_to_hid_list(patient_id)
        if not hid_list:
            raise HTTPException(status_code=404, detail=f"未解析到患者: {patient_id}")
        last_err = None
        for hid in hid_list:
            try:
                content = await get_pdf(hid, report_no, source)
                return Response(
                    content=content,
                    media_type="application/pdf",
                    headers={"Content-Disposition": "inline; filename=report.pdf"},
                )
            except ValueError as e:
                last_err = e
                continue
        raise HTTPException(status_code=404, detail=str(last_err) if last_err else "未找到报告")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取报告 PDF 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
