# -*- coding: utf-8 -*-
"""
一键初始化/修复脚本
删除旧数据库，重建所有表和默认账号
"""
import sqlite3
import os
import sys

# 确保能导入项目依赖
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'railway.db')

print("=" * 50)
print("铁路客票系统 - 一键初始化修复")
print("=" * 50)

# 1. 删除旧数据库
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print("✓ 已删除旧数据库")

# 2. 确保data目录存在
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# 3. 创建数据库和所有表
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("\n正在创建数据表...")

# 用户表
c.execute('''CREATE TABLE users (
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
)''')
print("  ✓ users")

# 车站表
c.execute('''CREATE TABLE stations (
    station_id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_name TEXT NOT NULL,
    station_code TEXT UNIQUE NOT NULL,
    pinyin_code TEXT
)''')
print("  ✓ stations")

# 车次表
c.execute('''CREATE TABLE trains (
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
)''')
print("  ✓ trains")

# 经停站表
c.execute('''CREATE TABLE train_stops (
    stop_id INTEGER PRIMARY KEY AUTOINCREMENT,
    train_number TEXT NOT NULL,
    stop_order INTEGER NOT NULL,
    station_name TEXT,
    station_code TEXT NOT NULL,
    arrival_time TEXT,
    departure_time TEXT,
    distance INTEGER DEFAULT 0
)''')
print("  ✓ train_stops")

# 票价表
c.execute('''CREATE TABLE ticket_prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_station TEXT NOT NULL,
    to_station TEXT NOT NULL,
    seat_type TEXT NOT NULL,
    price REAL NOT NULL
)''')
print("  ✓ ticket_prices")

# 班次表
c.execute('''CREATE TABLE shifts (
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
)''')
print("  ✓ shifts")

# 票务表
c.execute('''CREATE TABLE tickets (
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
)''')
print("  ✓ tickets")

# 补票表
c.execute('''CREATE TABLE supplement_tickets (
    supplement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_ticket_id INTEGER NOT NULL,
    train_number TEXT NOT NULL,
    from_station TEXT NOT NULL,
    to_station TEXT NOT NULL,
    seat_type TEXT NOT NULL,
    price REAL NOT NULL,
    employee_no TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
print("  ✓ supplement_tickets")

# 退票表
c.execute('''CREATE TABLE refunds (
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
)''')
print("  ✓ refunds")

# 操作日志表（包含所有INSERT用到的列）
c.execute('''CREATE TABLE operation_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id INTEGER,
    employee_no TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    ticket_id INTEGER,
    details TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    operation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
print("  ✓ operation_logs")

# 柜台表
c.execute('''CREATE TABLE counters (
    counter_id INTEGER PRIMARY KEY AUTOINCREMENT,
    counter_no INTEGER NOT NULL,
    employee_no TEXT,
    status TEXT DEFAULT 'idle',
    station_code TEXT DEFAULT 'BJP'
)''')
print("  ✓ counters")

# 注册申请表
c.execute('''CREATE TABLE registration_applications (
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
)''')
print("  ✓ registration_applications")

# 邮箱验证码表
c.execute('''CREATE TABLE email_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    code TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    verified INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
print("  ✓ email_verifications")

# 风控记录表
c.execute('''CREATE TABLE risk_controls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    original_machine_code TEXT NOT NULL,
    new_machine_code TEXT NOT NULL,
    action TEXT DEFAULT 'freeze',
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    operated_by INTEGER
)''')
print("  ✓ risk_controls")

# 机器码绑定表
c.execute('''CREATE TABLE machine_bindings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    machine_code TEXT NOT NULL,
    bound_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
print("  ✓ machine_bindings")

# 每日对账表
c.execute('''CREATE TABLE daily_reports (
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
)''')
print("  ✓ daily_reports")

# 退票审批表
c.execute('''CREATE TABLE refund_approvals (
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
)''')
print("  ✓ refund_approvals")

# 待退票表
c.execute('''CREATE TABLE pending_refunds (
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
)''')
print("  ✓ pending_refunds")

# 售票员统计表
c.execute('''CREATE TABLE seller_stats (
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
)''')
print("  ✓ seller_stats")

# 系统设置表
c.execute('''CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT
)''')
print("  ✓ system_settings")

# 插入系统设置
settings = [
    ('ticket_limit_per_shift', '200', '每班次票额限售'),
    ('refund_approval_threshold', '500', '退票审批金额阈值'),
    ('ticket_warning_ratio', '0.8', '票额预警比例'),
    ('ticket_anomaly_threshold', '20', '出票频率异常阈值'),
    ('monitor_refresh_interval', '30', '监控刷新间隔(秒)'),
]
for key, value, desc in settings:
    c.execute('INSERT OR REPLACE INTO system_settings VALUES (?, ?, ?)', (key, value, desc))
print("  ✓ system_settings 数据")

conn.commit()

# 4. 创建默认用户
print("\n正在创建默认用户...")

users = [
    ('admin', '系统管理员', 'admin123', 'admin', 0),
    ('seller001', '售票员张伟', '123456', 'seller', 1),
    ('seller002', '售票员李芳', '123456', 'seller', 2),
]

for emp_no, name, pwd, role, window in users:
    pwd_hash = generate_password_hash(pwd)
    c.execute('''INSERT INTO users (employee_no, name, password_hash, role, window_no, station_code, status)
                 VALUES (?, ?, ?, ?, ?, 'BJP', 'active')''',
              (emp_no, name, pwd_hash, role, window))
    
    # 立即验证
    c.execute('SELECT password_hash FROM users WHERE employee_no = ?', (emp_no,))
    row = c.fetchone()
    if row and check_password_hash(row['password_hash'], pwd):
        print(f"  ✓ {emp_no} / {pwd} ({role}) 验证通过")
    else:
        print(f"  ✗ {emp_no} 密码验证失败！！！")

# 5. 插入示例车站数据
print("\n正在创建示例车站...")
stations = [
    ('北京站', 'BJP', 'BJ'),
    ('北京西', 'BXP', 'BJX'),
    ('上海', 'SHH', 'SH'),
    ('上海虹桥', 'AOH', 'SHH'),
    ('广州', 'GZQ', 'GZ'),
    ('深圳', 'SZQ', 'SZ'),
    ('郑州', 'ZZF', 'ZZ'),
    ('武汉', 'WHN', 'WH'),
    ('西安', 'XAY', 'XA'),
    ('成都', 'CDW', 'CD'),
    ('南京', 'NJH', 'NJ'),
    ('杭州', 'HZH', 'HZ'),
    ('长沙', 'CSQ', 'CS'),
    ('重庆', 'CQW', 'CQ'),
    ('天津', 'TJP', 'TJ'),
]
for name, code, pinyin in stations:
    c.execute('INSERT OR IGNORE INTO stations (station_name, station_code, pinyin_code) VALUES (?, ?, ?)',
              (name, code, pinyin))
print(f"  ✓ {len(stations)} 个车站")

# 插入示例车次
print("\n正在创建示例车次...")
trains = [
    ('G101', '高铁', '北京站', '上海', '1', '06:30', '12:30', 1318),
    ('G305', '高铁', '北京西', '郑州', '1', '07:00', '09:40', 693),
    ('G501', '高铁', '北京西', '武汉', '1', '07:30', '11:30', 1229),
    ('G85', '高铁', '上海', '广州', '1', '08:00', '14:30', 1662),
    ('G7541', '高铁', '上海虹桥', '杭州', '1', '08:30', '09:30', 159),
    ('D941', '动车', '北京西', '深圳', '1', '19:30', '07:30', 2400),
    ('K179', '快速', '北京西', '郑州', '1', '22:30', '06:30', 693),
    ('Z35', '直达', '北京西', '广州', '1', '20:50', '08:30', 2294),
]
for t in trains:
    c.execute('''INSERT OR IGNORE INTO trains 
                 (train_number, train_type, start_station, end_station, running_days, start_time, end_time, total_distance)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', t)
print(f"  ✓ {len(trains)} 个车次")

# 插入经停站数据
print("\n正在创建经停站...")
stops_data = [
    # G101 北京-上海
    ('G101', 1, '北京站', 'BJP', None, '06:30', 0),
    ('G101', 2, '南京', 'NJH', '09:20', '09:23', 1023),
    ('G101', 3, '上海', 'SHH', '12:30', None, 1318),
    # G305 北京-郑州
    ('G305', 1, '北京西', 'BXP', None, '07:00', 0),
    ('G305', 2, '郑州', 'ZZF', '09:40', None, 693),
    # G501 北京-武汉
    ('G501', 1, '北京西', 'BXP', None, '07:30', 0),
    ('G501', 2, '郑州', 'ZZF', '10:10', '10:13', 693),
    ('G501', 3, '武汉', 'WHN', '11:30', None, 1229),
    # G85 上海-广州
    ('G85', 1, '上海', 'SHH', None, '08:00', 0),
    ('G85', 2, '杭州', 'HZH', '08:50', '08:53', 159),
    ('G85', 3, '长沙', 'CSQ', '12:00', '12:03', 1083),
    ('G85', 4, '广州', 'GZQ', '14:30', None, 1662),
]
for s in stops_data:
    c.execute('''INSERT OR IGNORE INTO train_stops 
                 (train_number, stop_order, station_name, station_code, arrival_time, departure_time, distance)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', s)
print(f"  ✓ {len(stops_data)} 条经停记录")

# 插入示例票价
print("\n正在创建示例票价...")
prices = [
    ('北京站', '上海', 'second', 553.0),
    ('北京站', '上海', 'first', 933.0),
    ('北京站', '上海', 'business', 1748.0),
    ('北京站', '南京', 'second', 443.0),
    ('北京站', '南京', 'first', 748.0),
    ('北京西', '郑州', 'second', 329.0),
    ('北京西', '郑州', 'first', 530.0),
    ('北京西', '武汉', 'second', 519.0),
    ('北京西', '武汉', 'first', 879.0),
    ('上海', '广州', 'second', 793.0),
    ('上海', '广州', 'first', 1319.0),
    ('上海', '杭州', 'second', 73.0),
    ('上海', '杭州', 'first', 117.0),
    ('上海', '长沙', 'second', 478.0),
    ('上海', '长沙', 'first', 795.0),
    ('杭州', '长沙', 'second', 405.0),
    ('长沙', '广州', 'second', 314.0),
    ('郑州', '武汉', 'second', 199.0),
    ('郑州', '武汉', 'first', 329.0),
]
for p in prices:
    c.execute('INSERT OR IGNORE INTO ticket_prices (from_station, to_station, seat_type, price) VALUES (?, ?, ?, ?)', p)
print(f"  ✓ {len(prices)} 条票价记录")

conn.commit()
conn.close()

print("\n" + "=" * 50)
print("✅ 初始化完成！")
print("=" * 50)
print("\n默认账号：")
print("  管理员: admin / admin123")
print("  售票员: seller001 / 123456")
print("  售票员: seller002 / 123456")
print("\n启动命令: python app.py")
