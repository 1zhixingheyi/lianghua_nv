"""
绩效分析模块
================

计算回测结果的各种绩效指标，包括收益率、风险指标、交易统计等。
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class PerformanceAnalyzer:
    """绩效分析器"""
    
    def __init__(self, risk_free_rate: float = 0.03):
        """
        初始化绩效分析器
        
        Args:
            risk_free_rate: 无风险利率，默认3%
        """
        self.risk_free_rate = risk_free_rate
    
    def calculate_metrics(
        self, 
        equity_curve: pd.Series,
        returns: pd.Series,
        trades: pd.DataFrame,
        benchmark_returns: Optional[pd.Series] = None
    ) -> Dict[str, Any]:
        """
        计算完整的绩效指标
        
        Args:
            equity_curve: 权益曲线
            returns: 日收益率序列
            trades: 交易记录
            benchmark_returns: 基准收益率（可选）
            
        Returns:
            绩效指标字典
        """
        metrics = {}
        
        # 基础统计
        metrics.update(self._calculate_basic_stats(equity_curve, returns))
        
        # 收益率指标
        metrics.update(self._calculate_return_metrics(equity_curve, returns))
        
        # 风险指标
        metrics.update(self._calculate_risk_metrics(equity_curve, returns))
        
        # 回撤指标
        metrics.update(self._calculate_drawdown_metrics(equity_curve))
        
        # 交易统计
        if not trades.empty:
            metrics.update(self._calculate_trade_stats(trades))
        
        # 风险调整收益指标
        metrics.update(self._calculate_risk_adjusted_metrics(returns))
        
        # 基准比较（如果提供）
        if benchmark_returns is not None:
            metrics.update(self._calculate_benchmark_metrics(returns, benchmark_returns))
        
        return metrics
    
    def _calculate_basic_stats(self, equity_curve: pd.Series, returns: pd.Series) -> Dict:
        """计算基础统计指标"""
        if equity_curve.empty:
            return {}
        
        start_value = equity_curve.iloc[0]
        end_value = equity_curve.iloc[-1]
        
        return {
            'start_date': equity_curve.index[0],
            'end_date': equity_curve.index[-1],
            'trading_days': len(equity_curve),
            'start_value': start_value,
            'end_value': end_value,
            'net_profit': end_value - start_value,
            'profit_factor': end_value / start_value if start_value > 0 else 0
        }
    
    def _calculate_return_metrics(self, equity_curve: pd.Series, returns: pd.Series) -> Dict:
        """计算收益率指标"""
        if equity_curve.empty or returns.empty:
            return {}
        
        # 总收益率
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        
        # 年化收益率
        trading_days = len(equity_curve)
        years = trading_days / 252  # 假设一年252个交易日
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # 平均日收益率
        avg_daily_return = returns.mean()
        
        # 累计收益率序列
        cumulative_returns = (1 + returns).cumprod() - 1
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'avg_daily_return': avg_daily_return,
            'positive_days': (returns > 0).sum(),
            'negative_days': (returns < 0).sum(),
            'win_rate': (returns > 0).mean(),
            'best_day': returns.max(),
            'worst_day': returns.min()
        }
    
    def _calculate_risk_metrics(self, equity_curve: pd.Series, returns: pd.Series) -> Dict:
        """计算风险指标"""
        if returns.empty:
            return {}
        
        # 波动率
        volatility = returns.std()
        annualized_volatility = volatility * np.sqrt(252)
        
        # VaR和CVaR
        var_95 = returns.quantile(0.05)
        var_99 = returns.quantile(0.01)
        cvar_95 = returns[returns <= var_95].mean() if (returns <= var_95).any() else 0
        cvar_99 = returns[returns <= var_99].mean() if (returns <= var_99).any() else 0
        
        # 下行波动率
        negative_returns = returns[returns < 0]
        downside_volatility = negative_returns.std() if len(negative_returns) > 0 else 0
        annualized_downside_volatility = downside_volatility * np.sqrt(252)
        
        return {
            'volatility': volatility,
            'annualized_volatility': annualized_volatility,
            'downside_volatility': downside_volatility,
            'annualized_downside_volatility': annualized_downside_volatility,
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'cvar_99': cvar_99,
            'skewness': returns.skew(),
            'kurtosis': returns.kurtosis()
        }
    
    def _calculate_drawdown_metrics(self, equity_curve: pd.Series) -> Dict:
        """计算回撤指标"""
        if equity_curve.empty:
            return {}
        
        # 计算回撤
        peak = equity_curve.expanding().max()
        drawdown = (equity_curve - peak) / peak
        
        # 最大回撤
        max_drawdown = drawdown.min()
        
        # 最大回撤对应的日期
        max_dd_date = drawdown.idxmin()
        
        # 回撤期分析
        # 找到所有回撤期
        is_drawdown = drawdown < 0
        drawdown_periods = []
        
        if is_drawdown.any():
            # 找到回撤期的开始和结束
            drawdown_starts = is_drawdown & ~is_drawdown.shift(1, fill_value=False)
            drawdown_ends = ~is_drawdown & is_drawdown.shift(1, fill_value=False)
            
            start_dates = equity_curve.index[drawdown_starts]
            end_dates = equity_curve.index[drawdown_ends]
            
            # 确保配对
            min_len = min(len(start_dates), len(end_dates))
            
            for i in range(min_len):
                start = start_dates[i]
                end = end_dates[i]
                period_dd = drawdown[start:end]
                if not period_dd.empty:
                    drawdown_periods.append({
                        'start': start,
                        'end': end,
                        'duration': (end - start).days,
                        'max_drawdown': period_dd.min()
                    })
        
        # 平均回撤持续时间
        avg_drawdown_duration = np.mean([p['duration'] for p in drawdown_periods]) if drawdown_periods else 0
        
        # 最长回撤持续时间
        max_drawdown_duration = max([p['duration'] for p in drawdown_periods]) if drawdown_periods else 0
        
        return {
            'max_drawdown': max_drawdown,
            'max_drawdown_date': max_dd_date,
            'avg_drawdown_duration': avg_drawdown_duration,
            'max_drawdown_duration': max_drawdown_duration,
            'drawdown_periods': len(drawdown_periods),
            'current_drawdown': drawdown.iloc[-1]
        }
    
    def _calculate_trade_stats(self, trades: pd.DataFrame) -> Dict:
        """计算交易统计"""
        if trades.empty:
            return {}
        
        # 按交易对配对（买入和卖出）
        buy_trades = trades[trades['side'] == 'buy']
        sell_trades = trades[trades['side'] == 'sell']
        
        # 计算每笔交易的盈亏
        trade_pnl = []
        
        # 简化的交易盈亏计算（假设FIFO）
        for symbol in trades['symbol'].unique():
            symbol_trades = trades[trades['symbol'] == symbol].sort_values('timestamp')
            position = 0
            cost_basis = 0
            
            for _, trade in symbol_trades.iterrows():
                if trade['side'] == 'buy':
                    # 更新成本基础
                    total_cost = position * cost_basis + trade['quantity'] * trade['price']
                    position += trade['quantity']
                    if position > 0:
                        cost_basis = total_cost / position
                elif trade['side'] == 'sell':
                    # 计算这笔卖出的盈亏
                    if position >= trade['quantity']:
                        pnl = trade['quantity'] * (trade['price'] - cost_basis) - trade['commission']
                        trade_pnl.append(pnl)
                        position -= trade['quantity']
        
        trade_pnl = np.array(trade_pnl)
        
        if len(trade_pnl) == 0:
            return {
                'total_trades': len(trades),
                'buy_trades': len(buy_trades),
                'sell_trades': len(sell_trades),
                'completed_trades': 0
            }
        
        # 盈利和亏损交易
        winning_trades = trade_pnl[trade_pnl > 0]
        losing_trades = trade_pnl[trade_pnl < 0]
        
        # 交易统计
        total_commission = trades['commission'].sum()
        
        return {
            'total_trades': len(trades),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'completed_trades': len(trade_pnl),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(trade_pnl) if len(trade_pnl) > 0 else 0,
            'avg_win': winning_trades.mean() if len(winning_trades) > 0 else 0,
            'avg_loss': losing_trades.mean() if len(losing_trades) > 0 else 0,
            'best_trade': trade_pnl.max() if len(trade_pnl) > 0 else 0,
            'worst_trade': trade_pnl.min() if len(trade_pnl) > 0 else 0,
            'profit_factor': abs(winning_trades.sum() / losing_trades.sum()) if len(losing_trades) > 0 and losing_trades.sum() != 0 else float('inf'),
            'total_commission': total_commission,
            'avg_trade': trade_pnl.mean() if len(trade_pnl) > 0 else 0
        }
    
    def _calculate_risk_adjusted_metrics(self, returns: pd.Series) -> Dict:
        """计算风险调整收益指标"""
        if returns.empty:
            return {}
        
        avg_return = returns.mean()
        volatility = returns.std()
        
        # 年化指标
        annualized_return = avg_return * 252
        annualized_volatility = volatility * np.sqrt(252)
        
        # 夏普比率
        excess_return = annualized_return - self.risk_free_rate
        sharpe_ratio = excess_return / annualized_volatility if annualized_volatility > 0 else 0
        
        # 索提诺比率（使用下行波动率）
        negative_returns = returns[returns < 0]
        downside_volatility = negative_returns.std() if len(negative_returns) > 0 else 0
        annualized_downside_volatility = downside_volatility * np.sqrt(252)
        sortino_ratio = excess_return / annualized_downside_volatility if annualized_downside_volatility > 0 else 0
        
        # 卡尔马比率（年化收益率/最大回撤）
        # 这里需要权益曲线来计算最大回撤，简化处理
        calmar_ratio = 0  # 需要在主函数中计算
        
        # 信息比率（这里设为0，需要基准收益）
        information_ratio = 0
        
        return {
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'information_ratio': information_ratio
        }
    
    def _calculate_benchmark_metrics(self, returns: pd.Series, benchmark_returns: pd.Series) -> Dict:
        """计算相对基准的指标"""
        if returns.empty or benchmark_returns.empty:
            return {}
        
        # 对齐时间序列
        aligned_returns, aligned_benchmark = returns.align(benchmark_returns, join='inner')
        
        if aligned_returns.empty:
            return {}
        
        # 超额收益
        excess_returns = aligned_returns - aligned_benchmark
        
        # 跟踪误差
        tracking_error = excess_returns.std() * np.sqrt(252)
        
        # 信息比率
        information_ratio = excess_returns.mean() * 252 / tracking_error if tracking_error > 0 else 0
        
        # Beta系数
        covariance = np.cov(aligned_returns, aligned_benchmark)[0, 1]
        benchmark_variance = aligned_benchmark.var()
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 0
        
        # Alpha
        risk_free_daily = self.risk_free_rate / 252
        alpha = (aligned_returns.mean() - risk_free_daily) - beta * (aligned_benchmark.mean() - risk_free_daily)
        alpha_annualized = alpha * 252
        
        # 相关系数
        correlation = aligned_returns.corr(aligned_benchmark)
        
        return {
            'alpha': alpha_annualized,
            'beta': beta,
            'correlation': correlation,
            'tracking_error': tracking_error,
            'information_ratio': information_ratio,
            'avg_excess_return': excess_returns.mean() * 252
        }
    
    def generate_report(self, metrics: Dict[str, Any]) -> str:
        """
        生成文本格式的绩效报告
        
        Args:
            metrics: 绩效指标字典
            
        Returns:
            格式化的报告字符串
        """
        report = []
        report.append("=" * 60)
        report.append("                    回测绩效报告")
        report.append("=" * 60)
        
        # 基础信息
        if 'start_date' in metrics:
            report.append(f"\n回测期间: {metrics['start_date'].strftime('%Y-%m-%d')} 至 {metrics['end_date'].strftime('%Y-%m-%d')}")
            report.append(f"交易天数: {metrics['trading_days']}")
        
        # 收益指标
        report.append(f"\n📈 收益指标:")
        if 'total_return' in metrics:
            report.append(f"总收益率: {metrics['total_return']:.2%}")
        if 'annualized_return' in metrics:
            report.append(f"年化收益率: {metrics['annualized_return']:.2%}")
        if 'win_rate' in metrics:
            report.append(f"胜率: {metrics['win_rate']:.2%}")
        
        # 风险指标
        report.append(f"\n⚠️ 风险指标:")
        if 'annualized_volatility' in metrics:
            report.append(f"年化波动率: {metrics['annualized_volatility']:.2%}")
        if 'max_drawdown' in metrics:
            report.append(f"最大回撤: {metrics['max_drawdown']:.2%}")
        if 'sharpe_ratio' in metrics:
            report.append(f"夏普比率: {metrics['sharpe_ratio']:.2f}")
        if 'sortino_ratio' in metrics:
            report.append(f"索提诺比率: {metrics['sortino_ratio']:.2f}")
        
        # 交易统计
        if 'total_trades' in metrics:
            report.append(f"\n💼 交易统计:")
            report.append(f"总交易次数: {metrics['total_trades']}")
            if 'completed_trades' in metrics:
                report.append(f"完成交易: {metrics['completed_trades']}")
                if metrics['completed_trades'] > 0:
                    report.append(f"盈利交易: {metrics.get('winning_trades', 0)}")
                    report.append(f"亏损交易: {metrics.get('losing_trades', 0)}")
                    report.append(f"平均盈利: {metrics.get('avg_win', 0):.2f}")
                    report.append(f"平均亏损: {metrics.get('avg_loss', 0):.2f}")
        
        report.append("=" * 60)
        
        return "\n".join(report)