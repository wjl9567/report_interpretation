"""PaddleOCR 服务封装

支持两种调用方式：
1. PaddleOCR Serving（HTTP API）—— 默认方式，适合已部署 PaddleServing 的场景
2. PaddleOCR 本地调用 —— 备选，直接加载模型推理

扩展：
3. PDF -> 图片 -> OCR -> 结构化文本的完整管线
"""

import base64
import io
import logging
import re
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings
from app.schemas.report import ReportData, ReportItem, PatientInfo

logger = logging.getLogger(__name__)


class OCRService:
    """OCR 识别服务"""

    def __init__(self):
        self.service_url = settings.OCR_SERVICE_URL
        self.timeout = settings.OCR_TIMEOUT

    async def recognize_image(self, image_path: str) -> str:
        """识别图片中的文字，返回纯文本"""
        image_bytes = Path(image_path).read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        try:
            result = await self._call_paddle_serving(image_b64)
            return result
        except Exception as e:
            logger.warning(f"PaddleOCR Serving 调用失败: {e}，尝试本地推理")
            return await self._call_local_ocr(image_path)

    async def recognize_bytes(self, image_bytes: bytes) -> str:
        """直接从字节流识别"""
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        try:
            result = await self._call_paddle_serving(image_b64)
            return result
        except Exception as e:
            logger.warning(f"PaddleOCR Serving 调用失败: {e}，尝试本地推理")
            return await self._call_local_ocr_bytes(image_bytes)

    # ---- PDF 解析管线 ----

    async def parse_pdf_report(self, pdf_bytes: bytes) -> Optional[ReportData]:
        """PDF -> 逐页图片 -> OCR -> 合并文本 -> 尝试结构化

        使用 pymupdf (fitz) 将 PDF 每页渲染为图片，依次 OCR。
        """
        pages_text = await self._pdf_to_text(pdf_bytes)
        if not pages_text:
            return None

        full_text = "\n".join(pages_text)
        report = self._try_structured_parse(full_text)
        if report:
            return report

        return ReportData(
            report_no="",
            patient=PatientInfo(patient_id="", name=""),
            raw_text=full_text,
        )

    async def _pdf_to_text(self, pdf_bytes: bytes) -> list[str]:
        """PDF -> 逐页 OCR -> 文本列表"""
        try:
            import fitz  # pymupdf
        except ImportError:
            logger.error("pymupdf 未安装，无法解析 PDF")
            return []

        pages_text = []
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                text = await self.recognize_bytes(img_bytes)
                if text:
                    pages_text.append(text)
            doc.close()
        except Exception as e:
            logger.error(f"PDF 解析异常: {e}")
        return pages_text

    @staticmethod
    def _try_structured_parse(text: str) -> Optional[ReportData]:
        """尝试从 OCR 文本中提取结构化检验数据

        适用于检验报告的常见格式（表格型），
        影像/心电等描述性报告不做结构化提取，直接返回原文。
        """
        lines = text.strip().split("\n")
        items: list[ReportItem] = []
        patient_name = ""
        patient_id = ""
        report_title = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            name_match = re.search(r"姓\s*名[：:]\s*(\S+)", line)
            if name_match:
                patient_name = name_match.group(1)
                continue

            id_match = re.search(r"(住院号|门诊号|病案号)[：:]\s*(\S+)", line)
            if id_match:
                patient_id = id_match.group(2)
                continue

            title_match = re.search(r"报告(名称|标题)[：:]\s*(.+)", line)
            if title_match:
                report_title = title_match.group(2).strip()
                continue

            item = _try_parse_lab_line(line)
            if item:
                items.append(item)

        if len(items) < 2:
            return None

        return ReportData(
            report_no="",
            patient=PatientInfo(patient_id=patient_id, name=patient_name),
            report_title=report_title,
            items=items,
            raw_text=text,
        )

    # ---- PaddleOCR HTTP ----

    async def _call_paddle_serving(self, image_b64: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.service_url}/predict/ocr_system",
                json={"images": [image_b64]},
            )

            if resp.status_code == 200:
                data = resp.json()
                return self._parse_paddle_hub_response(data)

            resp = await client.post(
                f"{self.service_url}/ocr",
                json={"image": image_b64},
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse_generic_response(data)

    @staticmethod
    def _parse_paddle_hub_response(data: dict) -> str:
        lines = []
        results = data.get("results", [])
        if isinstance(results, list):
            for result in results:
                if isinstance(result, dict):
                    for item in result.get("data", []):
                        text = item.get("text", "")
                        if text:
                            lines.append(text)
                elif isinstance(result, list):
                    for item in result:
                        if isinstance(item, dict):
                            lines.append(item.get("text", ""))
                        elif isinstance(item, (list, tuple)) and len(item) >= 2:
                            lines.append(str(item[1][0]) if isinstance(item[1], (list, tuple)) else str(item[1]))
        return "\n".join(lines)

    @staticmethod
    def _parse_generic_response(data: dict) -> str:
        if "text" in data:
            return data["text"] if isinstance(data["text"], str) else "\n".join(data["text"])
        if "result" in data:
            result = data["result"]
            if isinstance(result, str):
                return result
            if isinstance(result, list):
                return "\n".join(str(r) for r in result)
        return str(data)

    # ---- 本地 PaddleOCR ----

    async def _call_local_ocr(self, image_path: str) -> str:
        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            result = ocr.ocr(image_path, cls=True)
            lines = []
            if result:
                for line_group in result:
                    if line_group:
                        for line in line_group:
                            if line and len(line) >= 2:
                                lines.append(line[1][0])
            return "\n".join(lines)
        except ImportError:
            logger.error("PaddleOCR 未安装，无法进行本地推理")
            raise RuntimeError("OCR 服务不可用：PaddleOCR Serving 无法连接，本地 PaddleOCR 未安装")

    async def _call_local_ocr_bytes(self, image_bytes: bytes) -> str:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(image_bytes)
            temp_path = f.name
        try:
            return await self._call_local_ocr(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{self.service_url}/")
                return resp.status_code < 500
        except Exception:
            return False


def _try_parse_lab_line(line: str) -> Optional[ReportItem]:
    """尝试解析检验报告中的单行数据

    常见格式：
    - 谷丙转氨酶(ALT)  85  U/L  9-50  ↑
    - WBC 白细胞  5.6  10^9/L  3.5-9.5
    """
    pattern = re.compile(
        r"^(.+?)\s+"
        r"([\d.]+)\s+"
        r"(\S+)\s+"
        r"([\d.]+\s*[-~]\s*[\d.]+)\s*"
        r"([↑↓HLhl]*)?"
    )
    m = pattern.match(line)
    if not m:
        return None

    name = m.group(1).strip()
    value = m.group(2).strip()
    unit = m.group(3).strip()
    ref = m.group(4).strip()
    flag = (m.group(5) or "").strip()

    if len(name) < 1 or len(name) > 30:
        return None

    return ReportItem(
        name=name,
        value=value,
        unit=unit,
        reference_range=ref,
        abnormal_flag=flag,
        abnormal_level="normal" if not flag else "mild",
    )


ocr_service = OCRService()
