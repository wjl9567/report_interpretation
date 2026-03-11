"""可配置字段映射引擎

拿到 LIS 厂商接口文档后，只需修改 YAML 配置中的字段名，无需改代码。
支持：
- 嵌套路径提取（data.items.0.name）
- 批量字段重命名
- 日期字符串自动转换
- 布尔值归一化
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


class FieldMapper:
    """YAML 驱动的字段映射引擎"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self._config: dict = {}
        self._load()

    def _load(self):
        path = Path(self.config_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / self.config_path
        if not path.exists():
            logger.warning(f"字段映射配置不存在: {path}，使用空配置")
            self._config = {}
            return
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        for key, val in os.environ.items():
            raw = raw.replace(f"${{{key}}}", val)
        self._config = yaml.safe_load(raw) or {}

    def reload(self):
        self._load()

    @property
    def config(self) -> dict:
        return self._config

    @property
    def date_format(self) -> str:
        return self._config.get("date_format", "%Y-%m-%d %H:%M:%S")

    def get_endpoint_config(self, endpoint_name: str) -> dict:
        return self._config.get("endpoints", {}).get(endpoint_name, {})

    def get_auth_config(self) -> dict:
        return self._config.get("auth", {})

    # ---- 核心映射方法 ----

    @staticmethod
    def extract_by_path(data: dict, path: str) -> Any:
        """按点分路径从嵌套 dict 中提取值

        支持：data.items / data.items.0 / data.result.name
        """
        if not path:
            return data
        parts = path.split(".")
        current = data
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, (list, tuple)):
                try:
                    current = current[int(part)]
                except (IndexError, ValueError):
                    return None
            else:
                return None
        return current

    def map_list(
        self,
        raw_response: dict,
        endpoint_name: str,
    ) -> list[dict]:
        """将外部接口响应的列表数据映射为内部字段名

        Returns: list[dict] — 每个 dict 的 key 为内部字段名
        """
        ep = self.get_endpoint_config(endpoint_name)
        mapping = ep.get("response_mapping", {})
        data_root = mapping.get("data_root", "")
        fields = mapping.get("fields", {})

        raw_list = self.extract_by_path(raw_response, data_root)
        if not isinstance(raw_list, list):
            raw_list = [raw_list] if raw_list else []

        return [self._map_single(item, fields) for item in raw_list]

    def map_report_detail(self, raw_response: dict, endpoint_name: str = "report_detail") -> dict:
        """映射报告详情，包含患者信息 + 检验项目"""
        ep = self.get_endpoint_config(endpoint_name)
        mapping = ep.get("response_mapping", {})

        data_root = mapping.get("data_root", "")
        raw_data = self.extract_by_path(raw_response, data_root)
        if not raw_data:
            raw_data = raw_response

        patient_fields = mapping.get("patient_fields", {})
        patient = self._map_single(raw_data, patient_fields)

        items_root = mapping.get("items_root", "")
        item_fields = mapping.get("item_fields", {})
        raw_items = self.extract_by_path(raw_response, items_root)
        if not isinstance(raw_items, list):
            raw_items = []
        items = [self._map_single(item, item_fields) for item in raw_items]

        report_fields = mapping.get("fields", {})
        report = self._map_single(raw_data, report_fields) if report_fields else {}

        return {
            "patient": patient,
            "items": items,
            **report,
            **{k: v for k, v in raw_data.items() if k not in report and k not in patient_fields.values()},
        }

    def map_params(self, endpoint_name: str, **kwargs) -> dict:
        """将内部参数名映射为外部接口的参数名"""
        ep = self.get_endpoint_config(endpoint_name)
        param_mapping = ep.get("params", {})
        result = {}
        for internal_name, external_name in param_mapping.items():
            if internal_name in kwargs:
                result[external_name] = kwargs[internal_name]
        return result

    def get_request_config(self, endpoint_name: str) -> tuple[str, str]:
        """返回 (method, path)"""
        ep = self.get_endpoint_config(endpoint_name)
        return ep.get("method", "GET"), ep.get("path", "")

    def get_response_type(self, endpoint_name: str) -> str:
        ep = self.get_endpoint_config(endpoint_name)
        return ep.get("response_type", "json")

    # ---- 内部方法 ----

    def _map_single(self, raw_item: dict, fields: dict) -> dict:
        """单条记录的字段映射"""
        if not raw_item or not fields:
            return {}
        result = {}
        for internal_name, external_name in fields.items():
            val = raw_item.get(external_name)
            val = self._convert_value(internal_name, val)
            result[internal_name] = val
        return result

    def _convert_value(self, field_name: str, value: Any) -> Any:
        """根据字段名自动做类型转换"""
        if value is None:
            return value
        if "date" in field_name and isinstance(value, str):
            return self._parse_date(value)
        if field_name.startswith("has_") and not isinstance(value, bool):
            return self._to_bool(value)
        if field_name == "age" and not isinstance(value, int):
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        return value

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        for fmt in [self.date_format, "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y%m%d%H%M%S", "%Y-%m-%d"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        logger.warning(f"无法解析日期: {date_str}")
        return None

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "y", "是", "异常")
        if isinstance(value, (int, float)):
            return bool(value)
        return False
