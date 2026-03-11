"""HL7 管理 API"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.hl7.server import get_hl7_stats, get_mllp_server, MLLP_START, MLLP_END
from app.hl7.handler import get_recent_messages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/hl7", tags=["HL7 管理"])


@router.get("/status", summary="HL7 服务状态")
async def hl7_status():
    if not settings.HL7_ENABLED:
        return {"enabled": False, "message": "HL7 接收未启用"}

    server = get_mllp_server()
    stats = get_hl7_stats()
    return {
        "enabled": True,
        "running": server.is_running if server else False,
        "port": settings.HL7_PORT,
        "auto_interpret": settings.HL7_AUTO_INTERPRET,
        **stats,
    }


@router.get("/messages", summary="最近接收的 HL7 消息")
async def hl7_messages(limit: int = 50, offset: int = 0):
    if not settings.HL7_ENABLED:
        raise HTTPException(status_code=400, detail="HL7 接收未启用")
    messages = get_recent_messages(limit, offset)
    return {"data": messages, "total": len(messages)}


@router.post("/test", summary="发送测试 HL7 消息")
async def hl7_test():
    """构造一条 ORU^R01 测试消息并通过本地 TCP 发送，验证完整链路"""
    if not settings.HL7_ENABLED:
        raise HTTPException(status_code=400, detail="HL7 接收未启用")

    server = get_mllp_server()
    if not server or not server.is_running:
        raise HTTPException(status_code=503, detail="HL7 服务未运行")

    import asyncio
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    test_msg = (
        f"MSH|^~\\&|LIS|HOSPITAL|REPORT_AI|HOSPITAL|{now}||ORU^R01|TEST{now}|P|2.4\r"
        f"PID|||TEST001||测试患者^||19800101|M\r"
        f"PV1||I|内科\r"
        f"OBR||TEST_RPT_001||血常规|||{now}\r"
        f"OBX|1|NM|WBC^白细胞||5.6|10^9/L|3.5-9.5|N\r"
        f"OBX|2|NM|RBC^红细胞||4.5|10^12/L|4.3-5.8|N\r"
        f"OBX|3|NM|HGB^血红蛋白||135|g/L|130-175|N\r"
        f"OBX|4|NM|PLT^血小板||210|10^9/L|125-350|N\r"
    )

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", settings.HL7_PORT)
        writer.write(MLLP_START + test_msg.encode(settings.HL7_ENCODING) + MLLP_END)
        await writer.drain()

        ack_data = await asyncio.wait_for(reader.read(4096), timeout=5)
        writer.close()
        await writer.wait_closed()

        ack_text = ack_data.decode(settings.HL7_ENCODING, errors="replace")
        return {
            "success": True,
            "message": "测试消息已发送并收到 ACK",
            "ack": ack_text.replace("\r", "\n").strip(),
        }
    except Exception as e:
        logger.error(f"HL7 测试发送失败: {e}")
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")
