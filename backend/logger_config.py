import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta
import glob
import threading

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "gameplan.log")
LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logging():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # 清除已有 handler
    root.handlers.clear()

    # 文件 handler：每天轮转，保留 30 天
    file_handler = TimedRotatingFileHandler(
        LOG_FILE, when="midnight", interval=1, backupCount=30,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root.addHandler(file_handler)

    # 控制台 handler（仅 WARNING+）
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root.addHandler(console)

    # 降低第三方库日志级别
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("passlib").setLevel(logging.WARNING)

    root.info("日志系统初始化完成")

def clean_old_logs():
    """清理 30 天前的日志文件"""
    cutoff = datetime.now() - timedelta(days=30)
    for f in glob.glob(os.path.join(LOG_DIR, "gameplan.log*")):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(f))
            if mtime < cutoff:
                os.remove(f)
        except: pass
