"""FastAPI 主入口"""

import logging
from contextlib import asynccontextmanager

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
    logging.info(f"vLLM 地址: {settings.VLLM_BASE_URL}")
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
