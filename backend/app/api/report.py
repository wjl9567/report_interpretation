"""报告解读 API 路由"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.schemas.report import (
    InterpretRequest,
    InterpretDirectRequest,
    InterpretResponse,
    ReportListResponse,
    ReportData,
)
from app.services.interpretation import InterpretationService
from app.services.hid_resolver import resolve_pat_num_to_hid
from app.adapters import get_lis_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/report", tags=["报告解读"])

lis_adapter = get_lis_adapter()
interpret_service = InterpretationService(lis_adapter)


async def _resolve_to_hid(patient_id: str) -> str:
    """若配置了 SQL Server pat_num→xh，则用病历号/门诊卡号解析出 HID，否则原样作为 HID。"""
    hid = await resolve_pat_num_to_hid(patient_id)
    return (hid if hid else patient_id).strip()


@router.get("/list/{patient_id}", response_model=ReportListResponse, summary="获取患者报告列表")
async def get_report_list(patient_id: str):
    """根据住院号/门诊号或病历号/门诊卡号获取患者的检验报告列表；若配置 MSSQL 则先按 pat_num 解析为 xh（HID）再查 LIS。"""
    try:
        hid = await _resolve_to_hid(patient_id)
        reports = await lis_adapter.get_patient_reports(hid)
        patients = await lis_adapter.search_patient(hid)
        patient = patients[0] if patients else None

        if not patient:
            raise HTTPException(status_code=404, detail=f"未找到患者: {patient_id}")
        # 返回时 patient_id 保持为前端/EMR 传入的标识（可能为 pat_num），内部已用 hid 查 LIS

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
    """通过住院号/门诊号或病历号/门诊卡号与报告编号触发AI解读；若配置 MSSQL 则先按 pat_num 解析为 HID。"""
    try:
        hid = await _resolve_to_hid(req.patient_id)
        result = await interpret_service.interpret_by_patient(
            patient_id=hid,
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
    """根据 patient_id（或病历号）与 report_no 返回报告完整数据，供前端在解读前展示报告项目。"""
    try:
        hid = await _resolve_to_hid(patient_id)
        report = await lis_adapter.get_report_detail(hid, report_no)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取报告详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdf", summary="报告 PDF 流（代理）")
async def get_report_pdf(patient_id: str, report_no: str):
    """根据 patient_id（或病历号/门诊卡号，若配置 MSSQL 则先解析为 HID）与 report_no 返回 PDF 字节流。"""
    get_pdf = getattr(lis_adapter, "get_report_pdf_bytes", None)
    if not get_pdf:
        raise HTTPException(status_code=501, detail="当前 LIS 适配器不支持 PDF 代理")
    try:
        hid = await _resolve_to_hid(patient_id)
        content = await get_pdf(hid, report_no)
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
