"""卫宁健康 LIS 适配器

对接方式：
1. LisWebService.asmx（SOAP）：入参 HID（住院首页序号/门诊挂号序号），返回 XML 包 JSON，data[].FILEURL 为 PDF 地址
2. REST + FieldMapper：通用配置驱动（见 config/lis_field_mapping.yaml）
3. HL7 推送由 hl7 模块处理
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.adapters.base import BaseLISAdapter
from app.adapters.field_mapper import FieldMapper
from app.core.config import settings
from app.schemas.report import (
    ReportData, ReportListItem, PatientInfo, ReportItem
)

logger = logging.getLogger(__name__)


def _is_asmx() -> bool:
    return settings.LIS_USE_ASMX or (settings.LIS_API_BASE_URL or "").rstrip("/").endswith(".asmx")


def _parse_asmx_datetime(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip()[:19], fmt)
        except ValueError:
            continue
    return None


class WinningLISAdapter(BaseLISAdapter):
    """卫宁健康 LIS 适配器 — 支持 ASMX（HID + FILEURL）与 REST 配置驱动"""

    def __init__(self, field_mapper: FieldMapper):
        self.mapper = field_mapper
        self.base_url = (settings.LIS_API_BASE_URL or "").rstrip("/")
        self.timeout = 10

    def _get_client(self) -> httpx.AsyncClient:
        headers = self._build_auth_headers()
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
        )

    def _build_auth_headers(self) -> dict:
        auth = self.mapper.get_auth_config()
        auth_type = auth.get("type", "none")
        if auth_type == "bearer" and settings.LIS_API_KEY:
            return {auth.get("token_field", "Authorization"): f"Bearer {settings.LIS_API_KEY}"}
        if auth_type == "basic":
            import base64
            cred = base64.b64encode(
                f"{auth.get('basic_user', '')}:{auth.get('basic_pass', '')}".encode()
            ).decode()
            return {"Authorization": f"Basic {cred}"}
        if auth_type == "custom_header":
            name = auth.get("custom_header_name", "")
            value = auth.get("custom_header_value", "")
            return {name: value} if name else {}
        return {}

    @retry(
        stop=stop_after_attempt(settings.LIS_RETRY_COUNT),
        wait=wait_exponential(multiplier=settings.LIS_RETRY_DELAY, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _request(self, endpoint_name: str, **params) -> httpx.Response:
        """统一请求入口，自带重试"""
        if not self.base_url:
            raise ValueError("LIS_API_BASE_URL 未配置")
        method, path = self.mapper.get_request_config(endpoint_name)
        mapped_params = self.mapper.map_params(endpoint_name, **params)

        async with self._get_client() as client:
            if method.upper() == "POST":
                resp = await client.post(path, json=mapped_params)
            else:
                resp = await client.get(path, params=mapped_params)
            resp.raise_for_status()
            return resp

    # ---- 卫宁 ASMX（LisWebService.asmx）----

    async def _call_asmx(self, hid: str) -> list[dict]:
        """调用 ASMX：入参 HID，返回 data 数组（含 FILEURL、DOCUMENTNAME、REPORTNO 等）"""
        if not self.base_url:
            raise ValueError("LIS_API_BASE_URL 未配置，无法调用 ASMX")
        ns = settings.LIS_ASMX_NAMESPACE
        method = settings.LIS_ASMX_METHOD_NAME
        param_name = settings.LIS_ASMX_JSON_PARAM_NAME
        body = json.dumps({"HID": hid})
        envelope = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
            "<soap:Body>"
            f"<{method} xmlns=\"{ns}\">"
            f"<{param_name}>{body}</{param_name}>"
            f"</{method}>"
            "</soap:Body></soap:Envelope>"
        )
        async with self._get_client() as client:
            resp = await client.post(
                self.base_url,
                content=envelope,
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": f'"{ns}{method}"',
                },
            )
            resp.raise_for_status()
        text = resp.text
        match = re.search(r"<[^:>]*:?string[^>]*>([^<]*)</[^:>]*:?string>", text, re.DOTALL)
        if not match:
            raise ValueError("ASMX 响应中未找到 JSON 字符串")
        inner = match.group(1).strip()
        if "<?xml" in inner:
            inner = re.sub(r"<\?xml[^?]*\?>", "", inner).strip()
        data = json.loads(inner)
        if data.get("status") != "success":
            raise ValueError(data.get("desc", "ASMX 返回非 success"))
        return data.get("data") or []

    def _proxy_pdf_url(self, patient_id: str, report_no: str) -> str:
        return f"/api/v1/report/pdf?patient_id={patient_id}&report_no={report_no}"

    async def get_report_pdf_bytes(self, patient_id: str, report_no: str) -> bytes:
        """按 HID + 报告号取 PDF 字节流（供前端 /report/pdf 代理使用）"""
        items = await self._call_asmx(patient_id)
        for item in items:
            rno = item.get("REPORTNO") or item.get("FILEID") or ""
            if str(rno) == str(report_no):
                url = item.get("FILEURL")
                if not url:
                    raise ValueError(f"报告 {report_no} 无 FILEURL")
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.get(url)
                    r.raise_for_status()
                    return r.content
        raise ValueError(f"未找到报告: {report_no}")

    # ---- BaseLISAdapter 接口实现 ----

    async def get_patient_reports(self, patient_id: str) -> list[ReportListItem]:
        if _is_asmx():
            try:
                items = await self._call_asmx(patient_id)
                reports = []
                for item in items:
                    rno = item.get("REPORTNO") or item.get("FILEID") or ""
                    reports.append(ReportListItem(
                        report_no=str(rno),
                        report_title=item.get("DOCUMENTNAME", ""),
                        report_date=_parse_asmx_datetime(item.get("FILECREATEDATE")),
                        has_abnormal=False,
                        has_critical=False,
                        has_interpretation=False,
                        pdf_url=self._proxy_pdf_url(patient_id, rno),
                    ))
                return reports
            except Exception as e:
                logger.error(f"ASMX 获取报告列表失败: {e}")
                raise
        try:
            resp = await self._request("report_list", patient_id=patient_id)
            mapped = self.mapper.map_list(resp.json(), "report_list")

            reports = []
            for item in mapped:
                reports.append(ReportListItem(
                    report_no=item.get("report_no", ""),
                    report_title=item.get("report_title", ""),
                    report_date=item.get("report_date"),
                    has_abnormal=item.get("has_abnormal", False),
                    has_critical=item.get("has_critical", False),
                    has_interpretation=False,
                    pdf_url=item.get("pdf_url"),
                ))
            return reports
        except Exception as e:
            logger.error(f"获取患者报告列表失败: {e}")
            raise

    async def get_report_detail(self, patient_id: str, report_no: str) -> ReportData:
        if _is_asmx():
            try:
                items = await self._call_asmx(patient_id)
                for item in items:
                    rno = item.get("REPORTNO") or item.get("FILEID") or ""
                    if str(rno) != str(report_no):
                        continue
                    file_url = item.get("FILEURL")
                    patient = PatientInfo(patient_id=patient_id, name="")
                    report_date = _parse_asmx_datetime(item.get("FILECREATEDATE"))
                    raw_text = ""
                    if file_url:
                        async with httpx.AsyncClient(timeout=30) as c:
                            r = await c.get(file_url)
                            r.raise_for_status()
                            pdf_bytes = r.content
                        from app.services.ocr_service import ocr_service
                        parsed = await ocr_service.parse_pdf_report(pdf_bytes)
                        if parsed and parsed.raw_text:
                            raw_text = parsed.raw_text
                    return ReportData(
                        report_no=str(report_no),
                        patient=patient,
                        report_title=item.get("DOCUMENTNAME", ""),
                        report_date=report_date,
                        items=[],
                        raw_text=raw_text,
                        pdf_url=self._proxy_pdf_url(patient_id, report_no),
                    )
                raise ValueError(f"未找到报告: {report_no}")
            except ValueError:
                raise
            except Exception as e:
                logger.error(f"ASMX 获取报告详情失败: {e}")
                raise
        try:
            resp_type = self.mapper.get_response_type("report_detail")

            if resp_type == "pdf":
                return await self._get_report_from_pdf(report_no)

            resp = await self._request("report_detail", patient_id=patient_id, report_no=report_no)
            mapped = self.mapper.map_report_detail(resp.json(), "report_detail")
            return self._build_report_data(mapped)
        except Exception as e:
            logger.error(f"获取报告详情失败: {e}")
            raise

    async def get_latest_report(self, patient_id: str) -> ReportData:
        reports = await self.get_patient_reports(patient_id)
        if not reports:
            raise ValueError(f"未找到患者 {patient_id} 的报告")
        latest = sorted(reports, key=lambda r: r.report_date or datetime.min, reverse=True)[0]
        return await self.get_report_detail(patient_id, latest.report_no)

    async def search_patient(self, keyword: str) -> list[PatientInfo]:
        if _is_asmx():
            return [PatientInfo(patient_id=keyword, name="")]
        try:
            resp = await self._request("patient_search", keyword=keyword)
            mapped = self.mapper.map_list(resp.json(), "patient_search")

            patients = []
            for item in mapped:
                patients.append(PatientInfo(
                    patient_id=item.get("patient_id", ""),
                    name=self._desensitize_name(item.get("name", "")),
                    gender=item.get("gender", ""),
                    age=item.get("age"),
                    department=item.get("department", ""),
                ))
            return patients
        except Exception as e:
            logger.error(f"搜索患者失败: {e}")
            raise

    # ---- PDF 报告处理 ----

    async def _get_report_from_pdf(self, report_no: str) -> ReportData:
        """下载 PDF 并通过 OCR 解析"""
        from app.services.ocr_service import ocr_service

        resp = await self._request("report_pdf", report_no=report_no)
        pdf_bytes = resp.content

        report_data = await ocr_service.parse_pdf_report(pdf_bytes)
        if report_data:
            report_data.report_no = report_no
            return report_data

        text = await ocr_service.recognize_bytes(pdf_bytes)
        return ReportData(
            report_no=report_no,
            patient=PatientInfo(patient_id="", name=""),
            raw_text=text,
        )

    # ---- 数据构建 ----

    def _build_report_data(self, mapped: dict) -> ReportData:
        patient_data = mapped.get("patient", {})
        patient = PatientInfo(
            patient_id=patient_data.get("patient_id", ""),
            name=self._desensitize_name(patient_data.get("name", "")),
            gender=patient_data.get("gender", ""),
            age=patient_data.get("age"),
            department=patient_data.get("department", ""),
        )

        items = []
        for item_data in mapped.get("items", []):
            abnormal_flag = item_data.get("abnormal_flag", "")
            items.append(ReportItem(
                name=item_data.get("name", ""),
                value=str(item_data.get("value", "")),
                unit=item_data.get("unit", ""),
                reference_range=item_data.get("reference_range", ""),
                abnormal_flag=abnormal_flag,
                abnormal_level=self._classify_abnormal(
                    item_data.get("name", ""),
                    item_data.get("value"),
                    item_data.get("reference_range", ""),
                    abnormal_flag,
                ),
            ))

        return ReportData(
            report_no=mapped.get("report_no", ""),
            patient=patient,
            report_title=mapped.get("report_title", ""),
            report_date=mapped.get("report_date"),
            items=items,
        )

    @staticmethod
    def _desensitize_name(name: str) -> str:
        if not name:
            return ""
        if len(name) <= 1:
            return name
        return name[0] + "*" * (len(name) - 1)

    @staticmethod
    def _classify_abnormal(
        item_name: str,
        result,
        reference_range: str,
        abnormal_flag: str,
    ) -> str:
        """异常分级 — 基于规则引擎，不依赖 AI

        危急值标准参考《临床检验危急值管理专家共识》，
        实际使用时需根据各医院危急值标准配置。
        """
        CRITICAL_RULES = {
            "血钾": {"low": 2.5, "high": 6.5},
            "血钠": {"low": 115, "high": 160},
            "血糖": {"low": 2.2, "high": 33.3},
            "血小板": {"low": 30, "high": None},
            "白细胞": {"low": 1.0, "high": 30.0},
            "血红蛋白": {"low": 50, "high": None},
            "肌钙蛋白": {"low": None, "high": 0.5},
            "国际标准化比值": {"low": None, "high": 4.5},
        }

        if not abnormal_flag or abnormal_flag in ("正常", "N", ""):
            return "normal"

        try:
            val = float(result)
        except (TypeError, ValueError):
            return "mild"

        for key, thresholds in CRITICAL_RULES.items():
            if key in item_name:
                if thresholds.get("low") is not None and val < thresholds["low"]:
                    return "critical"
                if thresholds.get("high") is not None and val > thresholds["high"]:
                    return "critical"

        try:
            if "-" in reference_range:
                parts = reference_range.replace(" ", "").split("-")
                low_ref, high_ref = float(parts[0]), float(parts[1])
                mid = (low_ref + high_ref) / 2
                range_span = high_ref - low_ref
                if range_span > 0:
                    deviation = abs(val - mid) / range_span
                    if deviation > 2.0:
                        return "severe"
                    elif deviation > 1.0:
                        return "moderate"
        except (ValueError, IndexError):
            pass

        return "mild"
