# 缠论 AI 分析系统

> 基于 Binance 行情数据 + 缠论结构计算 + AI 智能决策的数字货币量化分析工具

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 📖 项目简介

本项目是一个将**传统缠论技术分析**与**AI 大模型**相结合的量化工具，旨在为数字货币交易者提供智能化的市场分析和决策支持。

### 核心特性

- 🔄 **实时行情获取**：通过 Binance REST API 获取现货 K 线数据
- 📊 **缠论结构计算**：自动识别笔、线段、中枢、买卖点、背驰等关键结构（自实现简化版引擎）
- 🤖 **AI 智能分析**：支持 DeepSeek、Claude、GPT 等多种 AI 模型进行走势预测
- 📊 **策略概率分析**：自动计算并显示做多/做空/震荡策略的成功概率
- 💾 **数据库存储**：SQLite 本地存储，支持历史分析追溯
- 📈 **准确率统计**：自动回填预测结果，统计 AI 预测准确率
- 🛠️ **CLI 工具**：完整的命令行工具，支持多种分析模式

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

### 查看分析记录

```bash
# 显示所有统计
python query_stats.py

# 只显示快照列表
python query_stats.py --snapshots

# 只显示准确率统计
python query_stats.py --accuracy
```

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
   python query_stats.py --accuracy
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

在 `query_stats.py --accuracy` 中展示的：

- **平均得分** = 所有已评估记录的 score 平均值（0~1）
- 用于衡量“这批预测整体质量如何”，而不仅仅是命中率。
- 含义就是：
在所有已评估的预测中，每次预测的平均“质量”，0~1 之间，越接近 1 表示整体越常出现“方向对且到目标”的情况。
3. 如何解读 0.33 / 1.0 这种数字？
接近 1.0：大部分预测是“方向对 + 达目标”
接近 0.5：很多是“方向对但没到目标”，或者“好坏参半”
接近 0.0：要么经常止损，要么方向经常错，整体表现较弱
所以你看到终端里类似：
text
平均得分: 0.33 / 1.0
可以理解为：
系统历史上这批预测的整体质量 偏中下，大部分不是满分命中，也有不少方向错或止损的情况。

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
│   ├── evaluate_outcome.py    # 预测结果评估脚本（按时间间隔评估未来走势）
│   ├── query_stats.py         # 快照与结果的快速查询工具
│   └── stats_report.py        # 研究报告生成器（AI × 缠论结构统计）
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

- **`query_stats.py`**：快照/结果快速查看
  - **作用**：查看最近的分析快照、结果回填记录和简单的准确率统计
  - **示例**：
    ```bash
    # 最近快照
    python query_stats.py --snapshots

    # 回填结果
    python query_stats.py --outcomes

    # 准确率汇总
    python query_stats.py --accuracy
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
---

欢迎提交 Issue 和 Pull Request！

### 开发流程

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

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

---

## 📚 更多文档

- [命令行参数详解](COMMANDS.md)
- [API 文档](docs/API.md)（待补充）
- [开发指南](docs/DEVELOPMENT.md)（待补充）

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**
