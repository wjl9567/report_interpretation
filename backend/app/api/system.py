"""系统状态 API"""

import logging

import httpx
from fastapi import APIRouter

from app.core.config import settings
from app.services.llm_service import llm_service
from app.services.ocr_service import ocr_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["系统"])


@router.get("/health", summary="健康检查")
async def health_check():
    vllm_ok = await llm_service.health_check()
    ocr_ok = await ocr_service.health_check()

    hl7_info = {"enabled": settings.HL7_ENABLED}
    if settings.HL7_ENABLED:
        from app.hl7.server import get_mllp_server, get_hl7_stats
        server = get_mllp_server()
        hl7_info["running"] = server.is_running if server else False
        hl7_info["stats"] = get_hl7_stats()

    return {
        "status": "ok",
        "hospital": settings.HOSPITAL_NAME,
        "version": settings.APP_VERSION,
        "lis_adapter": settings.LIS_ADAPTER,
        "vllm_status": "connected" if vllm_ok else "disconnected",
        "ocr_status": "connected" if ocr_ok else "disconnected",
        "hl7": hl7_info,
    }


@router.get("/config", summary="前端配置信息")
async def get_frontend_config():
    return {
        "app_name": settings.APP_NAME,
        "hospital_name": settings.HOSPITAL_NAME,
        "version": settings.APP_VERSION,
        "lis_adapter": settings.LIS_ADAPTER,
        "hl7_enabled": settings.HL7_ENABLED,
        "embed_report_mode": settings.EMBED_REPORT_MODE,
        "departments": [
            {"code": "hematology", "name": "血液科"},
            {"code": "internal", "name": "内科"},
            {"code": "respiratory", "name": "呼吸科"},
            {"code": "general", "name": "通用"},
        ],
        "report_types": [
            {"code": "lab", "name": "检验报告"},
            {"code": "ultrasound", "name": "B超"},
            {"code": "ecg", "name": "心电图"},
            {"code": "eeg", "name": "脑电图"},
            {"code": "pulmonary", "name": "肺功能"},
            {"code": "ct", "name": "CT"},
            {"code": "xray", "name": "放射/X光"},
            {"code": "mri", "name": "核磁共振"},
        ],
    }


@router.get("/lis-check", summary="LIS 接口连通性检测")
async def lis_connectivity_check():
    """检测卫宁 Web API 是否可达"""
    if settings.LIS_ADAPTER == "mock":
        return {
            "adapter": "mock",
            "status": "ok",
            "message": "当前使用 Mock 适配器，无需连通性检测",
        }

    base_url = settings.LIS_API_BASE_URL
    if not base_url:
        return {
            "adapter": settings.LIS_ADAPTER,
            "status": "error",
            "message": "LIS_API_BASE_URL 未配置",
        }

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(base_url)
            reachable = resp.status_code < 500
    except httpx.ConnectError:
        return {
            "adapter": settings.LIS_ADAPTER,
            "status": "error",
            "base_url": base_url,
            "message": "无法连接到 LIS 服务",
        }
    except httpx.TimeoutException:
        return {
            "adapter": settings.LIS_ADAPTER,
            "status": "error",
            "base_url": base_url,
            "message": "连接超时",
        }
    except Exception as e:
        return {
            "adapter": settings.LIS_ADAPTER,
            "status": "error",
            "base_url": base_url,
            "message": str(e),
        }

    return {
        "adapter": settings.LIS_ADAPTER,
        "status": "ok" if reachable else "degraded",
        "base_url": base_url,
        "http_status": resp.status_code,
        "message": "LIS 服务可达" if reachable else f"LIS 服务返回异常状态码: {resp.status_code}",
    }
