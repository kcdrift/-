#!/usr/bin/env python
"""自动重启守护脚本 - 每30分钟重启足彩预测服务器更新体彩数据"""
import os
import sys
import time
import socket
import subprocess
import logging
from datetime import datetime

# 配置
RESTART_INTERVAL = 30 * 60  # 30分钟（秒）
PORT = 8080
APP_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
WORKING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# 日志 - 使用Temp目录避免权限问题
LOG_DIR = os.path.join(os.path.expanduser("~"), ".workbuddy", "football_logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "auto_restart.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def is_port_in_use(port):
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def get_pid_on_port(port):
    """获取占用端口的PID（Windows）"""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            encoding='gbk',
            errors='replace',
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                if parts and parts[-1].isdigit():
                    return int(parts[-1])
    except Exception as e:
        logger.warning(f"获取PID失败: {e}")
    return None


def kill_process(pid):
    """终止进程"""
    if pid:
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            logger.info(f"已终止PID {pid}")
        except Exception as e:
            logger.warning(f"终止进程失败: {e}")


def start_server():
    """启动服务器"""
    logger.info(f"启动服务器...")
    python_exe = sys.executable

    process = subprocess.Popen(
        [python_exe, APP_SCRIPT],
        cwd=WORKING_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 等待启动
    for i in range(20):
        time.sleep(1)
        if is_port_in_use(PORT):
            logger.info(f"✓ 服务器启动成功 (PID: {process.pid})")
            return process
        logger.info(f"  等待启动... ({i+1}/20)")

    logger.error("✗ 服务器启动超时")
    return None


def main():
    logger.info("=" * 60)
    logger.info("自动重启守护脚本启动")
    logger.info(f"重启间隔: {RESTART_INTERVAL // 60} 分钟")
    logger.info(f"目标端口: {PORT}")
    logger.info(f"日志文件: {LOG_FILE}")
    logger.info("=" * 60)

    process = None

    while True:
        try:
            # 检查是否需要重启
            if process is None or process.poll() is not None:
                # 进程不存在或已退出，重启
                kill_process(get_pid_on_port(PORT))
                time.sleep(2)
                process = start_server()
            else:
                # 进程运行中，检查端口
                if not is_port_in_use(PORT):
                    logger.warning("端口未监听，重启服务器")
                    kill_process(process.pid)
                    time.sleep(2)
                    process = start_server()

            # 等待下一轮检查
            time.sleep(60)  # 每分钟检查一次

        except KeyboardInterrupt:
            logger.info("收到中断信号，退出")
            if process and process.poll() is None:
                process.terminate()
            break
        except Exception as e:
            logger.error(f"错误: {e}", exc_info=True)
            time.sleep(60)


if __name__ == "__main__":
    main()
