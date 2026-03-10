@echo off
REM 启动缠论分析 Web 界面 - Windows 版本

cd /d "%~dp0"

echo ================================
echo  缠论分析 Web 界面启动脚本
echo ================================
echo.

REM 检查 Python 环境
echo 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo   ✓ Python 版本: %PYTHON_VERSION%
echo.

REM 检查前端依赖
echo 检查前端依赖...
if not exist "web\node_modules" (
    echo   正在安装 npm 依赖...
    cd web
    call npm install
    cd ..
    echo   ✓ 依赖安装完成
) else (
    echo   ✓ 前端依赖已安装
)
echo.

REM 启动后端 API 服务
echo 启动后端 API 服务 (端口 8001)...
start /B python api/server.py
echo   等待 API 服务启动...

REM 等待服务就绪（循环检查）
:wait_loop
timeout /t 1 >nul
curl -s http://127.0.0.1:8001/ >nul 2>&1
if errorlevel 1 (
    goto wait_loop
)
echo   ✓ API 服务已启动
echo.

REM 启动前端开发服务器
echo 启动前端开发服务器 (端口 5173)...
cd web
start /B npm run dev
cd ..
echo   ✓ 前端服务已启动
echo.

echo ================================
echo  服务已启动！
echo ================================
echo.
echo   前端: http://localhost:5173
echo   API:  http://127.0.0.1:8001
echo.
echo 按任意键关闭此窗口将停止服务
echo.

pause
