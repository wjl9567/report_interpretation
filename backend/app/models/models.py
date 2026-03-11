"""数据库模型定义"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime,
    Enum, JSON, ForeignKey, Boolean, Index
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class AbnormalLevel(str, enum.Enum):
    """异常等级"""
    CRITICAL = "critical"       # 危急值
    SEVERE = "severe"           # 重度异常
    MODERATE = "moderate"       # 中度异常
    MILD = "mild"               # 轻度异常
    NORMAL = "normal"           # 正常


class ReportType(str, enum.Enum):
    """报告类型"""
    LAB = "lab"                 # 检验报告
    ULTRASOUND = "ultrasound"   # B超
    ECG = "ecg"                 # 心电图
    EEG = "eeg"                 # 脑电图
    PULMONARY = "pulmonary"     # 肺功能
    CT = "ct"                   # CT
    XRAY = "xray"              # 放射/X光
    MRI = "mri"                 # 核磁共振
    PHYSICAL = "physical"       # 体检报告


class ReportSource(str, enum.Enum):
    """报告来源"""
    LIS_AUTO = "lis_auto"       # LIS自动拉取
    MANUAL_UPLOAD = "manual"    # 手动上传
    HL7_PUSH = "hl7_push"      # HL7推送


class Department(Base):
    """科室"""
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="科室名称")
    code = Column(String(50), unique=True, nullable=False, comment="科室编码")
    prompt_template = Column(String(50), default="default", comment="关联的Prompt模板名称")
    focus_indicators = Column(JSON, default=list, comment="重点关注指标列表")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class Patient(Base):
    """患者信息（脱敏存储）"""
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(50), unique=True, nullable=False, comment="住院号/门诊号")
    name = Column(String(50), comment="姓名（脱敏）")
    gender = Column(String(10), comment="性别")
    age = Column(Integer, comment="年龄")
    department_id = Column(Integer, ForeignKey("departments.id"), comment="所在科室")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    department = relationship("Department")
    reports = relationship("Report", back_populates="patient")

    __table_args__ = (
        Index("idx_patient_id", "patient_id"),
    )


class Report(Base):
    """检验报告"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_no = Column(String(100), unique=True, nullable=False, comment="报告编号")
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    report_type = Column(Enum(ReportType), default=ReportType.LAB, comment="报告类型")
    report_source = Column(Enum(ReportSource), default=ReportSource.LIS_AUTO, comment="来源")
    report_title = Column(String(200), comment="报告名称，如'生化全套'")
    report_date = Column(DateTime, comment="检查日期")
    items = Column(JSON, nullable=False, comment="检验项目列表（结构化）")
    raw_text = Column(Text, comment="原始报告文本")
    pdf_url = Column(String(500), comment="PDF报告路径")
    has_abnormal = Column(Boolean, default=False, comment="是否含异常项")
    has_critical = Column(Boolean, default=False, comment="是否含危急值")
    created_at = Column(DateTime, default=datetime.now)

    patient = relationship("Patient", back_populates="reports")
    interpretation = relationship("Interpretation", back_populates="report", uselist=False)

    __table_args__ = (
        Index("idx_report_no", "report_no"),
        Index("idx_report_patient", "patient_id"),
        Index("idx_report_date", "report_date"),
    )


class Interpretation(Base):
    """AI解读记录"""
    __tablename__ = "interpretations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey("reports.id"), unique=True, nullable=False)
    department_code = Column(String(50), comment="解读时的科室")
    abnormal_summary = Column(Text, comment="异常总结")
    clinical_significance = Column(Text, comment="临床意义")
    clinical_suggestion = Column(Text, comment="临床建议")
    full_response = Column(Text, comment="模型完整输出")
    abnormal_items = Column(JSON, comment="异常项结构化列表")
    confidence = Column(String(20), default="high", comment="可信度：high/medium/low")
    model_name = Column(String(100), comment="使用的模型名称")
    prompt_tokens = Column(Integer, comment="输入token数")
    completion_tokens = Column(Integer, comment="输出token数")
    latency_ms = Column(Integer, comment="推理耗时(毫秒)")
    created_at = Column(DateTime, default=datetime.now)

    report = relationship("Report", back_populates="interpretation")

    __table_args__ = (
        Index("idx_interp_report", "report_id"),
    )


class AuditLog(Base):
    """审计日志"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operator = Column(String(100), comment="操作人")
    action = Column(String(50), nullable=False, comment="操作类型")
    target_type = Column(String(50), comment="操作对象类型")
    target_id = Column(String(100), comment="操作对象ID")
    detail = Column(JSON, comment="操作详情")
    ip_address = Column(String(50), comment="操作IP")
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_audit_time", "created_at"),
        Index("idx_audit_operator", "operator"),
    )
