# -*- coding: utf-8 -*-
"""
数据库更新脚本
为SQLite数据库添加管理端和运营功能相关表和字段
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
    
    # ==================== 1. 更新 users 表 ====================
    cursor.execute("PRAGMA table_info(users)")
    user_columns = {row[1]: row[2] for row in cursor.fetchall()}
    print(f"users表字段: {list(user_columns.keys())}")
    
    # 添加 users 表缺失的字段（从注册审核系统）
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
    
    # 添加票额限售字段
    if 'ticket_limit' not in user_columns:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN ticket_limit INTEGER DEFAULT 200")
            print("✓ 添加字段: users.ticket_limit")
        except Exception as e:
            print(f"✗ 添加字段失败: users.ticket_limit - {e}")
    
    # 添加用户角色字段
    if 'role' not in user_columns:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'seller'")
            print("✓ 添加字段: users.role")
        except Exception as e:
            print(f"✗ 添加字段失败: users.role - {e}")
    
    # ==================== 2. 更新 refunds 表 ====================
    cursor.execute("PRAGMA table_info(refunds)")
    refund_columns = {row[1]: row[2] for row in cursor.fetchall()}
    print(f"refunds表字段: {list(refund_columns.keys())}")
    
    # 添加退票审批相关字段
    new_refund_columns = {
        'approval_status': 'TEXT DEFAULT "approved"',
        'approved_by': 'INTEGER',
        'approved_at': 'TIMESTAMP',
        'reject_reason': 'TEXT',
        'shift_id': 'INTEGER'
    }
    
    for col_name, col_type in new_refund_columns.items():
        if col_name not in refund_columns:
            try:
                cursor.execute(f"ALTER TABLE refunds ADD COLUMN {col_name} {col_type}")
                print(f"✓ 添加字段: refunds.{col_name}")
            except Exception as e:
                print(f"✗ 添加字段失败: refunds.{col_name} - {e}")
    
    # ==================== 3. 更新 tickets 表 ====================
    cursor.execute("PRAGMA table_info(tickets)")
    ticket_columns = {row[1]: row[2] for row in cursor.fetchall()}
    print(f"tickets表字段: {list(ticket_columns.keys())}")
    
    # 添加 shift_id 和 payment_method 字段
    new_ticket_columns = {
        'shift_id': 'INTEGER',
        'payment_method': 'TEXT DEFAULT "cash"',
        'created_at': 'TIMESTAMP'
    }
    
    for col_name, col_type in new_ticket_columns.items():
        if col_name not in ticket_columns:
            try:
                cursor.execute(f"ALTER TABLE tickets ADD COLUMN {col_name} {col_type}")
                print(f"✓ 添加字段: tickets.{col_name}")
            except Exception as e:
                print(f"✗ 添加字段失败: tickets.{col_name} - {e}")
    
    # ==================== 4. 更新 shifts 表 ====================
    cursor.execute("PRAGMA table_info(shifts)")
    shift_columns = {row[1]: row[2] for row in cursor.fetchall()}
    print(f"shifts表字段: {list(shift_columns.keys())}")
    
    # 添加 shifts 表缺失的字段
    new_shift_columns = {
        'user_id': 'INTEGER',
        'end_time': 'TIMESTAMP',
        'total_tickets': 'INTEGER DEFAULT 0',
        'total_amount': 'REAL DEFAULT 0',
        'cash_amount': 'REAL DEFAULT 0',
        'electronic_amount': 'REAL DEFAULT 0',
        'total_refunds': 'INTEGER DEFAULT 0',
        'refund_amount': 'REAL DEFAULT 0'
    }
    
    for col_name, col_type in new_shift_columns.items():
        if col_name not in shift_columns:
            try:
                cursor.execute(f"ALTER TABLE shifts ADD COLUMN {col_name} {col_type}")
                print(f"✓ 添加字段: shifts.{col_name}")
            except Exception as e:
                print(f"✗ 添加字段失败: shifts.{col_name} - {e}")
    
    # ==================== 5. 更新 operation_logs 表 ====================
    cursor.execute("PRAGMA table_info(operation_logs)")
    log_columns = {row[1]: row[2] for row in cursor.fetchall()}
    print(f"operation_logs表字段: {list(log_columns.keys())}")
    
    # 添加 IP 地址等字段（如果不存在）
    new_log_columns = {
        'ip_address': 'TEXT',
        'user_id': 'INTEGER',
        'operation_time': 'TIMESTAMP'
    }
    
    for col_name, col_type in new_log_columns.items():
        if col_name not in log_columns:
            try:
                cursor.execute(f"ALTER TABLE operation_logs ADD COLUMN {col_name} {col_type}")
                print(f"✓ 添加字段: operation_logs.{col_name}")
            except Exception as e:
                print(f"✗ 添加字段失败: operation_logs.{col_name} - {e}")
    
    # ==================== 6. 创建 daily_reports 表 ====================
    if 'daily_reports' not in tables:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_id INTEGER NOT NULL,
                employee_no TEXT NOT NULL,
                report_date DATE NOT NULL,
                total_tickets INTEGER DEFAULT 0,
                total_refunds INTEGER DEFAULT 0,
                total_amount REAL DEFAULT 0,
                cash_amount REAL DEFAULT 0,
                electronic_amount REAL DEFAULT 0,
                refund_amount REAL DEFAULT 0,
                net_amount REAL DEFAULT 0,
                ticket_details TEXT,
                seat_stats TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (shift_id) REFERENCES shifts(shift_id)
            )
        """)
        print("✓ 创建表: daily_reports")
    else:
        print("表已存在: daily_reports")
    
    # ==================== 7. 创建 refund_approvals 表 ====================
    if 'refund_approvals' not in tables:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS refund_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                refund_id INTEGER NOT NULL,
                ticket_id TEXT NOT NULL,
                refund_amount REAL NOT NULL,
                refund_fee REAL DEFAULT 0,
                reason TEXT,
                applicant_id INTEGER NOT NULL,
                applicant_employee_no TEXT,
                status TEXT DEFAULT 'pending',
                approved_by INTEGER,
                approved_at TIMESTAMP,
                reject_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (refund_id) REFERENCES refunds(refund_id)
            )
        """)
        print("✓ 创建表: refund_approvals")
    else:
        print("表已存在: refund_approvals")
    
    # ==================== 8. 创建 pending_refunds 表（待审批退票） ====================
    if 'pending_refunds' not in tables:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_refunds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                passenger_name TEXT,
                train_no TEXT,
                travel_date TEXT,
                from_station TEXT,
                to_station TEXT,
                original_price REAL,
                refund_amount REAL,
                refund_fee REAL,
                reason TEXT,
                applicant_id INTEGER,
                applicant_employee_no TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                processed_by INTEGER,
                reject_reason TEXT
            )
        """)
        print("✓ 创建表: pending_refunds")
    else:
        print("表已存在: pending_refunds")
    
    # ==================== 9. 创建 seller_stats 表（售票员统计） ====================
    if 'seller_stats' not in tables:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seller_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                shift_id INTEGER,
                date DATE NOT NULL,
                total_tickets INTEGER DEFAULT 0,
                total_refunds INTEGER DEFAULT 0,
                total_amount REAL DEFAULT 0,
                avg_tickets_per_hour REAL DEFAULT 0,
                anomaly_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ 创建表: seller_stats")
    else:
        print("表已存在: seller_stats")
    
    # ==================== 10. 创建系统设置表 ====================
    if 'system_settings' not in tables:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ 创建表: system_settings")
        
        # 插入默认设置
        cursor.execute("""
            INSERT OR IGNORE INTO system_settings (key, value, description) VALUES
            ('refund_approval_threshold', '500', '退票审批阈值，超过此金额需要管理员审批'),
            ('ticket_limit_per_shift', '200', '每班次票额限售数量'),
            ('ticket_warning_ratio', '0.8', '票额预警比例'),
            ('ticket_anomaly_threshold', '20', '出票频率异常阈值（5分钟内）'),
            ('monitor_refresh_interval', '30', '实时监控刷新间隔（秒）')
        """)
        print("✓ 插入默认系统设置")
    else:
        print("表已存在: system_settings")
    
    # ==================== 11. 创建索引 ====================
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_operation_logs_time ON operation_logs(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_operation_logs_type ON operation_logs(operation_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_operation_logs_employee ON operation_logs(employee_no)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_shift ON tickets(shift_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_refunds_shift ON refunds(shift_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_refunds_status ON pending_refunds(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_reports_date ON daily_reports(report_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shifts_status ON shifts(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shifts_employee ON shifts(employee_no)")
        print("✓ 创建索引完成")
    except Exception as e:
        print(f"索引创建: {e}")
    
    # ==================== 12. 创建管理员账户 ====================
    try:
        from werkzeug.security import generate_password_hash
        admin_password_hash = generate_password_hash('admin123')
        
        cursor.execute("""
            INSERT OR IGNORE INTO users (username, employee_no, name, password_hash, role, status)
            VALUES ('admin', 'admin', '系统管理员', ?, 'admin', 'active')
        """, (admin_password_hash,))
        print("✓ 创建/更新管理员账户")
    except Exception as e:
        print(f"创建管理员账户: {e}")
    
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
