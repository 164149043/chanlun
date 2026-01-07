# Windows 任务计划程序自动配置脚本
# 用于设置缠论 AI 分析的定时任务（每小时 / 每 4 小时自动运行）

# ========================================
# 配置参数
# ========================================

$ProjectPath = "C:\Users\16414\Desktop\Qoder\chanlun\"
$PythonExe = "$ProjectPath\venv\Scripts\python.exe"

# ========================================
# 任务 1: 每小时生成BTC分析快照
# ========================================

$TaskName1 = "ChanLun-AI-BTC-1h-Analysis"
$Action1 = New-ScheduledTaskAction -Execute $PythonExe -Argument "chanlun_ai.py BTCUSDT 1h --structured --limit 500" -WorkingDirectory $ProjectPath
$Trigger1 = New-ScheduledTaskTrigger -Once -At "00:00" -RepetitionInterval (New-TimeSpan -Hours 1)
$Settings1 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $TaskName1 -Action $Action1 -Trigger $Trigger1 -Settings $Settings1 -Description "每小时生成 BTCUSDT 1h 缠论 AI 分析快照" -Force
Write-Host "任务 1 已创建: $TaskName1" -ForegroundColor Green

# ========================================
# 任务 2: 每小时回填所有交易对预测结果
# ========================================

$TaskName2 = "ChanLun-AI-1h-Evaluate"
$Action2 = New-ScheduledTaskAction -Execute $PythonExe -Argument "evaluate_outcome.py 60" -WorkingDirectory $ProjectPath
$Trigger2 = New-ScheduledTaskTrigger -Once -At "00:05" -RepetitionInterval (New-TimeSpan -Hours 1)
$Settings2 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $TaskName2 -Action $Action2 -Trigger $Trigger2 -Settings $Settings2 -Description "每小时评估 60 分钟前的 AI 预测准确率" -Force
Write-Host "任务 2 已创建: $TaskName2" -ForegroundColor Green

# ========================================
# 任务 3: 每小时生成 ETH 分析快照
# ========================================

$TaskName3 = "ChanLun-AI-ETH-1h-Analysis"
$Action3 = New-ScheduledTaskAction -Execute $PythonExe -Argument "chanlun_ai.py ETHUSDT 1h --structured --limit 500" -WorkingDirectory $ProjectPath
$Trigger3 = New-ScheduledTaskTrigger -Once -At "00:00" -RepetitionInterval (New-TimeSpan -Hours 1)
$Settings3 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $TaskName3 -Action $Action3 -Trigger $Trigger3 -Settings $Settings3 -Description "每小时生成 ETHUSDT 1h 缠论 AI 分析快照" -Force
Write-Host "任务 3 已创建: $TaskName3" -ForegroundColor Green

# ========================================
# 完成
# ========================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "所有任务已创建完成" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "查看任务: 打开任务计划程序 taskschd.msc" -ForegroundColor Yellow
Write-Host ""
Write-Host "手动运行测试:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName ChanLun-AI-BTC-1h-Analysis" -ForegroundColor White
Write-Host "  Start-ScheduledTask -TaskName ChanLun-AI-1h-Evaluate" -ForegroundColor White
Write-Host "  Start-ScheduledTask -TaskName ChanLun-AI-ETH-1h-Analysis" -ForegroundColor White
Write-Host ""
Write-Host "删除任务:" -ForegroundColor Yellow
Write-Host ('  Unregister-ScheduledTask -TaskName ChanLun-AI-BTC-1h-Analysis -Confirm:$false') -ForegroundColor White
Write-Host ('  Unregister-ScheduledTask -TaskName ChanLun-AI-1h-Evaluate -Confirm:$false') -ForegroundColor White
Write-Host ('  Unregister-ScheduledTask -TaskName ChanLun-AI-ETH-1h-Analysis -Confirm:$false') -ForegroundColor White
Write-Host ""