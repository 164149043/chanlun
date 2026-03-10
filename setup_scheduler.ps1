# Windows 任务计划程序自动配置脚本 - 主入口
# 用于设置缠论 AI 分析的定时任务
# 
# 说明：本脚本已拆分为 3 个独立的脚本文件，请根据需要选择执行：
# 
# 1. setup_scheduler_15m.ps1  - 15分钟周期任务（BTC、ETH）
# 2. setup_scheduler_1h.ps1   - 1小时周期任务（BTC、ETH）
# 3. setup_scheduler_4h.ps1   - 4小时周期任务（BTC、ETH）
#
# ========================================
# 使用说明
# ========================================
#
# 执行单个周期：
#   .\setup_scheduler_15m.ps1   # 仅创建15分钟任务
#   .\setup_scheduler_1h.ps1    # 仅创建1小时任务
#   .\setup_scheduler_4h.ps1    # 仅创建4小时任务
#
# 执行所有周期（本脚本）：
#   .\setup_scheduler.ps1        # 一次性创建所有任务
#
# ========================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "缠论 AI 任务计划程序配置" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "请选择要配置的任务周期：" -ForegroundColor Yellow
Write-Host ""
Write-Host "  [1] 15分钟周期 (BTC + ETH)" -ForegroundColor White
Write-Host "  [2] 1小时周期 (BTC + ETH)" -ForegroundColor White
Write-Host "  [3] 4小时周期 (BTC + ETH)" -ForegroundColor White
Write-Host "  [4] 全部周期 (6个任务)" -ForegroundColor White
Write-Host "  [0] 退出" -ForegroundColor White
Write-Host ""

$choice = Read-Host "请输入选项 (0-4)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "正在配置 15分钟周期任务..." -ForegroundColor Cyan
        & .\setup_scheduler_15m.ps1
    }
    "2" {
        Write-Host ""
        Write-Host "正在配置 1小时周期任务..." -ForegroundColor Cyan
        & .\setup_scheduler_1h.ps1
    }
    "3" {
        Write-Host ""
        Write-Host "正在配置 4小时周期任务..." -ForegroundColor Cyan
        & .\setup_scheduler_4h.ps1
    }
    "4" {
        Write-Host ""
        Write-Host "正在配置所有周期任务..." -ForegroundColor Cyan
        Write-Host ""
        & .\setup_scheduler_15m.ps1
        Write-Host ""
        & .\setup_scheduler_1h.ps1
        Write-Host ""
        & .\setup_scheduler_4h.ps1
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "所有任务配置完成！" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Cyan
    }
    "0" {
        Write-Host ""
        Write-Host "已取消配置" -ForegroundColor Yellow
        exit
    }
    default {
        Write-Host ""
        Write-Host "无效的选项，请重新运行脚本" -ForegroundColor Red
        exit
    }
}

Write-Host ""