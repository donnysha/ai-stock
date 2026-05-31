"""
参数抽取器模块

【模块功能】
负责从用户自然语言输入中抽取结构化参数，支持灵活的filters数组格式。

【支持的参数类型】
1. filters数组 - 筛选条件列表
   - field: 字段名（成交额、涨幅%、现价等）
   - op: 操作符（>, <, >=, <=, =, LIKE）
   - value: 比较值
   - days_ago: 距今天数（0=今天, 1=昨天, 2=前天）

2. grid_backtest参数
   - stock_code: 股票代码
   - grid_buy_percent: 买入下跌幅度
   - grid_sell_percent: 卖出上涨幅度
   - start_date: 回测起始日期

【字段名映射】
将用户口语化表达转换为标准字段名：
- 成交额/总金额 -> 成交额
- 现价/价格 -> 现价
- 涨幅/涨跌幅 -> 涨幅%
- 市盈率/市盈(动) -> 市盈率

【抽取策略】
1. 优先使用大模型（AI）解析
2. 用规则补充/修正AI结果
3. 最后检查参数完整性

【常见表达转换规则】
详见 prompts.py 和 选股逻辑.md
"""

import json
import re
from typing import Dict, Any, List, Optional
from config.settings import AI_CONFIG
from config.prompts import STOCK_SELECT_PROMPT, GRID_BACKTEST_PROMPT, FLEX_BACKTEST_PROMPT
from config.phrase_mapping import get_market_cap_conditions, get_value_investment_conditions
from .schema import IntentType, OutputSchema, OutputStatus, check_params_completeness


class ParamExtractor:
    """
    参数抽取器
    
    【功能说明】
    1. 接收用户输入和意图类型
    2. 优先使用AI解析自然语言
    3. 用规则补充/修正
    4. 返回标准OutputSchema
    """

    # ========== 常量定义 ==========
    
    # 行业列表 - 用于识别行业筛选条件
    INDUSTRIES = [
        '科技', '医药', '银行', '证券', '新能源', '白酒', '军工', '房地产', 
        '半导体', '消费', '电子', '软件', '光伏', '锂电池', '医疗', '食品',
        '化工', '机械', '汽车', '家电', '基建', '环保', '通信', '传媒'
    ]
    
    # 市值划分阈值（元）
    MARKET_CAP_THRESHOLDS = {
        '微盘': {'field': '总市值', 'op': '<', 'value': 1_000_000_000},  # < 10亿
        '小盘': {'field': '总市值', 'op': '<', 'value': 10_000_000_000},  # < 100亿
        '中盘': {'field': '总市值', 'op': '>=', 'value': 10_000_000_000}, # >= 100亿
        '大盘': {'field': '总市值', 'op': '>=', 'value': 50_000_000_000}, # >= 500亿
        '超大盘': {'field': '总市值', 'op': '>=', 'value': 100_000_000_000}, # >= 1000亿
    }
    
    # 涨停阈值（考虑四舍五入容差）
    LIMIT_UP_THRESHOLDS = {
        '主板': 9.5,      # 主板 ±10%
        '科创创业': 19.5, # 科创板/创业板 ±20%
        '北交所': 29.5,   # 北交所 ±30%
        'ST': 4.5,        # ST股 ±5%
    }
    
    # 板块代码前缀映射
    BOARD_CODE_PREFIX = {
        '创业板': '30%',
        '科创板': '688%',
        '主板上海': '6%',
        '主板深圳': '0%',
        '北交所': ['8%', '4%'],
    }
    
    # 换手率条件
    TURNOVER_THRESHOLDS = {
        '高换手': {'field': '换手率', 'op': '>=', 'value': 5},
        '低换手': {'field': '换手率', 'op': '<', 'value': 2},
    }
    
    # 量比条件
    VOLUME_RATIO_THRESHOLDS = {
        '放量': {'field': '量比', 'op': '>=', 'value': 1.5},
        '缩量': {'field': '量比', 'op': '<', 'value': 0.7},
        '地量': {'field': '量比', 'op': '<', 'value': 0.5},
    }
    
    # 字段名映射（中文 -> 标准化字段名）
    FIELD_MAPPING = {
        '成交额': '成交额',
        '总金额': '成交额',
        '成交量': '成交量',
        '总量': '成交量',
        '价格': '现价',
        '现价': '现价',
        '涨幅': '涨幅%',
        '涨幅%': '涨幅%',
        '涨跌幅': '涨幅%',
        '涨跌': '涨跌额',
        '涨跌额': '涨跌额',
        '市盈率': '市盈率',
        '市盈(动)': '市盈率',
        '换手率': '换手率',
        '量比': '量比',
        '流通市值': '流通市值',
        '总市值': '总市值',
        '最高': '最高',
        '最低': '最低',
        '今开': '今开',
        '昨收': '昨收',
    }

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.model = AI_CONFIG['model']
        self.temperature = AI_CONFIG['temperature']

    def extract(self, user_input: str, intent: IntentType) -> OutputSchema:
        """
        抽取参数 - 优先使用AI解析

        Args:
            user_input: 用户自然语言输入
            intent: 已识别的意图类型

        Returns:
            OutputSchema: 标准输出协议
        """
        # 优先使用AI解析自然语言（如果可用）
        if self.llm_client:
            try:
                llm_params = self._llm_extract(user_input, intent)
                if llm_params and 'filters' in llm_params:
                    params = llm_params
                    print("[OK] AI解析成功，提取到 {} 个筛选条件".format(len(params.get('filters', []))))
                else:
                    # AI解析失败，使用规则补充
                    params = self._rule_based_extract(user_input, intent)
                    if llm_params:
                        params = self._merge_params(params, llm_params)
            except Exception as e:
                print(f"[FAIL] AI解析失败，使用规则: {e}")
                params = self._rule_based_extract(user_input, intent)
        else:
            # AI不可用，使用规则抽取
            params = self._rule_based_extract(user_input, intent)

        # 检查缺失字段
        missing = check_params_completeness(intent, params)
        status = OutputStatus.READY if len(missing) == 0 else OutputStatus.NEED_INPUT

        return OutputSchema(
            intent=intent,
            status=status,
            params=params,
            missing_fields=missing
        )

    def _rule_based_extract(self, user_input: str, intent: IntentType) -> Dict[str, Any]:
        """
        基于规则抽取参数
        
        Args:
            user_input: 用户输入
            intent: 意图类型
        
        Returns:
            参数字典
        """
        if intent == IntentType.STOCK_SELECT:
            return self._extract_stock_select_params(user_input)
        elif intent == IntentType.GRID_BACKTEST:
            return self._extract_grid_backtest_params(user_input)
        elif intent == IntentType.FLEX_BACKTEST:
            return self._extract_flex_backtest_params(user_input)
        return {}

    def _extract_stock_select_params(self, text: str) -> Dict[str, Any]:
        """
        抽取选股参数 - 新格式（当前时间）
        返回 filters 数组
        """
        filters = []
        params = {
            'filters': filters,
            'description': text  # 保存原始描述
        }
        
        # ========== 1. 涨跌幅条件（最重要！）==========
        change_conditions = self._extract_change_conditions(text)
        filters.extend(change_conditions)
        
        # ========== 2. 涨停/跌停条件 ==========
        consecutive_days = self._extract_consecutive_days(text)
        days_mapping = {
            '今天': 0, '今日': 0,
            '昨天': 1, '昨日': 1,
            '前天': 2, '前日': 2,
        }
        limit_conditions = self._extract_limit_conditions(text, consecutive_days, days_mapping)
        if limit_conditions:
            for cond in limit_conditions:
                if cond.get('days_ago', 0) == 0:  # 只取今天
                    filters.append(cond)
        
        # ========== 3. 板块条件（创业板、科创板等）==========
        board_conditions = self._extract_board_conditions(text)
        filters.extend(board_conditions)
        
        # ========== 4. 市值条件（大盘股、小盘股等）==========
        market_cap_conditions = get_market_cap_conditions(text)
        if market_cap_conditions:
            filters.extend(market_cap_conditions)
        
        # 也检查自定义的市值条件
        custom_market_cap = self._extract_custom_market_cap(text)
        if custom_market_cap:
            filters.extend(custom_market_cap)
        
        # ========== 5. 成交额条件 ==========
        volume_match = self._extract_volume_condition(text)
        if volume_match:
            filters.append(volume_match)
        
        # ========== 6. 换手率条件 ==========
        turnover_conditions = self._extract_turnover_conditions(text)
        filters.extend(turnover_conditions)
        
        # ========== 7. 量比条件 ==========
        volume_ratio_conditions = self._extract_volume_ratio_conditions(text)
        filters.extend(volume_ratio_conditions)
        
        # ========== 8. 行业条件 ==========
        industry_conditions = self._extract_industry_conditions(text)
        filters.extend(industry_conditions)
        
        # ========== 9. 价格条件 ==========
        price_range = self._extract_price_range(text)
        if price_range:
            filters.extend(price_range)
        
        price_single = self._extract_price_single(text)
        if price_single:
            filters.append(price_single)
        
        # ========== 10. 市盈率条件 ==========
        pe_cond = self._extract_pe_condition(text)
        if pe_cond:
            filters.append(pe_cond)

        # ========== 11. 价值投资条件（财报+估值）==========
        value_conditions = self._extract_value_investment_conditions(text)
        filters.extend(value_conditions)

        # ========== 12. 市净率条件 ==========
        pb_cond = self._extract_pb_condition(text)
        if pb_cond:
            filters.append(pb_cond)

        # ========== 13. 风险过滤条件 ==========
        risk_conditions = self._extract_risk_conditions(text)
        filters.extend(risk_conditions)

        return params

    def _extract_change_conditions(self, text: str) -> List[Dict]:
        """
        提取涨跌幅条件 - 核心功能
        支持：大涨、大跌、涨幅大于X、跌幅大于X等
        """
        conditions = []
        
        # ========== 大涨/涨幅大于 ==========
        # "大涨"、"大幅上涨"、"涨幅大于5%"
        if any(kw in text for kw in ['大涨', '大幅上涨', '大幅上扬']):
            conditions.append({'field': '涨幅%', 'op': '>=', 'value': 5})
        
        # "涨幅大于X%"
        up_match = re.search(r'涨幅\s?(?:大于|超过|高于|>)\s*(\d+(?:\.\d+)?)\s*%?', text)
        if up_match:
            conditions.append({
                'field': '涨幅%',
                'op': '>=',
                'value': float(up_match.group(1))
            })
        
        # "今日涨幅大于X%"
        today_up_match = re.search(r'(?:今日|今天)[的]?(?:涨幅)?\s?(?:大于|超过|高于|>)?\s*(\d+(?:\.\d+)?)\s*%?', text)
        if today_up_match:
            conditions.append({
                'field': '涨幅%',
                'op': '>=',
                'value': float(today_up_match.group(1))
            })
        
        # ========== 大跌/跌幅大于 ==========
        # "大跌"、"大幅下跌"、"大幅下挫"
        if any(kw in text for kw in ['大跌', '大幅下跌', '大幅下挫']):
            conditions.append({'field': '涨幅%', 'op': '<=', 'value': -5})
        
        # "跌幅大于X%"
        down_match = re.search(r'跌幅\s?(?:大于|超过|高于|>)\s*(\d+(?:\.\d+)?)\s*%?', text)
        if down_match:
            conditions.append({
                'field': '涨幅%',
                'op': '<=',
                'value': -float(down_match.group(1))
            })
        
        # "今日跌幅大于X%"
        today_down_match = re.search(r'(?:今日|今天)[的]?(?:跌幅)?\s?(?:大于|超过|高于|>)?\s*(\d+(?:\.\d+)?)\s*%?', text)
        if today_down_match:
            conditions.append({
                'field': '涨幅%',
                'op': '<=',
                'value': -float(today_down_match.group(1))
            })
        
        # "跌了X%"
        dropped_match = re.search(r'跌\s?了\s?(\d+(?:\.\d+)?)\s*%?', text)
        if dropped_match:
            conditions.append({
                'field': '涨幅%',
                'op': '<=',
                'value': -float(dropped_match.group(1))
            })
        
        # "涨了X%"
        rose_match = re.search(r'涨\s?了\s?(\d+(?:\.\d+)?)\s*%?', text)
        if rose_match:
            conditions.append({
                'field': '涨幅%',
                'op': '>=',
                'value': float(rose_match.group(1))
            })
        
        return conditions

    def _extract_limit_conditions(self, text: str, consecutive_days: Optional[int], days_mapping: Dict) -> List[Dict]:
        """
        提取涨跌停条件
        例如："涨停" -> 涨幅% >= 9.5（主板）
        """
        conditions = []
        
        # 检测涨跌停相关关键词
        is_limit_up = any(kw in text for kw in ['涨停', '连板', '连续涨停'])
        is_limit_down = any(kw in text for kw in ['跌停', '连续跌停'])
        
        if not is_limit_up and not is_limit_down:
            return conditions
        
        # ========== 确定涨停阈值 ==========
        limit_value = self.LIMIT_UP_THRESHOLDS['主板']  # 默认主板
        
        # 根据板块调整阈值
        if any(kw in text for kw in ['科创', '688', '创业', '300']):
            limit_value = self.LIMIT_UP_THRESHOLDS['科创创业']
        elif any(kw in text for kw in ['北交', '8开头']):
            limit_value = self.LIMIT_UP_THRESHOLDS['北交所']
        
        # 根据ST股调整阈值
        if 'ST' in text or 'st' in text:
            limit_value = self.LIMIT_UP_THRESHOLDS['ST']
        
        # ========== 涨停条件 ==========
        if is_limit_up:
            if consecutive_days and consecutive_days > 0:
                for i in range(1, consecutive_days + 1):
                    conditions.append({
                        'field': '涨幅%',
                        'op': '>=',
                        'value': limit_value,
                        'days_ago': i,
                        'note': f'涨停阈值{limit_value}%'
                    })
            else:
                conditions.append({
                    'field': '涨幅%',
                    'op': '>=',
                    'value': limit_value,
                    'days_ago': 0,
                    'note': f'涨停阈值{limit_value}%'
                })
        
        # ========== 跌停条件 ==========
        if is_limit_down:
            limit_value = -abs(limit_value)  # 取负值
            if consecutive_days and consecutive_days > 0:
                for i in range(1, consecutive_days + 1):
                    conditions.append({
                        'field': '涨幅%',
                        'op': '<=',
                        'value': limit_value,
                        'days_ago': i,
                        'note': f'跌停阈值{limit_value}%'
                    })
            else:
                conditions.append({
                    'field': '涨幅%',
                    'op': '<=',
                    'value': limit_value,
                    'days_ago': 0,
                    'note': f'跌停阈值{limit_value}%'
                })
        
        return conditions

    def _extract_board_conditions(self, text: str) -> List[Dict]:
        """
        提取板块条件（创业板、科创板等）
        通过代码前缀匹配
        """
        conditions = []
        
        # 创业板（300开头）
        if any(kw in text for kw in ['创业板', '300']):
            conditions.append({
                'field': '代码',
                'op': 'LIKE',
                'value': '30%'
            })
        
        # 科创板（688开头）
        if any(kw in text for kw in ['科创板', '科创', '688']):
            conditions.append({
                'field': '代码',
                'op': 'LIKE',
                'value': '688%'
            })
        
        # 北交所（8/4开头）
        if any(kw in text for kw in ['北交所', '北交']):
            conditions.append({
                'field': '代码',
                'op': 'LIKE',
                'value': '8%'
            })
        
        return conditions

    def _extract_custom_market_cap(self, text: str) -> List[Dict]:
        """
        提取自定义市值条件
        支持："市值大于X亿"、"流通市值小于X万"等
        """
        conditions = []
        
        # 总市值条件
        # "市值大于500亿" -> 总市值 >= 500亿
        total_cap_match = re.search(r'(?:总)?市值\s?(?:大于|超过|高于|>)\s*(\d+(?:\.\d+)?)\s*(亿|万|元)?', text)
        if total_cap_match:
            value = float(total_cap_match.group(1))
            unit = total_cap_match.group(2) or '亿'
            # 转换为元
            if unit == '亿':
                value *= 100_000_000
            elif unit == '万':
                value *= 10_000
            conditions.append({
                'field': '总市值',
                'op': '>=',
                'value': value
            })
        
        # 流通市值条件
        # "流通市值小于100亿" -> 流通市值 < 100亿
        flow_cap_match = re.search(r'流通市值\s?(?:小于|低于|<)\s*(\d+(?:\.\d+)?)\s*(亿|万|元)?', text)
        if flow_cap_match:
            value = float(flow_cap_match.group(1))
            unit = flow_cap_match.group(2) or '亿'
            if unit == '亿':
                value *= 100_000_000
            elif unit == '万':
                value *= 10_000
            conditions.append({
                'field': '流通市值',
                'op': '<',
                'value': value
            })
        
        return conditions

    def _extract_turnover_conditions(self, text: str) -> List[Dict]:
        """
        提取换手率条件
        "高换手" -> 换手率 >= 5
        "低换手" -> 换手率 < 2
        """
        conditions = []
        
        # "高换手"、"成交活跃"
        if any(kw in text for kw in ['高换手', '成交活跃', '换手率高']):
            conditions.append({
                'field': '换手率',
                'op': '>=',
                'value': 5
            })
        
        # "低换手"、"冷门"
        if any(kw in text for kw in ['低换手', '冷门', '换手率低']):
            conditions.append({
                'field': '换手率',
                'op': '<',
                'value': 2
            })
        
        # 自定义换手率条件
        # "换手率大于5%"
        turnover_match = re.search(r'换手率\s?(?:大于|超过|高于|>)\s*(\d+(?:\.\d+)?)\s*%?', text)
        if turnover_match:
            conditions.append({
                'field': '换手率',
                'op': '>=',
                'value': float(turnover_match.group(1))
            })
        
        return conditions

    def _extract_volume_ratio_conditions(self, text: str) -> List[Dict]:
        """
        提取量比条件
        "放量" -> 量比 >= 1.5
        "缩量" -> 量比 < 0.7
        """
        conditions = []
        
        # "放量"、"量能放大"
        if any(kw in text for kw in ['放量', '量能放大', '量比放大']):
            conditions.append({
                'field': '量比',
                'op': '>=',
                'value': 1.5
            })
        
        # "缩量"、"地量"
        if any(kw in text for kw in ['缩量', '地量', '量比缩小']):
            conditions.append({
                'field': '量比',
                'op': '<',
                'value': 0.7
            })
        
        # 自定义量比条件
        # "量比大于2"
        vol_ratio_match = re.search(r'量比\s?(?:大于|超过|高于|>)\s*(\d+(?:\.\d+)?)', text)
        if vol_ratio_match:
            conditions.append({
                'field': '量比',
                'op': '>=',
                'value': float(vol_ratio_match.group(1))
            })
        
        return conditions

    def _extract_industry_conditions(self, text: str) -> List[Dict]:
        """
        提取行业条件
        "科技股" -> 细分行业 LIKE "%科技%"
        """
        conditions = []
        
        # 行业关键词映射到细分行业匹配模式
        industry_mapping = {
            '科技': ['%科技%', '%软件%', '%电子%', '%计算机%'],
            '医药': ['%医药%', '%医疗%', '%生物%'],
            '新能源': ['%新能源%', '%光伏%', '%锂电池%', '%储能%'],
            '白酒': ['%白酒%', '%食品%', '%饮料%'],
            '军工': ['%军工%', '%国防%', '%航天%'],
            '银行': ['%银行%'],
            '证券': ['%证券%', '%券商%'],
            '房地产': ['%房地产%', '%地产%', '%建筑%'],
            '半导体': ['%半导体%', '%芯片%', '%集成电路%'],
            '消费': ['%消费%', '%零售%'],
            '汽车': ['%汽车%', '%新能源车%'],
            '家电': ['%家电%', '%电器%'],
            '化工': ['%化工%', '%化学%'],
            '机械': ['%机械%', '%设备%'],
            '通信': ['%通信%', '%电信%'],
            '传媒': ['%传媒%', '%文化%', '%游戏%'],
        }
        
        for keyword, patterns in industry_mapping.items():
            if keyword in text:
                # 使用OR逻辑组合多个模式
                for pattern in patterns:
                    conditions.append({
                        'field': '细分行业',
                        'op': 'LIKE',
                        'value': pattern
                    })
                break  # 只匹配一个主要行业
        
        return conditions

    def _extract_flex_backtest_params(self, text: str) -> Dict[str, Any]:
        """
        抽取灵活回测参数 - 支持 days_ago 时序条件
        """
        filters = []
        params = {
            'filters': filters,
            'target_day': 0,  # 默认今天
            'description': text
        }
        
        # ========== 分析时间表达 ==========
        consecutive_days = self._extract_consecutive_days(text)
        days_mapping = {
            '今天': 0, '今日': 0,
            '昨天': 1, '昨日': 1,
            '前天': 2, '前日': 2,
        }
        
        # ========== 成交额条件 ==========
        volume_conditions = self._extract_volume_with_time(text, days_mapping)
        filters.extend(volume_conditions)
        
        # ========== 涨跌幅条件 ==========
        limit_conditions = self._extract_limit_conditions(text, consecutive_days, days_mapping)
        filters.extend(limit_conditions)
        
        # ========== 板块条件 ==========
        board_conditions = self._extract_board_conditions(text)
        filters.extend(board_conditions)
        
        # ========== 市值条件 ==========
        market_cap_conditions = get_market_cap_conditions(text)
        filters.extend(market_cap_conditions)
        
        # ========== 价格条件 ==========
        price_range = self._extract_price_range(text)
        if price_range:
            for pc in price_range:
                pc['days_ago'] = 0
            filters.extend(price_range)
        
        # ========== 市盈率条件 ==========
        pe_cond = self._extract_pe_condition(text)
        if pe_cond:
            filters.append(pe_cond)
        
        return params

    def _extract_volume_condition(self, text: str) -> Optional[Dict]:
        """提取成交额条件"""
        patterns = [
            r'成交[额亿]?(?:大于|高于|超过|大于等于)?\s*(\d+(?:\.\d+)?)\s*(万|亿)?',
            r'成交量?(?:大于|高于|超过|大于等于)?\s*(\d+(?:\.\d+)?)\s*(万|亿)?',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = float(match.group(1))
                unit = match.group(2) or '万'
                if unit == '亿':
                    value *= 100_000_000  # 转换为元
                else:
                    value *= 10_000  # 万转换为元
                return {
                    'field': '成交额',
                    'op': '>=',
                    'value': value
                }
        return None

    def _extract_volume_with_time(self, text: str, days_mapping: Dict) -> List[Dict]:
        """提取带时间的成交额条件"""
        conditions = []
        
        # 检测连续N天成交额大于X
        consecutive = re.search(r'连续(\d+)天.*?成交[额亿]?(?:大于|高于|超过)?\s*(\d+(?:\.\d+)?)\s*(万|亿)?', text)
        if consecutive:
            days = int(consecutive.group(1))
            value = float(consecutive.group(2))
            unit = consecutive.group(3) or '万'
            if unit == '亿':
                value *= 100_000_000
            else:
                value *= 10_000
            
            for i in range(1, days + 1):
                conditions.append({
                    'field': '成交额',
                    'op': '>=',
                    'value': value,
                    'days_ago': i
                })
        
        return conditions

    def _extract_consecutive_days(self, text: str) -> Optional[int]:
        """提取连续天数"""
        match = re.search(r'连续(\d+)天', text)
        if match:
            return int(match.group(1))
        
        day_count = {'两天': 2, '三天': 3, '四天': 4, '五天': 5}
        for phrase, count in day_count.items():
            if phrase in text:
                return count
        
        return None

    def _extract_time_from_context(self, text: str, days_mapping: Dict) -> int:
        """从上下文提取时间"""
        for phrase, days in days_mapping.items():
            if phrase in text:
                return days
        
        day_n = re.search(r'第(\d+)天', text)
        if day_n:
            return int(day_n.group(1))
        
        return 0

    def _extract_price_range(self, text: str) -> List[Dict]:
        """提取价格区间条件"""
        conditions = []
        
        # 区间格式: 10-20元 或 价格在10到20之间
        range_match = re.search(r'价格?\s*(?:在|低于|高于|小于|大于)?\s*(\d+(?:\.\d+)?)\s*[-~至]\s*(\d+(?:\.\d+)?)', text)
        if range_match:
            low, high = float(range_match.group(1)), float(range_match.group(2))
            conditions.append({
                'field': '现价',
                'op': '>=',
                'value': low
            })
            conditions.append({
                'field': '现价',
                'op': '<=',
                'value': high
            })
        
        return conditions

    def _extract_price_single(self, text: str) -> Optional[Dict]:
        """提取单个价格条件"""
        # 低价股
        if any(kw in text for kw in ['低价股', '几块钱', '便宜股票']):
            return {'field': '现价', 'op': '<', 'value': 10}
        
        # 百元股
        if any(kw in text for kw in ['百元股', '高价股']):
            return {'field': '现价', 'op': '>=', 'value': 100}
        
        # 价格大于
        gt_match = re.search(r'价格?\s*(?:高于|大于|>)\s*(\d+(?:\.\d+)?)', text)
        if gt_match:
            return {
                'field': '现价',
                'op': '>',
                'value': float(gt_match.group(1))
            }
        
        # 价格小于
        lt_match = re.search(r'价格?\s*(?:低于|小于|<)\s*(\d+(?:\.\d+)?)', text)
        if lt_match:
            return {
                'field': '现价',
                'op': '<',
                'value': float(lt_match.group(1))
            }
        
        return None

    def _extract_pe_condition(self, text: str) -> Optional[Dict]:
        """提取市盈率条件"""
        pe_match = re.search(r'市盈率?\s*(?:低于|小于|<)\s*(\d+(?:\.\d+)?)', text)
        if pe_match:
            return {
                'field': '市盈率',
                'op': '<',
                'value': float(pe_match.group(1))
            }
        return None

    def _extract_pb_condition(self, text: str) -> Optional[Dict]:
        """提取市净率条件"""
        # "市净率低于X"
        pb_match = re.search(r'市净率?\s*(?:低于|小于|<)\s*(\d+(?:\.\d+)?)', text)
        if pb_match:
            return {
                'field': '市净率',
                'op': '<',
                'value': float(pb_match.group(1)),
                'source': 'market'
            }
        # "PB小于X"
        pb_match2 = re.search(r'PB\s*(?:低于|小于|<)\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if pb_match2:
            return {
                'field': '市净率',
                'op': '<',
                'value': float(pb_match2.group(1)),
                'source': 'market'
            }
        return None

    def _extract_value_investment_conditions(self, text: str) -> List[Dict]:
        """
        提取价值投资条件

        从用户输入中识别价值投资相关表述，转换为结构化筛选条件。
        来源：phrase_mapping.py 中的 VALUE_INVESTMENT_PHRASES

        支持的类别：
        - 估值：低估值、破净、低市净率
        - 盈利质量：绩优股、ROE高、利润扎实
        - 财务健康：低负债、现金流好、偿债无忧
        - 分红回报：高股息、红利股
        - 成长稳健：业绩平稳、稳步增长
        - 市值风格：蓝筹股、中盘价值
        """
        return get_value_investment_conditions(text)

    def _extract_risk_conditions(self, text: str) -> List[Dict]:
        """
        提取风险过滤条件

        1. 排除ST股
        2. 排除退市股
        3. 排除冷门/垃圾股（成交额下限）
        """
        conditions = []

        # 排除ST：如果用户明确说了排除ST
        if any(kw in text for kw in ['排除ST', '不要ST', '去掉ST', '剔除ST', '非ST']):
            conditions.append({
                'field': '风险标签',
                'op': '!=',
                'value': 'ST',
                'source': 'market',
                'note': '排除ST股'
            })

        # 排除冷门股（成交额下限）
        if any(kw in text for kw in ['排除冷门', '排除垃圾', '非冷门', '活跃']):
            conditions.append({
                'field': '日成交额下限',
                'op': '>=',
                'value': 5000000,
                'source': 'market',
                'note': '排除成交额 < 500万的冷门股'
            })

        return conditions

    def _extract_grid_backtest_params(self, text: str) -> Dict[str, Any]:
        """抽取网格回测参数"""
        params = {
            'stock_code': None,
            'grid_buy_percent': None,
            'grid_sell_percent': None,
            'start_date': None,
            'base_price_type': None,
            'description': text
        }
        
        # 股票代码
        code_match = re.search(r'(\d{6})', text)
        if code_match:
            params['stock_code'] = code_match.group(1)
        
        # 股票名称
        name_patterns = [
            r'([\u4e00-\u9fa5]{2,8})(?:进行|做)?(?:网格|回测)',
            r'对\s*([\u4e00-\u9fa5]{2,8})\s*进行',
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text)
            if name_match:
                params['stock_name'] = name_match.group(1)
                break
        
        # 网格买卖点
        buy_match = re.search(r'下[跌调]?\s*(\d+(?:\.\d+)?)\s*%?\s*(?:买|买入|加仓)', text)
        if buy_match:
            params['grid_buy_percent'] = -float(buy_match.group(1))
        
        sell_match = re.search(r'上[涨跌]?\s*(\d+(?:\.\d+)?)\s*%?\s*(?:卖|卖出|止盈|减仓)', text)
        if sell_match:
            params['grid_sell_percent'] = float(sell_match.group(1))
        
        # 日期
        date_match = re.search(r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})', text)
        if date_match:
            year, month, day = date_match.groups()
            params['start_date'] = f"{year}{month.zfill(2)}{day.zfill(2)}"
        
        # 基准价类型
        if '开盘价' in text:
            params['base_price_type'] = 'open_price'
        elif '均价' in text or '平均价' in text:
            params['base_price_type'] = 'avg_price'
        
        return params

    def _llm_extract(self, user_input: str, intent: IntentType) -> Dict[str, Any]:
        """使用大模型抽取参数"""
        if intent == IntentType.STOCK_SELECT:
            prompt = STOCK_SELECT_PROMPT.format(user_input=user_input)
        elif intent == IntentType.FLEX_BACKTEST:
            prompt = FLEX_BACKTEST_PROMPT.format(user_input=user_input)
        else:
            prompt = GRID_BACKTEST_PROMPT.format(user_input=user_input)

        try:
            print(f"[INFO] 调用AI解析: {user_input[:50]}...")
            response = self.llm_client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的股票策略分析助手。请严谨地分析用户输入，确保参数准确。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature
            )

            content = response['choices'][0]['message']['content']
            print(f"[DEBUG] AI原始响应: {content[:200]}...")

            # 尝试提取JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                params = data.get('params', {})
                if params:
                    return params
                return data

        except json.JSONDecodeError as e:
            print(f"[FAIL] JSON解析失败: {e}")
        except Exception as e:
            print(f"LLM参数抽取失败: {e}")

        return {}

    def _merge_params(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """合并参数，override优先级更高"""
        result = base.copy()
        for key, value in override.items():
            if value is not None and value != '' and value != []:
                result[key] = value
        return result
