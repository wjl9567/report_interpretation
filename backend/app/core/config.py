"""应用配置 - 通过环境变量和配置文件驱动，支持多医院部署"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "报告AI解读系统"
    APP_VERSION: str = "1.0.1"
    DEBUG: bool = False

    # 医院信息（每家医院独立配置）
    HOSPITAL_NAME: str = "默认医院"
    HOSPITAL_CODE: str = "default"

    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    # 数据库（默认SQLite，生产环境切换PostgreSQL）
    DATABASE_URL: str = "sqlite+aiosqlite:///./report_ai.db"

    # 推理服务（本次实施使用 sglang 部署安诊儿模型，OpenAI 兼容 chat 接口；亦支持 vLLM）
    VLLM_BASE_URL: str = "http://localhost:8000"
    VLLM_MODEL_NAME: str = "AntAngelMed"
    VLLM_TIMEOUT: int = 30
    VLLM_MAX_TOKENS: int = 2048
    VLLM_TEMPERATURE: float = 0.3

    # LIS 对接（适配器选择: mock / winning）
    LIS_ADAPTER: str = "mock"
    LIS_API_BASE_URL: str = ""
    LIS_API_KEY: str = ""
    LIS_FIELD_MAPPING_FILE: str = "config/lis_field_mapping.yaml"
    LIS_RETRY_COUNT: int = 3
    LIS_RETRY_DELAY: float = 1.0
    # 卫宁 LisWebService.asmx：入参 HID（住院首页序号/门诊挂号序号），返回 JSON 含 data[].FILEURL
    LIS_USE_ASMX: bool = False
    # 检查报告 ASMX（TechQueue.asmx），与 LIS_API_BASE_URL（检验 8092）同时配置时合并列表、按 source 取 PDF
    LIS_EXAM_ASMX_BASE_URL: str = ""
    LIS_ASMX_METHOD_NAME: str = "GetReportList"
    LIS_ASMX_NAMESPACE: str = "http://tempuri.org/"
    LIS_ASMX_JSON_PARAM_NAME: str = "jsonParam"

    # HL7 消息接收（保留实现，默认关闭；有集成平台推送的医院可设为 True）
    HL7_ENABLED: bool = False
    HL7_PORT: int = 2575
    HL7_ENCODING: str = "utf-8"
    HL7_AUTO_INTERPRET: bool = False
    HL7_FIELD_MAPPING_FILE: str = "config/hl7_field_mapping.yaml"

    # PaddleOCR 服务
    OCR_SERVICE_URL: str = "http://localhost:8866"
    OCR_TIMEOUT: int = 15

    # 上传文件
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Redis（可选）
    REDIS_URL: Optional[str] = None

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # 嵌入/患者接口展示模式（按医院可配置）
    # list_select：弹出界面先展示报告列表，选中某条再解读该条
    # latest_auto：弹出后自动解读该患者最新一条报告
    EMBED_REPORT_MODE: str = "list_select"

    # 全站中文与时区：API 日期序列化、日志等使用中国时区
    TIMEZONE: str = "Asia/Shanghai"

    # 前端展示：帮助与反馈链接（可选，为空则不显示）
    HELP_URL: str = ""
    FEEDBACK_URL: str = ""

    # 轻量知识增强：按科室/报告类型加载规范与指南片段并注入 prompt，不依赖向量库
    KNOWLEDGE_ENABLED: bool = False
    KNOWLEDGE_DIR: str = "knowledge"
    KNOWLEDGE_MAX_CHARS: int = 4000

    # SQL Server：根据 pat_num（病历号/门诊卡号）解析为 xh（HID），再调 LIS 获取报告。不配置则 API 的 patient_id 视为 HID。
    MSSQL_ENABLED: bool = False
    MSSQL_SERVER: str = ""
    MSSQL_USER: str = ""
    MSSQL_PASSWORD: str = ""
    MSSQL_DATABASE: str = ""
    MSSQL_VIEW_HID: str = "VW_BRJZXXK"
    MSSQL_COLUMN_PAT_NUM: str = "pat_num"
    MSSQL_COLUMN_XH: str = "xh"
    # 视图中“记录日期”列（住院为入院日期 rqrq，门诊为挂号日期 ghrq），用于按时间范围筛 xh
    MSSQL_COLUMN_JLRQ: str = "jlrq"
    # 报告范围（天）：0=不按日期过滤只取 TOP1；7/14=只取近 7/14 天内的门急诊/住院记录对应的 xh，合并多 HID 报告列表
    MSSQL_VIEW_REPORT_DAYS: int = 0

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
