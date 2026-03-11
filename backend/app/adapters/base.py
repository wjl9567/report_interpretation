"""LIS 数据适配器基类 - 可插拔设计，支持多家EMR/LIS厂商"""

from abc import ABC, abstractmethod

from app.schemas.report import ReportData, ReportListItem, PatientInfo


class BaseLISAdapter(ABC):
    """LIS 数据适配器基类，每家医院实现自己的子类"""

    @abstractmethod
    async def get_patient_reports(self, patient_id: str) -> list[ReportListItem]:
        """根据住院号/门诊号获取患者的报告列表"""
        ...

    @abstractmethod
    async def get_report_detail(self, patient_id: str, report_no: str) -> ReportData:
        """获取某份报告的详细数据（结构化）"""
        ...

    @abstractmethod
    async def get_latest_report(self, patient_id: str) -> ReportData:
        """获取患者最新一份报告"""
        ...

    @abstractmethod
    async def search_patient(self, keyword: str) -> list[PatientInfo]:
        """搜索患者"""
        ...
