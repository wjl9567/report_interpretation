"""MLLP TCP 异步服务器

实现 Minimum Lower Layer Protocol (MLLP) 接收 HL7 v2.x 消息。
协议格式：\x0b + HL7消息 + \x1c\x0d
接收后立即回复 ACK，消息放入异步队列后台处理。
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

MLLP_START = b"\x0b"
MLLP_END = b"\x1c\x0d"

# 全局统计
_stats = {
    "started_at": None,
    "total_received": 0,
    "total_processed": 0,
    "total_errors": 0,
    "last_message_at": None,
}


def get_hl7_stats() -> dict:
    return {**_stats}


class MLLPServer:
    """MLLP 协议异步 TCP 服务器"""

    def __init__(self, host: str = "0.0.0.0", port: int = 2575):
        self.host = host
        self.port = port
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle_connection, self.host, self.port
        )
        _stats["started_at"] = datetime.now().isoformat()
        logger.info(f"HL7 MLLP 服务器启动: {self.host}:{self.port}")

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("HL7 MLLP 服务器已停止")

    @property
    def is_running(self) -> bool:
        return self._server is not None and self._server.is_serving()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        addr = writer.get_extra_info("peername")
        logger.info(f"HL7 新连接: {addr}")
        try:
            while True:
                data = await asyncio.wait_for(reader.read(65536), timeout=60)
                if not data:
                    break
                messages = self._extract_messages(data)
                for raw_msg in messages:
                    _stats["total_received"] += 1
                    _stats["last_message_at"] = datetime.now().isoformat()
                    logger.debug(f"收到 HL7 消息 ({len(raw_msg)} bytes)")

                    ack = self._build_ack(raw_msg)
                    writer.write(MLLP_START + ack.encode(settings.HL7_ENCODING) + MLLP_END)
                    await writer.drain()

                    try:
                        self.queue.put_nowait(raw_msg)
                    except asyncio.QueueFull:
                        logger.warning("HL7 消息队列已满，丢弃消息")
                        _stats["total_errors"] += 1
        except asyncio.TimeoutError:
            logger.debug(f"HL7 连接超时: {addr}")
        except Exception as e:
            logger.error(f"HL7 连接处理异常: {e}")
            _stats["total_errors"] += 1
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    @staticmethod
    def _extract_messages(data: bytes) -> list[str]:
        """从原始 TCP 数据中提取 MLLP 帧中的 HL7 消息"""
        messages = []
        while MLLP_START in data and MLLP_END in data:
            start = data.index(MLLP_START) + len(MLLP_START)
            end = data.index(MLLP_END)
            if start < end:
                try:
                    msg = data[start:end].decode(settings.HL7_ENCODING)
                    messages.append(msg)
                except UnicodeDecodeError:
                    msg = data[start:end].decode("latin-1")
                    messages.append(msg)
            data = data[end + len(MLLP_END):]
        return messages

    @staticmethod
    def _build_ack(raw_msg: str) -> str:
        """构建 HL7 ACK 应答消息"""
        msg_ctrl_id = ""
        for line in raw_msg.split("\r"):
            if line.startswith("MSH"):
                fields = line.split("|")
                if len(fields) > 9:
                    msg_ctrl_id = fields[9]
                break

        now = datetime.now().strftime("%Y%m%d%H%M%S")
        ack = (
            f"MSH|^~\\&|REPORT_AI|HOSPITAL|WINNING|PLATFORM|{now}||ACK|{msg_ctrl_id}|P|2.4\r"
            f"MSA|AA|{msg_ctrl_id}\r"
        )
        return ack


mllp_server: Optional[MLLPServer] = None


def get_mllp_server() -> Optional[MLLPServer]:
    return mllp_server


def create_mllp_server() -> MLLPServer:
    global mllp_server
    mllp_server = MLLPServer(host="0.0.0.0", port=settings.HL7_PORT)
    return mllp_server
