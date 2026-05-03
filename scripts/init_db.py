# -*- coding: utf-8 -*-
"""
铁路客票系统 - 数据库初始化脚本
首次运行时创建所有基础表和数据
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'railway.db')

def init_database():
    # 确保data目录存在
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("正在初始化数据库...")
    
    # ========== 基础表 ==========
    
    # 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'seller',
            window_no INTEGER DEFAULT 1,
            station_code TEXT DEFAULT 'BJP',
            status TEXT DEFAULT 'active',
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            id_card TEXT,
            email TEXT,
            machine_code TEXT,
            ticket_limit INTEGER DEFAULT 200
        )
    ''')
    
    # 车站表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stations (
            station_id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_name TEXT NOT NULL,
            station_code TEXT UNIQUE NOT NULL,
            pinyin_code TEXT
        )
    ''')
    
    # 车次表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trains (
            train_id INTEGER PRIMARY KEY AUTOINCREMENT,
            train_number TEXT UNIQUE NOT NULL,
            train_type TEXT NOT NULL,
            start_station TEXT NOT NULL,
            end_station TEXT NOT NULL,
            running_days TEXT,
            start_time TEXT,
            end_time TEXT,
            total_distance INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # 经停站表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS train_stops (
            stop_id INTEGER PRIMARY KEY AUTOINCREMENT,
            train_number TEXT NOT NULL,
            stop_order INTEGER NOT NULL,
            station_name TEXT,
            station_code TEXT NOT NULL,
            arrival_time TEXT,
            departure_time TEXT,
            distance INTEGER DEFAULT 0
        )
    ''')
    
    # 票价表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_prices (
            price_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_station TEXT NOT NULL,
            to_station TEXT NOT NULL,
            seat_type TEXT NOT NULL,
            price REAL NOT NULL
        )
    ''')
    
    # 班次表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shifts (
            shift_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_no TEXT NOT NULL,
            shift_type TEXT NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            total_tickets INTEGER DEFAULT 0,
            total_amount REAL DEFAULT 0,
            cash_amount REAL DEFAULT 0,
            electronic_amount REAL DEFAULT 0,
            total_refunds INTEGER DEFAULT 0,
            refund_amount REAL DEFAULT 0
        )
    ''')
    
    # 票务表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_no TEXT UNIQUE NOT NULL,
            train_number TEXT NOT NULL,
            from_station TEXT NOT NULL,
            to_station TEXT NOT NULL,
            departure_date TEXT NOT NULL,
            seat_type TEXT NOT NULL,
            car_number TEXT,
            seat_number TEXT,
            passenger_name TEXT,
            passenger_id TEXT,
            price REAL NOT NULL,
            status TEXT DEFAULT 'valid',
            employee_no TEXT NOT NULL,
            shift_id INTEGER,
            payment_method TEXT DEFAULT 'cash',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 补票表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supplement_tickets (
            supplement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_ticket_id INTEGER NOT NULL,
            train_number TEXT NOT NULL,
            from_station TEXT NOT NULL,
            to_station TEXT NOT NULL,
            seat_type TEXT NOT NULL,
            price REAL NOT NULL,
            employee_no TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 退票表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS refunds (
            refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            ticket_no TEXT NOT NULL,
            train_number TEXT NOT NULL,
            from_station TEXT NOT NULL,
            to_station TEXT NOT NULL,
            price REAL NOT NULL,
            refund_fee REAL NOT NULL,
            actual_refund REAL NOT NULL,
            reason TEXT,
            employee_no TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approval_status TEXT DEFAULT 'approved',
            approved_by INTEGER,
            approved_at TIMESTAMP,
            reject_reason TEXT,
            shift_id INTEGER
        )
    ''')
    
    # 操作日志表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS operation_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_no TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_id INTEGER,
            operation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 柜台表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS counters (
            counter_id INTEGER PRIMARY KEY AUTOINCREMENT,
            counter_no INTEGER NOT NULL,
            employee_no TEXT,
            status TEXT DEFAULT 'idle',
            station_code TEXT DEFAULT 'BJP'
        )
    ''')
    
    # ========== 注册系统相关表 ==========
    
    # 注册申请表
    cursor.execute('''
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
    ''')
    
    # 邮箱验证码表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 风控记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_controls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            original_machine_code TEXT NOT NULL,
            new_machine_code TEXT NOT NULL,
            action TEXT DEFAULT 'freeze',
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            operated_by INTEGER
        )
    ''')
    
    # 机器码绑定表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS machine_bindings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            machine_code TEXT NOT NULL,
            bound_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ========== 管理端相关表 ==========
    
    # 每日对账表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id INTEGER NOT NULL,
            employee_no TEXT NOT NULL,
            employee_name TEXT,
            shift_type TEXT,
            report_date DATE NOT NULL,
            total_tickets INTEGER DEFAULT 0,
            total_amount REAL DEFAULT 0,
            cash_amount REAL DEFAULT 0,
            electronic_amount REAL DEFAULT 0,
            total_refunds INTEGER DEFAULT 0,
            refund_amount REAL DEFAULT 0,
            net_income REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 退票审批表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS refund_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            refund_id INTEGER NOT NULL,
            ticket_no TEXT NOT NULL,
            amount REAL NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            approved_by INTEGER,
            approved_at TIMESTAMP,
            reject_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 待退票表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_refunds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            ticket_no TEXT NOT NULL,
            train_number TEXT NOT NULL,
            from_station TEXT NOT NULL,
            to_station TEXT NOT NULL,
            price REAL NOT NULL,
            refund_fee REAL NOT NULL,
            actual_refund REAL NOT NULL,
            reason TEXT,
            employee_no TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 售票员统计表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seller_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_no TEXT NOT NULL,
            shift_id INTEGER,
            date DATE NOT NULL,
            tickets_sold INTEGER DEFAULT 0,
            total_amount REAL DEFAULT 0,
            refunds_processed INTEGER DEFAULT 0,
            refund_amount REAL DEFAULT 0,
            avg_ticket_time REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    
    # ========== 创建索引 ==========
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stations_code ON stations(station_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stations_name ON stations(station_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trains_number ON trains(train_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_train_stops_train ON train_stops(train_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_train_stops_station ON train_stops(station_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_employee ON tickets(employee_no)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_train ON tickets(train_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_date ON tickets(departure_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_operation_logs_employee ON operation_logs(employee_no)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_operation_logs_type ON operation_logs(operation_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_operation_logs_time ON operation_logs(created_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_registration_applications_status ON registration_applications(status)')
    conn.commit()
    
    # ========== 插入默认管理员 ==========
    cursor.execute("SELECT COUNT(*) FROM users WHERE employee_no = 'admin'")
    if cursor.fetchone()[0] == 0:
        admin_hash = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (employee_no, name, password_hash, role, window_no, station_code, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('admin', '系统管理员', admin_hash, 'admin', 0, 'BJP', 'active'))
        print("✓ 创建管理员账号: admin / admin123")
    
    # ========== 插入默认售票员 ==========
    cursor.execute("SELECT COUNT(*) FROM users WHERE employee_no = 'seller001'")
    if cursor.fetchone()[0] == 0:
        seller_hash = generate_password_hash('123456')
        cursor.execute('''
            INSERT INTO users (employee_no, name, password_hash, role, window_no, station_code, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('seller001', '售票员张伟', seller_hash, 'seller', 1, 'BJP', 'active'))
        print("✓ 创建售票员账号: seller001 / 123456")
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE employee_no = 'seller002'")
    if cursor.fetchone()[0] == 0:
        seller_hash = generate_password_hash('123456')
        cursor.execute('''
            INSERT INTO users (employee_no, name, password_hash, role, window_no, station_code, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('seller002', '售票员李芳', seller_hash, 'seller', 2, 'BJP', 'active'))
        print("✓ 创建售票员账号: seller002 / 123456")
    
    conn.commit()
    
    # ========== 验证 ==========
    print("\n=== 数据库初始化完成 ===")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"共创建 {len(tables)} 个表:")
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
        count = cursor.fetchone()[0]
        print(f"  {t}: {count} 条记录")
    
    print("\n默认账号:")
    print("  管理员: admin / admin123")
    print("  售票员: seller001 / 123456")
    print("  售票员: seller002 / 123456")
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    init_database()
