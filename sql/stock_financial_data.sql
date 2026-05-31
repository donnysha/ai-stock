/*
 Navicat Premium Data Transfer

 Source Server         : localhost
 Source Server Type    : MySQL
 Source Server Version : 80046 (8.0.46)
 Source Host           : localhost:3306
 Source Schema         : stock

 Target Server Type    : MySQL
 Target Server Version : 80046 (8.0.46)
 File Encoding         : 65001

 Date: 30/05/2026 16:49:00
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for stock_financial_data
-- ----------------------------
DROP TABLE IF EXISTS `stock_financial_data`;
CREATE TABLE `stock_financial_data`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `stock_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '股票代码',
  `stock_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '股票名称',
  `report_date` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '报告期',
  `report_type` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '报告类型(年报/季报)',
  `fiscal_year` int NULL DEFAULT NULL COMMENT '财年',
  `fiscal_quarter` int NULL DEFAULT NULL COMMENT '季度',
  `revenue` decimal(20, 4) NULL DEFAULT NULL COMMENT '营业总收入(万元)',
  `operating_profit` decimal(20, 4) NULL DEFAULT NULL COMMENT '营业利润(万元)',
  `net_profit` decimal(20, 4) NULL DEFAULT NULL COMMENT '净利润(万元)',
  `total_cost` decimal(20, 4) NULL DEFAULT NULL COMMENT '营业总成本(万元)',
  `total_assets` decimal(20, 4) NULL DEFAULT NULL COMMENT '总资产(万元)',
  `total_liabilities` decimal(20, 4) NULL DEFAULT NULL COMMENT '总负债(万元)',
  `equity` decimal(20, 4) NULL DEFAULT NULL COMMENT '所有者权益(万元)',
  `operating_cash_flow` decimal(20, 4) NULL DEFAULT NULL COMMENT '经营性现金流(万元)',
  `investing_cash_flow` decimal(20, 4) NULL DEFAULT NULL COMMENT '投资性现金流(万元)',
  `financing_cash_flow` decimal(20, 4) NULL DEFAULT NULL COMMENT '筹资性现金流(万元)',
  `roe` decimal(10, 4) NULL DEFAULT NULL COMMENT '净资产收益率ROE(%)',
  `gross_margin` decimal(10, 4) NULL DEFAULT NULL COMMENT '毛利率(%)',
  `net_margin` decimal(10, 4) NULL DEFAULT NULL COMMENT '净利率(%)',
  `revenue_growth` decimal(10, 4) NULL DEFAULT NULL COMMENT '营收增速(%)',
  `profit_growth` decimal(10, 4) NULL DEFAULT NULL COMMENT '净利润增速(%)',
  `debt_ratio` decimal(10, 4) NULL DEFAULT NULL COMMENT '资产负债率(%)',
  `current_ratio` decimal(10, 4) NULL DEFAULT NULL COMMENT '流动比率',
  `basic_eps` decimal(10, 4) NULL DEFAULT NULL COMMENT '基本每股收益',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_code_date`(`stock_code` ASC, `report_date` ASC) USING BTREE,
  INDEX `idx_report_date`(`report_date` ASC) USING BTREE,
  INDEX `idx_fiscal_year`(`fiscal_year` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 104070 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '股票财务数据表' ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;
