# -*- coding: utf-8 -*-
"""
数据库更新脚本
为SQLite数据库添加注册审核系统相关表
"""

import sqlite3
import os
import sys

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'railway.db')


def update_database():
    """更新数据库结构"""
    print(f"数据库路径: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print("错误: 数据库文件不存在!")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查现有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"现有表: {tables}")
    
    # 检查users表结构
    cursor.execute("PRAGMA table_info(users)")
    user_columns = {row[1]: row[2] for row in cursor.fetchall()}
    print(f"users表字段: {list(user_columns.keys())}")
    
    # 1. 为users表添加缺失的字段
    new_user_columns = {
        'id_card': 'TEXT',
        'email': 'TEXT',
        'machine_code': 'TEXT',
        'status': 'TEXT DEFAULT "active"',
        'last_login': 'TIMESTAMP'
    }
    
    for col_name, col_type in new_user_columns.items():
        if col_name not in user_columns:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                print(f"✓ 添加字段: users.{col_name}")
            except Exception as e:
                print(f"✗ 添加字段失败: users.{col_name} - {e}")
    
    # 2. 创建 registration_applications 表
    if 'registration_applications' not in tables:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registration_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                real_name TEXT NOT NULL,
                id_card TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                station_code TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE,
                window_no INTEGER NOT NULL,
                password_hash TEXT NOT NULL,
                machine_code TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                reject_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                reviewed_by INTEGER
            )
        """)
        print("✓ 创建表: registration_applications")
    else:
        print("表已存在: registration_applications")
    
    # 3. 创建 email_verifications 表
    if 'email_verifications' not in tables:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                code TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                verified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ 创建表: email_verifications")
    else:
        print("表已存在: email_verifications")
    
    # 4. 创建 risk_controls 表
    if 'risk_controls' not in tables:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_controls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                original_machine_code TEXT NOT NULL,
                new_machine_code TEXT,
                action TEXT DEFAULT 'freeze',
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                operated_by INTEGER
            )
        """)
        print("✓ 创建表: risk_controls")
    else:
        print("表已存在: risk_controls")
    
    # 5. 创建 machine_bindings 表
    if 'machine_bindings' not in tables:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS machine_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                machine_code TEXT NOT NULL,
                bound_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ 创建表: machine_bindings")
    else:
        print("表已存在: machine_bindings")
    
    # 6. 创建索引
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reg_app_status ON registration_applications(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reg_app_username ON registration_applications(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reg_app_idcard ON registration_applications(id_card)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_userid ON risk_controls(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_verif_email ON email_verifications(email)")
        print("✓ 创建索引完成")
    except Exception as e:
        print(f"索引创建: {e}")
    
    # 提交更改
    conn.commit()
    
    # 验证表结构
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    final_tables = [row[0] for row in cursor.fetchall()]
    print(f"\n最终表列表: {final_tables}")
    
    cursor.close()
    conn.close()
    
    print("\n✓ 数据库更新完成!")
    return True


if __name__ == '__main__':
    success = update_database()
    sys.exit(0 if success else 1)
