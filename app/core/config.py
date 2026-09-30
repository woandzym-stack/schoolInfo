from typing import Optional
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- 基础配置 ---
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "my-new-app"
    
    # --- 1. 数据库配置 (必须在 .env 中提供) ---
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # --- 2. Nacos 配置 (支持 .env 覆盖，提供默认值方便本地开发) ---

    ENABLE_NACOS: bool = True
    
    NACOS_SERVER_ADDR: str = "127.0.0.1:8848"
    NACOS_NAMESPACE: Optional[str] = ""       # public 命名空间通常为空字符串
    NACOS_USERNAME: str = "nacos"
    NACOS_PASSWORD: str = "nacos"
    NACOS_CLIENT_IP: Optional[str] = None     # 优先用于服务注册的本机 IP
    
    # --- 3. 本服务注册信息 ---
    # 这个名字要和 Gateway 配置的 lb://service-name 一致
    SERVICE_NAME: str = "my-new-app"      
    SERVICE_PORT: int = 8008
    SERVICE_GROUP: str = "DEFAULT_GROUP"

    ALIYUN_OSS_ENDPOINT: str = "oss-cn-shenzhen.aliyuncs.com"
    ALIYUN_OSS_BUCKET_NAME: str = "my-company"
    ALIYUN_OSS_ACCESS_KEY_ID: str = ""      # OSS 访问密钥 ID
    ALIYUN_OSS_ACCESS_KEY_SECRET: str = ""  # OSS 访问密钥 Secret

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""  # 生产环境必须配置密码，移除Optional强制验证
    REDIS_DB: int = 0

    PDF_CONVERT_MAX_WORKERS: Optional[int] = 2

    LOG_LEVEL: str = "INFO"

    REGION: str = "hongkong"

    RUN_MODE: str = "prod"

    PROMPT_DIR: str = "./prompts"

    GEMINI_API_WHITELIST: Optional[str] = ""

    GATEWAY_AUTH_TOKEN: Optional[str] = None

    PRODUCT_IP: Optional[str] = None

    GMAIL_APP_PASSWORD: Optional[str] = None

    GMAIL_SENDER:str="zhouopenclaw@gmail.com"

    # --- 认证 ---
    JWT_SECRET: str = ""                # HS256 密钥；prod 模式缺失拒绝启动（lifespan 强制校验）
    JWT_EXPIRE_DAYS: int = 7
    AUTH_COOKIE_NAME: str = "auth_token"
    SESSION_COOKIE_SECURE: bool = True  # 客户端→nginx 是 HTTPS 时可开；纯 HTTP 部署置 False

    # --- 4. 组装 DATABASE_URL ---
    @property
    def DATABASE_URL(self) -> str:
        """
        自动组装 SQLAlchemy 连接字符串
        格式: mysql+pymysql://user:password@host:port/dbname
        """
        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASSWORD)
        
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        异步连接字符串 (用于 asyncmy)
        """
        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASSWORD)
        return (
            f"mysql+asyncmy://{user}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        case_sensitive = True
        # 指定读取 .env 文件
        env_file = ".env"
        # 忽略 .env 中多余的字段 (防止 .env 有注释或其他无关变量导致报错)
        extra = "ignore"

settings = Settings()