"""
Backtrader回测引擎适配器
整合backtrader专业回测框架，增强现有回测功能
"""

import backtrader as bt
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

from data_layer.models import GridTrade, BacktestResult
from config.settings import BACKTEST_CONFIG


@dataclass
class BTAnalyzerResult:
    """Backtrader分析结果"""
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    annual_return: float = 0.0
    annual_return_pct: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade: float = 0.0
    sqn: float = 0.0  # System Quality Number
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown_pct,
            'annual_return': self.annual_return,
            'annual_return_pct': self.annual_return_pct,
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'avg_trade': self.avg_trade,
            'sqn': self.sqn
        }


class AkshareDatafeed(bt.feeds.PandasData):
    """
    akshare数据适配器
    将akshare返回的DataFrame转换为backtrader格式
    """
    
    params = (
        ('datetime', None),      # 使用索引作为日期
        ('open', 0),             # open列索引
        ('high', 1),             # high列索引
        ('low', 2),              # low列索引
        ('close', 3),            # close列索引
        ('volume', 4),           # volume列索引
        ('openinterest', -1),    # 无持仓数据
    )


class GridStrategy(bt.Strategy):
    """
    网格交易策略 - Backtrader实现
    """
    
    params = (
        ('grid_buy_pct', -3.0),      # 买入下跌幅度
        ('grid_sell_pct', 5.0),      # 卖出上涨幅度
        ('buy_ratio', 0.1),          # 每次买入仓位比例
        ('sell_ratio', 0.5),         # 每次卖出持仓比例
        ('commission', 0.0003),      # 佣金费率
        ('stamp_tax', 0.001),        # 印花税
        ('printlog', False),
    )
    
    def __init__(self):
        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        self.datavolume = self.datas[0].volume
        
        # 初始化状态
        self.last_trade_price = None
        self.order = None
        self.trades_log = []
        
        # 基准价（首日开盘价）
        self.base_price = None
        self.base_price_set = False
        
        # 指标
        self.sma = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=20)
    
    def log(self, txt, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, '
                        f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, '
                        f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
        
        self.order = None
    
    def next(self):
        # 设置基准价
        if not self.base_price_set:
            self.base_price = self.dataopen[0]
            self.base_price_set = True
            self.last_trade_price = self.base_price
            return
        
        current_price = self.dataclose[0]
        
        # 计算价格变化
        if self.last_trade_price and self.last_trade_price > 0:
            pct_change = (current_price - self.last_trade_price) / self.last_trade_price * 100
        else:
            pct_change = 0
        
        # 检查是否已有挂单
        if self.order:
            return
        
        # 买入条件：价格下跌超过阈值
        if pct_change <= self.params.grid_buy_pct:
            if not self.position:
                # 计算买入金额（仓位的10%）
                available_cash = self.broker.getcash()
                buy_value = available_cash * self.params.buy_ratio
                size = int(buy_value / current_price / 100) * 100
                
                if size > 0:
                    self.log(f'BUY CREATE, Price: {current_price:.2f}, Size: {size}')
                    self.order = self.buy(size=size)
                    self.last_trade_price = current_price
        
        # 卖出条件：价格上涨超过阈值
        elif pct_change >= self.params.grid_sell_pct:
            if self.position:
                # 卖出50%持仓
                size = int(self.position.size * self.params.sell_ratio / 100) * 100
                size = max(size, 100)  # 至少100股
                
                if size > 0:
                    self.log(f'SELL CREATE, Price: {current_price:.2f}, Size: {size}')
                    self.order = self.sell(size=size)
                    self.last_trade_price = current_price
    
    def stop(self):
        self.log(f'Final Portfolio Value: {self.broker.getvalue():.2f}', dt=self.datas[0].datetime.date(0))


class BacktraderEngine:
    """
    Backtrader回测引擎 - 核心封装类
    
    功能：
    1. 数据准备和格式化
    2. 策略配置和执行
    3. 分析器结果提取
    4. 结果统一输出
    """
    
    def __init__(self, data_fetcher=None):
        self.data_fetcher = data_fetcher
        self.config = BACKTEST_CONFIG
        self.cerebro = None
        self.strategy = None
        self.results = None
        
    def prepare_data(self, stock_code: str, start_date: str, end_date: str) -> Optional[AkshareDatafeed]:
        """
        准备backtrader数据格式
        
        Args:
            stock_code: 股票代码
            start_date: 起始日期
            end_date: 结束日期
        
        Returns:
            Backtrader格式的数据源
        """
        import traceback
        
        if self.data_fetcher is None:
            print(f"[BacktraderEngine] 错误: data_fetcher 为 None")
            return None
        
        try:
            # 使用akshare获取数据
            print(f"[BacktraderEngine] 正在获取数据: {stock_code}, {start_date} ~ {end_date}")
            df = self.data_fetcher.get_kline_dataframe(stock_code, start_date, end_date)
            
            if df is None:
                print(f"[BacktraderEngine] 错误: get_kline_dataframe 返回 None")
                return None
            
            if df.empty:
                print(f"[BacktraderEngine] 错误: 获取到空数据")
                return None
            
            print(f"[BacktraderEngine] 成功获取 {len(df)} 条数据")
            print(f"[BacktraderEngine] 数据列: {list(df.columns)}")
            print(f"[BacktraderEngine] 数据前5行:\n{df.head()}")
            
            # 重命名列为backtrader标准格式
            column_mapping = {
                '日期': 'date',
                'trade_date': 'date',
                '今开': 'open',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '现价': 'close',
                '收盘': 'close',
                '总量': 'volume',
                '成交额': 'volume'
            }
            df_renamed = df.rename(columns=column_mapping)
            
            # 确保有date列
            if 'date' not in df_renamed.columns:
                if 'trade_date' in df.columns:
                    df_renamed['date'] = pd.to_datetime(df['trade_date'])
                elif '日期' in df.columns:
                    df_renamed['date'] = pd.to_datetime(df['日期'])
            
            # 设置日期为索引
            df_renamed = df_renamed.set_index('date')
            df_renamed = df_renamed.sort_index()
            
            # 转换数值类型
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df_renamed.columns:
                    df_renamed[col] = pd.to_numeric(df_renamed[col], errors='coerce')
            
            # 删除不需要的列
            cols_to_keep = ['open', 'high', 'low', 'close', 'volume']
            df_renamed = df_renamed[[c for c in cols_to_keep if c in df_renamed.columns]]
            
            # 创建backtrader数据源
            try:
                datafeed = AkshareDatafeed(dataname=df_renamed)
                print(f"[BacktraderEngine] 数据feed创建成功")
                return datafeed
            except Exception as e:
                print(f"[BacktraderEngine] 创建数据feed失败: {e}")
                print(traceback.format_exc())
                return None
            
        except Exception as e:
            print(f"[BacktraderEngine] prepare_data 异常: {e}")
            print(traceback.format_exc())
            return None
    
    def setup_cerebro(
        self,
        datafeed,
        initial_capital: float = None,
        commission: float = None,
        stamp_tax: float = None
    ) -> bt.Cerebro:
        """
        配置Cerebro引擎
        
        Args:
            datafeed: 数据源
            initial_capital: 初始资金
            commission: 佣金费率
            stamp_tax: 印花税率
        
        Returns:
            配置好的Cerebro实例
        """
        if initial_capital is None:
            initial_capital = self.config['initial_capital']
        if commission is None:
            commission = self.config['commission_rate']
        if stamp_tax is None:
            stamp_tax = self.config['stamp_tax']
        
        cerebro = bt.Cerebro()
        
        # 添加数据源
        cerebro.adddata(datafeed)
        
        # 设置初始资金
        cerebro.broker.setcash(initial_capital)
        
        # 设置佣金
        cerebro.broker.setcommission(commission=commission)
        
        # 设置成交量限制（A股T+1，次日才能卖）
        cerebro.broker.set_socklen(True)
        
        return cerebro
    
    def add_strategy(self, cerebro, strategy_class, **strategy_params):
        """添加策略"""
        cerebro.addstrategy(strategy_class, **strategy_params)
        return cerebro
    
    def add_analyzers(self, cerebro):
        """添加分析器"""
        # 夏普比率
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', 
                           riskfreerate=0.03, annualize=True)
        
        # 回撤分析
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        
        # 年化收益
        cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual_return')
        
        # 交易统计
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        
        # SQN (System Quality Number)
        cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')
        
        # 收益分析
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        
        # VWR (Variability-Weighted Return)
        cerebro.addanalyzer(bt.analyzers.VWR, _name='vwr')
        
        return cerebro
    
    def run_backtest(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        initial_capital: float = None,
        grid_buy_pct: float = -3.0,
        grid_sell_pct: float = 5.0,
        buy_ratio: float = 0.1,
        sell_ratio: float = 0.5
    ) -> Dict[str, Any]:
        """
        执行完整回测
        
        Args:
            stock_code: 股票代码
            start_date: 起始日期
            end_date: 结束日期
            initial_capital: 初始资金
            grid_buy_pct: 买入下跌幅度
            grid_sell_pct: 卖出上涨幅度
            buy_ratio: 买入仓位比例
            sell_ratio: 卖出持仓比例
        
        Returns:
            回测结果字典
        """
        # 准备数据
        try:
            datafeed = self.prepare_data(stock_code, start_date, end_date)
            if datafeed is None:
                return {'success': False, 'message': '获取数据失败：无法从数据源获取K线数据，请检查股票代码和日期范围'}
        except Exception as e:
            import traceback
            error_msg = f"准备数据时出错: {str(e)}"
            print(f"[BacktraderEngine] {error_msg}")
            print(traceback.format_exc())
            return {'success': False, 'message': error_msg}
        
        # 配置引擎
        cerebro = self.setup_cerebro(datafeed, initial_capital)
        
        # 添加策略
        cerebro = self.add_strategy(
            cerebro, GridStrategy,
            grid_buy_pct=grid_buy_pct,
            grid_sell_pct=grid_sell_pct,
            buy_ratio=buy_ratio,
            sell_ratio=sell_ratio
        )
        
        # 添加分析器
        cerebro = self.add_analyzers(cerebro)
        
        # 执行回测
        print(f'Starting Portfolio Value: {cerebro.broker.getvalue():.2f}')
        results = cerebro.run()
        print(f'Final Portfolio Value: {cerebro.broker.getvalue():.2f}')
        
        # 提取结果
        strat = results[0]
        
        # 获取分析结果
        analyzer_results = self._extract_analyzer_results(strat)
        
        # 获取交易记录
        trades = self._extract_trades(strat)
        
        # 整理最终结果
        final_result = {
            'success': True,
            'stock_code': stock_code,
            'initial_capital': initial_capital or self.config['initial_capital'],
            'final_value': cerebro.broker.getvalue(),
            'total_return': analyzer_results.annual_return_pct,
            'analyzer': analyzer_results.to_dict(),
            'trades': trades
        }
        
        # 绘图（可选）
        # cerebro.plot(style='candlestick')
        
        return final_result
    
    def _extract_analyzer_results(self, strategy) -> BTAnalyzerResult:
        """提取分析器结果"""
        result = BTAnalyzerResult()
        
        # 夏普比率
        sharpe_dict = strategy.analyzers.sharpe.get_analysis()
        result.sharpe_ratio = sharpe_dict.get('sharperatio', 0) or 0
        
        # 回撤
        drawdown_dict = strategy.analyzers.drawdown.get_analysis()
        result.max_drawdown = drawdown_dict.get('max', {}).get('drawdown', 0) or 0
        result.max_drawdown_pct = drawdown_dict.get('max', {}).get('drawdownlen', 0) or 0
        
        # 年化收益
        annual_dict = strategy.analyzers.annual_return.get_analysis()
        if annual_dict:
            returns = list(annual_dict.values())
            result.annual_return_pct = sum(returns) / len(returns) * 100 if returns else 0
        
        # 交易统计
        trades_dict = strategy.analyzers.trades.get_analysis()
        
        total_trades = trades_dict.get('total', {}).get('total', 0) or 0
        result.total_trades = total_trades
        
        # 胜率
        won = trades_dict.get('won', {}).get('total', 0) or 0
        if total_trades > 0:
            result.win_rate = (won / total_trades) * 100
        
        # 盈亏比
        avg_win = trades_dict.get('won', {}).get('average', 0) or 0
        avg_loss = abs(trades_dict.get('lost', {}).get('average', 0) or 0)
        if avg_loss > 0:
            result.profit_factor = avg_win / avg_loss
        
        result.avg_trade = avg_win - abs(trades_dict.get('lost', {}).get('average', 0) or 0)
        
        # SQN
        sqn_dict = strategy.analyzers.sqn.get_analysis()
        result.sqn = sqn_dict.get('sqn', 0) or 0
        
        return result
    
    def _extract_trades(self, strategy) -> List[Dict[str, Any]]:
        """提取交易记录"""
        trades = []
        
        # 从策略中提取交易（如果有记录的话）
        if hasattr(strategy, 'trades_log'):
            for trade in strategy.trades_log:
                trades.append({
                    'date': trade.get('date', ''),
                    'action': trade.get('action', ''),
                    'price': trade.get('price', 0),
                    'shares': trade.get('shares', 0),
                    'amount': trade.get('amount', 0)
                })
        
        return trades
    
    def compare_with_buy_hold(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        initial_capital: float = None
    ) -> Dict[str, Any]:
        """
        对比策略收益与买入持有收益
        
        Args:
            stock_code: 股票代码
            start_date: 起始日期
            end_date: 结束日期
            initial_capital: 初始资金
        
        Returns:
            对比结果
        """
        if initial_capital is None:
            initial_capital = self.config['initial_capital']
        
        # 获取数据
        datafeed = self.prepare_data(stock_code, start_date, end_date)
        if datafeed is None:
            return {'success': False, 'message': '获取数据失败'}
        
        # 买入持有策略
        class BuyAndHold(bt.Strategy):
            def __init__(self):
                pass
            
            def next(self):
                if not self.position:
                    self.buy()
        
        # 运行买入持有策略
        cerebro = bt.Cerebro()
        cerebro.adddata(datafeed)
        cerebro.addstrategy(BuyAndHold)
        cerebro.broker.setcash(initial_capital)
        
        results = cerebro.run()
        buyhold_final = cerebro.broker.getvalue()
        
        # 运行网格策略
        grid_result = self.run_backtest(stock_code, start_date, end_date, initial_capital)
        
        # 计算差异
        strategy_return = (grid_result['final_value'] - initial_capital) / initial_capital * 100
        buyhold_return = (buyhold_final - initial_capital) / initial_capital * 100
        
        return {
            'success': True,
            'initial_capital': initial_capital,
            'strategy_final': grid_result['final_value'],
            'strategy_return': strategy_return,
            'buyhold_final': buyhold_final,
            'buyhold_return': buyhold_return,
            'alpha': strategy_return - buyhold_return
        }
