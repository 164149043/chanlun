# 缠论 AI 分析系统

> 基于 Binance 行情数据 + 缠论结构计算 + AI 智能决策的数字货币量化分析工具

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 📖 项目简介

本项目是一个将**传统缠论技术分析**与**AI 大模型**相结合的量化工具，旨在为数字货币交易者提供智能化的市场分析和决策支持。

### 核心特性

- 🔄 **实时行情获取**：通过 Binance REST API 获取现货 K 线数据
- 📊 **缠论结构计算**：自动识别笔、线段、中枢、买卖点、背驰等关键结构
- 🤖 **AI 智能分析**：支持 DeepSeek、Claude、GPT 等多种 AI 模型进行走势预测
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
git clone https://github.com/your-username/chanlun-ai.git
cd chanlun-ai/chanlun_ai
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
python chanlun_ai.py BTCUSDT 1h --structured --limit 200
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

4. **查看准确率**
   ```bash
   python query_stats.py --accuracy
   ```

---

## 🏗️ 项目架构

```
chanlun_ai/
├── ai/                          # AI 调用模块
│   ├── llm.py                  # LLM 统一接口
│   └── prompt_builder.py       # Prompt 模板（已废弃）
│
├── chanlun_local/              # 缠论计算引擎
│   ├── engine.py              # 核心计算逻辑
│   └── mapper.py              # 字段映射工具
│
├── output/                     # 分析报告输出目录
│
├── 核心业务模块
│   ├── binance.py             # Binance API 封装
│   ├── chanlun_adapter.py     # 数据适配器
│   ├── chanlun_icl.py         # ICL 接口封装
│   ├── ai_data_builder.py     # AI 输入数据构建器
│   ├── chanlun_ai_exporter.py # AI JSON 导出器
│   ├── ai_output_schema.py    # AI 输出验证
│   ├── output_formatter.py    # 终端输出格式化
│   └── prompt_builder.py      # Prompt 模板构造器
│
├── 程序入口
│   ├── chanlun_ai.py          # 主 CLI 工具
│   ├── query_stats.py         # 查询统计工具
│   └── evaluate_outcome.py    # 结果回填脚本
│
├── 配置文件
│   ├── .env                   # 环境变量（不上传）
│   ├── .env.example           # 配置示例
│   ├── .gitignore             # Git 忽略规则
│   ├── config.yaml            # 项目配置
│   └── requirements.txt       # Python 依赖
│
└── 文档
    ├── README.md              # 项目说明
    └── COMMANDS.md            # 命令行参数详解
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

### 表 1: `analysis_snapshot`（分析快照）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| symbol | TEXT | 交易对 |
| interval | TEXT | 周期 |
| timestamp | TEXT | 分析时间 |
| price | REAL | 当时价格 |
| chanlun_json | TEXT | 完整缠论结构 JSON |
| ai_json | TEXT | AI 输出 JSON |
| created_at | TEXT | 创建时间 |

### 表 2: `analysis_outcome`（结果回填）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| snapshot_id | INTEGER | 关联快照 ID |
| check_after_minutes | INTEGER | 评估间隔 |
| future_price | REAL | 未来价格 |
| max_price | REAL | 期间最高价 |
| min_price | REAL | 期间最低价 |
| result_direction | TEXT | 实际方向 |
| hit_scenario_rank | INTEGER | 命中的 scenario |
| note | TEXT | 备注 |
| checked_at | TEXT | 检查时间 |

---

## 🎯 功能特性

### 1. 缠论结构计算

- ✅ 笔（Bi）：自动识别向上笔和向下笔
- ✅ 线段（Segment）：基于笔计算线段
- ✅ 中枢（ZS）：识别震荡中枢和中枢关系
- ✅ 买卖点（MMD）：一买、二买、三买、一卖、二卖、三卖
- ✅ 背驰（BC）：笔背驰、段背驰

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

---

## 🛡️ 安全说明

### 敏感信息保护

- ✅ `.env` 文件已在 `.gitignore` 中排除
- ✅ API Key 不会上传到 GitHub
- ✅ 数据库文件不会上传
- ✅ 仅上传 `.env.example` 作为配置示例

### 推荐做法

1. **不要**直接在代码中硬编码 API Key
2. **使用** `.env` 文件管理敏感配置
3. **定期更换** API Key
4. **监控** API 使用量，避免超额

---

## 🤝 贡献指南

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

## 🙏 致谢

- [Binance API](https://binance-docs.github.io/apidocs/) - 提供免费的行情数据
- [缠论](https://baike.baidu.com/item/%E7%BC%A0%E8%AE%BA) - 技术分析理论基础
- [DeepSeek](https://www.deepseek.com/) - AI 模型支持
- [硅基流动](https://siliconflow.cn/) - AI 服务提供商

---

## 📞 联系方式

- **项目主页**：[https://github.com/your-username/chanlun-ai](https://github.com/your-username/chanlun-ai)
- **问题反馈**：[Issues](https://github.com/your-username/chanlun-ai/issues)

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
