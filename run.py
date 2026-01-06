#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
短剧制作平台启动脚本
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from loguru import logger
from src.utils.config_loader import config_loader
from server.http_server import start_server_in_thread
from server.init_db import init_db

# 配置日志
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)

logger.add(
    log_dir / "app.log",
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    encoding="utf-8"
)

def main():
    """主函数"""
    logger.info("启动短剧制作平台...")
    
    # 创建必要的目录
    dirs = [
        project_root / "data" / "projects",
        project_root / "data" / "temp",
        project_root / "config"
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    
    # 检查配置文件
    config_file = project_root / "config" / "config.yaml"
    if not config_file.exists():
        logger.warning("配置文件不存在，将使用默认配置")
    
    # 初始化数据库
    try:
        init_db()
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
    
    # 启动HTTP服务
    # 优先读取环境变量 (Docker部署友好)
    host = os.environ.get("WEB_SERVER_HOST", config_loader.get("web.server.host", "127.0.0.1"))
    port = int(os.environ.get("WEB_SERVER_PORT", config_loader.get("web.server.port", 8000)))
    try:
        t = start_server_in_thread(host, port)
        # Keep main thread alive
        while t.is_alive():
            t.join(1)
    except KeyboardInterrupt:
        logger.info("正在停止服务...")
    except Exception as e:
        logger.error(f"HTTP服务启动失败: {e}")

if __name__ == "__main__":
    main()
