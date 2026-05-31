"""
核心调度器模块

【模块功能】
协调AI层、业务层、数据层的工作，是系统的核心调度器。

【工作流程】
1. 接收用户自然语言输入
2. 调用AI层进行意图识别（IntentClassifier）
3. 调用AI层进行参数抽取（ParamExtractor）
4. 根据意图类型调用相应业务层执行
5. 返回统一格式的结果

【支持的意图类型】
- STOCK_SELECT: 调用StockSelector执行选股
- FLEX_BACKTEST: 调用StockSelector执行灵活回测
- GRID_BACKTEST: 调用GridBacktester执行网格回测

【返回格式】
{
    'success': bool,       # 是否成功
    'intent': str,         # 意图类型
    'message': str,        # 消息
    'data': Any,          # 数据
    'count': int,         # 返回数量
    'total': int,         # 总数量
    'params': dict         # 参数
}
"""

from typing import Dict, Any, Optional
from ai_layer import IntentClassifier, ParamExtractor, IntentType, OutputSchema
from business_layer import StockSelector, GridBacktester
from data_layer.akshare_data_fetcher import akshare_fetcher


class StrategyDispatcher:
    """
    策略调度器 - 核心协调器
    
    【功能说明】
    1. 接收用户输入
    2. 调用AI层进行意图识别和参数抽取
    3. 根据意图调用相应的业务层执行
    4. 返回统一格式的结果
    
    【组件依赖】
    - AI层: IntentClassifier, ParamExtractor
    - 业务层: StockSelector, GridBacktester
    - 数据层: AkshareDataFetcher
    """
    
    def __init__(self, llm_client=None):
        """
        初始化调度器
        
        Args:
            llm_client: 大模型客户端（可选，不传入则使用规则匹配）
        """
        # AI层组件
        self.intent_classifier = IntentClassifier(llm_client)
        self.param_extractor = ParamExtractor(llm_client)
        
        # 业务层组件
        self.stock_selector = StockSelector(akshare_fetcher)
        self.grid_backtester = GridBacktester(akshare_fetcher)
        
        # 数据层 - akshare 数据获取器
        self.data_fetcher = akshare_fetcher
        self.db = akshare_fetcher
    
    def process(self, user_input: str) -> Dict[str, Any]:
        """
        处理用户输入的主入口方法
        
        【处理流程】
        1. 调用IntentClassifier识别意图
        2. 调用ParamExtractor抽取参数
        3. 检查参数完整性
        4. 根据意图类型执行相应业务
        
        Args:
            user_input: 用户的自然语言输入
        
        Returns:
            统一格式的结果字典
        """
        try:
            # 步骤1: 意图识别
            intent = self.intent_classifier.classify(user_input)
            
            # 步骤2: 参数抽取
            schema = self.param_extractor.extract(user_input, intent)
            
            # 步骤3: 检查参数完整性
            if schema.status.value == "need_input":
                return {
                    'success': False,
                    'intent': intent.value,
                    'message': f"缺少必要参数: {', '.join(schema.missing_fields)}",
                    'data': None,
                    'schema': schema,
                    'missing_fields': schema.missing_fields
                }
            
            # 步骤4: 根据意图执行相应业务
            if intent == IntentType.STOCK_SELECT:
                return self._execute_stock_select(schema.params)
            elif intent == IntentType.FLEX_BACKTEST:
                return self._execute_flex_backtest(schema.params)
            elif intent == IntentType.GRID_BACKTEST:
                return self._execute_grid_backtest(schema.params)
            
            return {
                'success': False,
                'intent': intent.value,
                'message': '未知意图类型',
                'data': None,
                'schema': schema
            }
            
        except Exception as e:
            return {
                'success': False,
                'intent': 'unknown',
                'message': str(e),
                'data': None,
                'schema': None
            }
    
    def process_intent_only(self, user_input: str) -> OutputSchema:
        """
        仅进行意图识别和参数抽取（不执行）
        
        Args:
            user_input: 用户输入
        
        Returns:
            OutputSchema
        """
        try:
            intent = self.intent_classifier.classify(user_input)
            schema = self.param_extractor.extract(user_input, intent)
            return schema
        except Exception as e:
            return OutputSchema(
                intent=IntentType.STOCK_SELECT,
                status=OutputSchema.status,
                params={},
                missing_fields=[]
            )
    
    def _execute_stock_select(self, params: Dict) -> Dict[str, Any]:
        """
        执行选股（当前时间）
        """
        try:
            result = self.stock_selector.select_stocks(params)
            
            return {
                'success': result.success,
                'intent': 'stock_select',
                'message': result.message,
                'data': result.data if result.success else None,
                'count': result.count,
                'total': result.total,
                'params': params,
                'schema': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'intent': 'stock_select',
                'message': str(e),
                'data': None
            }
    
    def _execute_flex_backtest(self, params: Dict) -> Dict[str, Any]:
        """
        执行灵活回测（自定义时序条件）
        """
        try:
            result = self.stock_selector.flex_backtest(params)
            
            return {
                'success': result.success,
                'intent': 'flex_backtest',
                'message': result.message,
                'data': result.data if result.success else None,
                'count': result.count,
                'params': params,
                'schema': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'intent': 'flex_backtest',
                'message': str(e),
                'data': None
            }
    
    def _execute_grid_backtest(self, params: Dict) -> Dict[str, Any]:
        """
        执行网格回测
        """
        try:
            stock_code = params.get('stock_code')
            start_date = params.get('start_date')
            
            if not stock_code:
                return {
                    'success': False,
                    'intent': 'grid_backtest',
                    'message': '缺少股票代码',
                    'data': None
                }
            
            # 如果没有结束日期，使用今天
            from datetime import datetime
            if not params.get('end_date'):
                end_date = datetime.now().strftime('%Y%m%d')
            else:
                end_date = params.get('end_date')
            
            result = self.grid_backtester.backtest(
                stock_code=stock_code,
                start_date=start_date or '20240101',
                end_date=end_date,
                grid_buy_percent=params.get('grid_buy_percent', -3.0),
                grid_sell_percent=params.get('grid_sell_percent', 5.0),
                base_price_type=params.get('base_price_type', 'open_price'),
                min_volume=self._parse_volume(params.get('volume_condition'))
            )
            
            return {
                'success': True,
                'intent': 'grid_backtest',
                'message': '回测完成',
                'data': result.to_dict(),
                'total_return': result.total_return,
                'win_rate': result.win_rate,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'trades': [t.to_dict() for t in result.trades],
                'params': params,
                'schema': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'intent': 'grid_backtest',
                'message': str(e),
                'data': None
            }
    
    def process_backtest(
        self,
        stock_code: str,
        start_date: str,
        end_date: Optional[str] = None,
        grid_buy_percent: float = -3.0,
        grid_sell_percent: float = 5.0,
        base_price_type: str = 'open_price',
        min_volume: float = 1000
    ) -> Dict[str, Any]:
        """
        直接执行网格回测（绕过AI解析）
        
        Args:
            stock_code: 股票代码
            start_date: 起始日期
            end_date: 结束日期（None表示今天）
            grid_buy_percent: 买入幅度
            grid_sell_percent: 卖出幅度
            base_price_type: 基准价类型
            min_volume: 最小成交额
        
        Returns:
            回测结果
        """
        try:
            from datetime import datetime
            # 如果结束日期为空，使用今天
            if not end_date:
                end_date = datetime.now().strftime('%Y%m%d')
            
            # 执行回测
            result = self.grid_backtester.backtest(
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date,
                grid_buy_percent=grid_buy_percent,
                grid_sell_percent=grid_sell_percent,
                base_price_type=base_price_type,
                min_volume=min_volume
            )
            
            return {
                'success': True,
                'intent': 'grid_backtest',
                'message': '回测完成',
                'data': result.to_dict(),
                'total_return': result.total_return,
                'win_rate': result.win_rate,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'trades': [t.to_dict() for t in result.trades]
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def _parse_volume(self, volume_str: Optional[str]) -> float:
        """解析成交量字符串"""
        if not volume_str:
            return 0

        import re
        match = re.match(r'(\d+(?:\.\d+)?)\s*(万|亿)?', str(volume_str))
        if match:
            value = float(match.group(1))
            unit = match.group(2) or '万'
            if unit == '亿':
                return value * 10000
            return value
        return 0

    def process_batch_backtest(
        self,
        stocks_df,
        start_date: str,
        end_date: Optional[str] = None,
        grid_buy_percent: float = -3.0,
        grid_sell_percent: float = 5.0,
        base_price_type: str = 'open_price',
        min_volume: float = 1000
    ) -> list:
        """
        批量执行网格回测

        Args:
            stocks_df: 股票DataFrame，包含'代码'列
            start_date: 起始日期
            end_date: 结束日期（None表示今天）
            grid_buy_percent: 买入幅度
            grid_sell_percent: 卖出幅度
            base_price_type: 基准价类型
            min_volume: 最小成交额

        Returns:
            回测结果列表
        """
        from datetime import datetime
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        results = []

        # 遍历每只股票
        for _, row in stocks_df.iterrows():
            stock_code = str(row.get('代码', '')).strip()
            stock_name = str(row.get('名称', '')).strip()

            if not stock_code:
                continue

            try:
                result = self.grid_backtester.backtest(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    grid_buy_percent=grid_buy_percent,
                    grid_sell_percent=grid_sell_percent,
                    base_price_type=base_price_type,
                    min_volume=min_volume
                )

                results.append({
                    'success': True,
                    'stock_code': stock_code,
                    'stock_name': stock_name or result.stock_name,
                    'total_return': result.total_return,
                    'win_rate': result.win_rate,
                    'max_drawdown': result.max_drawdown,
                    'sharpe_ratio': result.sharpe_ratio,
                    'trades': [t.to_dict() for t in result.trades],
                    'final_position': result.final_position,
                    'final_cash': result.final_cash
                })

            except Exception as e:
                results.append({
                    'success': False,
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'message': str(e),
                    'total_return': 0,
                    'win_rate': 0,
                    'max_drawdown': 0,
                    'sharpe_ratio': 0,
                    'trades': []
                })

        return results
