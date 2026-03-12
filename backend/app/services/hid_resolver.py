"""
根据 pat_num（病历号/门诊卡号）从 SQL Server 视图解析出 xh（HID）。
用于正式对接：EMR 传病历号/门诊卡号，本服务查 VW_BRJZXXK 得首页序号/挂号序号，再以 xh 调 LIS 获取报告。
视图若含 jlrq（记录日期：住院为入院日期，门诊为挂号日期），可配置 MSSQL_VIEW_REPORT_DAYS=7 或 14，
只取近一周或两周内的门急诊/住院记录对应的多个 xh，合并多 HID 报告列表。
"""

import asyncio
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _resolve_hid_sync(pat_num: str) -> Optional[str]:
    """同步查询 SQL Server：pat_num -> 单个 xh（TOP 1）。未配置或查询失败返回 None。"""
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
            sql = f"SELECT TOP 1 [{col_xh}] FROM [{view}] WHERE [{col_pat}] = %s ORDER BY [{col_xh}] DESC"
            with conn.cursor() as cur:
                cur.execute(sql, (pat_num,))
                row = cur.fetchone()
            return str(row[0]).strip() if row and row[0] is not None else None
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"HID 解析失败 pat_num={pat_num!r}: {e}")
        return None


def _resolve_hid_list_sync(pat_num: str, days: int) -> list[str]:
    """
    同步查询：pat_num -> 近 days 天内所有 xh（按 jlrq 倒序）。
    视图需含 jlrq 列（住院 rqrq/门诊 ghrq）。days<=0 时退化为单条逻辑。
    """
    if not settings.MSSQL_ENABLED or not settings.MSSQL_SERVER or not pat_num or not pat_num.strip():
        return []
    if days <= 0:
        single = _resolve_hid_sync(pat_num)
        return [single] if single else []
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
            col_jlrq = getattr(settings, "MSSQL_COLUMN_JLRQ", "jlrq") or "jlrq"
            # 只取 jlrq >= (当前 - days 天) 的记录，按 jlrq 倒序
            sql = (
                f"SELECT [{col_xh}] FROM [{view}] WHERE [{col_pat}] = %s "
                f"AND [{col_jlrq}] >= DATEADD(day, -%s, GETDATE()) ORDER BY [{col_jlrq}] DESC"
            )
            with conn.cursor() as cur:
                cur.execute(sql, (pat_num, days))
                rows = cur.fetchall()
            out = [str(r[0]).strip() for r in rows if r and r[0] is not None]
            return out
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"HID 列表解析失败 pat_num={pat_num!r} days={days}: {e}")
        return []


async def resolve_pat_num_to_hid(pat_num: str) -> Optional[str]:
    """
    根据病历号/门诊卡号解析出单个 HID（xh）。在事件循环中不阻塞。
    当 MSSQL_VIEW_REPORT_DAYS>0 时返回“近 N 天”内的第一条（最近一次入院/挂号）；否则 TOP 1。
    未启用 MSSQL 或未查到则返回 None，调用方应把传入的 patient_id 当作 HID 使用。
    """
    if not settings.MSSQL_ENABLED:
        return None
    days = getattr(settings, "MSSQL_VIEW_REPORT_DAYS", 0) or 0
    if days > 0:
        loop = asyncio.get_event_loop()
        hids = await loop.run_in_executor(None, _resolve_hid_list_sync, pat_num, days)
        return hids[0] if hids else None
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _resolve_hid_sync, pat_num)


async def resolve_pat_num_to_hid_list(pat_num: str) -> list[str]:
    """
    根据病历号/门诊卡号解析出 HID 列表。当 MSSQL_VIEW_REPORT_DAYS>0 时返回近 N 天内所有 xh（用于合并报告列表）；否则返回单条列表。
    """
    if not settings.MSSQL_ENABLED:
        return []
    days = getattr(settings, "MSSQL_VIEW_REPORT_DAYS", 0) or 0
    loop = asyncio.get_event_loop()
    hids = await loop.run_in_executor(None, _resolve_hid_list_sync, pat_num, days)
    if hids:
        return hids
    single = await resolve_pat_num_to_hid(pat_num)
    return [single] if single else []
