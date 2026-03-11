"""图片上传与OCR解读 API"""

import os
import uuid
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.core.config import settings
from app.services.ocr_service import ocr_service
from app.services.llm_service import llm_service
from app.prompts.templates import get_system_prompt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ocr", tags=["图片上传解读"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
MAX_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/interpret", summary="上传报告图片进行AI解读")
async def upload_and_interpret(
    file: UploadFile = File(..., description="报告图片（JPG/PNG）"),
    department_code: str = Form(default="general", description="科室编码"),
    report_type: str = Form(default="lab", description="报告类型：lab/ultrasound/ecg/eeg/pulmonary/ct/xray/mri"),
    patient_name: str = Form(default="", description="患者姓名（可选）"),
    patient_age: str = Form(default="", description="患者年龄（可选）"),
    patient_gender: str = Form(default="", description="患者性别（可选）"),
):
    """上传外院报告图片 → OCR识别 → AI解读

    支持 JPG/PNG/BMP/TIFF 格式，单张图片最大10MB。
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，请上传 JPG/PNG/BMP/TIFF 图片"
        )

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制（最大 {settings.MAX_UPLOAD_SIZE_MB}MB）"
        )

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = upload_dir / filename

    try:
        file_path.write_bytes(content)
    except Exception as e:
        logger.error(f"保存上传文件失败: {e}")
        raise HTTPException(status_code=500, detail="文件保存失败")

    # OCR 识别
    try:
        ocr_text = await ocr_service.recognize_bytes(content)
    except Exception as e:
        logger.error(f"OCR 识别失败: {e}")
        raise HTTPException(status_code=500, detail=f"OCR识别失败: {str(e)}")

    if not ocr_text or len(ocr_text.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="OCR识别结果为空或内容过少，请检查图片是否清晰、是否为检验报告"
        )

    # 拼接患者信息（如果提供）
    patient_context = ""
    if patient_name or patient_age or patient_gender:
        parts = []
        if patient_name:
            parts.append(f"姓名: {patient_name}")
        if patient_gender:
            parts.append(f"性别: {patient_gender}")
        if patient_age:
            parts.append(f"年龄: {patient_age}岁")
        patient_context = f"患者信息：{'，'.join(parts)}\n\n"

    # AI 解读
    system_prompt = get_system_prompt(department_code, report_type=report_type) + """

## 特别说明
以下报告内容来自OCR识别（外院报告拍照），可能存在识别误差。
如发现明显的数值或单位异常，请标注"可能为OCR识别误差，建议核对原始报告"。"""

    user_message = f"""{patient_context}以下是通过OCR识别的检验报告内容：

{ocr_text}"""

    try:
        import time
        start = time.time()
        llm_resp = await llm_service.chat(
            system_prompt=system_prompt,
            user_message=user_message,
        )
        latency_ms = int((time.time() - start) * 1000)
    except Exception as e:
        logger.error(f"AI 解读失败: {e}")
        raise HTTPException(status_code=500, detail=f"AI解读服务异常: {str(e)}")

    return {
        "ocr_text": ocr_text,
        "interpretation": llm_resp.content,
        "model_name": llm_resp.model,
        "prompt_tokens": llm_resp.prompt_tokens,
        "completion_tokens": llm_resp.completion_tokens,
        "latency_ms": latency_ms,
        "file_name": filename,
        "department_code": department_code,
        "disclaimer": "本解读结果由AI辅助生成，仅供临床参考，不替代医生诊断。报告内容来自OCR识别，可能存在识别误差，请以原始报告为准。",
    }


@router.post("/recognize", summary="仅OCR识别（不解读）")
async def upload_and_recognize(
    file: UploadFile = File(..., description="报告图片"),
):
    """仅进行OCR识别，返回识别文本，不触发AI解读"""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail=f"文件超过 {settings.MAX_UPLOAD_SIZE_MB}MB 限制")

    try:
        ocr_text = await ocr_service.recognize_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR识别失败: {str(e)}")

    return {"ocr_text": ocr_text}
