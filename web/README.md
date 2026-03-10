# 缠论分析 Web 界面

基于 Vue 3 + TypeScript + ECharts + Rough.js 的缠论技术分析 Web 界面。

## 功能特性

- **浅色主题** - TradingView 风格配色
- **手绘风格图标** - 使用 Rough.js 绘制的手绘图标
- **ECharts K线图** - 显示：
  - K线（绿涨红跌）
  - 笔（蓝色向上 / 橙色向下）
  - 线段（紫色粗线）
  - 中枢（半透明矩形）
  - 分型（三角形标记）
  - 买卖点（不同形状标记）
- **周期切换** - 支持 15分钟、1小时、4小时、1天
- **交易对切换** - BTC/USDT、ETH/USDT
- **图层控制** - 可显示/隐藏各个缠论元素
- **AI 分析** - 集成后端 AI 分析功能

## 快速启动

### Windows
双击运行 `start_web.bat`

### Linux/Mac
```bash
chmod +x start_web.sh
./start_web.sh
```

## 手动启动

### 1. 启动后端 API 服务
```bash
python api/server.py
# 访问 http://127.0.0.1:8001
```

### 2. 启动前端开发服务器
```bash
cd web
npm install  # 首次运行需要安装依赖
npm run dev
# 访问 http://localhost:5173
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 前端框架 | Vue 3 + TypeScript |
| 构建工具 | Vite 5 |
| 图表库 | ECharts 5 |
| 手绘图标 | Rough.js 4.6 |
| UI 样式 | SCSS |
| 后端 API | FastAPI + Python |

## 目录结构

```
web/
├── index.html           # 入口 HTML
├── package.json         # 项目配置
├── vite.config.ts       # Vite 配置
├── tsconfig.json        # TypeScript 配置
├── src/
│   ├── main.ts           # 应用入口
│   ├── App.vue           # 根组件
│   ├── components/       # Vue 组件
│   │   ├── ToolBar.vue       # 工具栏
│   │   ├── ChartContainer.vue # 图表容器
│   │   ├── AISidebar.vue     # AI 侧边栏
│   │   └── RoughIcon.vue     # 手绘图标
│   ├── api/             # API 客户端
│   ├── types/           # TypeScript 类型
│   ├── utils/           # 工具函数
│   └── assets/styles/   # 样式文件
└── start_web.bat        # Windows 启动脚本
```

## 配置说明

### API 地址配置
前端通过 Vite 代理将 `/api` 请求转发到后端 `http://127.0.0.1:8001`

如需修改后端地址，编辑 `vite.config.ts`:
```typescript
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8001',  // 修改此处
    changeOrigin: true
  }
}
```

### AI API 配置
后端需要配置 AI 服务提供商，编辑项目根目录的 `.env` 文件：
```
AI_PROVIDER=siliconflow
AI_MODEL=Pro/deepseek-ai/DeepSeek-V3.2
SILICONFLOW_API_KEY=your_key_here
```

## 注意事项

1. 确保 Python 3.8+ 已安装
2. 确保后端 AI API 密钥已配置
3. 首次运行需要执行 `npm install` 安装前端依赖
4. 前端开发服务器运行在 5173 端口
5. 后端 API 服务运行在 8001 端口
