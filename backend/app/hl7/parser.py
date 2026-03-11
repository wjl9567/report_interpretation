"""HL7 v2.x 消息解析器

支持解析 ORU^R01（检验结果）消息，字段映射由 YAML 配置驱动。
使用 hl7apy 做消息结构解析，退化为手动分隔符解析作为 fallback。
"""

import logging
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional

import yaml

from app.schemas.report import ReportData, ReportItem, PatientInfo

logger = logging.getLogger(__name__)


class HL7Parser:
    """HL7 消息解析器 — 配置驱动"""

    def __init__(self, config_path: str = "config/hl7_field_mapping.yaml"):
        self._config: dict = {}
        self._load_config(config_path)

    def _load_config(self, config_path: str):
        path = Path(config_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / config_path
        if not path.exists():
            logger.warning(f"HL7 字段映射配置不存在: {path}，使用默认值")
            self._config = self._default_config()
            return
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        self._config = raw.get("hl7", raw)

    @staticmethod
    def _default_config() -> dict:
        return {
            "field_mapping": {
                "patient": {
                    "patient_id": "PID.3.1",
                    "name": "PID.5.1",
                    "gender": "PID.8",
                    "date_of_birth": "PID.7",
                    "department": "PV1.3.1",
                },
                "report": {
                    "report_no": "OBR.3.1",
                    "report_title": "OBR.4.2",
                    "report_date": "OBR.7",
                },
                "item": {
                    "name": "OBX.3.2",
                    "value": "OBX.5",
                    "unit": "OBX.6.1",
                    "reference_range": "OBX.7",
                    "abnormal_flag": "OBX.8",
                },
            },
            "gender_map": {"M": "男", "F": "女", "O": "其他", "U": "未知"},
            "date_format": "%Y%m%d%H%M%S",
        }

    @property
    def supported_types(self) -> list[str]:
        return self._config.get("message_types", ["ORU^R01"])

    def parse(self, raw_message: str) -> Optional[ReportData]:
        """解析 HL7 原始消息为 ReportData"""
        try:
            return self._parse_with_hl7apy(raw_message)
        except Exception as e:
            logger.debug(f"hl7apy 解析失败，降级为手动解析: {e}")
            return self._parse_manual(raw_message)

    # ---- hl7apy 解析 ----

    def _parse_with_hl7apy(self, raw_message: str) -> ReportData:
        from hl7apy.parser import parse_message
        msg = parse_message(raw_message, find_groups=False)

        msg_type = self._get_hl7apy_field(msg, "MSH.9")
        if msg_type and "^" in str(msg_type):
            type_code = str(msg_type).replace("^", "^")
            if type_code not in self.supported_types and type_code.split("^")[0] not in ("ORU",):
                logger.warning(f"不支持的 HL7 消息类型: {type_code}")

        mapping = self._config.get("field_mapping", {})

        patient = self._extract_patient_hl7apy(msg, mapping.get("patient", {}))
        report_no, report_title, report_date = self._extract_report_hl7apy(msg, mapping.get("report", {}))
        items = self._extract_items_hl7apy(msg, mapping.get("item", {}))

        return ReportData(
            report_no=report_no,
            patient=patient,
            report_title=report_title,
            report_date=report_date,
            items=items,
        )

    def _extract_patient_hl7apy(self, msg, mapping: dict) -> PatientInfo:
        patient_id = str(self._get_hl7apy_field(msg, mapping.get("patient_id", "PID.3.1")) or "")
        name = str(self._get_hl7apy_field(msg, mapping.get("name", "PID.5.1")) or "")
        gender_raw = str(self._get_hl7apy_field(msg, mapping.get("gender", "PID.8")) or "")
        dob_raw = str(self._get_hl7apy_field(msg, mapping.get("date_of_birth", "PID.7")) or "")
        department = str(self._get_hl7apy_field(msg, mapping.get("department", "PV1.3.1")) or "")

        gender_map = self._config.get("gender_map", {})
        gender = gender_map.get(gender_raw, gender_raw)
        age = self._calculate_age(dob_raw)

        return PatientInfo(
            patient_id=patient_id,
            name=name,
            gender=gender,
            age=age,
            department=department,
        )

    def _extract_report_hl7apy(self, msg, mapping: dict) -> tuple[str, str, Optional[datetime]]:
        report_no = str(self._get_hl7apy_field(msg, mapping.get("report_no", "OBR.3.1")) or "")
        report_title = str(self._get_hl7apy_field(msg, mapping.get("report_title", "OBR.4.2")) or "")
        report_date_raw = str(self._get_hl7apy_field(msg, mapping.get("report_date", "OBR.7")) or "")
        report_date = self._parse_hl7_date(report_date_raw)
        return report_no, report_title, report_date

    def _extract_items_hl7apy(self, msg, mapping: dict) -> list[ReportItem]:
        items = []
        name_path = mapping.get("name", "OBX.3.2")
        value_path = mapping.get("value", "OBX.5")
        unit_path = mapping.get("unit", "OBX.6.1")
        ref_path = mapping.get("reference_range", "OBX.7")
        flag_path = mapping.get("abnormal_flag", "OBX.8")

        try:
            obx_segments = [s for s in msg.children if s.name == "OBX"]
        except Exception:
            obx_segments = []

        for obx in obx_segments:
            name = str(self._get_segment_field(obx, name_path) or "")
            value = str(self._get_segment_field(obx, value_path) or "")
            unit = str(self._get_segment_field(obx, unit_path) or "")
            ref = str(self._get_segment_field(obx, ref_path) or "")
            flag = str(self._get_segment_field(obx, flag_path) or "")

            if name or value:
                items.append(ReportItem(
                    name=name,
                    value=value,
                    unit=unit,
                    reference_range=ref,
                    abnormal_flag=flag,
                    abnormal_level="normal" if not flag or flag in ("N", "") else "mild",
                ))
        return items

    @staticmethod
    def _get_hl7apy_field(msg, path: str) -> Any:
        """从 hl7apy 消息对象按路径取值，如 PID.3.1"""
        try:
            parts = path.split(".")
            current = msg
            for part in parts:
                if hasattr(current, part.lower()):
                    current = getattr(current, part.lower())
                elif hasattr(current, part):
                    current = getattr(current, part)
                else:
                    children = [c for c in current.children if c.name == part]
                    if children:
                        current = children[0]
                    else:
                        return None
            return current.value if hasattr(current, "value") else str(current)
        except Exception:
            return None

    @staticmethod
    def _get_segment_field(segment, path: str) -> Any:
        """从单个 OBX 段按字段路径取值（路径去掉段名部分）"""
        try:
            parts = path.split(".")
            field_parts = parts[1:] if len(parts) > 1 else parts
            current = segment
            for part in field_parts:
                if hasattr(current, part.lower()):
                    current = getattr(current, part.lower())
                elif hasattr(current, part):
                    current = getattr(current, part)
                else:
                    try:
                        idx = int(part) - 1
                        current = current.children[idx]
                    except (ValueError, IndexError):
                        return None
            return current.value if hasattr(current, "value") else str(current)
        except Exception:
            return None

    # ---- 手动分隔符解析（fallback） ----

    def _parse_manual(self, raw_message: str) -> Optional[ReportData]:
        """不依赖 hl7apy 的手动解析"""
        segments = {}
        obx_list = []
        for line in raw_message.replace("\n", "\r").split("\r"):
            line = line.strip()
            if not line:
                continue
            seg_name = line[:3]
            if seg_name == "OBX":
                obx_list.append(line)
            else:
                segments[seg_name] = line

        mapping = self._config.get("field_mapping", {})

        patient = self._extract_patient_manual(segments, mapping.get("patient", {}))
        report_no, report_title, report_date = self._extract_report_manual(
            segments, mapping.get("report", {})
        )
        items = self._extract_items_manual(obx_list, mapping.get("item", {}))

        return ReportData(
            report_no=report_no,
            patient=patient,
            report_title=report_title,
            report_date=report_date,
            items=items,
        )

    def _extract_patient_manual(self, segments: dict, mapping: dict) -> PatientInfo:
        pid_fields = self._split_segment(segments.get("PID", ""))
        pv1_fields = self._split_segment(segments.get("PV1", ""))

        patient_id = self._get_manual_field(mapping.get("patient_id", "PID.3.1"), pid_fields, pv1_fields)
        name = self._get_manual_field(mapping.get("name", "PID.5.1"), pid_fields, pv1_fields)
        gender_raw = self._get_manual_field(mapping.get("gender", "PID.8"), pid_fields, pv1_fields)
        dob_raw = self._get_manual_field(mapping.get("date_of_birth", "PID.7"), pid_fields, pv1_fields)
        department = self._get_manual_field(mapping.get("department", "PV1.3.1"), pid_fields, pv1_fields)

        gender_map = self._config.get("gender_map", {})
        gender = gender_map.get(gender_raw, gender_raw)
        age = self._calculate_age(dob_raw)

        return PatientInfo(
            patient_id=patient_id,
            name=name,
            gender=gender,
            age=age,
            department=department,
        )

    def _extract_report_manual(self, segments: dict, mapping: dict) -> tuple[str, str, Optional[datetime]]:
        obr_fields = self._split_segment(segments.get("OBR", ""))
        pv1_fields = self._split_segment(segments.get("PV1", ""))

        report_no = self._get_manual_field(mapping.get("report_no", "OBR.3.1"), obr_fields, pv1_fields)
        report_title = self._get_manual_field(mapping.get("report_title", "OBR.4.2"), obr_fields, pv1_fields)
        report_date_raw = self._get_manual_field(mapping.get("report_date", "OBR.7"), obr_fields, pv1_fields)
        report_date = self._parse_hl7_date(report_date_raw)
        return report_no, report_title, report_date

    def _extract_items_manual(self, obx_lines: list[str], mapping: dict) -> list[ReportItem]:
        items = []
        for line in obx_lines:
            fields = self._split_segment(line)
            name = self._get_obx_field(mapping.get("name", "OBX.3.2"), fields)
            value = self._get_obx_field(mapping.get("value", "OBX.5"), fields)
            unit = self._get_obx_field(mapping.get("unit", "OBX.6.1"), fields)
            ref = self._get_obx_field(mapping.get("reference_range", "OBX.7"), fields)
            flag = self._get_obx_field(mapping.get("abnormal_flag", "OBX.8"), fields)

            if name or value:
                items.append(ReportItem(
                    name=name,
                    value=value,
                    unit=unit,
                    reference_range=ref,
                    abnormal_flag=flag,
                    abnormal_level="normal" if not flag or flag in ("N", "") else "mild",
                ))
        return items

    @staticmethod
    def _split_segment(segment_line: str) -> list[str]:
        if not segment_line:
            return []
        return segment_line.split("|")

    @staticmethod
    def _get_manual_field(path: str, pid_fields: list[str], pv1_fields: list[str]) -> str:
        """按 SEG.field.component 路径从手动分割的字段中取值"""
        parts = path.split(".")
        seg = parts[0] if parts else ""
        field_idx = int(parts[1]) if len(parts) > 1 else 0
        comp_idx = int(parts[2]) - 1 if len(parts) > 2 else 0

        if seg == "PID":
            fields = pid_fields
        elif seg in ("PV1", "OBR"):
            fields = pv1_fields
        else:
            return ""

        if field_idx >= len(fields):
            return ""
        field_val = fields[field_idx]
        components = field_val.split("^")
        if comp_idx < len(components):
            return components[comp_idx]
        return field_val

    @staticmethod
    def _get_obx_field(path: str, fields: list[str]) -> str:
        parts = path.split(".")
        field_idx = int(parts[1]) if len(parts) > 1 else 0
        comp_idx = int(parts[2]) - 1 if len(parts) > 2 else 0

        if field_idx >= len(fields):
            return ""
        field_val = fields[field_idx]
        components = field_val.split("^")
        if comp_idx < len(components):
            return components[comp_idx]
        return field_val

    # ---- 工具方法 ----

    def _parse_hl7_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        date_str = date_str.strip()
        fmt = self._config.get("date_format", "%Y%m%d%H%M%S")
        for f in [fmt, "%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d"]:
            try:
                return datetime.strptime(date_str[:len(f.replace("%", ""))], f)
            except (ValueError, IndexError):
                continue
        return None

    @staticmethod
    def _calculate_age(dob_str: str) -> Optional[int]:
        if not dob_str or len(dob_str) < 8:
            return None
        try:
            dob = datetime.strptime(dob_str[:8], "%Y%m%d").date()
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            return age if age >= 0 else None
        except ValueError:
            return None
