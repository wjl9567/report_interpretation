"""模拟数据适配器 - 开发和演示用

在未对接卫宁LIS之前，使用模拟数据进行开发和演示。
"""

from datetime import datetime

from app.adapters.base import BaseLISAdapter
from app.schemas.report import (
    ReportData, ReportListItem, PatientInfo, ReportItem
)


MOCK_PATIENTS = {
    "100001": PatientInfo(
        patient_id="100001", name="张*", gender="男", age=52, department="内科"
    ),
    "100002": PatientInfo(
        patient_id="100002", name="李*", gender="女", age=45, department="血液科"
    ),
    "100003": PatientInfo(
        patient_id="100003", name="王*", gender="男", age=68, department="呼吸科"
    ),
}

MOCK_REPORTS = {
    "RPT20260301001": ReportData(
        report_no="RPT20260301001",
        patient=MOCK_PATIENTS["100001"],
        report_title="生化全套",
        report_date=datetime(2026, 3, 1, 9, 30),
        items=[
            ReportItem(name="谷丙转氨酶(ALT)", value="85", unit="U/L", reference_range="9-50", abnormal_flag="↑", abnormal_level="moderate"),
            ReportItem(name="谷草转氨酶(AST)", value="62", unit="U/L", reference_range="15-40", abnormal_flag="↑", abnormal_level="mild"),
            ReportItem(name="总胆红素", value="22.5", unit="μmol/L", reference_range="5.1-19.0", abnormal_flag="↑", abnormal_level="mild"),
            ReportItem(name="空腹血糖", value="7.2", unit="mmol/L", reference_range="3.9-6.1", abnormal_flag="↑", abnormal_level="mild"),
            ReportItem(name="肌酐", value="78", unit="μmol/L", reference_range="57-111", abnormal_flag="", abnormal_level="normal"),
            ReportItem(name="尿素氮", value="5.8", unit="mmol/L", reference_range="3.1-8.0", abnormal_flag="", abnormal_level="normal"),
            ReportItem(name="总胆固醇", value="6.1", unit="mmol/L", reference_range="2.8-5.2", abnormal_flag="↑", abnormal_level="mild"),
            ReportItem(name="甘油三酯", value="2.8", unit="mmol/L", reference_range="0.56-1.7", abnormal_flag="↑", abnormal_level="moderate"),
            ReportItem(name="血钾", value="4.2", unit="mmol/L", reference_range="3.5-5.3", abnormal_flag="", abnormal_level="normal"),
            ReportItem(name="血钠", value="141", unit="mmol/L", reference_range="137-147", abnormal_flag="", abnormal_level="normal"),
        ],
    ),
    "RPT20260305001": ReportData(
        report_no="RPT20260305001",
        patient=MOCK_PATIENTS["100002"],
        report_title="血常规",
        report_date=datetime(2026, 3, 5, 10, 15),
        items=[
            ReportItem(name="白细胞(WBC)", value="2.1", unit="×10⁹/L", reference_range="3.5-9.5", abnormal_flag="↓", abnormal_level="severe"),
            ReportItem(name="红细胞(RBC)", value="2.8", unit="×10¹²/L", reference_range="4.3-5.8", abnormal_flag="↓", abnormal_level="severe"),
            ReportItem(name="血红蛋白(Hb)", value="68", unit="g/L", reference_range="130-175", abnormal_flag="↓", abnormal_level="severe"),
            ReportItem(name="血小板(PLT)", value="45", unit="×10⁹/L", reference_range="125-350", abnormal_flag="↓", abnormal_level="severe"),
            ReportItem(name="中性粒细胞比例", value="35.2", unit="%", reference_range="40-75", abnormal_flag="↓", abnormal_level="mild"),
            ReportItem(name="淋巴细胞比例", value="58.6", unit="%", reference_range="20-50", abnormal_flag="↑", abnormal_level="mild"),
            ReportItem(name="网织红细胞", value="0.3", unit="%", reference_range="0.5-1.5", abnormal_flag="↓", abnormal_level="mild"),
        ],
    ),
    "RPT20260308001": ReportData(
        report_no="RPT20260308001",
        patient=MOCK_PATIENTS["100003"],
        report_title="血气分析+感染标志物",
        report_date=datetime(2026, 3, 8, 8, 0),
        items=[
            ReportItem(name="pH", value="7.32", unit="", reference_range="7.35-7.45", abnormal_flag="↓", abnormal_level="moderate"),
            ReportItem(name="PaO₂", value="55", unit="mmHg", reference_range="80-100", abnormal_flag="↓", abnormal_level="severe"),
            ReportItem(name="PaCO₂", value="58", unit="mmHg", reference_range="35-45", abnormal_flag="↑", abnormal_level="moderate"),
            ReportItem(name="HCO₃⁻", value="28.5", unit="mmol/L", reference_range="22-27", abnormal_flag="↑", abnormal_level="mild"),
            ReportItem(name="乳酸", value="3.2", unit="mmol/L", reference_range="0.5-1.6", abnormal_flag="↑", abnormal_level="moderate"),
            ReportItem(name="C反应蛋白(CRP)", value="86", unit="mg/L", reference_range="0-8", abnormal_flag="↑", abnormal_level="severe"),
            ReportItem(name="降钙素原(PCT)", value="2.8", unit="ng/mL", reference_range="0-0.05", abnormal_flag="↑", abnormal_level="severe"),
            ReportItem(name="D-二聚体", value="1.85", unit="mg/L", reference_range="0-0.5", abnormal_flag="↑", abnormal_level="moderate"),
            ReportItem(name="白细胞(WBC)", value="15.6", unit="×10⁹/L", reference_range="3.5-9.5", abnormal_flag="↑", abnormal_level="moderate"),
        ],
    ),
}

PATIENT_REPORTS_MAP = {
    "100001": ["RPT20260301001"],
    "100002": ["RPT20260305001"],
    "100003": ["RPT20260308001"],
}


class MockLISAdapter(BaseLISAdapter):
    """模拟 LIS 适配器"""

    async def get_patient_reports(self, patient_id: str) -> list[ReportListItem]:
        report_nos = PATIENT_REPORTS_MAP.get(patient_id, [])
        results = []
        for rno in report_nos:
            report = MOCK_REPORTS.get(rno)
            if report:
                has_abnormal = any(i.abnormal_level != "normal" for i in report.items)
                has_critical = any(i.abnormal_level == "critical" for i in report.items)
                results.append(ReportListItem(
                    report_no=report.report_no,
                    report_title=report.report_title,
                    report_date=report.report_date,
                    has_abnormal=has_abnormal,
                    has_critical=has_critical,
                    has_interpretation=False,
                ))
        return results

    async def get_report_detail(self, patient_id: str, report_no: str) -> ReportData:
        report = MOCK_REPORTS.get(report_no)
        if not report:
            raise ValueError(f"未找到报告: {report_no}")
        return report

    async def get_latest_report(self, patient_id: str) -> ReportData:
        report_nos = PATIENT_REPORTS_MAP.get(patient_id, [])
        if not report_nos:
            raise ValueError(f"未找到患者 {patient_id} 的检验报告")
        return MOCK_REPORTS[report_nos[-1]]

    async def search_patient(self, keyword: str) -> list[PatientInfo]:
        results = []
        for pid, patient in MOCK_PATIENTS.items():
            if keyword in pid or keyword in patient.name:
                results.append(patient)
        return results
