"""应用配置 - 通过环境变量和配置文件驱动，支持多医院部署"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "报告AI解读系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # 医院信息（每家医院独立配置）
    HOSPITAL_NAME: str = "默认医院"
    HOSPITAL_CODE: str = "default"

    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    # 数据库（默认SQLite，生产环境切换PostgreSQL）
    DATABASE_URL: str = "sqlite+aiosqlite:///./report_ai.db"

    # vLLM 推理服务
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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
