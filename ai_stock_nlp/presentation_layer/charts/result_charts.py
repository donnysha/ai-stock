"""
回测结果图表组件
使用Plotly绘制回测收益曲线、资金曲线、回撤曲线等
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Any
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class ResultCharts:
    """
    回测结果图表生成器
    
    功能：
    1. 绘制收益率曲线
    2. 绘制资金曲线
    3. 绘制回撤曲线
    4. 绘制收益分布图
    5. 综合仪表盘
    """
    
    def __init__(self):
        self.fig = None
    
    def create_return_chart(
        self,
        trades: List[Dict],
        initial_capital: float,
        kline_data: Optional[pd.DataFrame] = None,
        title: str = "收益率曲线"
    ) -> go.Figure:
        """
        创建收益率曲线图
        
        Args:
            trades: 交易记录列表
            initial_capital: 初始资金
            kline_data: K线数据（可选，用于对比基准）
            title: 图表标题
        
        Returns:
            Plotly Figure对象
        """
        if not trades:
            return go.Figure()
        
        # 构建每日资金DataFrame
        df = self._build_capital_df(trades, initial_capital, kline_data)
        
        if df.empty:
            return go.Figure()
        
        # 计算收益率
        df['return_pct'] = (df['capital'] - initial_capital) / initial_capital * 100
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.6, 0.4],
            subplot_titles=('收益率曲线', '持仓变化')
        )
        
        # 收益率曲线
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['return_pct'],
                mode='lines',
                name='策略收益',
                line=dict(color='#2196F3', width=2),
                fill='tozeroy',
                fillcolor='rgba(33, 150, 243, 0.1)'
            ),
            row=1, col=1
        )
        
        # 添加零线
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)
        
        # 添加买入持有基准线（如果有K线数据）
        if kline_data is not None and not kline_data.empty and '现价' in kline_data.columns:
            first_price = kline_data.iloc[0]['现价']
            last_price = kline_data.iloc[-1]['现价']
            buy_hold_return = (last_price - first_price) / first_price * 100
            
            fig.add_trace(
                go.Scatter(
                    x=df['date'],
                    y=[buy_hold_return] * len(df),
                    mode='lines',
                    name=f'买入持有 ({buy_hold_return:.2f}%)',
                    line=dict(color='#FF5722', width=1, dash='dash')
                ),
                row=1, col=1
            )
        
        # 持仓变化
        fig.add_trace(
            go.Bar(
                x=df['date'],
                y=df['position'],
                name='持仓数量',
                marker_color='rgba(76, 175, 80, 0.6)'
            ),
            row=2, col=1
        )
        
        fig.update_layout(
            title=title,
            template='plotly_dark',
            height=500,
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        fig.update_xaxes(title_text="日期", row=2, col=1)
        fig.update_yaxes(title_text="收益率 (%)", row=1, col=1)
        fig.update_yaxes(title_text="持仓", row=2, col=1)
        
        self.fig = fig
        return fig
    
    def create_drawdown_chart(
        self,
        trades: List[Dict],
        initial_capital: float,
        title: str = "回撤分析"
    ) -> go.Figure:
        """
        创建回撤分析图
        
        Args:
            trades: 交易记录列表
            initial_capital: 初始资金
            title: 图表标题
        
        Returns:
            Plotly Figure对象
        """
        if not trades:
            return go.Figure()
        
        df = self._build_capital_df(trades, initial_capital)
        
        if df.empty:
            return go.Figure()
        
        # 计算回撤
        df['peak'] = df['capital'].cummax()
        df['drawdown'] = (df['capital'] - df['peak']) / df['peak'] * 100
        df['drawdown'] = df['drawdown'].clip(upper=0)  # 只保留负值
        
        # 找到最大回撤点
        max_dd_idx = df['drawdown'].idxmin()
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.5, 0.5],
            subplot_titles=('资金曲线与峰值', '回撤曲线')
        )
        
        # 资金曲线
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['capital'],
                mode='lines',
                name='资金曲线',
                line=dict(color='#2196F3', width=2)
            ),
            row=1, col=1
        )
        
        # 资金峰值
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['peak'],
                mode='lines',
                name='资金峰值',
                line=dict(color='#4CAF50', width=1, dash='dash')
            ),
            row=1, col=1
        )
        
        # 回撤曲线
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['drawdown'],
                mode='lines',
                name='回撤',
                line=dict(color='#F44336', width=2),
                fill='tozeroy',
                fillcolor='rgba(244, 67, 54, 0.3)'
            ),
            row=2, col=1
        )
        
        # 标记最大回撤点
        if not df.empty and max_dd_idx is not None:
            max_dd_date = df.loc[max_dd_idx, 'date']
            max_dd_value = df.loc[max_dd_idx, 'drawdown']
            
            fig.add_trace(
                go.Scatter(
                    x=[max_dd_date],
                    y=[max_dd_value],
                    mode='markers',
                    marker=dict(size=12, color='red', symbol='x'),
                    name=f'最大回撤 ({max_dd_value:.2f}%)',
                    showlegend=True
                ),
                row=2, col=1
            )
        
        fig.update_layout(
            title=title,
            template='plotly_dark',
            height=500,
            hovermode='x unified',
            showlegend=True
        )
        
        fig.update_xaxes(title_text="日期", row=2, col=1)
        fig.update_yaxes(title_text="资金 (元)", row=1, col=1)
        fig.update_yaxes(title_text="回撤 (%)", row=2, col=1)
        
        self.fig = fig
        return fig
    
    def create_trade_analysis_chart(
        self,
        trades: List[Dict],
        title: str = "交易分析"
    ) -> go.Figure:
        """
        创建交易分析图
        
        Args:
            trades: 交易记录列表
            title: 图表标题
        
        Returns:
            Plotly Figure对象
        """
        if not trades:
            return go.Figure()
        
        # 分离买卖交易
        buy_trades = [t for t in trades if t.get('action') == 'buy']
        sell_trades = [t for t in trades if t.get('action') == 'sell']
        
        # 计算每笔卖出交易的盈亏
        profit_data = []
        for i, sell in enumerate(sell_trades):
            if i < len(buy_trades):
                buy = buy_trades[i]
                buy_cost = buy.get('amount', 0) * 1.0003  # 买入成本（含佣金）
                sell_income = sell.get('amount', 0) * 0.9987  # 卖出收入（含佣金和印花税）
                profit = sell_income - buy_cost
                profit_pct = profit / buy_cost * 100 if buy_cost > 0 else 0
                
                profit_data.append({
                    'trade': i + 1,
                    'profit': profit,
                    'profit_pct': profit_pct,
                    'sell_price': sell.get('price', 0),
                    'buy_price': buy.get('price', 0)
                })
        
        if not profit_data:
            return go.Figure()
        
        profit_df = pd.DataFrame(profit_data)
        
        # 创建子图
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('每笔交易盈亏', '盈亏分布', '买卖价格对比', '累计盈亏'),
            specs=[
                [{"type": "bar"}, {"type": "histogram"}],
                [{"type": "scatter"}, {"type": "scatter"}]
            ]
        )
        
        # 每笔交易盈亏柱状图
        colors = ['#4CAF50' if p > 0 else '#F44336' for p in profit_df['profit_pct']]
        fig.add_trace(
            go.Bar(
                x=profit_df['trade'],
                y=profit_df['profit_pct'],
                marker_color=colors,
                name='交易盈亏%'
            ),
            row=1, col=1
        )
        
        # 盈亏分布直方图
        fig.add_trace(
            go.Histogram(
                x=profit_df['profit_pct'],
                nbinsx=10,
                marker_color='#2196F3',
                name='分布'
            ),
            row=1, col=2
        )
        
        # 买卖价格对比
        fig.add_trace(
            go.Scatter(
                x=profit_df['trade'],
                y=profit_df['buy_price'],
                mode='lines+markers',
                name='买入价',
                line=dict(color='#4CAF50')
            ),
            row=2, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=profit_df['trade'],
                y=profit_df['sell_price'],
                mode='lines+markers',
                name='卖出价',
                line=dict(color='#F44336')
            ),
            row=2, col=1
        )
        
        # 累计盈亏
        profit_df['cumsum'] = profit_df['profit_pct'].cumsum()
        fig.add_trace(
            go.Scatter(
                x=profit_df['trade'],
                y=profit_df['cumsum'],
                mode='lines+markers',
                name='累计盈亏',
                fill='tozeroy',
                fillcolor='rgba(33, 150, 243, 0.2)'
            ),
            row=2, col=2
        )
        
        fig.update_layout(
            title=title,
            template='plotly_dark',
            height=600,
            showlegend=True
        )
        
        fig.update_xaxes(title_text="交易次数", row=1, col=1)
        fig.update_yaxes(title_text="盈亏 (%)", row=1, col=1)
        fig.update_xaxes(title_text="盈亏 (%)", row=1, col=2)
        fig.update_yaxes(title_text="频次", row=1, col=2)
        fig.update_xaxes(title_text="交易次数", row=2, col=1)
        fig.update_yaxes(title_text="价格", row=2, col=1)
        fig.update_xaxes(title_text="交易次数", row=2, col=2)
        fig.update_yaxes(title_text="累计盈亏 (%)", row=2, col=2)
        
        self.fig = fig
        return fig
    
    def create_metrics_dashboard(
        self,
        metrics: Dict[str, Any],
        title: str = "回测指标"
    ) -> go.Figure:
        """
        创建指标仪表盘
        
        Args:
            metrics: 指标字典
            title: 图表标题
        
        Returns:
            Plotly Figure对象
        """
        # 定义指标
        key_metrics = [
            ('总收益率', f"{metrics.get('total_return', 0):.2f}%", 
             '#4CAF50' if metrics.get('total_return', 0) >= 0 else '#F44336'),
            ('年化收益率', f"{metrics.get('annual_return', 0):.2f}%",
             '#4CAF50' if metrics.get('annual_return', 0) >= 0 else '#F44336'),
            ('胜率', f"{metrics.get('win_rate', 0):.1f}%",
             '#4CAF50' if metrics.get('win_rate', 0) >= 50 else '#FF9800'),
            ('最大回撤', f"{metrics.get('max_drawdown', 0):.2f}%",
             '#F44336'),
            ('夏普比率', f"{metrics.get('sharpe_ratio', 0):.2f}",
             '#4CAF50' if metrics.get('sharpe_ratio', 0) >= 1 else '#FF9800'),
            ('盈亏比', f"{metrics.get('profit_factor', 0):.2f}",
             '#4CAF50' if metrics.get('profit_factor', 0) >= 1 else '#FF9800'),
            ('交易次数', f"{metrics.get('total_trades', 0)}", '#2196F3'),
            ('盈利次数', f"{metrics.get('winning_trades', 0)}", '#4CAF50'),
            ('亏损次数', f"{metrics.get('losing_trades', 0)}", '#F44336'),
        ]
        
        # 创建仪表盘
        fig = make_subplots(
            rows=3, cols=3,
            specs=[[{'type': 'indicator'}] * 3] * 3,
            subplot_titles=[m[0] for m in key_metrics]
        )
        
        for i, (name, value, color) in enumerate(key_metrics):
            row = i // 3 + 1
            col = i % 3 + 1
            
            # 解析数值
            try:
                num_value = float(value.replace('%', ''))
            except:
                num_value = 0
            
            fig.add_trace(
                go.Indicator(
                    mode="number",
                    value=num_value if '%' not in value else num_value,
                    number={
                        'suffix': '%' if '%' in value else '',
                        'font': {'size': 24, 'color': color}
                    },
                    domain={'x': [0, 1], 'y': [0, 1]},
                    gauge={
                        'axis': {'visible': False},
                        'bar': {'color': color}
                    }
                ),
                row=row, col=col
            )
        
        fig.update_layout(
            title=title,
            template='plotly_dark',
            height=400,
            showlegend=False
        )
        
        self.fig = fig
        return fig
    
    def create_comprehensive_dashboard(
        self,
        trades: List[Dict],
        initial_capital: float,
        metrics: Dict[str, Any],
        kline_data: Optional[pd.DataFrame] = None
    ) -> go.Figure:
        """
        创建综合仪表盘
        
        Args:
            trades: 交易记录列表
            initial_capital: 初始资金
            metrics: 指标字典
            kline_data: K线数据（可选）
        
        Returns:
            Plotly Figure对象
        """
        df = self._build_capital_df(trades, initial_capital, kline_data)
        
        if df.empty:
            return go.Figure()
        
        # 计算各项数据
        df['return_pct'] = (df['capital'] - initial_capital) / initial_capital * 100
        df['peak'] = df['capital'].cummax()
        df['drawdown'] = (df['capital'] - df['peak']) / df['peak'] * 100
        df['drawdown'] = df['drawdown'].clip(upper=0)
        
        # 创建4行子图
        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.25, 0.25, 0.25, 0.25],
            subplot_titles=(
                '资金曲线',
                '收益率曲线',
                '回撤曲线',
                '持仓变化'
            )
        )
        
        # 资金曲线
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['capital'],
                mode='lines',
                name='资金',
                line=dict(color='#2196F3', width=2),
                fill='tozeroy',
                fillcolor='rgba(33, 150, 243, 0.1)'
            ),
            row=1, col=1
        )
        fig.add_hline(y=initial_capital, line_dash="dash", line_color="gray", row=1, col=1)
        
        # 收益率曲线
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['return_pct'],
                mode='lines',
                name='收益率',
                line=dict(color='#9C27B0', width=2),
                fill='tozeroy',
                fillcolor='rgba(156, 39, 176, 0.1)'
            ),
            row=2, col=1
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
        
        # 回撤曲线
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['drawdown'],
                mode='lines',
                name='回撤',
                line=dict(color='#F44336', width=2),
                fill='tozeroy',
                fillcolor='rgba(244, 67, 54, 0.2)'
            ),
            row=3, col=1
        )
        
        # 持仓变化
        fig.add_trace(
            go.Bar(
                x=df['date'],
                y=df['position'],
                name='持仓',
                marker_color='rgba(76, 175, 80, 0.6)'
            ),
            row=4, col=1
        )
        
        # 添加关键指标标注
        max_return = df['return_pct'].max()
        max_dd = df['drawdown'].min()
        
        fig.update_layout(
            title=f'回测综合仪表盘 | 总收益: {metrics.get("total_return", 0):.2f}% | 最大回撤: {abs(max_dd):.2f}% | 夏普: {metrics.get("sharpe_ratio", 0):.2f}',
            template='plotly_dark',
            height=800,
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        fig.update_xaxes(title_text="日期", row=4, col=1)
        fig.update_yaxes(title_text="资金 (元)", row=1, col=1)
        fig.update_yaxes(title_text="收益率 (%)", row=2, col=1)
        fig.update_yaxes(title_text="回撤 (%)", row=3, col=1)
        fig.update_yaxes(title_text="持仓", row=4, col=1)
        
        self.fig = fig
        return fig
    
    def _build_capital_df(
        self,
        trades: List[Dict],
        initial_capital: float,
        kline_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        构建资金DataFrame
        
        Args:
            trades: 交易记录
            initial_capital: 初始资金
            kline_data: K线数据
        
        Returns:
            资金DataFrame
        """
        if not trades and kline_data is not None:
            # 只有K线数据，没有交易记录
            df = kline_data[['trade_date']].copy()
            df.columns = ['date']
            df['capital'] = initial_capital
            df['position'] = 0
            return df
        
        if not trades:
            return pd.DataFrame()
        
        # 从交易记录构建
        data = []
        current_cash = initial_capital
        current_position = 0
        
        for trade in trades:
            data.append({
                'date': trade.get('date', ''),
                'cash': trade.get('cash', current_cash),
                'position': trade.get('position', current_position),
                'capital': trade.get('cash', current_cash) + trade.get('position', 0) * trade.get('price', 0)
            })
            current_cash = trade.get('cash', current_cash)
            current_position = trade.get('position', current_position)
        
        df = pd.DataFrame(data)
        
        # 如果有K线数据，填充每日数据
        if kline_data is not None and not kline_data.empty:
            trade_dates = set(df['date'].tolist())
            kline_dates = kline_data['trade_date'].tolist()
            
            # 补充没有交易的日期
            for date in kline_dates:
                if date not in trade_dates:
                    if data:
                        last_data = data[-1]
                        data.append({
                            'date': date,
                            'cash': last_data['cash'],
                            'position': last_data['position'],
                            'capital': last_data['cash'] + last_data['position'] * kline_data[kline_data['trade_date'] == date].iloc[0].get('现价', last_data.get('price', 0)) if not kline_data[kline_data['trade_date'] == date].empty else last_data['capital']
                        })
            
            df = pd.DataFrame(data)
        
        return df.sort_values('date') if not df.empty else df
    
    def to_html(self) -> str:
        """转换为HTML字符串"""
        if self.fig:
            return self.fig.to_html()
        return ""
    
    def save_html(self, filepath: str):
        """保存为HTML文件"""
        if self.fig:
            self.fig.write_html(filepath)
