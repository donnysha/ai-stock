"""
涨跌停阈值数据库验证脚本

【模块功能】
连接MySQL数据库，验证阈值(9.5%, 19.5%, 29.5%)与连板天字段的匹配度。

【分析方法】
1. 阈值覆盖不足（假阴性）：涨幅 >= 阈值，但连板天 = 0
   - 查询判断为涨停，但实际不是涨停
   - 可能是数据延迟或边界情况
   
2. 阈值过高（假阳性）：涨幅 < 阈值，但连板天 >= 1
   - 实际涨停，但查询未识别
   - 需要调整阈值

【容差说明】
- 主板 10%：round(10.00*1.10, 2) = 11.00，实际涨幅 10.00%
- 由于价格四舍五入到分(0.01)，极端情况下实际涨幅可能偏离
- 理论计算：主板 10% 对应实际涨幅约 9.89% ~ 10.11%

【使用前提】
- MySQL服务已启动
- stock数据库存在
- stock_daily_full表有数据

【输出指标】
- 总记录数
- 阈值判断为涨停的数量
- 连板天与阈值的匹配率
- 假阴性/假阳性案例
"""

import sys
from pathlib import Path
import pymysql
from collections import defaultdict
from datetime import datetime

# 添加项目根目录，复用统一配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_stock_nlp.config.settings import DB_CONFIG

# 涨跌停阈值配置
LIMIT_THRESHOLDS = {
    'main': 9.5,      # 主板 (60xxx, 000xxx, 001xxx)
    'gem_star': 19.5, # 创业板/科创板 (300xxx, 688xxx)
    'bse': 29.5,      # 北交所 (8xxxxx)
    'st': 4.5,        # ST股 (所有板块)
}

def get_board_type(stock_code):
    """根据股票代码判断板块类型"""
    code_str = str(stock_code).zfill(6)
    
    # 检测是否为ST股（需要从名称判断，这里先不处理）
    if code_str.startswith('60'):
        return 'main'
    elif code_str.startswith('688'):
        return 'gem_star'
    elif code_str.startswith('000') or code_str.startswith('001'):
        return 'main'
    elif code_str.startswith('300'):
        return 'gem_star'
    elif code_str.startswith('8'):
        return 'bse'
    else:
        return 'unknown'


def validate_limit_threshold(cursor, sample_size=10000):
    """
    验证涨跌停阈值与连板天的匹配度
    
    Args:
        cursor: 数据库游标
        sample_size: 采样数量
    
    Returns:
        验证统计结果
    """
    
    # ========== 1. 查询近期涨停/接近涨停的数据 ==========
    print("=" * 70)
    print("涨跌停阈值验证分析")
    print("=" * 70)
    
    # 查询条件：涨幅 >= 9% (包括接近涨停的股票)
    query = """
    SELECT 
        代码,
        名称,
        `涨幅%` AS change_pct,
        `连板天` AS lianban_days,
        `trade_date`,
        `上市日期` AS listing_date
    FROM stock_daily_full
    WHERE `涨幅%` >= 9.0
       OR `连板天` >= 1
    ORDER BY trade_date DESC
    LIMIT %s
    """
    
    cursor.execute(query, (sample_size,))
    records = cursor.fetchall()
    
    print(f"\n采样数量: {len(records)} 条记录")
    
    # ========== 2. 分类统计 ==========
    
    # 按阈值判断分类
    stats = {
        'total': 0,
        # 阈值判断为涨停
        'threshold_up': {'count': 0, 'lianban_ge_1': 0, 'lianban_eq_0': 0},
        # 阈值判断为跌停
        'threshold_down': {'count': 0, 'lianban_ge_1': 0, 'lianban_eq_0': 0},
        # 连板天 >= 1（阈值可能不足）
        'lianban_ge_1_but_threshold_miss': {'count': 0},
        # 连板天 = 0 但阈值判断为涨停
        'threshold_up_but_lianban_0': {'count': 0},
    }
    
    # 按涨幅区间统计
    change_range_stats = defaultdict(lambda: {
        'count': 0, 
        'lianban_ge_1': 0, 
        'lianban_eq_0': 0,
        'details': []
    })
    
    for row in records:
        stats['total'] += 1
        code = str(row['代码']).zfill(6) if row['代码'] else '000000'
        change_pct = row['change_pct'] or 0
        lianban_days = row['lianban_days'] or 0
        name = row['名称'] or ''
        
        # 判断是否为ST股
        is_st = 'ST' in name.upper() or '退' in name
        
        # 确定阈值
        if is_st:
            threshold_up = LIMIT_THRESHOLDS['st']
            threshold_down = -LIMIT_THRESHOLDS['st']
        else:
            board_type = get_board_type(code)
            threshold_up = LIMIT_THRESHOLDS.get(board_type, LIMIT_THRESHOLDS['main'])
            threshold_down = -threshold_up
        
        # 统计：阈值判断为涨停
        if change_pct >= threshold_up:
            stats['threshold_up']['count'] += 1
            if lianban_days >= 1:
                stats['threshold_up']['lianban_ge_1'] += 1
            else:
                stats['threshold_up']['lianban_eq_0'] += 1
                stats['threshold_up_but_lianban_0']['count'] += 1
        
        # 统计：阈值判断为跌停
        if change_pct <= threshold_down:
            stats['threshold_down']['count'] += 1
            if lianban_days >= 1:
                stats['threshold_down']['lianban_ge_1'] += 1
            else:
                stats['threshold_down']['lianban_eq_0'] += 1
        
        # 统计：连板天 >= 1 但涨幅未达到阈值
        if lianban_days >= 1 and abs(change_pct) < threshold_up:
            stats['lianban_ge_1_but_threshold_miss']['count'] += 1
        
        # 按涨幅区间统计
        if change_pct >= 9.0 and change_pct < 9.5:
            range_key = '9.0~9.5%'
        elif change_pct >= 9.5 and change_pct < 10.0:
            range_key = '9.5~10.0%'
        elif change_pct >= 10.0 and change_pct < 10.5:
            range_key = '10.0~10.5%'
        elif change_pct >= 10.5:
            range_key = '>=10.5%'
        elif change_pct >= -10.5 and change_pct <= -10.0:
            range_key = '-10.5%~-10.0%'
        elif change_pct >= -10.0 and change_pct < -9.5:
            range_key = '-10.0%~-9.5%'
        elif change_pct >= -9.5 and change_pct < -9.0:
            range_key = '-9.5%~-9.0%'
        else:
            range_key = '其他'
        
        change_range_stats[range_key]['count'] += 1
        if lianban_days >= 1:
            change_range_stats[range_key]['lianban_ge_1'] += 1
        else:
            change_range_stats[range_key]['lianban_eq_0'] += 1
        
        # 记录边界案例
        if (change_pct >= threshold_up and lianban_days == 0) or \
           (lianban_days >= 1 and change_pct < threshold_up):
            change_range_stats[range_key]['details'].append({
                'code': code,
                'name': name,
                'change_pct': change_pct,
                'lianban_days': lianban_days,
                'threshold': threshold_up
            })
    
    return stats, change_range_stats


def print_analysis(stats, change_range_stats):
    """打印分析结果"""
    
    print("\n" + "=" * 70)
    print("【1. 总体统计】")
    print("=" * 70)
    print(f"总记录数: {stats['total']}")
    
    print("\n【2. 涨停阈值(9.5%)验证】")
    print("-" * 50)
    threshold_up = stats['threshold_up']
    total_up = threshold_up['count']
    print(f"阈值判断为涨停: {total_up} 条")
    print(f"  - 连板天 >= 1: {threshold_up['lianban_ge_1']} 条 ({threshold_up['lianban_ge_1']/total_up*100:.1f}%)")
    print(f"  - 连板天 = 0: {threshold_up['lianban_eq_0']} 条 ({threshold_up['lianban_eq_0']/total_up*100:.1f}%)")
    
    # 计算错误率
    if total_up > 0:
        false_negative_rate = threshold_up['lianban_eq_0'] / total_up * 100
        print(f"\n【错误分析】阈值覆盖不足率: {false_negative_rate:.2f}%")
        print(f"  (涨幅 >= 9.5% 但连板天 = 0 的比例)")
    
    print("\n【3. 按涨幅区间统计】")
    print("-" * 50)
    print(f"{'涨幅区间':<15} {'总数':<8} {'连板>=1':<10} {'连板=0':<10} {'覆盖率':<10}")
    print("-" * 50)
    
    for range_key in sorted(change_range_stats.keys()):
        data = change_range_stats[range_key]
        coverage = data['lianban_ge_1'] / data['count'] * 100 if data['count'] > 0 else 0
        print(f"{range_key:<15} {data['count']:<8} {data['lianban_ge_1']:<10} {data['lianban_eq_0']:<10} {coverage:.1f}%")
    
    print("\n【4. 假阴性案例（涨幅>=阈值但连板天=0）】")
    print("-" * 70)
    for range_key in ['9.5~10.0%', '10.0~10.5%', '>=10.5%']:
        data = change_range_stats.get(range_key, {})
        if data.get('details'):
            print(f"\n涨幅区间: {range_key}")
            for detail in data['details'][:5]:  # 最多显示5条
                print(f"  {detail['code']} {detail['name']:<10} 涨幅:{detail['change_pct']:>6.2f}% 连板天:{detail['lianban_days']}")
    
    print("\n" + "=" * 70)
    print("【结论】")
    print("=" * 70)


def main():
    """主函数"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # 执行验证
        stats, change_range_stats = validate_limit_threshold(cursor, sample_size=20000)
        
        # 打印分析
        print_analysis(stats, change_range_stats)
        
        cursor.close()
        connection.close()
        
    except pymysql.Error as e:
        print(f"数据库连接错误: {e}")
        print("\n请确保：")
        print("1. MySQL 服务已启动")
        print("2. stock 数据库存在")
        print("3. stock_daily_full 表有数据")
        print("4. 连接配置正确")


if __name__ == '__main__':
    main()
