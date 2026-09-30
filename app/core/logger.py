import logging
import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


class InterceptHandler(logging.Handler):
    """
    拦截 Python 标准 logging 模块的日志，转发给 Loguru
    """

    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


# --- 过滤器定义 ---


# 1. AI 日志过滤器：只保留 extra["channel"] == "ai" 的日志
def ai_filter(record):
    return record["extra"].get("channel") == "ai"


# 2. 普通应用日志过滤器：排除掉独立通道（ai / link_report）的日志
#    这样 AI 的海量日志和链接报错流水就不会污染 app.log 和控制台
def app_filter(record):
    return record["extra"].get("channel") not in ("ai", "link_report")


# 3. 链接报错日志过滤器：只保留 extra["channel"] == "link_report" 的日志
def link_report_filter(record) -> bool:
    return record["extra"].get("channel") == "link_report"


def setup_logging():
    log_level = settings.LOG_LEVEL.upper()
    # 1. 移除默认 handler
    logger.remove()

    # -------------------------------------------------------------
    # 初始化 extra 默认值
    # request_id: Web请求ID
    # req_uuid: AI 内部追踪ID (默认 "-")
    # channel: 日志通道 (默认 "default")
    # -------------------------------------------------------------
    logger.configure(extra={"request_id": "SYSTEM", "req_uuid": "-", "channel": "default"})

    # 2. 定义通用日志格式 (Web请求用)
    common_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<magenta>{extra[request_id]}</magenta> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # 3. 定义 AI 专用日志格式 (强调 req_uuid)
    ai_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<magenta>{extra[req_uuid]}</magenta> | "  # 这里显示 AI 的 UUID
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )

    # --- 输出配置 ---

    # 4. 控制台 (仅输出普通日志，不输出 AI 刷屏日志)
    logger.add(
        sys.stderr,
        level=log_level,
        format=common_format,
        filter=app_filter,  # 关键：应用过滤器
    )

    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)

    # 5. 主应用日志 (app.log) - 排除 AI 日志
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        # compression="zip",
        level=log_level,
        format=common_format,
        encoding="utf-8",
        enqueue=True,
        filter=app_filter,  # 关键：应用过滤器
    )

    # 6. 错误日志 (error.log) - 只记录 ERROR 及以上级别的应用日志
    logger.add(
        "logs/error_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level="ERROR",
        format=common_format,
        encoding="utf-8",
        enqueue=True,
        filter=app_filter,  # 只记录应用的错误，AI 相关的错误在 ai_trace.log 中
    )

    def ai_trace_rotation(message, file):
        file.seek(0, 2)
        if file.tell() >= 20 * 1024 * 1024:
            return True

        current_date = message.record["time"].strftime("%Y-%m-%d")
        return f"ai_trace_{current_date}.log" != Path(file.name).name

    # 7. AI 专用日志 (ai_trace.log) - 只接收 AI 日志
    logger.add(
        "logs/ai_trace_{time:YYYY-MM-DD}.log",
        rotation=ai_trace_rotation,
        retention="10 days",
        # compression="zip",
        level=log_level,
        format=ai_format,
        encoding="utf-8",
        enqueue=True,
        filter=ai_filter,
    )

    # 8. 链接报错专用日志 (link_report.log) - 只接收链接报错流水
    #    格式从简（时间 + 消息体），消息体为一行 JSON，便于 grep/审阅。
    #    接口匿名且不限流，单文件加 10MB 上限防日志洪泛写满磁盘
    #    （一行 ~200 字节，10MB ≈ 5 万条/文件，对正常反馈足够宽松）
    def link_report_rotation(message, file):
        file.seek(0, 2)
        if file.tell() >= 10 * 1024 * 1024:
            return True

        current_date = message.record["time"].strftime("%Y-%m-%d")
        return f"link_report_{current_date}.log" != Path(file.name).name

    logger.add(
        "logs/link_report_{time:YYYY-MM-DD}.log",
        rotation=link_report_rotation,
        retention="90 days",
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{message}</level>",
        encoding="utf-8",
        enqueue=True,
        filter=link_report_filter,
    )

    # 9. 接管 Uvicorn 和 FastAPI 的原生日志
    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        mod_logger = logging.getLogger(logger_name)
        mod_logger.handlers = [InterceptHandler()]
        mod_logger.propagate = False
