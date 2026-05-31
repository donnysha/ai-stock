"""
Backtrader回测页面
提供专业的网格交易策略回测功能
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from business_layer.backtrader_engine import BacktraderEngine
from presentation_layer.charts.kline_chart import KLineChart


def get_stock_name_from_code(stock_code: str, akshare_fetcher=None) -> str:
    """
    根据股票代码获取股票名称
    
    Args:
        stock_code: 6位股票代码
        akshare_fetcher: 数据获取器
    
    Returns:
        股票名称，获取失败返回空字符串
    """
    if not stock_code or len(stock_code) != 6:
        return ""
    
    try:
        if akshare_fetcher:
            # 尝试从实时行情获取
            quote = akshare_fetcher.get_realtime_quote(stock_code)
            if quote and '名称' in quote:
                return quote['名称']
        
        # 备用：使用akshare直接获取
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        result = df[df['代码'] == stock_code]
        if not result.empty:
            return str(result.iloc[0]['名称'])
    except Exception as e:
        print(f"获取股票名称失败: {e}")
    
    return ""


def render_backtest_page(akshare_fetcher=None):
    """
    渲染Backtrader回测页面
    
    Args:
        akshare_fetcher: 数据获取器
    """
    st.subheader("📊 策略回测 (Backtrader)")
    
    # 检查是否有从操作列跳转过来的预填充股票
    preset_code = st.session_state.get('backtest_preset_code', None)
    preset_name = st.session_state.get('backtest_preset_name', None)
    
    # 股票选择区域
    st.subheader("选择回测股票")
    
    # 初始化session_state中的股票代码和名称
    if 'bt_stock_code' not in st.session_state:
        st.session_state.bt_stock_code = preset_code if preset_code else ""
    if 'bt_stock_name' not in st.session_state:
        st.session_state.bt_stock_name = preset_name if preset_name else ""
    
    # 如果有跳转过来的预设值，更新session_state
    if preset_code:
        st.session_state.bt_stock_code = preset_code
        if preset_name:
            st.session_state.bt_stock_name = preset_name
        # 清除预设值
        del st.session_state['backtest_preset_code']
        del st.session_state['backtest_preset_name']
    
    # 股票代码输入
    col1, col2 = st.columns([2, 1])
    
    with col1:
        stock_code = st.text_input(
            "股票代码",
            value=st.session_state.bt_stock_code,
            placeholder="例如：000001",
            help="输入6位股票代码",
            key="bt_code_input"
        )
    
    with col2:
        # 查询按钮
        if st.button("🔍 查询名称", key="bt_query_name"):
            if stock_code and len(stock_code) == 6:
                with st.spinner("查询中..."):
                    name = get_stock_name_from_code(stock_code, akshare_fetcher)
                    if name:
                        st.session_state.bt_stock_name = name
                        st.success(f"✓ {name}")
                        st.rerun()
                    else:
                        st.error("未找到该股票")
            else:
                st.error("请输入6位股票代码")
    
    # 自动查询：如果代码变化或名称为空，尝试自动获取
    if stock_code and len(stock_code) == 6:
        if stock_code != st.session_state.bt_stock_code or not st.session_state.bt_stock_name:
            st.session_state.bt_stock_code = stock_code
            # 自动获取名称
            name = get_stock_name_from_code(stock_code, akshare_fetcher)
            if name:
                st.session_state.bt_stock_name = name
                st.rerun()
    
    # 显示股票名称（只读）
    stock_name = st.session_state.get('bt_stock_name', '')
    if stock_name:
        st.text_input("股票名称", value=stock_name, disabled=True, key="bt_name_display")
    else:
        st.text_input("股票名称", value="请输入代码后自动获取", disabled=True, key="bt_name_display_empty")
    
    # 回测参数区域
    st.subheader("回测参数")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        start_date = st.date_input(
            "回测起始日期",
            value=datetime(2024, 1, 1).date(),
            help="选择回测开始日期",
            key="bt_start"
        )
    
    with col2:
        end_date = st.date_input(
            "回测结束日期",
            value=date.today(),
            help="选择回测结束日期",
            key="bt_end"
        )
    
    with col3:
        initial_capital = st.number_input(
            "初始资金（万元）",
            value=100,
            min_value=10,
            step=10,
            help="初始投入资金",
            key="bt_capital"
        )
    
    st.markdown("**网格策略设置**")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        grid_buy_pct = st.number_input(
            "下跌买入幅度 (%)",
            value=-3.0,
            step=0.5,
            help="相对于基准价下跌多少百分比时买入",
            key="bt_grid_buy"
        )
    
    with col2:
        grid_sell_pct = st.number_input(
            "上涨卖出幅度 (%)",
            value=5.0,
            step=0.5,
            help="相对于基准价上涨多少百分比时卖出",
            key="bt_grid_sell"
        )
    
    with col3:
        buy_ratio = st.slider(
            "买入仓位比例",
            min_value=0.05,
            max_value=0.5,
            value=0.1,
            step=0.05,
            help="每次买入时使用可用资金的比例",
            key="bt_buy_ratio"
        )
    
    with col4:
        sell_ratio = st.slider(
            "卖出持仓比例",
            min_value=0.1,
            max_value=1.0,
            value=0.5,
            step=0.1,
            help="每次卖出时卖出持仓的比例",
            key="bt_sell_ratio"
        )
    
    # 回测按钮
    submitted = st.button("🚀 开始回测", type="primary", key="bt_submit")
    
    if submitted:
        if not stock_code:
            st.warning("⚠️ 请输入或选择股票代码")
            return
        
        with st.spinner("正在执行Backtrader回测..."):
            try:
                # 调试信息
                import traceback
                from data_layer.stock_info_sync import get_or_fetch_list_date
                
                # 验证数据获取器
                if akshare_fetcher is None:
                    st.error("数据获取器未初始化")
                    return
                
                # 检查并调整开始日期（不能早于上市日期）
                adjusted_start_date = start_date
                with st.status("正在检查股票信息...") as status:
                    list_date_str = get_or_fetch_list_date(stock_code, akshare_fetcher)
                    if list_date_str:
                        from datetime import datetime
                        try:
                            list_date = datetime.strptime(list_date_str, '%Y-%m-%d').date()
                            if start_date < list_date:
                                old_start = start_date
                                adjusted_start_date = list_date
                                status.update(
                                    label=f"⚠️ 开始日期已从 {old_start} 调整为上市日期 {list_date}",
                                    state="complete"
                                )
                                st.info(f"股票 {stock_code} 的上市日期为 {list_date}，回测开始日期已自动调整")
                            else:
                                status.update(label=f"✓ 上市日期: {list_date}", state="complete")
                        except Exception as e:
                            status.update(label=f"⚠️ 日期解析失败: {e}", state="error")
                    else:
                        status.update(label="⚠️ 无法获取上市日期", state="warning")
                
                # 先测试数据获取
                with st.status("正在获取数据...") as status:
                    test_data = akshare_fetcher.get_kline_dataframe(
                        stock_code=stock_code,
                        start_date=adjusted_start_date.strftime("%Y%m%d"),
                        end_date=end_date.strftime("%Y%m%d")
                    )
                    if test_data is None or test_data.empty:
                        status.update(label="数据获取失败", state="error")
                        st.error(f"无法获取 {stock_code} 从 {adjusted_start_date} 到 {end_date} 的数据")
                        st.info("请检查：\n1. 股票代码是否正确\n2. 日期范围是否有效（是否为交易日）\n3. 网络连接是否正常")
                        if list_date_str:
                            st.info(f"该股票上市日期为: {list_date_str}")
                        return
                    else:
                        status.update(label=f"✓ 获取到 {len(test_data)} 条数据", state="complete")
                
                # 创建回测引擎
                engine = BacktraderEngine(data_fetcher=akshare_fetcher)
                
                # 执行回测
                result = engine.run_backtest(
                    stock_code=stock_code,
                    start_date=adjusted_start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    initial_capital=initial_capital * 10000,  # 转换为元
                    grid_buy_pct=grid_buy_pct,
                    grid_sell_pct=grid_sell_pct,
                    buy_ratio=buy_ratio,
                    sell_ratio=sell_ratio
                )
                
                if result['success']:
                    # 获取K线数据用于展示
                    kline_data = None
                    if akshare_fetcher is not None:
                        try:
                            kline_data = akshare_fetcher.get_kline_dataframe(
                                stock_code=stock_code,
                                start_date=adjusted_start_date.strftime("%Y%m%d"),
                                end_date=end_date.strftime("%Y%m%d")
                            )
                        except Exception as e:
                            st.warning(f"获取K线数据失败: {e}")
                    
                    display_bt_result(result, kline_data, stock_code, stock_name)
                else:
                    st.error(f"回测失败: {result.get('message', '未知错误')}")
                    
            except Exception as e:
                st.error(f"执行出错: {str(e)}")
                st.code(traceback.format_exc())


def display_bt_result(result: dict, kline_data: pd.DataFrame, stock_code: str, stock_name: str):
    """
    显示Backtrader回测结果
    
    Args:
        result: 回测结果字典
        kline_data: K线数据DataFrame
        stock_code: 股票代码
        stock_name: 股票名称
    """
    st.success("✅ Backtrader回测完成！")
    
    # 基本信息
    st.subheader("📋 回测概况")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("股票代码", stock_code)
    with col2:
        st.metric("股票名称", stock_name or "-")
    with col3:
        initial = result.get('initial_capital', 0)
        st.metric("初始资金", f"{initial/10000:.0f}万")
    with col4:
        final = result.get('final_value', 0)
        st.metric("最终资金", f"{final/10000:.2f}万")
    
    # 分析器指标
    st.markdown("---")
    st.subheader("📊 绩效指标")
    
    analyzer = result.get('analyzer', {})
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_return = ((final - initial) / initial * 100) if initial > 0 else 0
        st.metric("总收益率", f"{total_return:.2f}%")
    
    with col2:
        sharpe = analyzer.get('sharpe_ratio', 0)
        st.metric("夏普比率", f"{sharpe:.2f}")
    
    with col3:
        max_dd = analyzer.get('max_drawdown_pct', 0)
        st.metric("最大回撤", f"{max_dd:.2f}%")
    
    with col4:
        win_rate = analyzer.get('win_rate', 0)
        st.metric("胜率", f"{win_rate:.1f}%")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_trades = analyzer.get('total_trades', 0)
        st.metric("总交易次数", f"{total_trades}")
    
    with col2:
        profit_factor = analyzer.get('profit_factor', 0)
        st.metric("盈亏比", f"{profit_factor:.2f}")
    
    with col3:
        sqn = analyzer.get('sqn', 0)
        st.metric("SQN系统质量", f"{sqn:.2f}")
    
    with col4:
        annual_return = analyzer.get('annual_return_pct', 0)
        st.metric("年化收益率", f"{annual_return:.2f}%")
    
    # K线图
    if kline_data is not None and not kline_data.empty:
        st.markdown("---")
        st.subheader("📈 K线走势与交易点")
        
        chart = KLineChart()
        chart.create_kline_chart(
            df=kline_data,
            stock_name=f"{stock_name} ({stock_code})" if stock_name else stock_code,
            show_ma=True,
            trades=result.get('trades', []),
            height="600px"
        )
        chart.render(height="600px", key=f"backtest_kline_{stock_code}")
    
    # 交易记录
    trades = result.get('trades', [])
    if trades:
        st.markdown("---")
        st.subheader("📋 交易记录")
        
        trades_df = pd.DataFrame(trades)
        if not trades_df.empty:
            st.dataframe(trades_df, hide_index=True, use_container_width=True)
            
            # 下载交易记录
            csv = trades_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 下载交易记录 (CSV)",
                csv,
                f"{stock_code}_trades.csv",
                "text/csv",
                key="bt_download_trades"
            )
