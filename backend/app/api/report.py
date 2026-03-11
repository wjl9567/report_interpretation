"""报告解读 API 路由"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.schemas.report import (
    InterpretRequest,
    InterpretDirectRequest,
    InterpretResponse,
    ReportListResponse,
)
from app.services.interpretation import InterpretationService
from app.adapters import get_lis_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/report", tags=["报告解读"])

lis_adapter = get_lis_adapter()
interpret_service = InterpretationService(lis_adapter)


@router.get("/list/{patient_id}", response_model=ReportListResponse, summary="获取患者报告列表")
async def get_report_list(patient_id: str):
    """根据住院号/门诊号获取患者的检验报告列表"""
    try:
        reports = await lis_adapter.get_patient_reports(patient_id)
        patients = await lis_adapter.search_patient(patient_id)
        patient = patients[0] if patients else None

        if not patient:
            raise HTTPException(status_code=404, detail=f"未找到患者: {patient_id}")

        return ReportListResponse(
            patient=patient,
            reports=reports,
            total=len(reports),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取报告列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interpret", response_model=InterpretResponse, summary="AI解读报告")
async def interpret_report(req: InterpretRequest):
    """通过住院号和报告编号触发AI解读"""
    try:
        result = await interpret_service.interpret_by_patient(
            patient_id=req.patient_id,
            report_no=req.report_no,
            department_code=req.department_code,
            report_type=req.report_type,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"报告解读失败: {e}")
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


@router.get("/patient/search", summary="搜索患者")
async def search_patient(keyword: str):
    """根据住院号或姓名搜索患者"""
    try:
        patients = await lis_adapter.search_patient(keyword)
        return {"data": patients, "total": len(patients)}
    except Exception as e:
        logger.error(f"搜索患者失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdf", summary="报告 PDF 流（代理）")
async def get_report_pdf(patient_id: str, report_no: str):
    """根据 patient_id（HID）与 report_no 返回 PDF 字节流，供前端左侧展示。仅当 LIS 适配器支持时可用。"""
    get_pdf = getattr(lis_adapter, "get_report_pdf_bytes", None)
    if not get_pdf:
        raise HTTPException(status_code=501, detail="当前 LIS 适配器不支持 PDF 代理")
    try:
        content = await get_pdf(patient_id, report_no)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=report.pdf"},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取报告 PDF 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
