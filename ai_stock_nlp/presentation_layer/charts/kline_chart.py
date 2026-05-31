"""
K线图表组件
使用 ECharts (streamlit-echarts) 绘制K线图 + 成交量
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any
from streamlit_echarts import st_echarts


class KLineChart:
    """
    K线图表生成器（基于 ECharts）

    功能：
    1. 绘制K线蜡烛图
    2. 叠加 MA5 / MA10 / MA20 均线
    3. 底部成交量柱状图（红涨绿跌）
    4. DataZoom 滑动条
    5. 买卖点标记
    """

    def __init__(self):
        self.option = None

    # ---------- 公共入口 ----------

    def create_kline_chart(
        self,
        df: pd.DataFrame,
        stock_name: str = "",
        show_ma: bool = True,
        trades: List[Dict] = None,
        height: str = "600px",
    ) -> Dict:
        """
        创建K线图表配置

        Args:
            df: K线DataFrame（须含 date, open, close, high, low, volume）
            stock_name: 股票名称
            show_ma: 是否显示均线
            trades: 交易记录 [{date, price, action}, ...]
            height: 图高度

        Returns:
            ECharts option dict，可直接传给 st_echarts
        """
        if df.empty:
            return {}

        df = df.copy()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

        dates = df["date"].dt.strftime("%Y-%m-%d").tolist()
        opens = df["open"].astype(float).tolist()
        closes = df["close"].astype(float).tolist()
        highs = df["high"].astype(float).tolist()
        lows = df["low"].astype(float).tolist()
        volumes = df["volume"].astype(float).tolist()

        # ECharts candlestick 格式：[open, close, low, high]
        k_data = [
            [o, c, lo, hi]
            for o, c, lo, hi in zip(opens, closes, lows, highs)
        ]

        # 涨跌颜色
        up_color = "#ef232a"      # 红涨
        down_color = "#14b143"    # 绿跌

        # ---------- 构建 series ----------
        series = []

        # K线
        series.append({
            "name": "K线",
            "type": "candlestick",
            "data": k_data,
            "xAxisIndex": 0,
            "yAxisIndex": 0,
            "itemStyle": {
                "color": up_color,
                "color0": down_color,
                "borderColor": up_color,
                "borderColor0": down_color,
            },
        })

        # 均线
        if show_ma:
            close_series = pd.Series(closes)
            for ma_n, ma_color in [(5, "#f5a623"), (10, "#4a90d9"), (20, "#9013fe")]:
                if len(close_series) >= ma_n:
                    ma_vals = close_series.rolling(ma_n).mean().tolist()
                    series.append({
                        "name": f"MA{ma_n}",
                        "type": "line",
                        "data": ma_vals,
                        "xAxisIndex": 0,
                        "yAxisIndex": 0,
                        "symbol": "none",
                        "lineStyle": {"width": 1, "color": ma_color, "type": "solid"},
                        "smooth": False,
                    })

        # 成交量柱状图
        vol_colors = []
        for i in range(len(k_data)):
            if closes[i] >= opens[i]:
                vol_colors.append(up_color)
            else:
                vol_colors.append(down_color)
        series.append({
            "name": "成交量",
            "type": "bar",
            "data": volumes,
            "xAxisIndex": 0,
            "yAxisIndex": 1,
            "itemStyle": {"color": None},
            "dataGroupId": "vol",
        })

        # 买卖点
        if trades:
            buy_data = []
            sell_data = []
            for t in trades:
                t_date = str(t.get("date", ""))
                t_price = float(t.get("price", 0))
                if t.get("action") == "buy":
                    buy_data.append({
                        "coord": [t_date, t_price],
                        "value": "B",
                    })
                else:
                    sell_data.append({
                        "coord": [t_date, t_price],
                        "value": "S",
                    })
            if buy_data:
                series.append({
                    "name": "买入",
                    "type": "scatter",
                    "data": buy_data,
                    "xAxisIndex": 0,
                    "yAxisIndex": 0,
                    "symbol": "triangle",
                    "symbolSize": 14,
                    "symbolRotate": 0,
                    "itemStyle": {"color": "#ff0000"},
                    "label": {"show": True, "formatter": "B", "position": "top", "color": "#ff0000", "fontWeight": "bold"},
                })
            if sell_data:
                series.append({
                    "name": "卖出",
                    "type": "scatter",
                    "data": sell_data,
                    "xAxisIndex": 0,
                    "yAxisIndex": 0,
                    "symbol": "triangle",
                    "symbolSize": 14,
                    "symbolRotate": 180,
                    "itemStyle": {"color": "#00aa00"},
                    "label": {"show": True, "formatter": "S", "position": "bottom", "color": "#00aa00", "fontWeight": "bold"},
                })

        # ---------- Tooltip ----------
        tooltip = {
            "trigger": "axis",
            "axisPointer": {"type": "cross", "crossStyle": {"color": "#999"}},
            "formatter": """function(params) {{
                if (!params || params.length === 0) return '';
                var d = params[0].axisValue || '';
                var s = '<div style=\\'font-size:13px;font-weight:bold;margin-bottom:6px\\'>' + d + '</div>';
                for (var i = 0; i < params.length; i++) {{
                    var p = params[i];
                    if (p.seriesName === '成交量') {{
                        s += '<div style=\\'display:flex;justify-content:space-between;gap:20px\\'>'
                          +  '<span>' + p.marker + ' ' + p.seriesName + '</span>'
                          +  '<span><b>' + (p.value / 10000).toFixed(0) + '万手</b></span></div>';
                    }} else if (p.seriesName && p.seriesName.indexOf('MA') === 0) {{
                        s += '<div style=\\'display:flex;justify-content:space-between;gap:20px\\'>'
                          +  '<span>' + p.marker + ' ' + p.seriesName + '</span>'
                          +  '<span><b>' + (p.value != null ? p.value.toFixed(2) : '-') + '</b></span></div>';
                    }} else if (p.seriesName === 'K线') {{
                        var v = p.data;
                        s += '<div style=\\'display:flex;justify-content:space-between;gap:15px\\'>'
                          +  '<span>开: <b>' + (v[1] != null ? v[1].toFixed(2) : '-') + '</b></span>'
                          +  '<span>收: <b>' + (v[2] != null ? v[2].toFixed(2) : '-') + '</b></span>'
                          +  '<span>低: <b>' + (v[3] != null ? v[3].toFixed(2) : '-') + '</b></span>'
                          +  '<span>高: <b>' + (v[4] != null ? v[4].toFixed(2) : '-') + '</b></span></div>';
                    }}
                }}
                return s;
            }}""".replace("    ", ""),
        }

        # ---------- 组装 option ----------
        self.option = {
            "tooltip": tooltip,
            "axisPointer": {"link": [{"xAxisIndex": "all"}]},
            "grid": [
                {"left": "8%", "right": "8%", "top": 60, "height": "55%"},
                {"left": "8%", "right": "8%", "top": "78%", "height": "14%"},
            ],
            "xAxis": [
                {
                    "type": "category",
                    "data": dates,
                    "gridIndex": 0,
                    "axisLabel": {"show": False},
                    "axisLine": {"lineStyle": {"color": "#666"}},
                    "axisTick": {"show": False},
                    "splitLine": {"show": False},
                },
                {
                    "type": "category",
                    "data": dates,
                    "gridIndex": 1,
                    "axisLabel": {"rotate": 0, "fontSize": 10, "color": "#999"},
                    "axisLine": {"lineStyle": {"color": "#666"}},
                    "axisTick": {"show": False},
                    "splitLine": {"show": False},
                },
            ],
            "yAxis": [
                {
                    "type": "value",
                    "scale": True,
                    "gridIndex": 0,
                    "splitLine": {"lineStyle": {"color": "#333", "type": "dashed", "opacity": 0.3}},
                    "axisLabel": {"fontSize": 11, "color": "#aaa"},
                },
                {
                    "type": "value",
                    "gridIndex": 1,
                    "splitLine": {"show": False},
                    "axisLabel": {
                        "fontSize": 10,
                        "color": "#aaa",
                        "formatter": "{value}",
                    },
                },
            ],
            "dataZoom": [
                {
                    "type": "inside",
                    "xAxisIndex": [0, 1],
                    "start": max(0, 100 - max(30, 500 / max(len(dates), 1))),
                    "end": 100,
                },
                {
                    "show": True,
                    "xAxisIndex": [0, 1],
                    "type": "slider",
                    "bottom": 0,
                    "start": max(0, 100 - max(30, 500 / max(len(dates), 1))),
                    "end": 100,
                    "height": 25,
                },
            ],
            "series": series,
            "title": {
                "text": f"{stock_name} K线走势" if stock_name else "K线走势",
                "left": "center",
                "top": 5,
                "textStyle": {"fontSize": 16, "color": "#fff"},
            },
        }

        return self.option

    # ---------- Streamlit 渲染 ----------

    def render(self, height: str = "600px", key: str = None):
        """在 Streamlit 中直接渲染K线图"""
        if self.option is None:
            return
        st_echarts(options=self.option, height=height, key=key)

    # ---------- 兼容旧接口 ----------

    def to_html(self) -> str:
        """返回占位（ECharts 不支持导出 HTML）"""
        return '<div style="text-align:center;padding:100px;color:#888">'
        'ECharts K线图（需在 Streamlit 中渲染）</div>'

    def save_html(self, filepath: str):
        """保存占位 HTML"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_html())
