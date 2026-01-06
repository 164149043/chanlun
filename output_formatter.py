"""终端输出格式化器

本模块的职责：
- 将 AI 分析结果格式化为适合终端查看的形式
- 提供简洁、清晰的输出样式
- 支持彩色输出（可选）
"""
from typing import Dict, Any, Optional


class OutputFormatter:
    """终端输出格式化器"""
    
    def __init__(self, use_color: bool = False):
        """初始化格式化器
        
        参数：
        - use_color: 是否使用彩色输出（需要 colorama 库）
        """
        self.use_color = use_color
    
    def format_summary(
        self,
        symbol: str,
        interval: str,
        summary: Dict[str, Any],
    ) -> str:
        """格式化简洁摘要
        
        参数：
        - symbol: 交易对
        - interval: 周期
        - summary: 摘要数据（来自 ChanlunAIExporter.export_summary）
        
        返回：
        - 格式化的摘要字符串
        """
        
        lines = []
        lines.append("")
        lines.append("=" * 60)
        lines.append(f"【{symbol} · {interval} 缠论结构快览】")
        lines.append("=" * 60)
        lines.append("")
        
        # 当前价格
        latest_price = summary.get("latest_price", 0)
        lines.append(f"💰 当前价格：{latest_price:,.2f}")
        lines.append("")
        
        # 中枢信息
        centers = summary.get("centers", [])
        if centers:
            for i, center in enumerate(centers):
                level = center.get("level", 1)
                high = center.get("high", 0)
                low = center.get("low", 0)
                relation = center.get("relation", "unknown")
                
                lines.append(f"🧱 中枢 #{i+1}（{level} 级）：{low:,.2f} ~ {high:,.2f}")
                lines.append(f"   关系：{self._translate_relation(relation)}")
        else:
            lines.append("🧱 中枢：暂无")
        lines.append("")
        
        # 最新一笔
        latest_bi = summary.get("latest_bi")
        if latest_bi and latest_bi["direction"]:
            direction = "↑ 向上" if latest_bi["direction"] == "up" else "↓ 向下"
            status = "（已完成）" if latest_bi["is_done"] else "（进行中）"
            lines.append(f"📊 最新一笔：{direction} {status}")
        else:
            lines.append("📊 最新一笔：数据不足")
        lines.append("")
        
        # 信号汇总
        signals = summary.get("signals", {})
        buy_sell = signals.get("buy_sell_points", [])
        divergences = signals.get("divergences", [])
        
        if buy_sell or divergences:
            lines.append("🚨 近期信号：")
            if buy_sell:
                lines.append(f"   买卖点：{', '.join(buy_sell)}")
            if divergences:
                lines.append(f"   背驰：{', '.join(divergences)}")
        else:
            lines.append("🚨 近期信号：无")
        lines.append("")
        
        # 统计信息
        bi_count = summary.get("bi_count", 0)
        segment_count = summary.get("segment_count", 0)
        lines.append(f"📈 结构统计：{bi_count} 笔 / {segment_count} 线段")
        lines.append("")
        lines.append("=" * 60)
        lines.append("")
        
        return "\n".join(lines)
    
    def format_analysis(self, analysis_text: str) -> str:
        """格式化 AI 分析结果
        
        参数：
        - analysis_text: AI 返回的分析文本
        
        返回：
        - 格式化的分析字符串
        """
        
        lines = []
        lines.append("")
        lines.append("=" * 60)
        lines.append("【AI 缠论分析】")
        lines.append("=" * 60)
        lines.append("")
        lines.append(analysis_text)
        lines.append("")
        lines.append("=" * 60)
        lines.append("")
        
        return "\n".join(lines)
    
    def format_error(self, error_msg: str) -> str:
        """格式化错误信息
        
        参数：
        - error_msg: 错误消息
        
        返回：
        - 格式化的错误字符串
        """
        
        lines = []
        lines.append("")
        lines.append("=" * 60)
        lines.append("❌ 错误")
        lines.append("=" * 60)
        lines.append("")
        lines.append(error_msg)
        lines.append("")
        lines.append("=" * 60)
        lines.append("")
        
        return "\n".join(lines)
    
    def _translate_relation(self, relation: str) -> str:
        """翻译中枢关系类型"""
        
        translations = {
            "expand": "扩展",
            "震荡": "震荡",
            "突破": "突破",
            "unknown": "未知",
        }
        
        return translations.get(relation, relation)


def format_cli_output(
    symbol: str,
    interval: str,
    summary: Dict[str, Any],
    analysis: Optional[str] = None,
    error: Optional[str] = None,
) -> str:
    """快捷函数：格式化完整的 CLI 输出
    
    参数：
    - symbol: 交易对
    - interval: 周期
    - summary: 摘要数据
    - analysis: AI 分析结果（可选）
    - error: 错误信息（可选）
    
    返回：
    - 完整的格式化输出
    """
    
    formatter = OutputFormatter()
    output = []
    
    # 摘要
    output.append(formatter.format_summary(symbol, interval, summary))
    
    # AI 分析
    if analysis:
        output.append(formatter.format_analysis(analysis))
    
    # 错误信息
    if error:
        output.append(formatter.format_error(error))
    
    return "\n".join(output)
