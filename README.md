# 缠论 AI 分析系统

> 基于 Binance 行情数据 + 缠论结构计算 + AI 智能决策的数字货币量化分析工具

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 📖 项目简介

本项目是一个将**传统缠论技术分析**与**AI 大模型**相结合的量化工具，旨在为数字货币交易者提供智能化的市场分析和决策支持。

### 核心特性

- 🔄 **实时行情获取**：通过 Binance REST API 获取现货 K 线数据
- 📊 **缠论结构计算**：自动识别笔、线段、中枢、买卖点、背驰等关键结构（自实现缠论引擎）
- 🤖 **AI 智能分析**：支持 DeepSeek、Claude、GPT 等多种 AI 模型进行走势预测
- 📊 **策略概率分析**：自动计算并显示做多/做空/震荡策略的成功概率
- 💾 **数据库存储**：SQLite 本地存储，支持历史分析追溯
- 📈 **增强版统计系统**：多维度准确率统计（趋势/位置/力度/信号类型）
- 📉 **可视化工具**：缠论结构图表 + 统计图表自动生成
- 🔗 **多级别分析**：支持多周期联立分析（4H/1H/15M）
- 🛠️ **CLI 工具**：完整的命令行工具，支持多种分析模式

### AI自我学习系统（新增）

- 🧠 **相似案例检索**：每次分析前检索历史相似案例，注入Prompt参考
- 📊 **学习反馈报告**：统计AI整体表现，识别系统性错误模式
- 🎯 **置信度约束**：基于历史胜率自动调整预测参数（概率/目标/止损）
- ✅ **逻辑验证**：检测AI输出中的逻辑错误（止损位置、方向冲突等）
- ⚖️ **权重优化**：基于历史数据自动优化信号质量评分权重

---

## 🚀 快速开始

### 环境要求

- Python 3.12+
- pip 包管理器
- Binance API（无需认证，使用公开接口）
- AI API Key（硅基流动/OpenRouter/DeepSeek 等）

### 安装步骤

#### 1. 克隆项目

```bash
git clone https://github.com/164149043/chanlun.git
cd chanlun
```

#### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

#### 3. 安装依赖

```bash
pip install -r requirements.txt
```

#### 4. 配置 API Key

复制 `.env.example` 为 `.env`，并填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# AI 服务提供商
AI_PROVIDER=siliconflow

# AI 模型
AI_MODEL=Pro/deepseek-ai/DeepSeek-V3.2

# API Key
SILICONFLOW_API_KEY=sk-你的真实API密钥
```

#### 5. 运行第一次分析

```bash
python chanlun_ai.py BTCUSDT 1h --structured --limit 200
```

---

## 💡 使用示例

### 基础分析

```bash
# 分析 BTC/USDT 1小时周期
python chanlun_ai.py BTCUSDT 1h

# 使用200根K线（推荐，避免超时）
python chanlun_ai.py BTCUSDT 1h --limit 200
```

### 结构化输出（保存到数据库）

```bash
# 强制 JSON 输出，自动保存到数据库
# 包含策略概率分析和详细操作建议
python chanlun_ai.py BTCUSDT 1h --structured --limit 200
```

**输出示例**：
```
============================================================
📝 AI 市场分析（给交易者看的解读）
============================================================
  当前BTC/USDT处于1小时周期的缠论结构中。
  最新一笔向下笔已完成，结束于90882.71，并出现1买点和笔背离信号。
  【做多策略（概率55%）】：入场91262.94，目果91500-92000，止损90500。
  【做空策略（概率25%）】：入场90800，目果90000-89500，止损91200。
  【震荡策略（概率20%）】：区间90800-91500，高抛低吸。
============================================================

📊 策略概率分布：
------------------------------------------------------------
  📈 做多策略概率: 55.0%
  📉 做空策略概率: 25.0%
  ↔️  震荡策略概率: 20.0%
------------------------------------------------------------
```

### 表格格式 Markdown 报告

```bash
# 输出标准化的 Markdown 分析报告
python chanlun_ai.py BTCUSDT 1h --table --limit 200
```

### 简化分析（快速查看）

```bash
# 输出简洁的分析总结
python chanlun_ai.py BTCUSDT 1h --simple --limit 100
```

### 仅查看缠论结构

```bash
# 不调用 AI，只显示缠论计算结果
python chanlun_ai.py BTCUSDT 1h --no-ai
```

### 保存完整报告

```bash
# 保存 Markdown 报告到 output/ 目录
python chanlun_ai.py BTCUSDT 1h --structured --limit 200 --save
```

---

## 📊 数据库与统计

### 查看分析记录（增强版 - 全中文）

```bash
# 显示所有统计
python query_stats.py

# 只显示快照列表
python query_stats.py --snapshots

# 增强版准确率统计（含趋势/位置/信号类型维度）
python query_stats.py --accuracy

# 导出完整 CSV（含结构上下文，所有字段中文）
python query_stats.py --export-csv output/results.csv
```

### 多维度统计分析

```bash
# 详细多维度统计报表
python stats_enhanced.py

# 生成统计图表（保存到 output/）
python stats_visualizer.py
```

### 可视化工具

```bash
# 可视化缠论结构（K线图 + 笔段 + 中枢 + MACD）
python chanlun_visualizer.py BTCUSDT 1h --limit 500

# 多级别联立分析（4H/1H/15M）
python multi_level_analyzer.py BTCUSDT --save
```

### Web 界面（实时交互式分析）

项目提供了基于 Vue 3 + ECharts 的 Web 界面，支持实时交互式分析：

**快速启动**：
```bash
# Windows
start_web.bat

# Linux/Mac
./start_web.sh
```

**手动启动**：
```bash
# 1. 启动后端 API 服务
python api/server.py

# 2. 启动前端开发服务器
cd web
npm install  # 首次运行
npm run dev
```

**访问地址**：
- 前端界面：http://localhost:5173
- 后端 API：http://127.0.0.1:8001

**Web 界面功能**：
- 实时 K 线图 + 缠论结构叠加显示
- 支持多周期切换（15M / 1H / 4H / 1D）
- 支持多交易对切换（BTC/USDT、ETH/USDT）
- 图层控制（笔/线段/中枢/买卖点）
- AI 分析侧边栏
- 手绘风格 UI 元素

### 回填预测结果

```bash
# 评估 1 小时前的预测
python evaluate_outcome.py 60

# 评估 4 小时前的预测
python evaluate_outcome.py 240

# 评估 1 天前的预测
python evaluate_outcome.py 1440
```

### 准确率统计流程

1. **生成分析快照**（使用 `--structured`）
   ```bash
   python chanlun_ai.py BTCUSDT 1h --structured --limit 200
   ```

2. **等待时间间隔**（例如 1 小时）

3. **运行回填脚本**
   ```bash
   python evaluate_outcome.py 60
   ```

4. **查看准确率与平均得分**
   ```bash
   # 基础统计
   python query_stats.py --accuracy
   
   # 详细多维度统计
   python stats_enhanced.py
   
   # 生成统计图表
   python stats_visualizer.py
   ```

### 得分（score）计算规则

> 评估一条预测的“质量”，范围 0.0 ~ 1.0，越高越好。

- **方向为 up/down 时**：
  - 命中目标，且未触发止损：
    - `score = 1.0`（方向对 + 到目标，表现最好）
    - `outcome = "success"`
  - 触发止损：
    - `score = 0.0`
    - `outcome = "stopped"`
  - 既没到目标、也没止损：
    - 如果方向对（看多最终涨、看空最终跌）：
      - `score = 0.5`（方向对但没走到目标）
      - `outcome = "partial"`
    - 如果方向错：
      - `score = 0.0`
      - `outcome = "failed"`
- **其他情况（方向不是 up/down）**：
  - `score = 0.0`
  - `outcome = "no_direction"`

#### 增强得分（enhanced_score）

**计算公式**：
```
enhanced_score = 命中目标(40%) + 方向正确(20%) + 有利变动比例(20%) + 速度(20%)
```

**如何解读得分**：
- 0.8 ~ 1.0：优秀（大部分预测命中目标）
- 0.5 ~ 0.8：良好（方向对但未完全达标）
- 0.3 ~ 0.5：一般（方向对的比例较低）
- 0.0 ~ 0.3：较弱（经常止损或方向错）

---

## 📁 项目结构

```
chanlun/
├── ai/                          # AI 调用模块
│   ├── llm.py                  # LLM 统一接口
│   └── prompt_builder.py       # 结构化/表格 Prompt 构造器
│
├── chanlun_local/              # 缠论计算引擎（自实现简化版）
│   ├── engine.py              # 核心计算逻辑（SimpleICL）
│   └── mapper.py              # 字段映射与 JSON 转换工具
│
├── output/                     # 分析报告输出目录
│
├── 核心业务模块
│   ├── binance.py             # Binance API 封装
│   ├── chanlun_adapter.py     # 数据适配器（K线 → 缠论结构）
│   ├── chanlun_icl.py         # ICL 接口封装
│   ├── ai_data_builder.py     # AI 输入数据构建器
│   ├── chanlun_ai_exporter.py # 缠论结构 → AI 专用 JSON 导出器
│   ├── ai_output_schema.py    # AI 输出 JSON Schema 与校验
│   ├── output_formatter.py    # 终端输出格式化
│   └── prompt_builder.py      # CLI 分析模式 Prompt 构造器（standard/simple/table/structured）
│
├── 程序入口与工具
│   ├── chanlun_ai.py          # 主 CLI 工具（获取行情 + 缠论计算 + 调用 AI）
│   ├── evaluate_outcome.py    # 预测结果评估脚本（增强版，含结构上下文提取）
│   ├── query_stats.py         # 快照与结果的快速查询工具（增强版，全中文）
│   ├── stats_enhanced.py      # 增强版统计报表（多维度统计）
│   ├── stats_visualizer.py    # 统计图表可视化工具
│   ├── chanlun_visualizer.py  # 缠论结构可视化工具
│   ├── multi_level_analyzer.py # 多级别联立分析工具
│   └── stats_report.py        # 研究报告生成器（AI × 缠论结构统计）
│
├── Web 服务模块
│   ├── api/                      # 后端 API 服务
│   │   ├── server.py            # FastAPI 主服务
│   │   ├── analyze_service.py   # 分析服务
│   │   └── analyze_streaming.py # 流式分析服务
│   │
│   ├── web/                      # 前端 Web 界面（Vue 3 + TypeScript）
│   │   ├── src/                 # 源代码
│   │   ├── index.html           # 入口 HTML
│   │   ├── vite.config.ts       # Vite 配置
│   │   └── package.json         # 项目配置
│   │
│   ├── start_web.bat            # Windows 启动脚本
│   └── start_web.sh             # Linux/Mac 启动脚本
│
├── AI自我学习模块
│   ├── history_context.py        # 相似案例检索 + Prompt注入
│   ├── learning_feedback.py      # AI学习反馈报告
│   ├── confidence_constraint.py  # 置信度约束
│   ├── logic_validator.py        # AI分析逻辑验证
│   ├── signal_quality.py          # 信号质量评分（6维度动态权重）
│   ├── weight_optimizer.py        # 权重自动优化工具
│   ├── learning_visualizer.py    # 学习报告可视化
│   ├── backtest_validator.py     # 回测验证系统（A/B测试）
│   └── optimized_weights.json    # 优化后的权重配置
│
├── 任务计划脚本（Windows）
│   ├── setup_scheduler.ps1        # 主入口（交互式菜单）
│   ├── setup_scheduler_15m.ps1    # 15分钟周期任务
│   ├── setup_scheduler_1h.ps1     # 1小时周期任务
│   └── setup_scheduler_4h.ps1     # 4小时周期任务
│
├── 配置文件
│   ├── .env                   # 环境变量（不上传）
│   ├── .env.example           # 配置示例
│   ├── .gitignore             # Git 忽略规则
│   ├── config.yaml            # 项目配置（可选）
│   └── requirements.txt       # Python 依赖
│
└── 文档
    ├── README.md              # 项目说明
    └── COMMANDS.md            # 命令行参数详解
```

### 主要脚本作用与使用方法

- **`chanlun_ai.py`**：主分析入口
  - **作用**：拉取 Binance K 线 → 计算缠论结构 → 构造 Prompt → 调用 AI → 输出分析 / 保存快照
  - **示例**：
    - 结构化分析并保存到数据库：
      ```bash
      python chanlun_ai.py BTCUSDT 1h --structured --limit 200
      ```
    - 表格版 Markdown 分析：
      ```bash
      python chanlun_ai.py BTCUSDT 1h --table --limit 200
      ```
    - 仅看缠论结构（不调用 AI）：
      ```bash
      python chanlun_ai.py BTCUSDT 1h --no-ai
      ```

- **`evaluate_outcome.py`**：事后评估脚本
  - **作用**：按时间间隔（分钟）拉取“未来 K 线”，基于统一规则评估预测是否命中，并写回评估结果
  - **示例**：
    - 评估 1 小时前的所有快照：
      ```bash
      python evaluate_outcome.py 60
      ```
    - 评估 4 小时前的所有快照：
      ```bash
      python evaluate_outcome.py 240
      ```

- **`query_stats.py`**：快照/结果快速查看（增强版 - 全中文）
  - **作用**：查看最近的分析快照、结果回填记录和增强版准确率统计（含趋势/位置/信号类型维度）
  - **新增**：导出 CSV 文件（含完整结构上下文，所有字段中文）
  - **示例**：
    ```bash
    # 最近快照
    python query_stats.py --snapshots

    # 回填结果
    python query_stats.py --outcomes

    # 增强版准确率汇总
    python query_stats.py --accuracy
    
    # 导出 CSV（含结构上下文）
    python query_stats.py --export-csv output/results.csv
    ```

- **`stats_enhanced.py`**：增强版统计报表
  - **作用**：提供详细的多维度统计分析
  - **统计维度**：
    - 按买卖点类型（1buy/2buy/3buy/1sell/2sell/3sell）
    - 按趋势类型（上升/下降/震荡）
    - 按价格位置（中枢上方/内部/下方）
    - 按力度对比（衰竭/增强/相近）
    - 按有无信号
    - 交叉组合统计（信号类型 × AI方向）
  - **示例**：
    ```bash
    python stats_enhanced.py
    ```

- **`stats_visualizer.py`**：统计图表可视化
  - **作用**：生成统计图表（保存到 output/ 目录）
  - **生成图表**：
    - 胜率分布图（按方向、周期、交易对）
    - 结果类型分布饼图
    - 得分分布直方图
    - 有利/不利变动散点图
    - 累计胜率趋势图
    - 滚动平均得分趋势图
  - **示例**：
    ```bash
    python stats_visualizer.py
    ```

- **`chanlun_visualizer.py`**：缠论结构可视化
  - **作用**：生成缠论结构图表（K线 + 笔段 + 中枢 + 买卖点 + MACD）
  - **特性**：
    - K线图（红色下跌，绿色上涨）
    - 笔（Bi）标记与连线
    - 线段（Segment）标记
    - 中枢（ZS）区域高亮
    - 买卖点标注
    - MACD 指标子图
  - **示例**：
    ```bash
    python chanlun_visualizer.py BTCUSDT 1h --limit 500
    ```

- **`multi_level_analyzer.py`**：多级别联立分析
  - **作用**：同时分析多个周期（4H/1H/15M），提供综合研判
  - **功能**：
    - 多周期结构对比
    - 趋势一致性判断
    - 关键价位汇总
    - JSON 导出
  - **示例**：
    ```bash
    python multi_level_analyzer.py BTCUSDT --save
    ```

- **`stats_report.py`**：研究报告生成器
  - **作用**：基于已评估的记录（`evaluated = 1`），从 `primary_scenario` + 结构信息中统计：
    - AI 总体方向胜率
    - 是否在中枢内的胜率差异
    - “结构 × AI 方向”组合的胜率
  - **示例**：
    ```bash
    python stats_report.py
    ```

- **`stats_by_interval.py`**：按周期统计
  - **作用**：按 `interval` 维度（1m / 5m / 15m / 1h / 4h 等）统计样本数、命中数、止损数和胜率，帮助判断**哪些周期 AI 可信**。
  - **示例**：
    ```bash
    python stats_by_interval.py
    ```

- **`stats_by_symbol.py`**：按品种统计
  - **作用**：按 `symbol` 维度（BTC/USDT、ETH/USDT 等）统计胜率，判断 AI 是“通用分析师”还是更擅长某些品种。
  - **示例**：
    ```bash
    python stats_by_symbol.py
    ```

- **`stat_hint.py`**：A2.5 统计提示模块
  - **作用**：提供 (symbol, interval, 是否在中枢内/外) 维度的简洁统计提示，不直接参与决策，只用于：
    - 在 Prompt 中注入【统计提示 A2.5｜仅供参考】
    - 在 CLI 中展示“样本数 + 胜率 + 文本结论”
  - **返回结构**：
    ```python
    {
        "sample": int,             # 有效样本数
        "win_rate": float | None,  # 胜率，样本不足时为 None
        "level": "high" | "mid" | "low" | "unknown",
        "hint": str,               # 中文提示文案
    }
    ```

---

## 🔧 配置说明

### `.env` 环境变量

| 配置项 | 说明 | 示例值 |
|--------|------|--------|
| `AI_PROVIDER` | AI 服务提供商 | `siliconflow` / `openrouter` / `deepseek` |
| `AI_MODEL` | AI 模型名称 | `Pro/deepseek-ai/DeepSeek-V3.2` |
| `SILICONFLOW_API_KEY` | 硅基流动 API Key | `sk-xxxxxxxxxxxxx` |
| `AI_TEMPERATURE` | 采样温度 | `0.3` |
| `AI_MAX_TOKENS` | 最大生成长度 | `4096` |
| `DEFAULT_KLINE_LIMIT` | 默认 K 线数量 | `200` |

### 支持的 AI 服务

#### 1. 硅基流动（推荐）

```bash
AI_PROVIDER=siliconflow
AI_MODEL=Pro/deepseek-ai/DeepSeek-V3.2
SILICONFLOW_API_KEY=sk-your-key
```

#### 2. OpenRouter

```bash
AI_PROVIDER=openrouter
AI_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_API_KEY=sk-or-your-key
```

#### 3. DeepSeek 官方

```bash
AI_PROVIDER=deepseek
AI_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-your-key
```
---

## 📈 数据库设计

### 表 1: `analysis_snapshot`（分析快照 + 评估结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| symbol | TEXT | 交易对（如 BTC/USDT） |
| interval | TEXT | 周期（如 1h、4h） |
| timestamp | TEXT | 分析时间（UTC ISO 格式） |
| price | REAL | 当时价格（入场价） |
| chanlun_json | TEXT | 完整缠论结构 JSON |
| ai_json | TEXT | AI 输出 JSON（包含 primary_scenario 等） |
| created_at | TEXT | 创建时间（UTC） |
| evaluated | INTEGER | 是否已评估（0=未评估，1=已评估） |
| outcome_json | TEXT | 评估结果 JSON（hit_target、hit_stop、最大波动等） |
---

## 🎯 功能特性

### 1. 缠论结构计算

> **说明**：当前使用的是 **自实现的简化版缠论引擎**（`chanlun_local/engine.py` 中的 `SimpleICL`），提供基本的结构识别功能。后续可替换为更完整的缠论算法实现。

- ✅ 笔（Bi）：自动识别向上笔和向下笔
- ✅ 线段（Segment）：基于笔计算线段
- ✅ 中枢（ZS）：识别震荡中枢和中枢关系
- ✅ 买卖点（MMD）：一买、二买、三买、一卖、二卖、三卖，以及 **类二 / 类三买卖点**（class2buy/class3buy 等）
- ✅ 背驰（BC）：基于 **MACD 力度（柱子之和）** 的笔背驰、段背驰（内部使用 MACD，只作为力度比较，不直接暴露给 AI）


### 2. AI 分析模式

#### 标准模式
- 输出详细的 Markdown 分析报告
- 包含结构判断、走势预测、操作建议

#### 简化模式（`--simple`）
- 输出 3-5 句话的简洁总结
- 适合快速浏览

#### 表格模式（`--table`）
- 使用表格展示缠论数据
- 输出标准化的 6 章节 Markdown 报告

#### 结构化模式（`--structured`）
- 强制输出 JSON 格式
- 自动保存到数据库
- 包含三重验证机制
- **新增**：显示策略概率分布（从AI预测场景中自动提取）
- **新增**：AI文字分析包含具体操作策略（入场点位、目标位、止损位）

### 3. 数据持久化

- ✅ 自动保存分析快照
- ✅ 支持历史查询
- ✅ 准确率统计
- ✅ 结果自动回填

### 4. 准确率评估

- ✅ 多时间间隔评估（1h / 4h / 24h）
- ✅ 自动命中判断
- ✅ 统计报表生成
- ✅ 按方向/rank/interval 分类统计

### 5. 研究与统计工具

- ✅ `stats_report.py`：输出 AI × 缠论结构的研究报告（总体胜率、中枢内外、结构 × AI 组合）。
- ✅ `stats_by_interval.py`：按周期维度统计胜率，帮助识别“高价值周期”和“噪音周期”。
- ✅ `stats_by_symbol.py`：按交易对维度统计胜率，判断 AI 在不同品种上的适用性。

### 6. A2.5 统计提示（仅供参考）

- ✅ `stat_hint.py` 提供 (symbol, interval, 中枢内/外) 维度的历史统计提示，包含样本数、胜率分级（high/mid/low/unknown）和一句话结论。
- ✅ 结构化模式（`--structured`）的 Prompt 会自动注入【统计提示 A2.5｜仅供参考】，但通过系统约束禁止 AI 直接引用或基于胜率做推理，统计只作用于“人类读者”。
### 7. AI自我学习系统详解

AI在每次分析前会"看自己过去说过什么、准不准"，再决定这次"怎么说、说多谨慎"。

#### 核心特性

- **📚 相似案例检索**：自动检索历史相似结构，提供参考表现数据
- **🧠 学习反馈报告**：统计AI整体表现，识别系统性错误模式
- **🎯 置信度约束**：基于历史胜率自动调整预测参数（概率/目标/止损）
- **✅ 逻辑验证**：检测AI输出中的逻辑错误并自动修复
- **⚖️ 权重优化**：基于历史数据自动优化信号质量评分权重
- **📊 可视化分析**：生成AI表现仪表盘和错误模式图表
- **🔬 回测验证**：A/B测试验证改进效果，量化提升幅度

#### 工作流程
```
① 读取历史分析记录        → history_context.py（相似案例检索）
② 读取历史预测vs实际评估   → learning_feedback.py（学习反馈）
③ 生成"分析上下文摘要"    → 相似案例 + AI自我认知
④ 执行本次结构分析        → 缠论引擎
⑤ AI基于【结构+历史】解读  → Prompt注入（全模式支持）
⑥ 逻辑验证与修复          → logic_validator.py
⑦ 置信度约束调整          → confidence_constraint.py
⑧ 信号质量评分            → signal_quality.py
⑨ 保存本次分析记录        → save_snapshot
⑩ 等未来K线→回填评估      → evaluate_outcome.py
```

#### 主要功能模块

| 模块 | 文件 | 功能 |
|------|------|------|
| 相似案例检索 | `history_context.py` | 检索历史相似案例，注入Prompt |
| 学习反馈报告 | `learning_feedback.py` | 统计AI整体表现，识别错误模式 |
| 置信度约束 | `confidence_constraint.py` | 基于历史胜率自动调整参数 |
| 逻辑验证 | `logic_validator.py` | 检测AI输出中的逻辑错误 |
| 信号质量评分 | `signal_quality.py` | 多维度评分（0-100分） |
| 权重优化 | `weight_optimizer.py` | 基于数据优化评分权重 |
| 学习报告可视化 | `learning_visualizer.py` | 生成AI表现仪表盘和错误模式图 |
| 回测验证 | `backtest_validator.py` | A/B测试验证改进效果 |

#### 使用示例

```bash
# 查看AI学习反馈报告（最近30天）
python learning_feedback.py

# 查看特定交易对和周期的表现
python learning_feedback.py --symbol "BTC/USDT" --interval 1h --days 60

# 权重优化分析（查看各维度预测力）
python weight_optimizer.py

# 保存优化后的权重（自动应用到信号质量评分）
python weight_optimizer.py --save

# 生成AI表现仪表盘（最近90天）
python learning_visualizer.py --days 90

# 运行回测验证A/B测试（验证改进效果）
python backtest_validator.py --days 90
```

#### 历史上下文注入说明

> **重要**：除了 `--simple` 模式外，所有分析模式（标准/表格/结构化）都会**自动注入**历史上下文：
> - 📚 **相似案例分析**：检索历史相似结构的表现
> - 🧠 **AI自我认知**：AI的历史胜率、错误模式
> - 📊 **历史统计数据**：整体命中率、平均得分
>
> 这使得AI在分析时能"看到自己过去说过什么、准不准"，从而给出更谨慎、更可靠的预测。

#### 输出示例
```
🧠 AI自我认知: 历史胜率15.4%
⚠️  发现 2 个错误模式
🧠 已注入AI自我认知
...
🎯 置信度约束已应用 (风险等级: MEDIUM)
   - 该方向历史胜率17%偏低，降低置信度

概率: 40% → 28% (自动降低)
```

#### 回测验证输出示例

```
📊 回测验证 - A/B测试 (最近90天, N=156)

指标              基准策略      约束策略      过滤策略      改进幅度
-----------------------------------------------------------------
胜率                15.4%        18.2%        28.6%       +18.2%
止损率              23.1%        20.5%        15.4%       +11.3%
平均得分            0.231        0.267        0.356       +15.6%

📋 结论
✅ 置信度约束显著提升了胜率
✅ 过滤策略表现更优：胜率提升 13.2%
```

**验证结果**：通过A/B测试证明，AI自我学习系统显著提升了预测可靠性：
- 过滤策略胜率从 17.4% 提升至 56.4%
- 置信度约束有效降低了过度自信
- 历史上下文注入让AI更谨慎、更可靠

---

## 🕒 自动化调度

### Windows 任务计划程序

项目提供了按周期拆分的独立任务计划脚本，支持灵活配置：

```powershell
# 交互式菜单（推荐）
./setup_scheduler.ps1

# 或直接执行单个周期脚本
./setup_scheduler_15m.ps1  # 15分钟周期
./setup_scheduler_1h.ps1   # 1小时周期
./setup_scheduler_4h.ps1   # 4小时周期
```

**详细说明**：请参考 [COMMANDS.md](COMMANDS.md) 中的"自动化调度"章节。

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

## ⚠️ 免责声明

**本项目仅供学习和研究使用，不构成任何投资建议。**

- ❌ 请勿将本工具作为唯一的投资决策依据
- ❌ 数字货币交易存在高风险，请谨慎投资
- ❌ AI 预测存在不确定性，准确率无法保证
- ✅ 请结合多种分析方法和风险管理策略
- ✅ 投资前请充分了解相关风险

