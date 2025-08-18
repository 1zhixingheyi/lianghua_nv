"""
回测结果可视化模块
================

提供回测结果的图表可视化功能，包括权益曲线、回撤图、收益分布等。
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Dict, List, Optional, Any, Tuple
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

class BacktestVisualizer:
    """回测结果可视化器"""
    
    def __init__(self, figsize: Tuple[int, int] = (15, 10)):
        """
        初始化可视化器
        
        Args:
            figsize: 图表尺寸
        """
        self.figsize = figsize
        self.color_palette = sns.color_palette("husl", 8)
        
    def plot_equity_curve(
        self,
        equity_curve: pd.Series,
        benchmark: Optional[pd.Series] = None,
        title: str = "权益曲线",
        save_path: Optional[str] = None
    ):
        """
        绘制权益曲线
        
        Args:
            equity_curve: 权益曲线数据
            benchmark: 基准数据（可选）
            title: 图表标题
            save_path: 保存路径（可选）
        """
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # 绘制权益曲线
        ax.plot(equity_curve.index, equity_curve.values, 
                label="策略权益", color=self.color_palette[0], linewidth=2)
        
        # 绘制基准线（如果提供）
        if benchmark is not None:
            # 将基准数据归一化到相同起点
            aligned_benchmark = benchmark.reindex(equity_curve.index).fillna(method='ffill')
            if not aligned_benchmark.empty:
                normalized_benchmark = aligned_benchmark / aligned_benchmark.iloc[0] * equity_curve.iloc[0]
                ax.plot(normalized_benchmark.index, normalized_benchmark.values,
                        label="基准", color=self.color_palette[1], linewidth=2, alpha=0.7)
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_xlabel("日期", fontsize=12)
        ax.set_ylabel("权益价值", fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # 格式化x轴日期
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_drawdown(
        self,
        equity_curve: pd.Series,
        title: str = "回撤分析",
        save_path: Optional[str] = None
    ):
        """
        绘制回撤图
        
        Args:
            equity_curve: 权益曲线数据
            title: 图表标题
            save_path: 保存路径（可选）
        """
        # 计算回撤
        peak = equity_curve.expanding().max()
        drawdown = (equity_curve - peak) / peak
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=self.figsize, 
                                       gridspec_kw={'height_ratios': [2, 1]})
        
        # 上图：权益曲线和峰值
        ax1.plot(equity_curve.index, equity_curve.values, 
                label="权益曲线", color=self.color_palette[0], linewidth=2)
        ax1.plot(peak.index, peak.values, 
                label="历史最高", color=self.color_palette[1], 
                linewidth=1, alpha=0.7, linestyle='--')
        
        ax1.set_title(title, fontsize=16, fontweight='bold')
        ax1.set_ylabel("权益价值", fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 下图：回撤
        ax2.fill_between(drawdown.index, drawdown.values, 0, 
                        color=self.color_palette[2], alpha=0.6, label="回撤")
        ax2.plot(drawdown.index, drawdown.values, 
                color=self.color_palette[2], linewidth=1)
        
        ax2.set_xlabel("日期", fontsize=12)
        ax2.set_ylabel("回撤", fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 格式化回撤为百分比
        ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1%}'))
        
        # 格式化x轴日期
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_returns_distribution(
        self,
        returns: pd.Series,
        title: str = "收益率分布",
        save_path: Optional[str] = None
    ):
        """
        绘制收益率分布图
        
        Args:
            returns: 收益率序列
            title: 图表标题
            save_path: 保存路径（可选）
        """
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=self.figsize)
        
        # 1. 收益率直方图
        ax1.hist(returns.values, bins=50, alpha=0.7, color=self.color_palette[0], edgecolor='black')
        ax1.axvline(returns.mean(), color='red', linestyle='--', label=f'均值: {returns.mean():.4f}')
        ax1.axvline(returns.median(), color='orange', linestyle='--', label=f'中位数: {returns.median():.4f}')
        ax1.set_title("收益率分布", fontweight='bold')
        ax1.set_xlabel("日收益率")
        ax1.set_ylabel("频数")
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. Q-Q图（正态性检验）
        from scipy import stats
        stats.probplot(returns.values, dist="norm", plot=ax2)
        ax2.set_title("Q-Q图 (正态性检验)", fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        # 3. 收益率时间序列
        ax3.plot(returns.index, returns.values, color=self.color_palette[1], alpha=0.7)
        ax3.axhline(0, color='black', linestyle='-', alpha=0.5)
        ax3.set_title("收益率时间序列", fontweight='bold')
        ax3.set_xlabel("日期")
        ax3.set_ylabel("日收益率")
        ax3.grid(True, alpha=0.3)
        
        # 4. 滚动波动率
        rolling_std = returns.rolling(window=30).std()
        ax4.plot(rolling_std.index, rolling_std.values, color=self.color_palette[3])
        ax4.set_title("30日滚动波动率", fontweight='bold')
        ax4.set_xlabel("日期")
        ax4.set_ylabel("波动率")
        ax4.grid(True, alpha=0.3)
        
        # 格式化日期轴
        for ax in [ax3, ax4]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.suptitle(title, fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_trade_analysis(
        self,
        trades: pd.DataFrame,
        title: str = "交易分析",
        save_path: Optional[str] = None
    ):
        """
        绘制交易分析图
        
        Args:
            trades: 交易记录
            title: 图表标题
            save_path: 保存路径（可选）
        """
        if trades.empty:
            print("无交易数据可视化")
            return
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=self.figsize)
        
        # 1. 交易数量统计
        buy_trades = trades[trades['side'] == 'buy']
        sell_trades = trades[trades['side'] == 'sell']
        
        trade_counts = [len(buy_trades), len(sell_trades)]
        labels = ['买入', '卖出']
        colors = [self.color_palette[0], self.color_palette[1]]
        
        ax1.pie(trade_counts, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax1.set_title("买卖交易比例", fontweight='bold')
        
        # 2. 交易时间分布
        trades_by_month = trades.groupby(trades['timestamp'].dt.to_period('M')).size()
        ax2.bar(range(len(trades_by_month)), trades_by_month.values, 
               color=self.color_palette[2], alpha=0.7)
        ax2.set_title("月度交易次数", fontweight='bold')
        ax2.set_xlabel("月份")
        ax2.set_ylabel("交易次数")
        ax2.set_xticks(range(len(trades_by_month)))
        ax2.set_xticklabels([str(p) for p in trades_by_month.index], rotation=45)
        ax2.grid(True, alpha=0.3)
        
        # 3. 交易价格分布
        ax3.hist(trades['price'].values, bins=30, alpha=0.7, 
                color=self.color_palette[3], edgecolor='black')
        ax3.set_title("交易价格分布", fontweight='bold')
        ax3.set_xlabel("价格")
        ax3.set_ylabel("频数")
        ax3.grid(True, alpha=0.3)
        
        # 4. 手续费统计
        commission_by_symbol = trades.groupby('symbol')['commission'].sum()
        if len(commission_by_symbol) > 0:
            ax4.bar(range(len(commission_by_symbol)), commission_by_symbol.values,
                   color=self.color_palette[4], alpha=0.7)
            ax4.set_title("各标的手续费", fontweight='bold')
            ax4.set_xlabel("证券代码")
            ax4.set_ylabel("总手续费")
            ax4.set_xticks(range(len(commission_by_symbol)))
            ax4.set_xticklabels(commission_by_symbol.index, rotation=45)
            ax4.grid(True, alpha=0.3)
        
        plt.suptitle(title, fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_performance_metrics(
        self,
        metrics: Dict[str, Any],
        title: str = "绩效指标概览",
        save_path: Optional[str] = None
    ):
        """
        绘制绩效指标概览图
        
        Args:
            metrics: 绩效指标字典
            title: 图表标题
            save_path: 保存路径（可选）
        """
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=self.figsize)
        
        # 1. 关键收益指标
        return_metrics = {
            '总收益率': metrics.get('total_return', 0),
            '年化收益率': metrics.get('annualized_return', 0),
            '最大回撤': metrics.get('max_drawdown', 0),
            '胜率': metrics.get('win_rate', 0)
        }
        
        bars1 = ax1.bar(return_metrics.keys(), 
                       [v if k != '最大回撤' else abs(v) for k, v in return_metrics.items()],
                       color=[self.color_palette[i] for i in range(len(return_metrics))])
        ax1.set_title("关键收益指标", fontweight='bold')
        ax1.set_ylabel("比例")
        ax1.tick_params(axis='x', rotation=45)
        
        # 为最大回撤使用负值显示
        for i, (k, v) in enumerate(return_metrics.items()):
            if k == '最大回撤':
                bars1[i].set_color('red')
                ax1.text(i, abs(v) + 0.01, f'{v:.2%}', ha='center', va='bottom')
            else:
                ax1.text(i, v + 0.01, f'{v:.2%}', ha='center', va='bottom')
        
        ax1.grid(True, alpha=0.3)
        
        # 2. 风险调整收益指标
        risk_metrics = {
            '夏普比率': metrics.get('sharpe_ratio', 0),
            '索提诺比率': metrics.get('sortino_ratio', 0),
            '年化波动率': metrics.get('annualized_volatility', 0)
        }
        
        bars2 = ax2.bar(risk_metrics.keys(), risk_metrics.values(),
                       color=[self.color_palette[i+4] for i in range(len(risk_metrics))])
        ax2.set_title("风险调整指标", fontweight='bold')
        ax2.set_ylabel("数值")
        ax2.tick_params(axis='x', rotation=45)
        
        for i, (k, v) in enumerate(risk_metrics.items()):
            format_str = f'{v:.2f}' if k != '年化波动率' else f'{v:.2%}'
            ax2.text(i, v + max(risk_metrics.values()) * 0.02, format_str, 
                    ha='center', va='bottom')
        
        ax2.grid(True, alpha=0.3)
        
        # 3. 交易统计（如果有交易数据）
        if 'total_trades' in metrics:
            trade_stats = {
                '总交易': metrics.get('total_trades', 0),
                '盈利交易': metrics.get('winning_trades', 0),
                '亏损交易': metrics.get('losing_trades', 0)
            }
            
            ax3.bar(trade_stats.keys(), trade_stats.values(),
                   color=[self.color_palette[i+1] for i in range(len(trade_stats))])
            ax3.set_title("交易统计", fontweight='bold')
            ax3.set_ylabel("次数")
            
            for i, (k, v) in enumerate(trade_stats.items()):
                ax3.text(i, v + max(trade_stats.values()) * 0.02, str(int(v)), 
                        ha='center', va='bottom')
            
            ax3.grid(True, alpha=0.3)
        
        # 4. 月度收益热力图（如果有足够数据）
        if 'equity_curve' in metrics and len(metrics['equity_curve']) > 30:
            # 这里简化处理，实际应该从equity_curve计算月度收益
            ax4.text(0.5, 0.5, '月度收益热力图\n(需要更多数据)', 
                    ha='center', va='center', transform=ax4.transAxes,
                    fontsize=12, bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray"))
            ax4.set_title("月度收益分析", fontweight='bold')
        else:
            ax4.axis('off')
        
        plt.suptitle(title, fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def create_comprehensive_report(
        self,
        results: Dict[str, Any],
        save_dir: Optional[str] = None
    ):
        """
        创建综合回测报告
        
        Args:
            results: 回测结果字典
            save_dir: 保存目录（可选）
        """
        print("生成综合回测报告...")
        
        equity_curve = results.get('equity_curve', pd.Series())
        trades = results.get('trades', pd.DataFrame())
        metrics = results.get('performance_metrics', {})
        
        # 权益曲线图
        if not equity_curve.empty:
            save_path = f"{save_dir}/equity_curve.png" if save_dir else None
            self.plot_equity_curve(equity_curve['equity'], save_path=save_path)
        
        # 回撤分析图
        if not equity_curve.empty:
            save_path = f"{save_dir}/drawdown_analysis.png" if save_dir else None
            self.plot_drawdown(equity_curve['equity'], save_path=save_path)
        
        # 收益率分布图
        if not equity_curve.empty and len(equity_curve) > 1:
            returns = equity_curve['equity'].pct_change().dropna()
            save_path = f"{save_dir}/returns_distribution.png" if save_dir else None
            self.plot_returns_distribution(returns, save_path=save_path)
        
        # 交易分析图
        if not trades.empty:
            save_path = f"{save_dir}/trade_analysis.png" if save_dir else None
            self.plot_trade_analysis(trades, save_path=save_path)
        
        # 绩效指标概览
        if metrics:
            save_path = f"{save_dir}/performance_overview.png" if save_dir else None
            self.plot_performance_metrics(metrics, save_path=save_path)
        
        print("回测报告生成完成！")