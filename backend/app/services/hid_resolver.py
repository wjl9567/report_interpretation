"""
根据 pat_num（病历号/门诊卡号）从 SQL Server 视图解析出 xh（HID）。
用于正式对接：EMR 传病历号/门诊卡号，本服务查 VW_BRJZXXK 得首页序号/挂号序号，再以 xh 调 LIS 获取报告。
"""

import asyncio
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _resolve_hid_sync(pat_num: str) -> Optional[str]:
    """同步查询 SQL Server：pat_num -> xh。未配置或查询失败返回 None。"""
    if not settings.MSSQL_ENABLED or not settings.MSSQL_SERVER or not pat_num or not pat_num.strip():
        return None
    pat_num = pat_num.strip()
    try:
        import pymssql
        conn = pymssql.connect(
            server=settings.MSSQL_SERVER,
            user=settings.MSSQL_USER,
            password=settings.MSSQL_PASSWORD,
            database=settings.MSSQL_DATABASE,
        )
        try:
            view = settings.MSSQL_VIEW_HID
            col_pat = settings.MSSQL_COLUMN_PAT_NUM
            col_xh = settings.MSSQL_COLUMN_XH
            # 防止 SQL 注入：列名来自配置，不用户输入；pat_num 用参数化
            sql = f"SELECT TOP 1 [{col_xh}] FROM [{view}] WHERE [{col_pat}] = %s"
            with conn.cursor() as cur:
                cur.execute(sql, (pat_num,))
                row = cur.fetchone()
            return str(row[0]).strip() if row and row[0] is not None else None
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"HID 解析失败 pat_num={pat_num!r}: {e}")
        return None


async def resolve_pat_num_to_hid(pat_num: str) -> Optional[str]:
    """
    根据病历号/门诊卡号解析出 HID（xh）。在事件循环中不阻塞。
    未启用 MSSQL 或未查到则返回 None，调用方应把传入的 patient_id 当作 HID 使用。
    """
    if not settings.MSSQL_ENABLED:
        return None
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _resolve_hid_sync, pat_num)
