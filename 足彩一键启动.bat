@echo off
chcp 65001 >nul
title 足彩量化预测 - 一键启动器
cd /d %~dp0

REM ========== Python 解释器探测（双击场景 PATH 不一定有 python） ==========
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  if exist "C:\Users\%USERNAME%\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
    set "PY=C:\Users\%USERNAME%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
  )
)
if not defined PY (
  for /d %%d in ("C:\Users\%USERNAME%\.workbuddy\binaries\python\versions\*") do set "PY=%%d\python.exe"
)
if not defined PY (
  echo [错误] 找不到 Python。请先安装 Python 3，或运行 WorkBuddy 安装 managed python。
  pause
  exit /b 1
)
echo [环境] 使用 Python：%PY%

:menu
if not defined MENU_TRIES set "MENU_TRIES=0"
set /a MENU_TRIES+=1
if %MENU_TRIES% GTR 20 ( echo 输入无效次数过多，已自动退出。 & goto end )
cls
echo.
echo ============================================================
echo         足彩量化预测 - 一键启动器
echo ============================================================
echo 赛后对比 Review  预测对真实比分，出命中报告并反哺模型（离线）  输入 1
echo 启动界面 Web     本地 8080 双 Tab，赛前预测与赛后对比         输入 2
echo 抓取数据 Fetch   真实历史训练加实时盘口（需 API key）         输入 3
echo 退出（输入 0 或关闭窗口）
set /p "CHOICE=请选择："
if "%CHOICE%"=="1" goto do_review
if "%CHOICE%"=="2" goto do_serve
if "%CHOICE%"=="3" goto do_fetch
if "%CHOICE%"=="0" goto end
echo 输入无效，请重新选择。
timeout /t 1 >nul
goto menu

:do_review
cls
echo [赛后对比] 自动配对最新预测 + 真实赛果 -> 命中报告 + 反哺模型
echo.
echo 说明：
echo   真实赛果填在 data/raw/actuals.csv（参考 actuals_template.csv）
echo   预测自动配对 data/processed/fetch_predictions.json（或最新 fetch_predictions_*.json）
echo.
"%PY%" scripts/review_pipeline.py
echo.
echo [完成] 报告已存 data/processed/review_report.json，界面「赛后对比」Tab 自动读取。
pause
goto menu

:do_serve
cls
echo [启动界面] 本地 Web 服务（http://127.0.0.1:8080）
echo.
set "SERVE_ARGS="
set /p "HIST=真实历史 CSV 路径（留空=演示盘口）："
if not "%HIST%"=="" (
  if exist "%HIST%" ( set "SERVE_ARGS=--csv "%HIST%"" ) else ( echo [警告] 文件不存在：%HIST%，改用演示盘口。 & timeout /t 1 >nul )
)
echo 正在后台启动服务...
start "足彩Web服务" cmd /c ""%PY%" main.py serve %SERVE_ARGS% & echo. & echo 服务已停止，按任意键关闭窗口。 & pause"
timeout /t 3 >nul
start "" http://127.0.0.1:8080
echo 已在新窗口启动服务，浏览器将自动打开。
echo 关闭那个黑色窗口即可停止服务（本菜单退出不影响它）。
pause
goto menu

:do_fetch
cls
echo [抓取数据] 真实历史训练 + 实时赛程/盘口
echo.
set /p "HIST2=真实历史 CSV 路径（训练必填，默认 data/raw/historical_sample.csv）："
if "%HIST2%"=="" set "HIST2=data/raw/historical_sample.csv"
if not exist "%HIST2%" ( echo [错误] 历史 CSV 不存在：%HIST2% & pause & goto menu )
set /p "KEY2=The Odds API key（留空则只抓历史 + 演示赛程，不抓实时盘口）："
set "FETCH_ARGS=--csv "%HIST2%""
if not "%KEY2%"=="" set "FETCH_ARGS=%FETCH_ARGS% --live --odds-api-key %KEY2%"
echo.
echo 正在抓取并生成预测...
"%PY%" main.py fetch %FETCH_ARGS%
echo.
echo [完成] 预测已存 data/processed/fetch_predictions.json，之后可运行 [1] 赛后对比。
pause
goto menu

:end
exit /b 0
