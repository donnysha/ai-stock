"""
数据库连接管理模块

【模块功能】
管理MySQL数据库连接，提供连接池管理、查询执行等功能。

【主要功能】
1. 连接池管理
   - 单例模式，全局复用连接
   - 延迟初始化，按需创建连接
   
2. 查询执行
   - execute_query: 执行SELECT查询
   - execute_update: 执行INSERT/UPDATE/DELETE
   
3. 上下文管理
   - 支持with语法自动管理连接
   - 自动事务提交/回滚

【使用前提】
- MySQL服务已启动
- 已创建stock数据库
- stock_daily_full表已创建

【使用示例】
db = get_db_connection()
result = db.execute_query("SELECT * FROM stock_daily_full LIMIT 10")
"""

import pymysql
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import DB_CONFIG


class DatabaseConnection:
    """
    数据库连接管理器
    
    【功能说明】
    1. 连接池管理
    2. 执行查询
    3. 获取连接/释放连接
    
    【配置来源】
    - 默认使用config.settings.DB_CONFIG
    - 支持自定义配置传入
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化数据库连接
        
        Args:
            config: 数据库配置，默认使用settings中的配置
        """
        self.config = config or DB_CONFIG
        self._connection: Optional[pymysql.Connection] = None
    
    def connect(self) -> pymysql.Connection:
        """
        建立数据库连接
        
        【连接参数】
        - host: 主机地址
        - port: 端口号，默认3306
        - user: 用户名
        - password: 密码
        - database: 数据库名
        - charset: 字符集，utf8mb4
        
        Returns:
            数据库连接对象
        """
        if self._connection is None or not self._connection.open:
            try:
                self._connection = pymysql.connect(
                    host=self.config['host'],
                    port=self.config.get('port', 3306),
                    user=self.config['user'],
                    password=self.config['password'],
                    database=self.config['database'],
                    charset=self.config.get('charset', 'utf8mb4'),
                    cursorclass=pymysql.cursors.DictCursor
                )
            except pymysql.Error as e:
                print(f"数据库连接失败: {e}")
                raise
        
        return self._connection
    
    def close(self):
        """关闭数据库连接"""
        if self._connection and self._connection.open:
            self._connection.close()
            self._connection = None
    
    def execute_query(
        self,
        sql: str,
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        执行查询SQL
        
        Args:
            sql: SQL语句
            params: 参数元组
        
        Returns:
            查询结果列表
        """
        conn = self.connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                results = cursor.fetchall()
                return results
        except pymysql.Error as e:
            print(f"查询执行失败: {e}")
            raise
        finally:
            # 不关闭连接，保持连接池复用
            pass
    
    def execute_update(
        self,
        sql: str,
        params: Optional[tuple] = None
    ) -> int:
        """
        执行更新SQL
        
        Args:
            sql: SQL语句
            params: 参数元组
        
        Returns:
            影响行数
        """
        conn = self.connect()
        try:
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, params)
                conn.commit()
                return affected
        except pymysql.Error as e:
            conn.rollback()
            print(f"更新执行失败: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        测试数据库连接
        
        Returns:
            连接是否成功
        """
        try:
            conn = self.connect()
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
        except Exception:
            return False
    
    @contextmanager
    def get_connection(self):
        """
        上下文管理器，获取数据库连接
        
        Usage:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(...)
        """
        conn = self.connect()
        try:
            yield conn
        finally:
            pass  # 不关闭连接，保持复用
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._connection.rollback()
        return False  # 不抑制异常


# 全局实例（延迟初始化）
_db_connection: Optional[DatabaseConnection] = None


def get_db_connection() -> DatabaseConnection:
    """获取全局数据库连接实例"""
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection()
    return _db_connection


def execute_query(sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """快捷函数：执行查询"""
    return get_db_connection().execute_query(sql, params)


def execute_update(sql: str, params: Optional[tuple] = None) -> int:
    """快捷函数：执行更新"""
    return get_db_connection().execute_update(sql, params)


def test_connection() -> bool:
    """快捷函数：测试连接"""
    return get_db_connection().test_connection()
