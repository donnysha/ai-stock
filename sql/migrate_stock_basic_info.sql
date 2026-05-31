-- =====================================================
-- 股票基础信息表扩充字段迁移脚本
-- 目标表: stock.stock_basic_info
-- =====================================================

-- 新增字段说明：
-- market: 市场(沪深北)
-- stock_type: 股票类型(主板/创业板/科创板/北交所)
-- total_market_cap: 总市值(元)
-- circulating_market_cap: 流通市值(元)
-- pe_ratio: 市盈率
-- pb_ratio: 市净率

-- 1. 添加 market 字段
ALTER TABLE stock_basic_info 
ADD COLUMN market VARCHAR(10) COMMENT '市场(沪深北)' AFTER exchange;

-- 2. 添加 stock_type 字段  
ALTER TABLE stock_basic_info 
ADD COLUMN stock_type VARCHAR(20) COMMENT '股票类型(主板/创业板/科创板/北交所)' AFTER market;

-- 3. 添加 total_market_cap 字段
ALTER TABLE stock_basic_info 
ADD COLUMN total_market_cap DECIMAL(20,2) COMMENT '总市值(元)' AFTER listing_status;

-- 4. 添加 circulating_market_cap 字段
ALTER TABLE stock_basic_info 
ADD COLUMN circulating_market_cap DECIMAL(20,2) COMMENT '流通市值(元)' AFTER total_market_cap;

-- 5. 添加 pe_ratio 字段
ALTER TABLE stock_basic_info 
ADD COLUMN pe_ratio DECIMAL(10,2) COMMENT '市盈率' AFTER circulating_market_cap;

-- 6. 添加 pb_ratio 字段
ALTER TABLE stock_basic_info 
ADD COLUMN pb_ratio DECIMAL(10,2) COMMENT '市净率' AFTER pe_ratio;

-- 7. 添加索引（可选，提升查询性能）
ALTER TABLE stock_basic_info 
ADD INDEX idx_market_cap (total_market_cap);

ALTER TABLE stock_basic_info 
ADD INDEX idx_exchange (exchange);

-- =====================================================
-- 验证表结构
-- =====================================================
DESCRIBE stock_basic_info;

-- =====================================================
-- 验证记录数
-- =====================================================
SELECT COUNT(*) as total_count FROM stock_basic_info;
