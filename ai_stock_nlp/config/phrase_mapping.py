"""
股票自然语言话术映射表模块

【模块功能】
将用户口语化表达转换为量化条件，用于参数抽取的规则匹配。

【话术类型】
1. MARKET_CAP_PHRASES - 市值规模映射
   - 小盘股: ≤50亿
   - 中盘股: 50-500亿
   - 大盘股: 500-2000亿
   - 超级大盘: >2000亿

2. TREND_PHRASES - 趋势强弱映射
   - 走势强势/近期很强/趋势向上
   - 短期强势/最近几天很强
   - 走势弱势/一直跌/近期弱势
   - 跑赢/跑输大盘

3. INDUSTRY_LEADER_PHRASES - 行业龙头映射

4. LIMIT_UP_THRESHOLDS - 涨停阈值
5. LIMIT_DOWN_THRESHOLDS - 跌停阈值

6. VOLUME_PHRASES - 成交额等级
   - 天量: ≥100亿
   - 巨量: ≥50亿
   - 放量: ≥10亿
   - 缩量: <1亿
   - 地量: <5000万

7. TURNOVER_RATIO_PHRASES - 量比相关

8. VALUE_INVESTMENT_PHRASES - 价值投资相关

9. SYNONYM_MAPPING - 同义词映射表
"""

# 市值规模映射（单位：亿元）
MARKET_CAP_PHRASES = {
    # 小盘股：总市值 ≤ 50亿
    '小盘股': {'总市值_max': 50, '说明': '总市值 ≤ 50亿'},
    '小盘标的': {'总市值_max': 50, '说明': '总市值 ≤ 50亿'},
    '盘子小': {'总市值_max': 50, '说明': '总市值 ≤ 50亿'},
    '小市值': {'总市值_max': 50, '说明': '总市值 ≤ 50亿'},
    '超小盘': {'总市值_max': 30, '说明': '总市值 ≤ 30亿'},

    # 中盘股：50亿 < 总市值 ≤ 500亿
    '中盘股': {'总市值_min': 50, '总市值_max': 500, '说明': '50亿 < 总市值 ≤ 500亿'},
    '中等市值': {'总市值_min': 50, '总市值_max': 500, '说明': '50亿 < 总市值 ≤ 500亿'},

    # 大盘股：500亿 < 总市值 ≤ 2000亿
    '大盘股': {'总市值_min': 500, '总市值_max': 2000, '说明': '500亿 < 总市值 ≤ 2000亿'},
    '大盘': {'总市值_min': 500, '总市值_max': 2000, '说明': '500亿 < 总市值 ≤ 2000亿'},
    '大盘的': {'总市值_min': 500, '总市值_max': 2000, '说明': '500亿 < 总市值 ≤ 2000亿'},
    '蓝筹大盘': {'总市值_min': 500, '总市值_max': 2000, '说明': '500亿 < 总市值 ≤ 2000亿'},
    '大盘蓝筹': {'总市值_min': 500, '总市值_max': 2000, '说明': '500亿 < 总市值 ≤ 2000亿'},
    '大盘标的': {'总市值_min': 500, '总市值_max': 2000, '说明': '500亿 < 总市值 ≤ 2000亿'},

    # 超级大盘：总市值 > 2000亿
    '超级大盘': {'总市值_min': 2000, '说明': '总市值 > 2000亿'},
    '巨无霸龙头': {'总市值_min': 2000, '说明': '总市值 > 2000亿'},
    '超大市值': {'总市值_min': 2000, '说明': '总市值 > 2000亿'},
    '大盘龙头': {'总市值_min': 2000, '说明': '总市值 > 2000亿'},
}

# 趋势强弱映射
TREND_PHRASES = {
    # 强势
    '走势强势': {'累计涨幅_days': 20, '累计涨幅_min': 15, '说明': '近20日累计涨幅 ≥ 15%'},
    '近期很强': {'累计涨幅_days': 20, '累计涨幅_min': 15, '说明': '近20日累计涨幅 ≥ 15%'},
    '趋势向上': {'累计涨幅_days': 20, '累计涨幅_min': 15, '说明': '近20日累计涨幅 ≥ 15%'},
    '近期强势': {'累计涨幅_days': 20, '累计涨幅_min': 15, '说明': '近20日累计涨幅 ≥ 15%'},
    
    # 短期强势
    '短期强势': {'累计涨幅_days': 5, '累计涨幅_min': 8, '说明': '近5日累计涨幅 ≥ 8%'},
    '最近几天很强': {'累计涨幅_days': 5, '累计涨幅_min': 8, '说明': '近5日累计涨幅 ≥ 8%'},
    '最近强势': {'累计涨幅_days': 5, '累计涨幅_min': 8, '说明': '近5日累计涨幅 ≥ 8%'},
    '短期走强': {'累计涨幅_days': 5, '累计涨幅_min': 8, '说明': '近5日累计涨幅 ≥ 8%'},
    
    # 弱势
    '走势弱势': {'累计涨幅_days': 20, '累计涨幅_max': -10, '说明': '近20日累计涨幅 ≤ -10%'},
    '一直跌': {'累计涨幅_days': 20, '累计涨幅_max': -10, '说明': '近20日累计涨幅 ≤ -10%'},
    '走得很弱': {'累计涨幅_days': 20, '累计涨幅_max': -10, '说明': '近20日累计涨幅 ≤ -10%'},
    '近期弱势': {'累计涨幅_days': 20, '累计涨幅_max': -10, '说明': '近20日累计涨幅 ≤ -10%'},
    
    # 跑赢大盘
    '跑赢大盘': {'超额收益_days': 20, '超额收益_min': 5, '说明': '近20日个股涨幅 - 沪深300涨幅 ≥ 5%'},
    '比大盘强': {'超额收益_days': 20, '超额收益_min': 5, '说明': '近20日个股涨幅 - 沪深300涨幅 ≥ 5%'},
    '强于大盘': {'超额收益_days': 20, '超额收益_min': 5, '说明': '近20日个股涨幅 - 沪深300涨幅 ≥ 5%'},
    
    # 跑输大盘
    '跑输大盘': {'超额收益_days': 20, '超额收益_max': -5, '说明': '近20日个股涨幅 - 沪深300涨幅 ≤ -5%'},
    '比大盘弱': {'超额收益_days': 20, '超额收益_max': -5, '说明': '近20日个股涨幅 - 沪深300涨幅 ≤ -5%'},
    '弱于大盘': {'超额收益_days': 20, '超额收益_max': -5, '说明': '近20日个股涨幅 - 沪深300涨幅 ≤ -5%'},
}

# 行业龙头映射
INDUSTRY_LEADER_PHRASES = {
    '行业龙头': {'is_industry_leader': True, '说明': '申万一级/二级行业内市值排名第1'},
    '板块龙头': {'is_industry_leader': True, '说明': '申万一级/二级行业内市值排名第1'},
    '行业老大': {'is_industry_leader': True, '说明': '申万一级/二级行业内市值排名第1'},
    '细分龙头': {'is_industry_leader': True, '说明': '申万二级行业内市值排名第1'},
}

# 涨停跌停阈值
LIMIT_UP_THRESHOLDS = {
    '主板': {'threshold': 9.5, 'description': '涨幅 ≥ 9.5% 视为涨停（含四舍五入容差）'},
    '科创板': {'threshold': 19.5, 'description': '涨幅 ≥ 19.5% 视为涨停'},
    '创业板': {'threshold': 19.5, 'description': '涨幅 ≥ 19.5% 视为涨停'},
    '北交所': {'threshold': 29.5, 'description': '涨幅 ≥ 29.5% 视为涨停'},
    'ST股': {'threshold': 4.5, 'description': '涨幅 ≥ 4.5% 视为涨停'},
}

LIMIT_DOWN_THRESHOLDS = {
    '主板': {'threshold': -9.5, 'description': '跌幅 ≤ -9.5% 视为跌停'},
    '科创板': {'threshold': -19.5, 'description': '跌幅 ≤ -19.5% 视为跌停'},
    '创业板': {'threshold': -19.5, 'description': '跌幅 ≤ -19.5% 视为跌停'},
    '北交所': {'threshold': -29.5, 'description': '跌幅 ≤ -29.5% 视为跌停'},
    'ST股': {'threshold': -4.5, 'description': '跌幅 ≤ -4.5% 视为跌停'},
}

# 成交额等级
VOLUME_PHRASES = {
    '天量': {'成交额_min': 10000000000, '说明': '成交额 ≥ 100亿'},
    '巨量': {'成交额_min': 5000000000, '说明': '成交额 ≥ 50亿'},
    '放量': {'成交额_min': 1000000000, '说明': '成交额 ≥ 10亿'},
    '缩量': {'成交额_min': None, '成交额_max': 100000000, '说明': '成交额 < 1亿'},
    '地量': {'成交额_min': None, '成交额_max': 50000000, '说明': '成交额 < 5000万'},
}

# 量比相关
TURNOVER_RATIO_PHRASES = {
    '高换手': {'换手率_min': 10, '说明': '换手率 ≥ 10%'},
    '低换手': {'换手率_max': 2, '说明': '换手率 < 2%'},
    '量比放大': {'量比_min': 2, '说明': '量比 ≥ 2'},
    '量比萎缩': {'量比_max': 0.5, '说明': '量比 < 0.5'},
}

# =============================================================================
# 价值投资相关（扩展版）
# =============================================================================
# 结构: {'source': 'market'|'financial', 'conditions': [...]}
# source='market': 从实时行情获取（市盈率、市净率等）
# source='financial': 从财报数据库获取（ROE、净利率等）
VALUE_INVESTMENT_PHRASES = {
    # ---- 估值（market） ----
    '低估值': {'source': 'market', 'field': '市盈率', 'op': '<', 'value': 20, '说明': '市盈率 < 20'},
    '估值低位': {'source': 'market', 'field': '市盈率', 'op': '<', 'value': 20, '说明': '市盈率 < 20'},
    '低估': {'source': 'market', 'field': '市盈率', 'op': '<', 'value': 15, '说明': '市盈率 < 15'},
    '深度低估': {'source': 'market', 'field': '市盈率', 'op': '<', 'value': 10, '说明': '市盈率 < 10'},
    '极度低估': {'source': 'market', 'field': '市盈率', 'op': '<', 'value': 10, '说明': '市盈率 < 10'},
    '便宜股票': {'source': 'market', 'field': '市盈率', 'op': '<', 'value': 15, '说明': '市盈率 < 15'},
    '破净': {'source': 'market', 'field': '市净率', 'op': '<', 'value': 1, '说明': '市净率 < 1'},
    '跌破净资产': {'source': 'market', 'field': '市净率', 'op': '<', 'value': 1, '说明': '市净率 < 1'},
    '低市净率': {'source': 'market', 'field': '市净率', 'op': '<', 'value': 2, '说明': '市净率 < 2'},
    'PB低': {'source': 'market', 'field': '市净率', 'op': '<', 'value': 2, '说明': '市净率 < 2'},
    '低估值蓝筹': {
        'source': 'market', 'field': '市盈率', 'op': '<', 'value': 20,
        'extra': [{'field': '总市值', 'op': '>=', 'value': 50000000000, 'source': 'market'}],
        '说明': '市盈率 < 20 且 总市值 >= 500亿'
    },

    # ---- 盈利质量（financial） ----
    '绩优股': {'source': 'financial', 'field': '净资产收益率ROE', 'op': '>=', 'value': 12, '说明': 'ROE >= 12%'},
    '盈利能力强': {'source': 'financial', 'field': '净资产收益率ROE', 'op': '>=', 'value': 12, '说明': 'ROE >= 12%'},
    'ROE高': {'source': 'financial', 'field': '净资产收益率ROE', 'op': '>=', 'value': 12, '说明': 'ROE >= 12%'},
    '盈利稳定': {'source': 'financial', 'field': '净资产收益率ROE', 'op': '>=', 'value': 8, '说明': 'ROE >= 8%'},
    '业绩好': {'source': 'financial', 'field': '净资产收益率ROE', 'op': '>=', 'value': 8, '说明': 'ROE >= 8%'},
    '利润扎实': {'source': 'financial', 'field': '销售净利率', 'op': '>=', 'value': 5, '说明': '销售净利率 >= 5%'},
    '净利率高': {'source': 'financial', 'field': '销售净利率', 'op': '>=', 'value': 5, '说明': '销售净利率 >= 5%'},

    # ---- 财务健康（financial） ----
    '财务稳健': {
        'source': 'financial', 'field': '资产负债率', 'op': '<', 'value': 60,
        'extra': [{'field': '经营性现金流', 'op': '>', 'value': 0, 'source': 'financial'}],
        '说明': '资产负债率 < 60% 且 经营性现金流 > 0'
    },
    '低负债': {'source': 'financial', 'field': '资产负债率', 'op': '<', 'value': 60, '说明': '资产负债率 < 60%'},
    '负债合理': {'source': 'financial', 'field': '资产负债率', 'op': '<', 'value': 60, '说明': '资产负债率 < 60%'},
    '现金流好': {'source': 'financial', 'field': '经营性现金流', 'op': '>', 'value': 0, '说明': '经营性现金流 > 0'},
    '不差钱': {'source': 'financial', 'field': '经营性现金流', 'op': '>', 'value': 0, '说明': '经营性现金流 > 0'},
    '现金流充沛': {'source': 'financial', 'field': '经营性现金流', 'op': '>', 'value': 0, '说明': '经营性现金流 > 0'},
    '短期偿债无忧': {'source': 'financial', 'field': '流动比率', 'op': '>', 'value': 1, '说明': '流动比率 > 1'},

    # ---- 分红回报（financial） ----
    '高股息': {'source': 'financial', 'field': '股息率', 'op': '>=', 'value': 3.5, '说明': '股息率 >= 3.5%'},
    '红利股': {'source': 'financial', 'field': '股息率', 'op': '>=', 'value': 3.5, '说明': '股息率 >= 3.5%'},
    '分红大方': {'source': 'financial', 'field': '股息率', 'op': '>=', 'value': 3.5, '说明': '股息率 >= 3.5%'},
    '中等红利': {'source': 'financial', 'field': '股息率', 'op': '>=', 'value': 2.5, '说明': '股息率 >= 2.5%'},

    # ---- 成长稳健（financial） ----
    '业绩平稳': {
        'source': 'financial', 'field': '营收增速', 'op': '>=', 'value': 0,
        'extra': [{'field': '营收增速', 'op': '<=', 'value': 20, 'source': 'financial'}],
        '说明': '0% <= 营收增速 <= 20%'
    },
    '稳步增长': {
        'source': 'financial', 'field': '净利润增速', 'op': '>=', 'value': 0,
        'extra': [{'field': '净利润增速', 'op': '<=', 'value': 20, 'source': 'financial'}],
        '说明': '0% <= 净利润增速 <= 20%'
    },
    '营收高增长': {'source': 'financial', 'field': '营收增速', 'op': '>=', 'value': 30, '说明': '营收增速 >= 30%'},
    '营收大增': {'source': 'financial', 'field': '营收增速', 'op': '>=', 'value': 30, '说明': '营收增速 >= 30%'},
    '业绩大增': {'source': 'financial', 'field': '净利润增速', 'op': '>=', 'value': 50, '说明': '净利润增速 >= 50%'},
    '净利润翻倍': {'source': 'financial', 'field': '净利润增速', 'op': '>=', 'value': 100, '说明': '净利润增速 >= 100%'},

    # ---- 市值&风格（market） ----
    '蓝筹股': {'source': 'market', 'field': '总市值', 'op': '>=', 'value': 50000000000, '说明': '总市值 >= 500亿'},
    '大盘蓝筹': {'source': 'market', 'field': '总市值', 'op': '>=', 'value': 50000000000, '说明': '总市值 >= 500亿'},
    '权重股': {'source': 'market', 'field': '总市值', 'op': '>=', 'value': 50000000000, '说明': '总市值 >= 500亿'},
    '中盘价值': {
        'source': 'market', 'field': '总市值', 'op': '>=', 'value': 20000000000,
        'extra': [{'field': '总市值', 'op': '<', 'value': 50000000000, 'source': 'market'}],
        '说明': '200亿 <= 总市值 < 500亿'
    },
}


def get_market_cap_conditions(text: str) -> list:
    """
    从文本中提取市值条件
    
    Args:
        text: 用户输入文本
    
    Returns:
        条件列表
    """
    conditions = []
    
    for phrase, params in MARKET_CAP_PHRASES.items():
        if phrase in text:
            if '总市值_min' in params:
                conditions.append({
                    'field': '总市值',
                    'op': '>=',
                    'value': params['总市值_min'] * 100000000,  # 转换为元
                    'note': params['说明']
                })
            if '总市值_max' in params:
                conditions.append({
                    'field': '总市值',
                    'op': '<=',
                    'value': params['总市值_max'] * 100000000,  # 转换为元
                    'note': params['说明']
                })
    
    return conditions


def get_trend_conditions(text: str) -> list:
    """
    从文本中提取趋势条件
    
    Args:
        text: 用户输入文本
    
    Returns:
        条件列表
    """
    conditions = []
    
    for phrase, params in TREND_PHRASES.items():
        if phrase in text:
            days = params.get('累计涨幅_days')
            if '累计涨幅_min' in params:
                conditions.append({
                    'field': f'{days}日涨幅%',
                    'op': '>=',
                    'value': params['累计涨幅_min'],
                    'days_ago': 0,
                    'note': params['说明']
                })
            if '累计涨幅_max' in params:
                conditions.append({
                    'field': f'{days}日涨幅%',
                    'op': '<=',
                    'value': params['累计涨幅_max'],
                    'days_ago': 0,
                    'note': params['说明']
                })
    
    return conditions


# 常用同义词映射表
SYNONYM_MAPPING = {
    # 涨跌幅
    '涨幅': '涨幅%',
    '涨幅%': '涨幅%',
    '涨跌幅': '涨幅%',
    '涨跌': '涨跌额',

    # 价格
    '现价': '最新价',
    '当前价': '最新价',
    '价格': '最新价',
    '股价': '最新价',

    # 成交额
    '成交额': '成交额',
    '总金额': '成交额',
    '交易额': '成交额',
    '金额': '成交额',

    # 成交量
    '成交量': '成交量',
    '总量': '成交量',
    '成交股数': '成交量',

    # 市盈率
    '市盈率': '市盈率-动态',
    '市盈(动)': '市盈率-动态',
    'PE': '市盈率-动态',

    # 市值
    '总市值': '总市值',
    '流通市值': '流通市值',
    '市值': '总市值',
}


def get_value_investment_conditions(text: str) -> list:
    """
    从文本中提取价值投资条件

    【处理逻辑】
    1. 遍历VALUE_INVESTMENT_PHRASES匹配关键词
    2. 提取主条件和额外条件
    3. 标注source字段(market/financial)

    Args:
        text: 用户输入文本

    Returns:
        条件列表，每项包含field/op/value/source
    """
    conditions = []

    for phrase, params in VALUE_INVESTMENT_PHRASES.items():
        if phrase in text:
            # 主条件
            main_cond = {
                'field': params['field'],
                'op': params['op'],
                'value': params['value'],
                'source': params.get('source', 'market'),
                'note': params.get('说明', '')
            }

            # 避免重复添加同一字段的条件
            if not _is_duplicate(conditions, main_cond):
                conditions.append(main_cond)

            # 额外条件（如低估值蓝筹同时需要市值条件）
            for extra in params.get('extra', []):
                extra_cond = {
                    'field': extra['field'],
                    'op': extra['op'],
                    'value': extra['value'],
                    'source': extra.get('source', 'market'),
                    'note': ''
                }
                if not _is_duplicate(conditions, extra_cond):
                    conditions.append(extra_cond)

    return conditions


def _is_duplicate(conditions: list, new_cond: dict) -> bool:
    """检查条件是否重复（同字段+同source+同op视为重复）"""
    for c in conditions:
        if (c['field'] == new_cond['field']
                and c.get('source') == new_cond.get('source')
                and c['op'] == new_cond['op']):
            return True
    return False
