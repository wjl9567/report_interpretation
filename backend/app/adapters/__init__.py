"""LIS 数据适配器包 — 适配器工厂"""

import logging

from app.adapters.base import BaseLISAdapter
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_lis_adapter() -> BaseLISAdapter:
    """根据配置创建对应的 LIS 适配器实例"""
    adapter_type = settings.LIS_ADAPTER

    if adapter_type == "winning":
        from app.adapters.field_mapper import FieldMapper
        from app.adapters.winning import WinningLISAdapter
        mapper = FieldMapper(settings.LIS_FIELD_MAPPING_FILE)
        logger.info(f"使用卫宁健康 LIS 适配器，映射配置: {settings.LIS_FIELD_MAPPING_FILE}")
        return WinningLISAdapter(mapper)

    if adapter_type == "mock":
        from app.adapters.mock import MockLISAdapter
        logger.info("使用 Mock LIS 适配器（开发模式）")
        return MockLISAdapter()

    raise ValueError(f"未知的 LIS 适配器类型: {adapter_type}，可选: winning / mock")
