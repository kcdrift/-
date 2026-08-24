#!/usr/bin/env bash
# 看门狗：web/app.py 一退出就自动重启，避免后台任务被回收后服务长断。
cd /d/足彩
while true; do
  echo "[watchdog $(date +%H:%M:%S)] 启动 web 服务..."
  PYTHONUNBUFFERED=1 python web/app.py --live --host 0.0.0.0 --port 8080 >> /d/足彩/web_server.log 2>&1
  echo "[watchdog $(date +%H:%M:%S)] web 退出(code=$?)，5秒后重启..."
  sleep 5
done
