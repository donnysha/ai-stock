# 数据源结构文档

## 一、实时行情数据 (akshare stock_zh_a_spot_em)

### 数据接口
```python
import akshare as ak
df = ak.stock_zh_a_spot_em()
```

### 完整列名列表
根据 `column_mapping.json` 和 `debug_akshare_format.py` 的定义：

| 序号 | 中文列名 | 内部映射 | 数据类型 | 说明 |
|------|----------|----------|----------|------|
| 1 | 代码 | code | string | 6位股票代码 |
| 2 | 名称 | name | string | 股票名称 |
| 3 | 最新价 | price | float | 当前价格 |
| 4 | 涨跌额 | change | float | 涨跌价格 |
| 5 | 涨跌幅 | change_pct | float | 涨跌幅(%) |
| 6 | 成交量 | volume | float | 成交量(手) |
| 7 | 成交额 | amount | float | 成交额(元) |
| 8 | 今开 | open | float | 今日开盘价 |
| 9 | 最高 | high | float | 最高价 |
| 10 | 最低 | low | float | 最低价 |
| 11 | 昨收 | prev_close | float | 昨日收盘价 |
| 12 | 市盈率-动态 | pe | float | 动态市盈率 |
| 13 | 市净率 | pb | float | 市净率 |
| 14 | **总市值** | market_cap | float | **单位：元** |
| 15 | **流通市值** | float_market_cap | float | **单位：元** |
| 16 | 换手率 | turnover | float | 换手率(%) |
| 17 | **细分行业** | industry | string | **行业板块** |
| 18 | 地区 | region | string | 上市公司地区 |
| 19 | 量比 | volume_ratio | float | 量比 |
| 20 | 振幅 | amplitude | float | 振幅(%) |

### 重要说明

#### 市值字段单位
- **总市值、流通市值单位是：元**
- 500亿 = 500,000,000,000 元 (5e11)
- 1亿 = 100,000,000 元 (1e8)

#### 市值范围参考（单位：元）
```
微盘: < 10亿      = < 1,000,000,000
小盘: < 50亿      = < 50,000,000,000
中盘: 50-500亿    = 50e8 - 500e8
大盘: 500-2000亿 = 500e8 - 2000e8
超大盘: > 2000亿  = > 2000e8
```

---

## 二、K线历史数据 (akshare stock_zh_a_hist)

### 数据接口
```python
df = ak.stock_zh_a_hist(
    symbol='000001',      # 股票代码
    period='daily',        # 日线
    start_date='20240101',
    end_date='20241231',
    adjust='qfq'          # 前复权
)
```

### 列名列表
| 序号 | 中文列名 | 内部映射 | 数据类型 |
|------|----------|----------|----------|
| 1 | 日期 | date | datetime |
| 2 | 股票代码 | code | string |
| 3 | 开盘 | open | float |
| 4 | 收盘 | close | float |
| 5 | 最高 | high | float |
| 6 | 最低 | low | float |
| 7 | 成交量 | volume | float |
| 8 | 成交额 | amount | float |
| 9 | 涨跌幅 | change_pct | float |
| 10 | 涨跌额 | change | float |
| 11 | 换手率 | turnover | float |
| 12 | 振幅 | amplitude | float |

---

## 三、字段映射关系

### 查询条件字段 → akshare列名

```python
FIELD_MAPPING = {
    # 价格类
    '现价': '最新价',
    '价格': '最新价',
    '今开': '今开',
    '最高': '最高',
    '最低': '最低',
    '昨收': '昨收',

    # 涨跌幅类
    '涨幅%': '涨跌幅',
    '涨跌幅': '涨跌幅',
    '涨跌额': '涨跌额',

    # 成交类
    '成交额': '成交额',
    '总金额': '成交额',
    '成交量': '成交量',

    # 市值类 (单位：元)
    '总市值': '总市值',
    '流通市值': '流通市值',
    '市值': '总市值',

    # 估值类
    '市盈率': '市盈率-动态',
    '市盈(动)': '市盈率-动态',
    '市净率': '市净率',

    # 行业类
    '细分行业': '细分行业',
    '行业': '细分行业',
    '板块': '细分行业',
    '地区': '地区',

    # 其他
    '换手率': '换手率',
    '换手%': '换手率',
}
```

---

## 四、测试脚本

### 检查实时数据
```python
import akshare as ak

df = ak.stock_zh_a_spot_em()
print("总列数:", len(df.columns))
print("列名:", df.columns.tolist())

# 检查市值列
if '总市值' in df.columns:
    print("总市值示例:", df['总市值'].head())
```

### 检查K线数据
```python
import akshare as ak

df = ak.stock_zh_a_hist(
    symbol='000001',
    period='daily',
    start_date='20240101',
    end_date='20240110'
)
print("K线列名:", df.columns.tolist())
```

---

## 五、已知问题

1. **市值过滤失效**: 需要在 `field_mapping` 中添加市值字段映射
2. **intent显示**: 需要显示用户友好的查询条件描述，而非枚举值
3. **K线获取失败**: 检查网络连接和akshare版本
