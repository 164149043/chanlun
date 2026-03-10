# -*- coding: utf-8 -*-
"""数据库连接管理器

提供线程安全的数据库连接管理，支持上下文管理器。
解决数据库连接泄漏和并发访问问题。
"""
import os
import sys
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

# Windows 终端编码修复
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

# 数据库路径
DB_PATH = Path(__file__).parent / "chanlun_ai.db"

# 线程锁（防止多线程同时访问）
_db_lock = threading.Lock()

# 连接池（简单实现）
_connection_pool: Optional[sqlite3.Connection] = None
_pool_lock = threading.Lock()


def get_db_path() -> Path:
    """获取数据库路径"""
    return DB_PATH


@contextmanager
def get_db_conn():
    """获取数据库连接（上下文管理器）

    使用方法:
        with get_db_conn() as conn:
            # 执行数据库操作
            conn.execute(...)
        # 自动提交和关闭

    特性:
    - 线程安全
    - 自动提交
    - 异常时回滚
    - 自动关闭连接
    - 启用WAL模式提高并发性能
    """
    with _db_lock:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.row_factory = sqlite3.Row

        # 启用WAL模式（提高并发性能）
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")

        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()


def get_db_conn_no_context():
    """获取数据库连接（非上下文管理器）

    用于兼容旧代码。建议使用 get_db_conn() 上下文管理器。

    注意：使用此方法需要手动关闭连接！
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构"""
    with get_db_conn() as conn:
        c = conn.cursor()

        # 表 1: analysis_snapshot（分析快照）
        c.execute("""
        CREATE TABLE IF NOT EXISTS analysis_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            price REAL NOT NULL,
            chanlun_json TEXT NOT NULL,
            ai_json TEXT,
            created_at TEXT NOT NULL,
            evaluated INTEGER DEFAULT 0,
            outcome_json TEXT
        )
        """)

        # 表 2: analysis_outcome（未来结果回填）
        c.execute("""
        CREATE TABLE IF NOT EXISTS analysis_outcome (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            check_after_minutes INTEGER NOT NULL,
            future_price REAL NOT NULL,
            max_price REAL NOT NULL,
            min_price REAL NOT NULL,
            result_direction TEXT NOT NULL,
            hit_scenario_rank INTEGER,
            note TEXT,
            checked_at TEXT NOT NULL,
            FOREIGN KEY(snapshot_id) REFERENCES analysis_snapshot(id)
        )
        """)

        # 创建索引以提高查询性能
        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshot_evaluated
        ON analysis_snapshot(evaluated)
        """)
        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshot_symbol_interval
        ON analysis_snapshot(symbol, interval)
        """)

        conn.commit()


def safe_json_loads(json_str: str, default=None):
    """安全的JSON解析

    参数:
        json_str: JSON字符串
        default: 解析失败时的默认返回值

    返回:
        解析后的对象，失败时返回默认值
    """
    import json
    if default is None:
        default = {}

    if not json_str or not isinstance(json_str, str):
        return default

    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        # 可以记录日志
        return default


def safe_json_dumps(obj, ensure_ascii=False):
    """安全的JSON序列化

    参数:
        obj: 要序列化的对象
        ensure_ascii: 是否确保ASCII编码

    返回:
        JSON字符串，失败时返回空对象的JSON
    """
    import json
    try:
        return json.dumps(obj, ensure_ascii=ensure_ascii)
    except (TypeError, ValueError) as e:
        # 可以记录日志
        return json.dumps({}, ensure_ascii=ensure_ascii)


# ============================================
# 测试
# ============================================

def main():
    """测试数据库管理器"""
    print("测试数据库连接管理器...")

    # 测试1: 初始化数据库
    print("\n1. 初始化数据库...")
    init_db()
    print("   ✓ 数据库初始化成功")

    # 测试2: 上下文管理器
    print("\n2. 测试上下文管理器...")
    with get_db_conn() as conn:
        result = conn.execute("SELECT COUNT(*) as count FROM analysis_snapshot").fetchone()
        print(f"   ✓ 当前记录数: {result['count']}")

    # 测试3: 安全JSON解析
    print("\n3. 测试安全JSON解析...")
    valid_json = '{"test": "value"}'
    invalid_json = '{invalid json}'
    print(f"   ✓ 有效JSON: {safe_json_loads(valid_json)}")
    print(f"   ✓ 无效JSON: {safe_json_loads(invalid_json)}")

    print("\n✅ 所有测试通过!")


if __name__ == "__main__":
    main()
