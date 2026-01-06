# Windows 任务计划程序自动配置脚本
# 用于设置缠论 AI 分析的定时任务（每小时 / 每 4 小时自动运行）
#
# 使用说明：
# 1. 请先确认 Python 路径：
#    - 如果使用虚拟环境：保持 $ProjectPath 和 $PythonExe 配置不变
#    - 如果使用全局 Python：将 $PythonExe 修改为例如 "C:\\Users\\16414\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"
# 2. 执行方式（以 PowerShell 7 为例）：
#    - 打开 PowerShell，切换到本脚本所在目录
#    - 运行：`./setup_scheduler.ps1`
# 3. 创建的任务：
#    - ChanLun-AI-1h-Analysis：每小时跑一次 1h 分析（--structured，会写入数据库）
#    - ChanLun-AI-1h-Evaluate：每小时评估 60 分钟前的预测结果
#    - ChanLun-AI-4h-Analysis：每 4 小时跑一次 4h 分析
#    - ChanLun-AI-4h-Evaluate：每 4 小时评估 240 分钟前的预测结果
#
# 如需修改交易对 / 周期 / 频率，只需要改下面的 -Argument 或 -RepetitionInterval 参数即可。

# ========================================
# 配置参数
# ========================================

# 项目路径：指向 chanlun_ai 目录
$ProjectPath = "C:\Users\16414\Desktop\Qoder\Chanlun\chanlun_ai"
# Python 解释器路径：默认指向项目虚拟环境中的 python.exe
$PythonExe = "$ProjectPath\venv\Scripts\python.exe"

# ========================================
# 任务 1: 每小时生成分析快照
# ========================================

$TaskName1 = "ChanLun-AI-1h-Analysis"
$Action1 = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "chanlun_ai.py BTCUSDT 1h --structured --limit 500" `
    -WorkingDirectory $ProjectPath

$Trigger1 = New-ScheduledTaskTrigger `
    -Once `
    -At "00:00" `
    -RepetitionInterval (New-TimeSpan -Hours 1)

$Settings1 = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName1 `
    -Action $Action1 `
    -Trigger $Trigger1 `
    -Settings $Settings1 `
    -Description "每小时生成 BTCUSDT 1h 缠论 AI 分析快照" `
    -Force

Write-Host "✓ 任务 1 已创建: $TaskName1" -ForegroundColor Green

# ========================================
# 任务 2: 每小时回填预测结果
# ========================================

$TaskName2 = "ChanLun-AI-1h-Evaluate"
$Action2 = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "evaluate_outcome.py 60" `
    -WorkingDirectory $ProjectPath

$Trigger2 = New-ScheduledTaskTrigger `
    -Once `
    -At "00:05" `
    -RepetitionInterval (New-TimeSpan -Hours 1)

$Settings2 = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName2 `
    -Action $Action2 `
    -Trigger $Trigger2 `
    -Settings $Settings2 `
    -Description "每小时评估 60 分钟前的 AI 预测准确率" `
    -Force

Write-Host "✓ 任务 2 已创建: $TaskName2" -ForegroundColor Green

# ========================================
# 任务 3: 每 4 小时生成分析快照（可选）
# ========================================

$TaskName3 = "ChanLun-AI-4h-Analysis"
$Action3 = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "chanlun_ai.py BTCUSDT 4h --structured --limit 400" `
    -WorkingDirectory $ProjectPath

$Trigger3 = New-ScheduledTaskTrigger `
    -Once `
    -At "00:00" `
    -RepetitionInterval (New-TimeSpan -Hours 4)

$Settings3 = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName3 `
    -Action $Action3 `
    -Trigger $Trigger3 `
    -Settings $Settings3 `
    -Description "每 4 小时生成 BTCUSDT 4h 缠论 AI 分析快照" `
    -Force

Write-Host "✓ 任务 3 已创建: $TaskName3" -ForegroundColor Green

# ========================================
# 任务 4: 每 4 小时回填预测结果（可选）
# ========================================

$TaskName4 = "ChanLun-AI-4h-Evaluate"
$Action4 = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "evaluate_outcome.py 240" `
    -WorkingDirectory $ProjectPath

$Trigger4 = New-ScheduledTaskTrigger `
    -Once `
    -At "00:10" `
    -RepetitionInterval (New-TimeSpan -Hours 4)

$Settings4 = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName4 `
    -Action $Action4 `
    -Trigger $Trigger4 `
    -Settings $Settings4 `
    -Description "每 4 小时评估 240 分钟前的 AI 预测准确率" `
    -Force

Write-Host "✓ 任务 4 已创建: $TaskName4" -ForegroundColor Green

# ========================================
# 完成
# ========================================

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "✅ 所有任务已创建完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "查看任务：" -ForegroundColor Yellow
Write-Host "  打开任务计划程序: taskschd.msc" -ForegroundColor White
Write-Host ""
Write-Host "手动运行任务测试：" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName '$TaskName1'" -ForegroundColor White
Write-Host "  Start-ScheduledTask -TaskName '$TaskName2'" -ForegroundColor White
Write-Host ""
Write-Host "删除任务：" -ForegroundColor Yellow
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName1' -Confirm:" -NoNewline -ForegroundColor White
Write-Host "`$false" -ForegroundColor White
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName2' -Confirm:" -NoNewline -ForegroundColor White
Write-Host "`$false" -ForegroundColor White
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName3' -Confirm:" -NoNewline -ForegroundColor White
Write-Host "`$false" -ForegroundColor White
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName4' -Confirm:" -NoNewline -ForegroundColor White
Write-Host "`$false" -ForegroundColor White
Write-Host ""
