"""数据获取器验证脚本"""
import sys
sys.path.insert(0, 'D:/code/ai-stock/ai_stock_nlp')

from data_layer.akshare_data_fetcher import AkshareDataFetcher

print("测试 AkshareDataFetcher")
print("=" * 50)

fetcher = AkshareDataFetcher()

# 测试K线数据
print("\n[1] 测试 K线数据")
df = fetcher.get_kline_dataframe('000001', '20240101', '20240110')
if not df.empty:
    print("列名:", list(df.columns))
    print("\n数据预览:")
    print(df[['trade_date', '今开', '现价', '最高', '最低', '总量', '总金额']].head(3))
else:
    print("K线数据获取失败")

# 测试实时行情
print("\n[2] 测试 实时行情")
quote = fetcher.get_realtime_quote('000001')
if quote:
    print("列名:", list(quote.keys()))
    print("数据:", quote)
else:
    print("实时行情获取失败")

print("\n" + "=" * 50)
print("测试完成")
