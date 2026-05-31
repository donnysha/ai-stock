"""
akshare数据格式检查脚本
用于调试和查看akshare返回的实际数据格式
"""

import pandas as pd
import json
import os
from datetime import datetime

# 输出目录
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def check_stock_spot():
    """检查股票实时数据格式"""
    import akshare as ak
    
    print("=" * 60)
    print("1. 股票实时数据 (stock_zh_a_spot)")
    print("=" * 60)
    
    try:
        df = ak.stock_zh_a_spot()
        
        print(f"\n列名: {df.columns.tolist()}")
        print(f"\n数据类型:\n{df.dtypes}")
        print(f"\n数据行数: {len(df)}")
        print(f"\n前3行完整数据:")
        print(df.head(3).to_string())
        
        # 保存到文件
        output_file = os.path.join(OUTPUT_DIR, "debug_stock_spot.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'columns': df.columns.tolist(),
                'sample_data': df.head(3).to_dict('records')
            }, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n已保存到: {output_file}")
        
        return df
    except Exception as e:
        print(f"获取数据失败: {e}")
        return None


def check_stock_kline():
    """检查K线数据格式"""
    import akshare as ak
    
    print("\n" + "=" * 60)
    print("2. K线数据 (stock_zh_a_hist)")
    print("=" * 60)
    
    try:
        df = ak.stock_zh_a_hist(
            symbol='000001',
            period='daily',
            start_date='20240101',
            end_date='20240110'
        )
        
        print(f"\n列名: {df.columns.tolist()}")
        print(f"\n数据类型:\n{df.dtypes}")
        print(f"\n数据行数: {len(df)}")
        print(f"\n前3行完整数据:")
        print(df.head(3).to_string())
        
        # 保存到文件
        output_file = os.path.join(OUTPUT_DIR, "debug_stock_kline.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'columns': df.columns.tolist(),
                'sample_data': df.head(3).to_dict('records')
            }, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n已保存到: {output_file}")
        
        return df
    except Exception as e:
        print(f"获取数据失败: {e}")
        return None


def check_stock_indicator():
    """检查股票指标数据格式"""
    import akshare as ak
    
    print("\n" + "=" * 60)
    print("3. 股票指标数据 (stock_individual_info_em)")
    print("=" * 60)
    
    try:
        df = ak.stock_individual_info_em(symbol='000001')
        
        print(f"\n列名: {df.columns.tolist()}")
        print(f"\n数据类型:\n{df.dtypes}")
        print(f"\n数据:\n{df}")
        
        # 保存到文件
        output_file = os.path.join(OUTPUT_DIR, "debug_stock_indicator.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'columns': df.columns.tolist(),
                'data': df.to_dict('records')
            }, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n已保存到: {output_file}")
        
        return df
    except Exception as e:
        print(f"获取数据失败: {e}")
        return None


def generate_column_mapping():
    """生成列名映射文档"""
    print("\n" + "=" * 60)
    print("列名映射参考")
    print("=" * 60)
    
    # 实时数据列名映射（akshare -> 系统内部）
    spot_mapping = {
        '代码': 'code',
        '名称': 'name', 
        '最新价': 'price',
        '涨跌额': 'change',
        '涨跌幅': 'change_pct',
        '成交量': 'volume',
        '成交额': 'amount',
        '今开': 'open',
        '最高': 'high',
        '最低': 'low',
        '昨收': 'prev_close',
        '市盈率-动态': 'pe',
        '市净率': 'pb',
        '总市值': 'market_cap',
        '流通市值': 'float_market_cap',
        '换手率': 'turnover'
    }
    
    # K线数据列名映射
    kline_mapping = {
        '日期': 'date',
        '股票代码': 'code',
        '开盘': 'open',
        '收盘': 'close',
        '最高': 'high',
        '最低': 'low',
        '成交量': 'volume',
        '成交额': 'amount',
        '涨跌幅': 'change_pct',
        '涨跌额': 'change',
        '换手率': 'turnover',
        '振幅': 'amplitude'
    }
    
    print("\n【实时数据列名映射】")
    for ak_name, internal_name in spot_mapping.items():
        print(f"  {ak_name:>12} -> {internal_name}")
    
    print("\n【K线数据列名映射】")
    for ak_name, internal_name in kline_mapping.items():
        print(f"  {ak_name:>12} -> {internal_name}")
    
    # 保存映射文件
    mapping_file = os.path.join(OUTPUT_DIR, "column_mapping.json")
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump({
            'spot_mapping': spot_mapping,
            'kline_mapping': kline_mapping,
            'generated_at': datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    print(f"\n映射文件已保存到: {mapping_file}")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("akshare 数据格式检查工具")
    print("=" * 60)
    
    # 1. 检查实时数据
    spot_df = check_stock_spot()
    
    # 2. 检查K线数据
    kline_df = check_stock_kline()
    
    # 3. 检查指标数据
    indicator_df = check_stock_indicator()
    
    # 4. 生成映射文档
    generate_column_mapping()
    
    print("\n" + "=" * 60)
    print("检查完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
