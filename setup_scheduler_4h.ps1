# Windows 任务计划程序自动配置脚本
# 用于设置缠论 AI 分析的定时任务（4小时周期）

# ========================================
# 配置参数
# ========================================

$ProjectPath = "C:\Users\16414\Desktop\Qoder\chanlun\"
$PythonExe = "$ProjectPath\venv\Scripts\python.exe"

# ========================================
# 任务 1: 每 4 小时生成 BTC 分析快照
# ========================================

$TaskName1 = "ChanLun-AI-BTC-4h-Analysis"
$Action1 = New-ScheduledTaskAction -Execute $PythonExe -Argument "chanlun_ai.py BTCUSDT 4h --structured --limit 500" -WorkingDirectory $ProjectPath
$Trigger1 = New-ScheduledTaskTrigger -Once -At "00:00" -RepetitionInterval (New-TimeSpan -Hours 4)
$Settings1 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $TaskName1 -Action $Action1 -Trigger $Trigger1 -Settings $Settings1 -Description "每 4 小时生成 BTCUSDT 4h 缠论 AI 分析快照" -Force
Write-Host "任务 1 已创建: $TaskName1" -ForegroundColor Green

# ========================================
# 任务 2: 每 4 小时生成 ETH 分析快照
# ========================================

$TaskName2 = "ChanLun-AI-ETH-4h-Analysis"
$Action2 = New-ScheduledTaskAction -Execute $PythonExe -Argument "chanlun_ai.py ETHUSDT 4h --structured --limit 500" -WorkingDirectory $ProjectPath
$Trigger2 = New-ScheduledTaskTrigger -Once -At "00:02" -RepetitionInterval (New-TimeSpan -Hours 4)
$Settings2 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $TaskName2 -Action $Action2 -Trigger $Trigger2 -Settings $Settings2 -Description "每 4 小时生成 ETHUSDT 4h 缠论 AI 分析快照" -Force
Write-Host "任务 2 已创建: $TaskName2" -ForegroundColor Green

# ========================================
# 完成
# ========================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "4小时周期任务已创建完成 (共 2 个任务)" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "查看任务: 打开任务计划程序 taskschd.msc" -ForegroundColor Yellow
Write-Host ""
Write-Host "手动运行测试:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName ChanLun-AI-BTC-4h-Analysis" -ForegroundColor White
Write-Host "  Start-ScheduledTask -TaskName ChanLun-AI-ETH-4h-Analysis" -ForegroundColor White
Write-Host ""
Write-Host "删除任务:" -ForegroundColor Yellow
Write-Host ('  Unregister-ScheduledTask -TaskName ChanLun-AI-BTC-4h-Analysis -Confirm:$false') -ForegroundColor White
Write-Host ('  Unregister-ScheduledTask -TaskName ChanLun-AI-ETH-4h-Analysis -Confirm:$false') -ForegroundColor White
Write-Host ""
