"""HL7 消息后台处理器

从 MLLP 服务器的异步队列中消费消息，执行：
1. HL7 解析 -> ReportData
2. 去重检查（按 report_no + message_control_id）
3. 持久化到数据库
4. 可选：自动触发 AI 解读
"""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.hl7.parser import HL7Parser
from app.hl7.server import MLLPServer, get_hl7_stats
from app.models.models import Patient, Report, ReportSource, ReportType
from app.schemas.report import ReportData

logger = logging.getLogger(__name__)

# LRU 去重缓存（内存级，最多保留 5000 条记录）
_dedup_cache: OrderedDict[str, datetime] = OrderedDict()
_DEDUP_MAX = 5000

# 最近处理的消息记录（供 API 查询）
_recent_messages: list[dict] = []
_RECENT_MAX = 100


def get_recent_messages(limit: int = 50, offset: int = 0) -> list[dict]:
    return _recent_messages[offset: offset + limit]


class HL7MessageHandler:
    """HL7 消息消费处理器"""

    def __init__(self, server: MLLPServer):
        self.server = server
        self.parser = HL7Parser(settings.HL7_FIELD_MAPPING_FILE)
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("HL7 消息处理器已启动")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("HL7 消息处理器已停止")

    async def _consume_loop(self):
        while self._running:
            try:
                raw_msg = await asyncio.wait_for(self.server.queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                await self._process_message(raw_msg)
                stats = get_hl7_stats()
                stats["total_processed"] = stats.get("total_processed", 0) + 1
            except Exception as e:
                logger.error(f"HL7 消息处理异常: {e}", exc_info=True)
                stats = get_hl7_stats()
                stats["total_errors"] = stats.get("total_errors", 0) + 1

    async def _process_message(self, raw_msg: str):
        msg_ctrl_id = self._extract_message_control_id(raw_msg)

        report_data = self.parser.parse(raw_msg)
        if not report_data:
            logger.warning(f"HL7 消息解析失败，message_control_id={msg_ctrl_id}")
            self._record_message(msg_ctrl_id, "parse_failed", None)
            return

        dedup_key = f"{report_data.report_no}:{msg_ctrl_id}"
        if self._is_duplicate(dedup_key):
            logger.debug(f"重复消息跳过: {dedup_key}")
            self._record_message(msg_ctrl_id, "duplicate", report_data.report_no)
            return

        await self._persist(report_data)
        self._record_message(msg_ctrl_id, "persisted", report_data.report_no)

        if settings.HL7_AUTO_INTERPRET:
            await self._auto_interpret(report_data)
            self._update_last_message_status("interpreted")

    async def _persist(self, report_data: ReportData):
        """将报告数据写入数据库"""
        async with async_session() as session:
            session: AsyncSession

            patient_db = await self._upsert_patient(session, report_data.patient)

            existing = await session.execute(
                select(Report).where(Report.report_no == report_data.report_no)
            )
            if existing.scalar_one_or_none():
                logger.debug(f"报告已存在: {report_data.report_no}，跳过入库")
                return

            report_type = self._guess_report_type(report_data.report_title)

            report = Report(
                report_no=report_data.report_no,
                patient_id=patient_db.id,
                report_type=report_type,
                report_source=ReportSource.HL7_PUSH,
                report_title=report_data.report_title,
                report_date=report_data.report_date,
                items=[item.model_dump() for item in report_data.items],
                raw_text=report_data.raw_text or "",
                has_abnormal=any(i.abnormal_level != "normal" for i in report_data.items),
                has_critical=any(i.abnormal_level == "critical" for i in report_data.items),
            )
            session.add(report)
            await session.commit()
            logger.info(f"HL7 报告入库: {report_data.report_no}")

    async def _upsert_patient(self, session: AsyncSession, patient_info) -> Patient:
        result = await session.execute(
            select(Patient).where(Patient.patient_id == patient_info.patient_id)
        )
        patient = result.scalar_one_or_none()
        if patient:
            patient.name = patient_info.name
            patient.gender = patient_info.gender
            patient.age = patient_info.age
            patient.updated_at = datetime.now()
        else:
            patient = Patient(
                patient_id=patient_info.patient_id,
                name=patient_info.name,
                gender=patient_info.gender,
                age=patient_info.age,
            )
            session.add(patient)
        await session.flush()
        return patient

    async def _auto_interpret(self, report_data: ReportData):
        """自动触发 AI 解读"""
        try:
            from app.services.interpretation import InterpretationService
            from app.adapters import get_lis_adapter

            service = InterpretationService(get_lis_adapter())
            report_type = self._guess_report_type(report_data.report_title)
            await service.interpret_report(
                report=report_data,
                department_code="general",
                report_type=report_type.value if hasattr(report_type, "value") else "lab",
            )
            logger.info(f"HL7 自动解读完成: {report_data.report_no}")
        except Exception as e:
            logger.error(f"HL7 自动解读失败: {e}")

    # ---- 去重 ----

    @staticmethod
    def _is_duplicate(key: str) -> bool:
        if key in _dedup_cache:
            return True
        _dedup_cache[key] = datetime.now()
        if len(_dedup_cache) > _DEDUP_MAX:
            _dedup_cache.popitem(last=False)
        return False

    @staticmethod
    def _extract_message_control_id(raw_msg: str) -> str:
        for line in raw_msg.split("\r"):
            if line.startswith("MSH"):
                fields = line.split("|")
                if len(fields) > 9:
                    return fields[9]
        return ""

    # ---- 消息记录 ----

    @staticmethod
    def _record_message(msg_ctrl_id: str, status: str, report_no: Optional[str]):
        record = {
            "message_control_id": msg_ctrl_id,
            "report_no": report_no or "",
            "status": status,
            "received_at": datetime.now().isoformat(),
        }
        _recent_messages.insert(0, record)
        if len(_recent_messages) > _RECENT_MAX:
            _recent_messages.pop()

    @staticmethod
    def _update_last_message_status(status: str):
        if _recent_messages:
            _recent_messages[0]["status"] = status

    @staticmethod
    def _guess_report_type(title: str) -> ReportType:
        """根据报告标题猜测报告类型"""
        title = title or ""
        mapping = {
            ReportType.ECG: ["心电", "ECG"],
            ReportType.EEG: ["脑电", "EEG"],
            ReportType.ULTRASOUND: ["B超", "超声", "彩超"],
            ReportType.CT: ["CT"],
            ReportType.MRI: ["核磁", "MRI", "磁共振"],
            ReportType.XRAY: ["X光", "放射", "DR", "CR"],
            ReportType.PULMONARY: ["肺功能"],
        }
        for rtype, keywords in mapping.items():
            for kw in keywords:
                if kw in title:
                    return rtype
        return ReportType.LAB
