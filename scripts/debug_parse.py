import akshare as ak
import pandas as pd
import numpy as np

# 测试解析
def parse_number(value) -> float:
    if pd.isna(value) or value is None:
        return None
    
    value = str(value).strip()
    
    if value in ['False', '', '-', 'nan', 'NaN', 'None', 'N/A']:
        return None
    
    units = {'亿': 100000000, '万': 10000, '千': 1000, '百': 100}
    
    for unit, multiplier in units.items():
        if unit in value:
            try:
                num_part = value.replace(unit, '').strip().replace(',', '')
                num = float(num_part)
                if pd.isna(num):
                    return None
                return num * multiplier
            except:
                return None
    
    try:
        num = float(value.replace(',', ''))
        if pd.isna(num):
            return None
        return num
    except:
        return None

# 获取利润表
print("获取利润表...")
df = ak.stock_financial_benefit_ths(symbol='000001')

# 尝试构建一条完整的记录
row = df.iloc[0]

# 模拟 merge_financial_data 的逻辑
result = {}
result['stock_code'] = '000001'
result['stock_name'] = '平安银行'
result['report_date'] = str(row.get('报告期', ''))
result['revenue'] = parse_number(row.get('*营业总收入') or row.get('一、营业总收入'))
result['net_profit'] = parse_number(row.get('*净利润') or row.get('五、净利润'))
result['total_cost'] = parse_number(row.get('*营业支出') or row.get('二、营业支出'))
result['operating_profit'] = parse_number(row.get('三、营业利润'))
result['basic_eps'] = parse_number(row.get('（一）基本每股收益'))

print(f"\nResult dict:")
for k, v in result.items():
    print(f"  {k}: {v}, type: {type(v)}, is NaN: {v is not None and str(v) == 'nan'}")

# 检查是否有 NaN 值
for k, v in result.items():
    if isinstance(v, float) and np.isnan(v):
        print(f"Found NaN at {k}!")
    if v is not None and not isinstance(v, (int, float, str)):
        print(f"Unexpected type at {k}: {type(v)}")
