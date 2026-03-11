"""Prompt 模板引擎

管理两个维度的模板：
1. 科室维度（血液科、内科、呼吸科等）—— 影响解读的关注侧重点
2. 报告类型维度（检验、B超、心电、CT、核磁等）—— 影响解读的专业方向

模板与代码分离，方便后续调优和按医院定制。
"""

import logging
from typing import Optional

from app.schemas.report import ReportData

logger = logging.getLogger(__name__)

# ===== 模板注册表 =====
DEPARTMENT_TEMPLATES: dict[str, dict] = {}
REPORT_TYPE_TEMPLATES: dict[str, dict] = {}


def register_department(code: str, name: str, focus: list[str]):
    def decorator(func):
        DEPARTMENT_TEMPLATES[code] = {"name": name, "focus": focus, "builder": func}
        return func
    return decorator


def register_report_type(code: str, name: str):
    def decorator(func):
        REPORT_TYPE_TEMPLATES[code] = {"name": name, "builder": func}
        return func
    return decorator


# ================================================================
# 基础 Prompt 模块
# ================================================================

OUTPUT_FORMAT = """
## 输出要求
请严格按以下三个模块输出，使用临床专业术语，简洁准确：

【异常发现】
汇总所有异常发现，按严重程度从高到低排列。

【临床意义】
逐项分析每个异常发现的临床意义，说明可能关联的疾病或病理状态。注意各项发现之间的关联性分析。

【临床建议】
给出针对性的后续检查或处置建议。紧急异常需特别标注。"""

CONSTRAINTS = """
## 约束条件
- 不得编造报告中不存在的内容或数值
- 不确定时明确表示"建议结合临床进一步判断"
- 不做确定性诊断，只做提示性分析
- 如有紧急异常，必须在异常发现中首先强调"""


def build_report_user_message(report: ReportData) -> str:
    """将报告数据转换为用户消息"""
    lines = []
    patient = report.patient
    lines.append(f"患者信息：{patient.name}，{patient.gender}，{patient.age}岁")
    if patient.department:
        lines.append(f"所在科室：{patient.department}")
    lines.append(f"报告名称：{report.report_title}")
    if report.report_date:
        lines.append(f"检查日期：{report.report_date.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    if report.items:
        lines.append("检查结果：")
        lines.append("-" * 60)
        for item in report.items:
            flag = f" {item.abnormal_flag}" if item.abnormal_flag else ""
            ref = f"(参考值: {item.reference_range})" if item.reference_range else ""
            lines.append(f"{item.name}: {item.value} {item.unit} {ref}{flag}")

    if report.raw_text:
        lines.append("")
        lines.append("报告原文：")
        lines.append("-" * 60)
        lines.append(report.raw_text)

    return "\n".join(lines)


def get_system_prompt(
    department_code: str = "general",
    report: Optional[ReportData] = None,
    report_type: str = "lab",
) -> str:
    """获取完整的 System Prompt

    优先级：报告类型模板 > 科室模板 > 通用模板
    最终 Prompt = 报告类型基础 + 科室专科补充
    """
    # 报告类型基础 Prompt
    rt = REPORT_TYPE_TEMPLATES.get(report_type)
    if rt:
        base = rt["builder"](report)
    else:
        base = _default_base_prompt()

    # 科室补充 Prompt
    dept = DEPARTMENT_TEMPLATES.get(department_code)
    if dept and department_code != "general":
        dept_extra = dept["builder"](report)
    else:
        dept_extra = ""

    return base + dept_extra


def _default_base_prompt() -> str:
    return f"你是一名资深临床医学专家，拥有丰富的临床经验。请对以下检查报告进行专业解读。{OUTPUT_FORMAT}{CONSTRAINTS}"


# ================================================================
# 报告类型模板
# ================================================================

@register_report_type("lab", "检验报告")
def lab_prompt(report=None):
    return f"""你是一名资深检验科主任医师，拥有丰富的临床检验经验。请对以下检验报告进行专业解读。
{OUTPUT_FORMAT}
{CONSTRAINTS}
- 如有危急值，必须在异常发现中首先强调并提示立即处理"""


@register_report_type("ultrasound", "B超报告")
def ultrasound_prompt(report=None):
    return f"""你是一名资深超声科主任医师，拥有丰富的超声诊断经验。请对以下B超/彩超报告进行专业解读。
{OUTPUT_FORMAT}

## 超声报告解读重点
- 关注器官大小、形态、回声是否正常
- 注意占位性病变的大小、边界、回声特征、血流信号，评估良恶性倾向
- 注意液性暗区（积液、囊肿）的位置和范围
- 注意血管管径、血流速度、阻力指数等血流动力学参数
- 对于结节/肿物，参考相应的分级标准（如甲状腺TI-RADS、乳腺BI-RADS、肝脏LI-RADS）
{CONSTRAINTS}"""


@register_report_type("ecg", "心电图报告")
def ecg_prompt(report=None):
    return f"""你是一名资深心电图诊断专家，拥有丰富的心电图判读经验。请对以下心电图报告进行专业解读。
{OUTPUT_FORMAT}

## 心电图解读重点
- 心率和节律：是否窦性心律，有无心律失常（房颤、房扑、室早、室速等）
- P波、PR间期、QRS波群、ST段、T波、QT间期的异常分析
- ST段改变的临床意义：抬高提示急性心肌梗死/心包炎，压低提示心肌缺血
- 传导阻滞：房室传导阻滞的分度及临床意义
- 心室肥厚：左室/右室肥厚的电压标准及临床意义
- 紧急异常（急性ST段抬高、致命性心律失常）必须首先强调
{CONSTRAINTS}"""


@register_report_type("eeg", "脑电图报告")
def eeg_prompt(report=None):
    return f"""你是一名资深神经电生理专家，拥有丰富的脑电图判读经验。请对以下脑电图报告进行专业解读。
{OUTPUT_FORMAT}

## 脑电图解读重点
- 背景活动：频率、波幅、对称性是否正常
- 异常放电：尖波、棘波、尖慢复合波、棘慢复合波等癫痫样放电的部位和特征
- 慢波活动：局灶性或弥漫性慢波的临床意义（局灶性病变、代谢性脑病等）
- 睡眠分期和睡眠结构是否正常
- 对于癫痫患者：发作间期和发作期放电特征，定位与分类
- 对于意识障碍患者：评估脑功能受损程度
{CONSTRAINTS}"""


@register_report_type("pulmonary", "肺功能报告")
def pulmonary_prompt(report=None):
    return f"""你是一名资深呼吸科主任医师，拥有丰富的肺功能检查判读经验。请对以下肺功能检查报告进行专业解读。
{OUTPUT_FORMAT}

## 肺功能解读重点
- **通气功能**：FVC、FEV1、FEV1/FVC比值判断阻塞性/限制性/混合性通气功能障碍
- **严重程度分级**：根据FEV1占预计值百分比进行分级（轻度/中度/重度/极重度）
- **支气管舒张试验**：阳性提示气道可逆性，支持哮喘诊断；阴性不能排除哮喘
- **弥散功能**：DLCO下降提示肺间质病变、肺气肿、肺血管病变等
- **小气道功能**：MEF25、MEF50异常提示小气道病变
- **肺容量**：TLC、RV、RV/TLC评估肺过度充气或限制
{CONSTRAINTS}"""


@register_report_type("ct", "CT报告")
def ct_prompt(report=None):
    return f"""你是一名资深放射科主任医师，拥有丰富的CT影像诊断经验。请对以下CT报告进行专业解读。
{OUTPUT_FORMAT}

## CT报告解读重点
- 关注病灶的位置、大小、形态、密度/信号特征、边界、强化方式
- 占位性病变：评估良恶性倾向，注意有无淋巴结转移、远处转移征象
- 炎症性病变：分布特征、范围、有无合并积液/脓肿
- 血管病变：有无动脉瘤、夹层、栓塞、狭窄
- 结合增强扫描的强化模式分析病变性质
- 对于肺结节：参考Lung-RADS分级，评估随访或干预策略
- 对于肝脏病变：参考LI-RADS分级
- 注意与既往影像对比，评估病变进展或消退
{CONSTRAINTS}"""


@register_report_type("xray", "放射/X光报告")
def xray_prompt(report=None):
    return f"""你是一名资深放射科主任医师，拥有丰富的X线影像诊断经验。请对以下放射/X光报告进行专业解读。
{OUTPUT_FORMAT}

## X光报告解读重点
- **胸片**：心影大小和形态、肺纹理、肺野透亮度、有无渗出/实变/结节/肿块、胸腔积液、气胸、纵隔
- **骨片**：骨质结构、有无骨折线、骨质疏松/硬化/破坏、关节间隙、软组织肿胀
- **腹平片**：肠管分布和气液平面、有无游离气体、结石、异常钙化
- 注意阅片时的系统性检查，避免遗漏非主要关注区域的异常
- 对于骨折：明确骨折部位、类型、移位情况
- 对于胸片异常：结合临床症状判断是否需要进一步CT检查
{CONSTRAINTS}"""


@register_report_type("mri", "核磁共振报告")
def mri_prompt(report=None):
    return f"""你是一名资深放射科主任医师，拥有丰富的MRI影像诊断经验。请对以下核磁共振（MRI）报告进行专业解读。
{OUTPUT_FORMAT}

## MRI报告解读重点
- 关注病灶在T1WI、T2WI、FLAIR、DWI各序列上的信号特征
- **DWI/ADC**：弥散受限提示急性缺血/高细胞密度肿瘤/脓肿
- **增强扫描**：强化方式（均匀/不均匀/环形）对病变定性的意义
- **颅脑MRI**：关注有无脑实质异常信号、占位效应、中线移位、脑室扩张
- **脊柱MRI**：椎间盘突出程度与方向、脊髓信号、椎管狭窄程度
- **关节MRI**：韧带/半月板/软骨损伤程度分级
- **腹部MRI**：肝脏病灶参考LI-RADS分级
- 注意与既往影像对比，评估病变演变
{CONSTRAINTS}"""


# ================================================================
# 科室专科补充模板
# ================================================================

@register_department("hematology", "血液科", ["白细胞", "红细胞", "血红蛋白", "血小板", "网织红细胞", "凝血功能", "铁代谢"])
def hematology_dept(report=None):
    return """

## 血液科专科关注
当前医生为血液科医生，请特别关注：
- **三系减少**：白细胞、红细胞、血小板是否同时减低，提示骨髓造血功能障碍
- **贫血分类**：根据MCV、MCH、MCHC判断贫血类型
- **网织红细胞**：评估骨髓红系增生活跃程度
- **凝血功能**：PT、APTT、纤维蛋白原、D-二聚体异常提示出血或血栓风险
- **血涂片异常**：幼稚细胞、异常淋巴细胞需高度重视
- 对于全血细胞减少，关注是否需要骨髓穿刺检查"""


@register_department("internal", "内科", ["肝功能", "肾功能", "血糖", "血脂", "电解质", "心肌酶", "甲功"])
def internal_dept(report=None):
    return """

## 内科专科关注
当前医生为内科医生，请特别关注：
- **肝功能**：ALT、AST比值关系，胆红素分类，白蛋白水平
- **肾功能**：肌酐、尿素氮、eGFR评估肾功能分期
- **血糖代谢**：空腹血糖、糖化血红蛋白综合评估
- **血脂异常**：总胆固醇、LDL-C、HDL-C、甘油三酯的心血管风险评估
- **电解质**：血钾、血钠、血钙异常的临床意义及紧急处理指征
- 注意各指标关联性，综合分析可能的病因"""


@register_department("respiratory", "呼吸科", ["血气分析", "CRP", "PCT", "D-二聚体", "血常规", "肺功能"])
def respiratory_dept(report=None):
    return """

## 呼吸科专科关注
当前医生为呼吸科医生，请特别关注：
- **血气分析**：pH、PaO₂、PaCO₂、HCO₃⁻综合判断酸碱平衡紊乱类型及代偿情况
- **氧合指数**：PaO₂/FiO₂评估ARDS严重程度
- **感染标志物**：CRP、PCT联合判断感染类型，PCT>0.5ng/mL高度提示细菌感染
- **D-二聚体**：升高需警惕肺栓塞，结合Wells评分综合判断
- **肺功能指标**：FEV1/FVC判断通气功能障碍类型及严重程度
- **乳酸**：升高提示组织灌注不足，需警惕脓毒症"""


@register_department("general", "通用", [])
def general_dept(report=None):
    return ""
