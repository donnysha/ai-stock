"""
Backtrader回测引擎使用示例
演示如何使用backtrader进行专业回测
"""

import sys
sys.path.insert(0, 'D:\\code\\ai-stock\\ai_stock_nlp')

from business_layer.backtrader_engine import BacktraderEngine, GridStrategy
from data_layer.akshare_data_fetcher import AkshareDataFetcher


def basic_backtest_example():
    """基础回测示例"""
    print("=" * 60)
    print("示例1: 基础网格交易回测")
    print("=" * 60)
    
    # 初始化数据获取器和回测引擎
    data_fetcher = AkshareDataFetcher()
    engine = BacktraderEngine(data_fetcher)
    
    # 执行回测
    result = engine.run_backtest(
        stock_code='000001',           # 平安银行
        start_date='20240101',
        end_date='20240301',
        initial_capital=1000000,       # 100万初始资金
        grid_buy_pct=-3.0,             # 下跌3%买入
        grid_sell_pct=5.0,             # 上涨5%卖出
        buy_ratio=0.1,                  # 每次买入10%仓位
        sell_ratio=0.5                  # 每次卖出50%持仓
    )
    
    # 打印结果
    if result['success']:
        print(f"\n股票代码: {result['stock_code']}")
        print(f"初始资金: {result['initial_capital']:,.2f}")
        print(f"最终价值: {result['final_value']:,.2f}")
        print(f"总收益率: {result['total_return']:.2f}%")
        
        # 分析器结果
        analyzer = result['analyzer']
        print("\n【专业分析指标】")
        print(f"夏普比率 (Sharpe): {analyzer['sharpe_ratio']:.2f}")
        print(f"最大回撤: {analyzer['max_drawdown']:.2f}")
        print(f"回撤周期: {analyzer['max_drawdown_pct']:.2f}天")
        print(f"年化收益率: {analyzer['annual_return_pct']:.2f}%")
        print(f"总交易次数: {analyzer['total_trades']}")
        print(f"胜率: {analyzer['win_rate']:.2f}%")
        print(f"盈亏比: {analyzer['profit_factor']:.2f}")
        print(f"SQN值: {analyzer['sqn']:.2f}")
        
        # SQN评级
        sqn = analyzer['sqn']
        sqn_rating = "极差" if sqn < 1.0 else "差" if sqn < 1.6 else "一般" if sqn < 2.0 else "良好" if sqn < 2.5 else "优秀" if sqn < 3.0 else "卓越"
        print(f"SQN评级: {sqn_rating}")
    else:
        print(f"回测失败: {result.get('message', '未知错误')}")


def compare_with_buyhold_example():
    """对比策略与买入持有"""
    print("\n" + "=" * 60)
    print("示例2: 策略与买入持有对比")
    print("=" * 60)
    
    data_fetcher = AkshareDataFetcher()
    engine = BacktraderEngine(data_fetcher)
    
    result = engine.compare_with_buy_hold(
        stock_code='000001',
        start_date='20240101',
        end_date='20240601',
        initial_capital=1000000
    )
    
    if result['success']:
        print(f"\n初始资金: {result['initial_capital']:,.2f}")
        print(f"\n【买入持有策略】")
        print(f"最终价值: {result['buyhold_final']:,.2f}")
        print(f"收益率: {result['buyhold_return']:.2f}%")
        
        print(f"\n【网格交易策略】")
        print(f"最终价值: {result['strategy_final']:,.2f}")
        print(f"收益率: {result['strategy_return']:.2f}%")
        
        print(f"\n【超额收益 (Alpha)】")
        print(f"Alpha: {result['alpha']:.2f}%")
        if result['alpha'] > 0:
            print("✅ 网格策略跑赢了买入持有！")
        else:
            print("❌ 买入持有更优")


def multiple_params_optimization():
    """参数优化示例"""
    print("\n" + "=" * 60)
    print("示例3: 网格参数优化")
    print("=" * 60)
    
    data_fetcher = AkshareDataFetcher()
    engine = BacktraderEngine(data_fetcher)
    
    # 定义参数范围
    buy_pcts = [-2.0, -3.0, -5.0]
    sell_pcts = [3.0, 5.0, 7.0]
    
    results = []
    
    print("\n正在优化参数，请稍候...")
    for buy_pct in buy_pcts:
        for sell_pct in sell_pcts:
            result = engine.run_backtest(
                stock_code='000001',
                start_date='20240101',
                end_date='20240301',
                initial_capital=1000000,
                grid_buy_pct=buy_pct,
                grid_sell_pct=sell_pct
            )
            
            if result['success']:
                results.append({
                    'buy_pct': buy_pct,
                    'sell_pct': sell_pct,
                    'return': result['total_return'],
                    'sharpe': result['analyzer']['sharpe_ratio'],
                    'max_dd': result['analyzer']['max_drawdown']
                })
    
    # 按收益率排序
    results.sort(key=lambda x: x['return'], reverse=True)
    
    print("\n【参数优化结果】")
    print(f"{'买入阈值':<12}{'卖出阈值':<12}{'收益率':<12}{'夏普比率':<12}{'最大回撤':<12}")
    print("-" * 60)
    
    for r in results:
        print(f"{r['buy_pct']:>9.1f}%   {r['sell_pct']:>9.1f}%   {r['return']:>8.2f}%   "
              f"{r['sharpe']:>8.2f}   {r['max_dd']:>8.2f}%")
    
    # 最佳参数
    if results:
        best = results[0]
        print(f"\n🏆 最佳参数: 买入-{best['buy_pct']}% 卖出-{best['sell_pct']}% 收益率-{best['return']:.2f}%")


def advanced_strategy_example():
    """进阶策略示例 - 双均线网格"""
    print("\n" + "=" * 60)
    print("示例4: 进阶策略 - 自定义策略类")
    print("=" * 60)
    
    import backtrader as bt
    
    # 定义更复杂的策略
    class DualMAGridStrategy(bt.Strategy):
        """双均线+网格策略"""
        
        params = (
            ('fast_ma', 10),      # 快速均线周期
            ('slow_ma', 30),      # 慢速均线周期
            ('grid_pct', 2.0),    # 网格幅度
            ('size_pct', 0.2),    # 仓位比例
        )
        
        def __init__(self):
            # 均线
            self.sma_fast = bt.indicators.SMA(self.data.close, period=self.p.fast_ma)
            self.sma_slow = bt.indicators.SMA(self.data.close, period=self.p.slow_ma)
            
            # 金叉/死叉信号
            self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)
            
            # 跟踪订单
            self.order = None
            
            # 上次交易价格
            self.last_trade_price = None
            
        def notify_order(self, order):
            if order.status in [order.Submitted, order.Accepted]:
                return
            if order.status == order.Completed:
                if order.isbuy():
                    self.last_trade_price = order.executed.price
            self.order = None
        
        def next(self):
            # 检查订单
            if self.order:
                return
            
            current_price = self.data.close[0]
            
            # 趋势判断：均线多头
            is_uptrend = self.sma_fast[0] > self.sma_slow[0]
            
            # 计算价格变动
            if self.last_trade_price:
                pct_change = (current_price - self.last_trade_price) / self.last_trade_price * 100
            else:
                pct_change = 0
            
            # 买入条件：上涨趋势 + 价格下跌到网格位
            if is_uptrend and pct_change <= -self.p.grid_pct and not self.position:
                size = int(self.broker.getcash() * self.p.size_pct / current_price / 100) * 100
                if size > 0:
                    self.order = self.buy(size=size)
                    self.last_trade_price = current_price
            
            # 卖出条件：死叉 或 价格涨到网格位
            elif self.position:
                should_sell = False
                
                # 死叉
                if self.crossover < 0:
                    should_sell = True
                # 价格涨到网格
                elif pct_change >= self.p.grid_pct:
                    should_sell = True
                
                if should_sell:
                    self.order = self.close()
                    self.last_trade_price = current_price
    
    # 使用引擎运行自定义策略
    data_fetcher = AkshareDataFetcher()
    engine = BacktraderEngine(data_fetcher)
    
    # 准备数据
    datafeed = engine.prepare_data('000001', '20240101', '20240301')
    if datafeed is None:
        print("数据获取失败")
        return
    
    # 配置Cerebro
    cerebro = engine.setup_cerebro(datafeed, initial_capital=1000000)
    
    # 添加自定义策略
    cerebro.addstrategy(DualMAGridStrategy, fast_ma=10, slow_ma=20, grid_pct=2.0, size_pct=0.2)
    
    # 添加分析器
    engine.add_analyzers(cerebro)
    
    # 运行
    print("运行双均线网格策略...")
    results = cerebro.run()
    strat = results[0]
    
    # 输出结果
    print(f"\n最终资产: {cerebro.broker.getvalue():,.2f}")
    print(f"夏普比率: {strat.analyzers.sharpe.get_analysis().get('sharperatio', 0):.2f}")


def run_all_examples():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("Backtrader回测引擎使用示例")
    print("=" * 60)
    
    try:
        basic_backtest_example()
        compare_with_buyhold_example()
        multiple_params_optimization()
        advanced_strategy_example()
        
        print("\n" + "=" * 60)
        print("✅ 所有示例运行完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 运行出错: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    run_all_examples()
