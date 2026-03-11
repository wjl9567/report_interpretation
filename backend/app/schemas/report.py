"""Pydantic schemas - API 请求/响应数据模型"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ========== 检验项目 ==========

class ReportItem(BaseModel):
    """单个检验项目"""
    name: str = Field(..., description="项目名称，如'谷丙转氨酶(ALT)'")
    value: str = Field(..., description="结果数值")
    unit: str = Field("", description="单位")
    reference_range: str = Field("", description="参考范围")
    abnormal_flag: str = Field("", description="异常标记：H/L/↑/↓/正常")
    abnormal_level: str = Field("normal", description="异常等级：critical/severe/moderate/mild/normal")


# ========== 报告相关 ==========

class PatientInfo(BaseModel):
    """患者基本信息"""
    patient_id: str = Field(..., description="住院号/门诊号")
    name: str = Field("", description="姓名")
    gender: str = Field("", description="性别")
    age: Optional[int] = Field(None, description="年龄")
    department: str = Field("", description="科室")


class ReportData(BaseModel):
    """检验报告数据"""
    report_no: str = Field(..., description="报告编号")
    patient: PatientInfo
    report_title: str = Field("", description="报告名称")
    report_date: Optional[datetime] = Field(None, description="检查日期")
    items: list[ReportItem] = Field(default_factory=list, description="检验项目列表")
    raw_text: str = Field("", description="原始报告文本")
    pdf_url: Optional[str] = Field(None, description="报告 PDF 地址（或后端代理路径，供前端左侧展示）")


# ========== 解读请求/响应 ==========

class InterpretRequest(BaseModel):
    """解读请求 - 通过住院号+报告编号"""
    patient_id: str = Field(..., description="住院号/门诊号")
    report_no: Optional[str] = Field(None, description="报告编号，为空则返回最新报告")
    department_code: str = Field("general", description="医生所在科室编码")
    report_type: str = Field("lab", description="报告类型：lab/ultrasound/ecg/eeg/pulmonary/ct/xray/mri")


class InterpretDirectRequest(BaseModel):
    """直接解读请求 - 直接传入报告数据"""
    report: ReportData
    department_code: str = Field("general", description="医生所在科室编码")
    report_type: str = Field("lab", description="报告类型：lab/ultrasound/ecg/eeg/pulmonary/ct/xray/mri")


class AbnormalItemResult(BaseModel):
    """异常项解读结果"""
    name: str
    value: str
    unit: str
    reference_range: str
    abnormal_level: str
    level_label: str = Field("", description="等级中文标签")
    color: str = Field("", description="标注颜色")


class InterpretResponse(BaseModel):
    """解读响应"""
    report_no: str
    patient: PatientInfo
    report_title: str
    report_date: Optional[datetime]
    items: list[ReportItem]
    abnormal_items: list[AbnormalItemResult]
    abnormal_summary: str = Field("", description="异常总结")
    clinical_significance: str = Field("", description="临床意义")
    clinical_suggestion: str = Field("", description="临床建议")
    confidence: str = Field("high", description="可信度")
    model_name: str = Field("")
    latency_ms: int = Field(0)
    disclaimer: str = Field("本解读结果由AI辅助生成，仅供临床参考，不替代医生诊断。")


# ========== 报告列表 ==========

class ReportListItem(BaseModel):
    """报告列表项"""
    report_no: str
    report_title: str
    report_date: Optional[datetime]
    has_abnormal: bool = False
    has_critical: bool = False
    has_interpretation: bool = False
    pdf_url: Optional[str] = Field(None, description="报告 PDF 地址或代理路径")


class ReportListResponse(BaseModel):
    """报告列表响应"""
    patient: PatientInfo
    reports: list[ReportListItem]
    total: int
