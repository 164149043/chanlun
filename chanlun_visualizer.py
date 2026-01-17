# -*- coding: utf-8 -*-
"""缠论结构可视化模块（v2.0 优化版）

本模块提供缠论结构的图表展示功能：
- K线图（蜡烛图）
- 笔（连接分型的线段）
- 线段
- 中枢（矩形区域 + GG/DD 边界线）
- 买卖点和背驰标记（智能避让）
- MACD 副图（验证背驰）

使用方法：
    python chanlun_visualizer.py BTCUSDT 1h --limit 200
    python chanlun_visualizer.py BTCUSDT 1h --save output/chart.png
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class ChanlunVisualizer:
    """缠论结构可视化器（v2.0 优化版）"""
    
    # 颜色配置（中国股市惯例：红跌绿涨）
    COLORS = {
        # K线颜色（红跌绿涨）
        'up_candle': '#26a69a',      # 阳线/上涨（绿色）
        'down_candle': '#ef5350',    # 阴线/下跌（红色）
        
        # 笔颜色（红跌绿涨）
        'bi_up': '#4ecdc4',          # 向上笔（绿色）
        'bi_down': '#ff6b6b',        # 向下笔（红色）
        'bi_line_width': 1.5,
        
        # 线段颜色（红跌绿涨）
        'xd_up': '#2ecc71',          # 向上线段（深绿）
        'xd_down': '#e74c3c',        # 向下线段（深红）
        'xd_line_width': 2.5,
        
        # 中枢颜色
        'zs_fill': '#3498db',        # 中枢填充（蓝色）
        'zs_alpha': 0.2,             # 中枢透明度
        'zs_edge': '#2980b9',        # 中枢边框
        'zs_gg_dd': '#e67e22',       # GG/DD 边界线（橙色）
        
        # 买卖点颜色
        'buy_marker': '#e74c3c',     # 买点（红色）
        'sell_marker': '#27ae60',    # 卖点（绿色）
        
        # 背驰颜色
        'bc_marker': '#9b59b6',      # 背驰（紫色）
        
        # MACD 颜色（红跌绿涨）
        'macd_up': '#26a69a',        # MACD 绿柱（上涨）
        'macd_down': '#ef5350',      # MACD 红柱（下跌）
        'macd_dif': '#2196f3',       # DIF 线（蓝色）
        'macd_dea': '#ff9800',       # DEA 线（橙色）
    }
    
    def __init__(self, figsize: tuple = (16, 10)):
        """初始化可视化器
        
        参数：
        - figsize: 图表大小 (宽, 高)
        """
        self.figsize = figsize
        self.fig = None
        self.axes = None
    
    def plot(
        self,
        df: pd.DataFrame,
        icl: Any,
        symbol: str = "",
        interval: str = "",
        show_bi: bool = True,
        show_xd: bool = True,
        show_zs: bool = True,
        show_mmd: bool = True,
        show_bc: bool = True,
        show_macd: bool = True,
        last_n: int = None,
    ) -> plt.Figure:
        """绑制完整的缠论结构图
        
        参数：
        - df: K线数据 DataFrame（需包含 date, open, high, low, close）
        - icl: 缠论计算结果（ICL 对象）
        - symbol: 交易对名称
        - interval: 周期
        - show_bi: 是否显示笔
        - show_xd: 是否显示线段
        - show_zs: 是否显示中枢
        - show_mmd: 是否显示买卖点
        - show_bc: 是否显示背驰
        - show_macd: 是否显示 MACD 副图
        - last_n: 只显示最后 N 根K线（None 表示全部）
        
        返回：
        - matplotlib Figure 对象
        """
        # 准备数据
        plot_df = df.copy()
        start_idx = 0
        if last_n and len(plot_df) > last_n:
            start_idx = len(plot_df) - last_n
            plot_df = plot_df.tail(last_n).reset_index(drop=True)
        
        # 确保日期列是 datetime 类型
        if 'date' in plot_df.columns:
            plot_df['date'] = pd.to_datetime(plot_df['date'])
            plot_df = plot_df.set_index('date')
        
        # 创建图表
        self.fig, self.axes = plt.subplots(2, 1, figsize=self.figsize, 
                                           gridspec_kw={'height_ratios': [3, 1]},
                                           sharex=True)
        
        ax_main = self.axes[0]  # 主图（K线 + 缠论结构）
        ax_macd = self.axes[1]  # 副图（MACD）
        
        # 1. 绘制K线图
        self._plot_candlestick(ax_main, plot_df)
        
        # 获取缠论结构
        bis = icl.get_bis() if hasattr(icl, 'get_bis') else []
        xds = icl.get_xds() if hasattr(icl, 'get_xds') else []
        bi_zss = icl.get_bi_zss() if hasattr(icl, 'get_bi_zss') else []
        
        # 过滤在显示范围内的结构
        if last_n:
            start_time = plot_df.index[0]
            end_time = plot_df.index[-1]
            bis = [bi for bi in bis if self._time_in_range(bi.end_time, start_time, end_time)]
            xds = [xd for xd in xds if self._time_in_range(xd.end_time, start_time, end_time)]
            bi_zss = [zs for zs in bi_zss if self._time_in_range(zs.end_time, start_time, end_time)]
        
        # 2. 绘制中枢（先画，在底层）
        if show_zs and bi_zss:
            self._plot_zhongshu(ax_main, bi_zss, plot_df)
        
        # 3. 绘制笔
        if show_bi and bis:
            self._plot_bi(ax_main, bis, plot_df)
        
        # 4. 绘制线段
        if show_xd and xds:
            self._plot_xd(ax_main, xds, plot_df)
        
        # 5. 绘制买卖点（带智能避让）
        if show_mmd:
            self._plot_mmd(ax_main, bis, xds, plot_df)
        
        # 6. 绘制背驰标记
        if show_bc:
            self._plot_bc(ax_main, bis, xds, plot_df)
        
        # 7. 绘制 MACD 副图
        if show_macd:
            self._plot_macd(ax_macd, icl, plot_df, start_idx)
        else:
            self._plot_subplot(ax_macd, plot_df)
        
        # 设置标题和图例
        title = f"{symbol} {interval} 缠论结构图" if symbol else "缠论结构图"
        ax_main.set_title(title, fontsize=14, fontweight='bold')
        
        # 添加图例
        self._add_legend(ax_main)
        
        # 格式化 x 轴日期
        ax_main.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        ax_main.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax_main.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # 添加网格
        ax_main.grid(True, alpha=0.3)
        ax_macd.grid(True, alpha=0.3)
        
        # 调整布局
        plt.tight_layout()
        
        return self.fig
    
    def _time_in_range(self, t: Any, start: Any, end: Any) -> bool:
        """检查时间是否在范围内"""
        try:
            t = pd.to_datetime(t)
            return start <= t <= end
        except:
            return True
    
    def _plot_candlestick(self, ax: plt.Axes, df: pd.DataFrame) -> None:
        """绘制K线图（蜡烛图）"""
        
        # 计算K线宽度
        if len(df) > 1:
            width = (df.index[1] - df.index[0]).total_seconds() / 86400 * 0.8
        else:
            width = 0.5
        
        for idx in range(len(df)):
            row = df.iloc[idx]
            date = df.index[idx]
            open_price = row['open']
            close_price = row['close']
            high_price = row['high']
            low_price = row['low']
            
            # 确定颜色
            if close_price >= open_price:
                color = self.COLORS['up_candle']
                body_bottom = open_price
                body_height = close_price - open_price
            else:
                color = self.COLORS['down_candle']
                body_bottom = close_price
                body_height = open_price - close_price
            
            # 绘制影线
            ax.plot([date, date], [low_price, high_price], color=color, linewidth=0.8)
            
            # 绘制实体
            if body_height > 0:
                rect = mpatches.Rectangle(
                    (mdates.date2num(date) - width/2, body_bottom),
                    width, body_height,
                    facecolor=color, edgecolor=color, linewidth=0.5
                )
                ax.add_patch(rect)
            else:
                # 十字星
                ax.plot([date, date], [open_price - 0.001, open_price + 0.001], 
                       color=color, linewidth=1)
        
        ax.set_ylabel('Price', fontsize=10)
    
    def _plot_bi(self, ax: plt.Axes, bis: List[Any], df: pd.DataFrame) -> None:
        """绘制笔"""
        
        for bi in bis:
            try:
                start_time = pd.to_datetime(bi.start_time)
                end_time = pd.to_datetime(bi.end_time)
                start_price = bi.start_price
                end_price = bi.end_price
                
                # 确定颜色
                color = self.COLORS['bi_up'] if bi.type == 'up' else self.COLORS['bi_down']
                
                # 绘制笔
                ax.plot(
                    [start_time, end_time],
                    [start_price, end_price],
                    color=color,
                    linewidth=self.COLORS['bi_line_width'],
                    alpha=0.8,
                    zorder=5,
                )
                
                # 在端点绘制小圆点
                ax.scatter([start_time], [start_price], color=color, s=20, zorder=6)
                ax.scatter([end_time], [end_price], color=color, s=20, zorder=6)
                
            except Exception as e:
                continue
    
    def _plot_xd(self, ax: plt.Axes, xds: List[Any], df: pd.DataFrame) -> None:
        """绘制线段"""
        
        for xd in xds:
            try:
                start_time = pd.to_datetime(xd.start_time)
                end_time = pd.to_datetime(xd.end_time)
                start_price = xd.start_price
                end_price = xd.end_price
                
                # 确定颜色
                color = self.COLORS['xd_up'] if xd.type == 'up' else self.COLORS['xd_down']
                
                # 绘制线段（更粗的线）
                ax.plot(
                    [start_time, end_time],
                    [start_price, end_price],
                    color=color,
                    linewidth=self.COLORS['xd_line_width'],
                    alpha=0.9,
                    linestyle='--',
                    zorder=4,
                )
                
            except Exception as e:
                continue
    
    def _plot_zhongshu(self, ax: plt.Axes, zss: List[Any], df: pd.DataFrame) -> None:
        """绘制中枢（含 GG/DD 边界线）"""
        
        for zs in zss:
            try:
                start_time = pd.to_datetime(zs.start_time)
                end_time = pd.to_datetime(zs.end_time)
                zg = zs.zg  # 中枢高点（ZG）
                zd = zs.zd  # 中枢低点（ZD）
                
                # 获取 GG/DD（如果有）
                gg = getattr(zs, 'gg', None) or zg  # 最高点
                dd = getattr(zs, 'dd', None) or zd  # 最低点
                
                # 绘制中枢矩形（ZG-ZD 区间）
                start_num = mdates.date2num(start_time)
                end_num = mdates.date2num(end_time)
                width = end_num - start_num
                height = zg - zd
                
                rect = mpatches.Rectangle(
                    (start_num, zd),
                    width, height,
                    facecolor=self.COLORS['zs_fill'],
                    edgecolor=self.COLORS['zs_edge'],
                    alpha=self.COLORS['zs_alpha'],
                    linewidth=1.5,
                    zorder=2,
                )
                ax.add_patch(rect)
                
                # 绘制 GG/DD 边界线（如果不等于 ZG/ZD）
                if gg > zg:
                    ax.hlines(y=gg, xmin=start_time, xmax=end_time,
                             colors=self.COLORS['zs_gg_dd'], linestyles='--',
                             linewidth=1, alpha=0.7, zorder=2)
                    ax.text(end_time, gg, ' GG', fontsize=6, va='center',
                           color=self.COLORS['zs_gg_dd'], alpha=0.8)
                
                if dd < zd:
                    ax.hlines(y=dd, xmin=start_time, xmax=end_time,
                             colors=self.COLORS['zs_gg_dd'], linestyles='--',
                             linewidth=1, alpha=0.7, zorder=2)
                    ax.text(end_time, dd, ' DD', fontsize=6, va='center',
                           color=self.COLORS['zs_gg_dd'], alpha=0.8)
                
                # 在中枢中心标注级别
                center_x = start_time + (end_time - start_time) / 2
                center_y = (zg + zd) / 2
                ax.text(
                    center_x, center_y,
                    f"ZS{zs.index}",
                    fontsize=8,
                    ha='center', va='center',
                    color=self.COLORS['zs_edge'],
                    fontweight='bold',
                    zorder=3,
                )
                
            except Exception as e:
                continue
    
    def _plot_mmd(self, ax: plt.Axes, bis: List[Any], xds: List[Any], df: pd.DataFrame) -> None:
        """绘制买卖点（带智能标签避让）"""
        
        # 收集所有买卖点
        all_points = []
        
        # 从笔中收集
        for bi in bis:
            for mmd in getattr(bi, 'mmds', []) or []:
                name = getattr(mmd, 'name', '')
                point_type = 'buy' if 'buy' in name.lower() else 'sell' if 'sell' in name.lower() else None
                if point_type:
                    all_points.append({
                        'time': bi.end_time,
                        'price': bi.end_price,
                        'name': name,
                        'type': point_type,
                    })
        
        # 从线段中收集
        for xd in xds:
            for mmd in getattr(xd, 'mmds', []) or []:
                name = getattr(mmd, 'name', '')
                point_type = 'buy' if 'buy' in name.lower() else 'sell' if 'sell' in name.lower() else None
                if point_type:
                    all_points.append({
                        'time': xd.end_time,
                        'price': xd.end_price,
                        'name': name,
                        'type': point_type,
                    })
        
        # 按时间排序
        all_points.sort(key=lambda x: pd.to_datetime(x['time']))
        
        # 智能避让：计算标签位置偏移
        label_positions = self._calculate_label_offsets(all_points, df)
        
        # 绘制买卖点
        for i, point in enumerate(all_points):
            try:
                t = pd.to_datetime(point['time'])
                p = point['price']
                is_buy = point['type'] == 'buy'
                
                # 标记符号
                marker = '^' if is_buy else 'v'
                color = self.COLORS['buy_marker'] if is_buy else self.COLORS['sell_marker']
                
                ax.scatter([t], [p], marker=marker, s=100, 
                          color=color, zorder=10,
                          edgecolors='white', linewidth=1)
                
                # 获取智能偏移位置
                offset_x, offset_y = label_positions.get(i, (0, -15 if is_buy else 15))
                
                ax.annotate(point['name'], (t, p), textcoords="offset points",
                           xytext=(offset_x, offset_y), ha='center', fontsize=7,
                           color=color, fontweight='bold',
                           bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                   edgecolor=color, alpha=0.8))
            except:
                continue
    
    def _calculate_label_offsets(self, points: List[Dict], df: pd.DataFrame) -> Dict[int, Tuple[int, int]]:
        """计算标签的智能偏移位置，避免重叠
        
        返回：{点索引: (x偏移, y偏移)}
        """
        if not points or len(df) == 0:
            return {}
        
        # 计算价格范围用于归一化
        price_range = df['high'].max() - df['low'].min()
        if price_range == 0:
            price_range = 1
        
        offsets = {}
        occupied = []  # 已占用的位置 [(time_num, price_norm, offset_y)]
        
        for i, point in enumerate(points):
            try:
                t = pd.to_datetime(point['time'])
                t_num = mdates.date2num(t)
                p_norm = (point['price'] - df['low'].min()) / price_range
                is_buy = point['type'] == 'buy'
                
                # 默认偏移
                base_y = -18 if is_buy else 18
                
                # 检查是否与已有标签冲突
                best_offset = (0, base_y)
                min_conflict = float('inf')
                
                # 尝试不同的偏移组合
                for dx in [0, -20, 20, -40, 40]:
                    for dy_mult in [1, 1.5, 2, 2.5]:
                        test_y = base_y * dy_mult
                        conflict_score = 0
                        
                        for occ_t, occ_p, occ_y in occupied:
                            # 计算距离
                            dt = abs(t_num - occ_t) * 1000  # 时间距离
                            dp = abs(p_norm - occ_p) * 100   # 价格距离
                            dy = abs(test_y - occ_y)         # y偏移距离
                            
                            # 如果距离太近，增加冲突分数
                            if dt < 50 and dp < 10:
                                conflict_score += max(0, 50 - dt) + max(0, 30 - dy)
                        
                        if conflict_score < min_conflict:
                            min_conflict = conflict_score
                            best_offset = (dx, test_y)
                
                offsets[i] = (int(best_offset[0]), int(best_offset[1]))
                occupied.append((t_num, p_norm, best_offset[1]))
                
            except:
                offsets[i] = (0, -18 if point.get('type') == 'buy' else 18)
        
        return offsets
    
    def _plot_bc(self, ax: plt.Axes, bis: List[Any], xds: List[Any], df: pd.DataFrame) -> None:
        """绘制背驰标记"""
        
        bc_points = []
        
        # 从笔中收集
        for bi in bis:
            bcs = getattr(bi, 'bcs', []) or []
            for bc in bcs:
                if getattr(bc, 'bc', False):
                    bc_points.append({
                        'time': bi.end_time,
                        'price': bi.end_price,
                        'type': getattr(bc, 'type', 'bi'),
                    })
        
        # 从线段中收集
        for xd in xds:
            bcs = getattr(xd, 'bcs', []) or []
            for bc in bcs:
                if getattr(bc, 'bc', False):
                    bc_points.append({
                        'time': xd.end_time,
                        'price': xd.end_price,
                        'type': getattr(bc, 'type', 'xd'),
                    })
        
        # 绘制背驰标记
        for bp in bc_points:
            try:
                t = pd.to_datetime(bp['time'])
                p = bp['price']
                ax.scatter([t], [p], marker='*', s=150,
                          color=self.COLORS['bc_marker'], zorder=11,
                          edgecolors='white', linewidth=0.5)
                ax.annotate('BC', (t, p), textcoords="offset points",
                           xytext=(10, 0), ha='left', fontsize=7,
                           color=self.COLORS['bc_marker'], fontweight='bold')
            except:
                continue
    
    def _plot_macd(self, ax: plt.Axes, icl: Any, df: pd.DataFrame, start_idx: int = 0) -> None:
        """绘制 MACD 副图
        
        参数：
        - ax: matplotlib Axes 对象
        - icl: 缠论计算结果
        - df: 显示范围内的 K 线数据（已设置 date 为 index）
        - start_idx: 原始数据中的起始索引（用于截取 MACD）
        """
        # 获取 MACD 数据
        macd_data = icl.get_macd_data() if hasattr(icl, 'get_macd_data') else None
        
        if not macd_data or not macd_data.get('hist'):
            # 如果没有 MACD 数据，回退到价格变化图
            self._plot_subplot(ax, df)
            return
        
        # 截取显示范围内的数据
        dates = macd_data['dates'][start_idx:]
        dif = macd_data['dif'][start_idx:]
        dea = macd_data['dea'][start_idx:]
        hist = macd_data['hist'][start_idx:]
        
        if len(dates) == 0:
            return
        
        # 转换日期
        dates = pd.to_datetime(dates)
        
        # 计算柱状图宽度
        if len(dates) > 1:
            width = (dates[1] - dates[0]).total_seconds() / 86400 * 0.8
        else:
            width = 0.5
        
        # 绘制 MACD 柱状图
        colors = [self.COLORS['macd_up'] if h >= 0 else self.COLORS['macd_down'] for h in hist]
        ax.bar(dates, hist, color=colors, alpha=0.7, width=width)
        
        # 绘制 DIF 和 DEA 线
        ax.plot(dates, dif, color=self.COLORS['macd_dif'], linewidth=1, label='DIF', alpha=0.9)
        ax.plot(dates, dea, color=self.COLORS['macd_dea'], linewidth=1, label='DEA', alpha=0.9)
        
        # 绘制零轴
        ax.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)
        
        # 设置标签和图例
        ax.set_ylabel('MACD', fontsize=10)
        ax.legend(loc='upper left', fontsize=7, framealpha=0.8)
    
    def _plot_subplot(self, ax: plt.Axes, df: pd.DataFrame) -> None:
        """绘制副图（价格变化率 - 备用）"""
        
        # 绘制价格变化率
        if len(df) > 1:
            returns = df['close'].pct_change() * 100
            colors = ['red' if r >= 0 else 'green' for r in returns]
            ax.bar(df.index, returns, color=colors, alpha=0.6, width=0.8)
            ax.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)
            ax.set_ylabel('Change %', fontsize=10)
    
    def _add_legend(self, ax: plt.Axes) -> None:
        """添加图例"""
        
        legend_elements = [
            mpatches.Patch(color=self.COLORS['bi_up'], label='Up Bi', alpha=0.8),
            mpatches.Patch(color=self.COLORS['bi_down'], label='Down Bi', alpha=0.8),
            mpatches.Patch(color=self.COLORS['zs_fill'], label='ZhongShu', alpha=0.3),
            plt.scatter([], [], marker='^', s=80, color=self.COLORS['buy_marker'], label='Buy'),
            plt.scatter([], [], marker='v', s=80, color=self.COLORS['sell_marker'], label='Sell'),
            plt.scatter([], [], marker='*', s=100, color=self.COLORS['bc_marker'], label='BeiChi'),
        ]
        
        ax.legend(handles=legend_elements, loc='upper left', fontsize=8, framealpha=0.9)
    
    def save(self, filepath: str, dpi: int = 150) -> None:
        """保存图表到文件
        
        参数：
        - filepath: 保存路径
        - dpi: 图像分辨率
        """
        if self.fig:
            self.fig.savefig(filepath, dpi=dpi, bbox_inches='tight',
                           facecolor='white', edgecolor='none')
            print(f"[OK] 图表已保存: {filepath}")
    
    def show(self) -> None:
        """显示图表"""
        if self.fig:
            plt.show()


def visualize_chanlun(
    symbol: str,
    interval: str,
    limit: int = 200,
    save_path: str = None,
    show: bool = True,
    last_n: int = None,
    show_macd: bool = True,
) -> Optional[plt.Figure]:
    """快捷函数：获取数据并绘制缠论图
    
    参数：
    - symbol: 交易对，如 "BTCUSDT"
    - interval: 周期，如 "1h"
    - limit: K线数量
    - save_path: 保存路径（可选）
    - show: 是否显示图表
    - last_n: 只显示最后 N 根K线
    - show_macd: 是否显示 MACD 副图
    
    返回：
    - matplotlib Figure 对象
    """
    from binance import get_klines
    from chanlun_adapter import convert_to_chanlun_bars
    from chanlun_icl import ICL
    
    print(f"[INFO] 获取 {symbol} {interval} K线数据...")
    klines = get_klines(symbol, interval, limit=limit)
    print(f"[OK] 获取到 {len(klines)} 根 K 线")
    
    print("[INFO] 转换K线格式...")
    bars = convert_to_chanlun_bars(klines)
    df = pd.DataFrame(bars)
    df = df.rename(columns={
        "date": "date",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "a": "volume",
    })
    
    print("[INFO] 计算缠论结构...")
    frequency_map = {
        "1m": "1m", "5m": "5m", "15m": "15m",
        "1h": "60m", "4h": "240m", "1d": "1440m"
    }
    frequency = frequency_map.get(interval.lower(), interval)
    
    display_symbol = f"{symbol[:3]}/{symbol[3:]}" if len(symbol) > 3 else symbol
    icl = ICL(code=display_symbol, frequency=frequency, config={})
    icl = icl.process_klines(df)
    
    # 统计信息
    bis = icl.get_bis()
    xds = icl.get_xds()
    bi_zss = icl.get_bi_zss()
    
    print(f"[OK] 笔: {len(bis)}, 线段: {len(xds)}, 中枢: {len(bi_zss)}")
    
    print("[INFO] 生成图表...")
    visualizer = ChanlunVisualizer(figsize=(16, 10))
    fig = visualizer.plot(
        df=df,
        icl=icl,
        symbol=display_symbol,
        interval=interval.upper(),
        last_n=last_n,
        show_macd=show_macd,
    )
    
    if save_path:
        visualizer.save(save_path)
    
    if show:
        visualizer.show()
    
    return fig


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="缠论结构可视化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python chanlun_visualizer.py BTCUSDT 1h
  python chanlun_visualizer.py ETHUSDT 4h --limit 300
  python chanlun_visualizer.py BTCUSDT 1h --save output/btc_1h.png
  python chanlun_visualizer.py BTCUSDT 1h --last 100
        """
    )
    
    parser.add_argument("symbol", type=str, help="交易对，如: BTCUSDT")
    parser.add_argument("interval", type=str, help="周期，如: 1m, 5m, 15m, 1h, 4h, 1d")
    parser.add_argument("--limit", type=int, default=200, help="K线数量 (默认: 200)")
    parser.add_argument("--save", type=str, help="保存图表到文件")
    parser.add_argument("--no-show", action="store_true", help="不显示图表窗口")
    parser.add_argument("--no-macd", action="store_true", help="不显示 MACD 副图")
    parser.add_argument("--last", type=int, help="只显示最后 N 根K线")
    
    args = parser.parse_args()
    
    symbol = args.symbol.upper().replace("/", "")
    interval = args.interval.lower()
    
    try:
        visualize_chanlun(
            symbol=symbol,
            interval=interval,
            limit=args.limit,
            save_path=args.save,
            show=not args.no_show,
            last_n=args.last,
            show_macd=not args.no_macd,
        )
    except KeyboardInterrupt:
        print("\n[WARN] 用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
