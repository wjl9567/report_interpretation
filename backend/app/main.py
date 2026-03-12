"""FastAPI 主入口 - 全站中文、UTF-8、中国时区"""

import logging
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.api.report import router as report_router
from app.api.system import router as system_router
from app.api.ocr import router as ocr_router
from app.api.hl7 import router as hl7_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info(f"启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    logging.info(f"医院: {settings.HOSPITAL_NAME}")
    logging.info(f"推理服务(sglang/安诊儿)地址: {settings.VLLM_BASE_URL}")
    logging.info(f"LIS 适配器: {settings.LIS_ADAPTER}")
    await init_db()

    hl7_handler = None
    if settings.HL7_ENABLED:
        try:
            from app.hl7.server import create_mllp_server
            from app.hl7.handler import HL7MessageHandler

            server = create_mllp_server()
            await server.start()
            hl7_handler = HL7MessageHandler(server)
            await hl7_handler.start()
            logging.info(f"HL7 MLLP 接收已启用，端口: {settings.HL7_PORT}")
        except Exception as e:
            logging.error(f"HL7 服务启动失败: {e}")

    yield

    if hl7_handler:
        await hl7_handler.stop()
    if settings.HL7_ENABLED:
        from app.hl7.server import get_mllp_server
        server = get_mllp_server()
        if server:
            await server.stop()

    logging.info("服务关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="报告AI解读系统 - 基于安诊儿医疗大模型",
    lifespan=lifespan,
)

# 确保 JSON 等文本类响应带 charset=utf-8，避免中文乱码
class CharsetUTF8Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        ct = response.headers.get("content-type") or ""
        if "application/json" in ct and "charset=" not in ct:
            response.headers["content-type"] = ct.rstrip("; ") + "; charset=utf-8"
        elif "text/" in ct and "charset=" not in ct:
            response.headers["content-type"] = ct.rstrip("; ") + "; charset=utf-8"
        return response


app.add_middleware(CharsetUTF8Middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(report_router)
app.include_router(system_router)
app.include_router(ocr_router)
app.include_router(hl7_router)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "hospital": settings.HOSPITAL_NAME,
        "lis_adapter": settings.LIS_ADAPTER,
        "hl7_enabled": settings.HL7_ENABLED,
        "docs": "/docs",
    }
