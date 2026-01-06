# 命令行参数说明文档

## 🚀 主程序：chanlun_ai.py

### 基础用法
```bash
python chanlun_ai.py <交易对> <周期> [选项]
```

### 必需参数

#### 1. `<交易对>` (symbol)
- **说明**：要分析的加密货币交易对
- **格式**：BTCUSDT, ETHUSDT, BNBUSDT 等（不带斜杠）
- **示例**：
  ```bash
  python chanlun_ai.py BTCUSDT 1h
  python chanlun_ai.py ETHUSDT 4h
  ```

#### 2. `<周期>` (interval)
- **说明**：K线时间周期
- **可选值**：
  - `1m` - 1分钟
  - `5m` - 5分钟
  - `15m` - 15分钟
  - `1h` - 1小时（推荐）
  - `4h` - 4小时
  - `1d` - 1天
- **示例**：
  ```bash
  python chanlun_ai.py BTCUSDT 1h   # 1小时周期
  python chanlun_ai.py BTCUSDT 4h   # 4小时周期
  ```

---

### 可选参数

#### `--limit <数量>`
- **说明**：指定获取的K线数量
- **默认值**：500
- **推荐值**：200（避免超时）
- **示例**：
  ```bash
  python chanlun_ai.py BTCUSDT 1h --limit 200
  python chanlun_ai.py BTCUSDT 1h --limit 100
  ```

#### `--save`
- **说明**：保存完整分析报告到 `output/` 目录
- **输出格式**：Markdown (.md)
- **文件命名**：`analysis_<交易对>_<周期>_<时间戳>.md`
- **示例**：
  ```bash
  python chanlun_ai.py BTCUSDT 1h --save
  # 输出：output/analysis_BTCUSDT_1h_20260105_223000.md
  ```

#### `--simple`
- **说明**：使用简化版 Prompt，输出更简洁的分析
- **特点**：
  - 速度更快
  - 输出3-5句话总结
  - 不保存到数据库
- **示例**：
  ```bash
  python chanlun_ai.py BTCUSDT 1h --simple
  ```

#### `--structured`
- **说明**：强制 AI 输出结构化 JSON 格式
- **特点**：
  - 输出符合预定义 Schema 的 JSON
  - 自动保存到数据库（用于后续准确率统计）
  - 包含三重验证（JSON解析、字段校验、概率校验）
- **推荐**：用于数据积累和准确率分析
- **示例**：
  ```bash
  python chanlun_ai.py BTCUSDT 1h --structured --limit 200
  ```

#### `--table`
- **说明**：使用表格格式 Prompt，输出标准化 Markdown 报告
- **输出包含**：
  - 技术形态概述
  - 当前市场状态
  - 关键技术信号
  - 可能走势分析（概率排序）
  - 操作建议（多头/空头/震荡策略）
  - 风险提示
- **示例**：
  ```bash
  python chanlun_ai.py BTCUSDT 1h --table
  ```

#### `--no-ai`
- **说明**：仅显示缠论结构，不调用 AI 分析
- **用途**：
  - 快速查看缠论计算结果
  - 测试缠论引擎是否正常
  - 不消耗 API 额度
- **示例**：
  ```bash
  python chanlun_ai.py BTCUSDT 1h --no-ai
  ```

---

### 参数组合示例

#### 1. 日常分析（推荐）
```bash
# 结构化输出 + 200根K线 + 保存报告
python chanlun_ai.py BTCUSDT 1h --structured --limit 200 --save
```

#### 2. 快速查看
```bash
# 简化分析，不保存
python chanlun_ai.py BTCUSDT 1h --simple --limit 100
```

#### 3. 标准格式报告
```bash
# 表格格式 + 结构化JSON
python chanlun_ai.py BTCUSDT 1h --table --structured --limit 200
```

#### 4. 测试功能
```bash
# 仅查看缠论结构，不调用AI
python chanlun_ai.py BTCUSDT 1h --no-ai
```

---

## 📊 辅助工具

### 1. query_stats.py - 查询统计工具

#### 基础用法
```bash
python query_stats.py [选项]
```

#### 可选参数

##### `--snapshots`
- **说明**：只显示分析快照列表
- **示例**：
  ```bash
  python query_stats.py --snapshots
  python query_stats.py --snapshots --limit 20
  ```

##### `--outcomes`
- **说明**：只显示结果回填记录
- **示例**：
  ```bash
  python query_stats.py --outcomes
  ```

##### `--accuracy`
- **说明**：只显示准确率统计
- **包含**：
  - 总体准确率
  - 按时间间隔统计
  - 按命中 rank 统计
  - 按走势方向统计
- **示例**：
  ```bash
  python query_stats.py --accuracy
  ```

##### `--limit <数量>`
- **说明**：查询记录数量
- **默认值**：10
- **示例**：
  ```bash
  python query_stats.py --limit 20
  ```

#### 完整示例
```bash
# 显示所有统计（默认）
python query_stats.py

# 只看最近20条快照
python query_stats.py --snapshots --limit 20

# 只看准确率统计
python query_stats.py --accuracy
```

---

### 2. evaluate_outcome.py - 结果回填工具

#### 基础用法
```bash
python evaluate_outcome.py [时间间隔]
```

#### 参数说明

##### `<时间间隔>` (check_after_minutes)
- **说明**：评估时间间隔（分钟）
- **默认值**：60（1小时）
- **常用值**：
  - `60` - 1小时后评估
  - `240` - 4小时后评估
  - `1440` - 1天后评估
- **示例**：
  ```bash
  python evaluate_outcome.py 60      # 评估1小时前的预测
  python evaluate_outcome.py 240     # 评估4小时前的预测
  python evaluate_outcome.py 1440    # 评估1天前的预测
  ```

#### 工作原理
1. 查找 N 分钟前生成的分析快照
2. 从 Binance 拉取未来 N 分钟的 K 线数据
3. 计算实际价格区间（最高/最低/收盘价）
4. 判断是否命中 AI 预测的 scenario
5. 保存结果到 `analysis_outcome` 表

#### 使用建议
```bash
# 设置定时任务，每小时自动回填
# Windows 任务计划程序：每小时运行
python evaluate_outcome.py 60

# Linux/Mac Crontab
# 每小时执行（延迟5分钟）
5 * * * * cd /path/to/chanlun_ai && python evaluate_outcome.py 60
```

---

## 🔑 环境变量配置

配置文件：`.env`

### 必需配置
```bash
# AI 服务提供商（siliconflow / openrouter / deepseek / anthropic）
AI_PROVIDER=siliconflow

# AI 模型名称
AI_MODEL=Pro/deepseek-ai/DeepSeek-V3.2

# API Key（根据 provider 选择对应的）
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxx
```

### 可选配置
```bash
# AI 调用参数
AI_TEMPERATURE=0.3        # 采样温度（0-1）
AI_MAX_TOKENS=4096        # 最大生成长度

# K线数据配置
DEFAULT_KLINE_LIMIT=200   # 默认K线数量
```

---

## 🕒 自动化调度（Windows 计划任务）

### setup_scheduler.ps1 - 一键创建定时任务

- **作用**：在 Windows 任务计划程序中，自动创建 4 个定时任务，用来定期运行分析和评估：
  - `ChanLun-AI-1h-Analysis`：每小时运行一次 `chanlun_ai.py BTCUSDT 1h --structured --limit 500`
  - `ChanLun-AI-1h-Evaluate`：每小时运行一次 `evaluate_outcome.py 60`
  - `ChanLun-AI-4h-Analysis`：每 4 小时运行一次 `chanlun_ai.py BTCUSDT 4h --structured --limit 400`
  - `ChanLun-AI-4h-Evaluate`：每 4 小时运行一次 `evaluate_outcome.py 240`

### 使用前准备

1. **确认 Python 路径**：
   - 如果你使用项目自带的虚拟环境：
     - 确保已经创建虚拟环境并安装依赖：
       ```bash
       cd chanlun_ai
       python -m venv venv
       venv\Scripts\pip install -r requirements.txt
       ```
     - 保持 `setup_scheduler.ps1` 中：
       ```powershell
       $ProjectPath = "C:\Users\16414\Desktop\Qoder\Chanlun\chanlun_ai"
       $PythonExe   = "$ProjectPath\venv\Scripts\python.exe"
       ```
   - 如果你使用全局 Python：
     - 把 `$PythonExe` 改成你自己的 Python 路径，例如：
       ```powershell
       $PythonExe = "C:\Users\你自己的路径\Python312\python.exe"
       ```

2. **确认项目路径**：
   - 如需移动项目目录，只要把 `$ProjectPath` 改成新的绝对路径即可。

### 执行脚本（PowerShell 7 示例）

```powershell
# 1. 打开 PowerShell（建议使用 PowerShell 7）
# 2. 切换到脚本所在目录
cd C:\Users\16414\Desktop\Qoder\Chanlun\chanlun_ai

# 3. 如果第一次运行脚本，可能需要临时放宽执行策略（只对当前进程生效）：
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 4. 执行脚本，自动创建所有任务
./setup_scheduler.ps1
```

### 查看 / 手动运行 / 删除任务

- **查看任务**：
  - 在开始菜单中打开：`任务计划程序 (taskschd.msc)`，在“任务计划程序库”里找到 `ChanLun-AI-*` 开头的任务。

- **手动运行任务测试**（PowerShell）：
  ```powershell
  Start-ScheduledTask -TaskName "ChanLun-AI-1h-Analysis"
  Start-ScheduledTask -TaskName "ChanLun-AI-1h-Evaluate"
  ```

- **删除任务**（如果不再需要自动运行）：
  ```powershell
  Unregister-ScheduledTask -TaskName "ChanLun-AI-1h-Analysis" -Confirm:$false
  Unregister-ScheduledTask -TaskName "ChanLun-AI-1h-Evaluate" -Confirm:$false
  Unregister-ScheduledTask -TaskName "ChanLun-AI-4h-Analysis" -Confirm:$false
  Unregister-ScheduledTask -TaskName "ChanLun-AI-4h-Evaluate" -Confirm:$false
  ```

> 提示：如果计划任务创建后没有跑起来，可以检查：
> - `$PythonExe` 路径是否正确
> - `venv` 是否存在、依赖是否安装
> - 任务的“起始于”目录是否为 `chanlun_ai`（脚本里已通过 `-WorkingDirectory` 设置）

### Q1: 如何避免超时？
**A**: 减少 K 线数量
```bash
python chanlun_ai.py BTCUSDT 1h --structured --limit 200
```

### Q2: 如何只测试缠论计算？
**A**: 使用 `--no-ai` 参数
```bash
python chanlun_ai.py BTCUSDT 1h --no-ai
```

### Q3: 如何查看历史分析记录？
**A**: 使用 `query_stats.py`
```bash
python query_stats.py --snapshots
```

### Q4: 如何统计 AI 准确率？
**A**: 先生成分析（`--structured`），等待1小时后回填
```bash
# 生成分析
python chanlun_ai.py BTCUSDT 1h --structured --limit 200

# 1小时后回填
python evaluate_outcome.py 60

# 查看准确率
python query_stats.py --accuracy
```

### Q5: 命令行参数拼写错误怎么办？
**A**: 查看帮助信息
```bash
python chanlun_ai.py --help
```

---

## 📋 快速参考

| 命令 | 说明 |
|------|------|
| `python chanlun_ai.py BTCUSDT 1h` | 基础分析 |
| `--limit 200` | 使用200根K线 |
| `--save` | 保存报告 |
| `--simple` | 简化分析 |
| `--structured` | 结构化JSON（保存数据库）|
| `--table` | 表格格式Markdown |
| `--no-ai` | 仅显示结构 |
| `python query_stats.py` | 查看统计 |
| `python evaluate_outcome.py 60` | 1小时后回填 |
