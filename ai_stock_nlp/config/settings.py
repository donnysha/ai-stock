"""
系统配置文件

【模块功能】
统一管理系统配置参数，支持 .env 文件和环境变量。

【安全策略】
- 所有敏感信息（密码、API Key）通过环境变量注入，代码中不存储任何真实凭证
- 本地开发：在项目根目录创建 .env 文件（参考 .env.example）
- 云部署：通过云平台设置环境变量

【环境变量】
- DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME
- AI_MODEL, AI_API_BASE, AI_API_KEY
- LOG_LEVEL
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 加载 .env 文件（本地开发用，生产环境通过系统环境变量注入）
# .env 文件不提交 git，详见 .env.example
try:
    from dotenv import load_dotenv
    _env_file = PROJECT_ROOT.parent / '.env'
    if _env_file.exists():
        load_dotenv(_env_file)
except ImportError:
    pass  # python-dotenv 未安装时跳过（生产环境直接用系统环境变量）

# =============================================================================
# 数据库配置
# =============================================================================
# 敏感信息通过环境变量 / .env 注入，不提供默认值
DB_CONFIG = {
    'host': os.getenv('DB_HOST', ''),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASS', ''),
    'database': os.getenv('DB_NAME', 'stock'),
    'charset': 'utf8mb4'
}

# 统一表名（所有数据在一个表中）
STOCK_TABLE = 'stock_daily_full'

# =============================================================================
# AI模型配置 - 火山引擎ARK
# =============================================================================
# 官方文档: https://www.volcengine.com/docs/82379/1399008
# API Key 通过环境变量 AI_API_KEY 注入，不提供默认值
# 注意: model 使用的是端点ID (ep-xxx)，不是模型名称
AI_CONFIG = {
    'model': os.getenv('AI_MODEL', ''),
    'api_base': os.getenv('AI_API_BASE', ''),
    'api_key': os.getenv('AI_API_KEY', ''),
    'temperature': 0,  # 固定为0，确保输出稳定
    'timeout': 60
}

# =============================================================================
# 回测配置
# =============================================================================
# 网格交易回测的默认参数
BACKTEST_CONFIG = {
    'default_start_date': '20240101',      # 默认回测起始日期
    'default_end_date': None,               # None表示今天
    'initial_capital': 1000000,            # 默认初始资金100万
    'commission_rate': 0.0003,             # 佣金费率万三（买入卖出都收）
    'stamp_tax': 0.001,                   # 印花税千一（仅卖出时收取）
    'max_position': 1.0,                   # 最大持仓比例100%
}

# =============================================================================
# 选股配置
# =============================================================================
STOCK_SELECT_CONFIG = {
    'default_limit': 50,        # 默认返回50条
    'min_volume': 0,           # 最小成交量过滤（0表示不过滤）
    'price_decimal_places': 2, # 价格保留小数位
}

# =============================================================================
# 前端配置
# =============================================================================
FRONTEND_CONFIG = {
    'page_title': 'AI股票策略分析系统',
    'page_icon': '📈',
    'layout': 'wide',
    'default_stock': '000001',
}

# =============================================================================
# 日志配置
# =============================================================================
LOG_CONFIG = {
    'level': os.getenv('LOG_LEVEL', 'INFO'),
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': PROJECT_ROOT / 'logs' / 'app.log'
}

# =============================================================================
# 缓存配置
# =============================================================================
CACHE_CONFIG = {
    'enable': True,
    'ttl': 300,      # 缓存5分钟
    'max_size': 1000  # 最大缓存数量
}
