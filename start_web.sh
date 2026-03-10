#!/bin/bash
# 启动缠论分析 Web 界面

# 获取脚本所在目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/.."

echo "=========================================="
echo " 缠论分析 Web 界面启动脚本"
echo "=========================================="
echo ""

# 检查 Python 环境
echo "检查 Python 环境..."
if ! command -v python &> /dev/null; then
    echo "错误: 未找到 Python，请先安装 Python 3.8+"
    exit 1
fi
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "  ✓ Python 版本: $PYTHON_VERSION"
echo ""

# 检查前端依赖
echo "检查前端依赖..."
if [ ! -d "web/node_modules" ]; then
    echo "  正在安装 npm 依赖..."
    cd web
    npm install
    cd ..
    echo "  ✓ 依赖安装完成"
else
    echo "  ✓ 前端依赖已安装"
fi
echo ""

# 启动后端 API 服务
echo "启动后端 API 服务 (端口 8001)..."
python api/server.py &
API_PID=$!
echo "  ✓ API 服务已启动 (PID: $API_PID)"
sleep 2
echo ""

# 启动前端开发服务器
echo "启动前端开发服务器 (端口 5173)..."
cd web
npm run dev &
WEB_PID=$!
cd ..
echo "  ✓ 前端服务已启动 (PID: $WEB_PID)"
echo ""

echo "=========================================="
echo " 服务已启动！"
echo "=========================================="
echo ""
echo "  前端: http://localhost:5173"
echo "  API:  http://127.0.0.1:8001"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo ""

# 等待 Ctrl+C
trap "echo ''; echo '正在停止服务...'; kill $API_PID $WEB_PID 2>/dev/null; exit 0" INT

# 持续运行
wait
