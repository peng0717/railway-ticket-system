# -*- coding: utf-8 -*-
"""
WebTRS 应用入口
模拟铁路车站人工售票系统
使用SQLite数据库
集成注册审核系统 (Flask Blueprint) 和管理端
"""

import os
import json
import random
import sqlite3
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, session, redirect, url_for, request, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# 导入配置
import config

# 创建Flask应用
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# 配置会话有效期为30分钟（会话超时）
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# 注册 Blueprint
from blueprints.register_bp import register_bp
app.register_blueprint(register_bp, url_prefix='/register')

# ==================== 数据库路径 ====================

def get_db_path():
    """获取数据库路径"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, 'data', 'railway.db')

# ==================== 自动初始化数据库 ====================

def ensure_database_initialized():
    """启动时自动检测并初始化数据库，从根源避免 'no such table' 错误"""
    db_path = get_db_path()
    need_full_init = True
    
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone():
                need_full_init = False
                
                # 即使数据库存在，也检查stations表是否有数据（修复车站搜索不到的问题）
                cursor.execute("SELECT COUNT(*) FROM stations")
                station_count = cursor.fetchone()[0]
                if station_count <= 1:
                    print("⚠️  车站数据为空，正在导入全国车站...")
                    import json
                    stations_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'all_stations.json')
                    if os.path.exists(stations_json):
                        with open(stations_json, 'r', encoding='utf-8') as f:
                            stations_data = json.load(f)
                        imported = 0
                        for s in stations_data:
                            if s.get('name') == 'station':
                                continue
                            try:
                                cursor.execute('INSERT OR IGNORE INTO stations (station_name, station_code, pinyin_code) VALUES (?, ?, ?)',
                                             (s.get('name', ''), s.get('telecode', ''), s.get('pinyin_code', '')))
                                imported += 1
                            except Exception:
                                pass
                        conn.commit()
                        cursor.execute("SELECT COUNT(*) FROM stations")
                        actual = cursor.fetchone()[0]
                        print(f"✅ 全国车站数据导入完成: {imported} 条，实际入库 {actual} 条")
                    else:
                        print("⚠️  未找到 all_stations.json，跳过车站导入")
                
                # 自动补表：检查并创建缺失的表
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = {row[0] for row in cursor.fetchall()}
                
                if 'system_settings' not in existing_tables:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS system_settings (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    default_settings = [
                        ('refund_approval_threshold', '500'),
                        ('ticket_limit_per_shift', '200'),
                        ('ticket_warning_ratio', '0.8'),
                        ('ticket_anomaly_threshold', '50'),
                        ('monitor_refresh_interval', '30'),
                        ('log_retention_days', '90'),
                    ]
                    for key, value in default_settings:
                        cursor.execute('INSERT OR IGNORE INTO system_settings (key, value) VALUES (?, ?)', (key, value))
                    conn.commit()
                    print("✅ 自动补表: system_settings")
                
                if 'risk_controls' not in existing_tables:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS risk_controls (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            username TEXT,
                            original_machine_code TEXT,
                            new_machine_code TEXT,
                            action TEXT NOT NULL,
                            reason TEXT,
                            operated_by INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    conn.commit()
                    print("✅ 自动补表: risk_controls")
                
                if 'machine_bindings' not in existing_tables:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS machine_bindings (
                            user_id INTEGER PRIMARY KEY,
                            machine_code TEXT NOT NULL,
                            bound_at TIMESTAMP,
                            updated_at TIMESTAMP
                        )
                    ''')
                    conn.commit()
                    print("✅ 自动补表: machine_bindings")
                
                if 'registration_applications' not in existing_tables:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS registration_applications (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            real_name TEXT NOT NULL,
                            id_card TEXT NOT NULL UNIQUE,
                            email TEXT NOT NULL,
                            station_code TEXT,
                            username TEXT NOT NULL UNIQUE,
                            window_no TEXT,
                            password_hash TEXT NOT NULL,
                            machine_code TEXT,
                            status TEXT DEFAULT 'pending',
                            reject_reason TEXT,
                            reviewed_by INTEGER,
                            reviewed_at TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    conn.commit()
                    print("✅ 自动补表: registration_applications")
                
                if 'email_verifications' not in existing_tables:
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
                    conn.commit()
                    print("✅ 自动补表: email_verifications")
                
                # 班列管理模块新表
                if 'import_logs' not in existing_tables:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS import_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            import_type TEXT,
                            filename TEXT,
                            total_rows INTEGER DEFAULT 0,
                            success_count INTEGER DEFAULT 0,
                            fail_count INTEGER DEFAULT 0,
                            skip_count INTEGER DEFAULT 0,
                            status TEXT DEFAULT 'processing',
                            error_details TEXT,
                            operator TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    conn.commit()
                    print("✅ 自动补表: import_logs")
                
                if 'data_sync_status' not in existing_tables:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS data_sync_status (
                            sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sync_type TEXT,
                            triggered_by TEXT,
                            train_count INTEGER DEFAULT 0,
                            station_count INTEGER DEFAULT 0,
                            seller_count INTEGER DEFAULT 0,
                            status TEXT DEFAULT 'running',
                            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            completed_at TIMESTAMP,
                            details TEXT
                        )
                    ''')
                    conn.commit()
                    print("✅ 自动补表: data_sync_status")
                
                if 'seller_train_cache' not in existing_tables:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS seller_train_cache (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            station_code TEXT,
                            train_id INTEGER,
                            train_number TEXT,
                            sync_id INTEGER,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(station_code, train_id)
                        )
                    ''')
                    conn.commit()
                    print("✅ 自动补表: seller_train_cache")
                
                if 'train_seat_inventory' not in existing_tables:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS train_seat_inventory (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            train_id INTEGER,
                            travel_date TEXT,
                            seat_type TEXT,
                            total_seats INTEGER DEFAULT 0,
                            sold_seats INTEGER DEFAULT 0,
                            available_seats INTEGER DEFAULT 0,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(train_id, travel_date, seat_type)
                        )
                    ''')
                    conn.commit()
                    print("✅ 自动补表: train_seat_inventory")
                
                # 自动填充座席默认票额（如果全是NULL）
                cursor.execute("""
                    SELECT COUNT(DISTINCT train_id) FROM train_stops 
                    WHERE seat_business IS NULL AND seat_first IS NULL AND seat_second IS NULL 
                        AND seat_soft IS NULL AND seat_hard IS NULL AND seat_soft_sleeper IS NULL AND seat_hard_sleeper IS NULL
                """)
                null_seats_count = cursor.fetchone()[0]
                
                if null_seats_count > 0:
                    print(f"⚠️  发现 {null_seats_count} 个车次座席数据为空，正在自动填充...")
                    # 车型默认票额配置
                    seat_defaults = {
                        'G': {'seat_business': 20, 'seat_first': 50, 'seat_second': 500},
                        'D': {'seat_first': 60, 'seat_second': 600},
                        'C': {'seat_first': 40, 'seat_second': 400},
                        'Z': {'seat_soft_sleeper': 30, 'seat_hard_sleeper': 200, 'seat_hard': 500},
                        'T': {'seat_soft_sleeper': 20, 'seat_hard_sleeper': 150, 'seat_hard': 400},
                        'K': {'seat_soft_sleeper': 15, 'seat_hard_sleeper': 100, 'seat_hard': 300},
                    }
                    
                    cursor.execute("SELECT train_id, train_number, train_type FROM trains")
                    for train_id, train_number, train_type in cursor.fetchall():
                        defaults = seat_defaults.get(train_type, seat_defaults.get(train_number[0] if train_number else 'K', {}))
                        if not defaults:
                            defaults = {'seat_hard': 200}
                        for seat_field, seat_count in defaults.items():
                            cursor.execute(f"""
                                UPDATE train_stops SET {seat_field} = ?
                                WHERE train_id = ? AND ({seat_field} IS NULL OR {seat_field} = 0)
                            """, (seat_count, train_id))
                    
                    conn.commit()
                    print("✅ 座席数据自动填充完成")
                
                # 自动填充running_days（如果全是NULL）
                cursor.execute("SELECT COUNT(*) FROM trains WHERE running_days IS NULL OR running_days = ''")
                null_days_count = cursor.fetchone()[0]
                
                if null_days_count > 0:
                    print(f"⚠️  发现 {null_days_count} 个车次开行日期为空，正在自动填充...")
                    cursor.execute("""
                        UPDATE trains SET running_days = '1234567' 
                        WHERE running_days IS NULL OR running_days = ''
                    """)
                    conn.commit()
                    print("✅ 开行日期自动填充完成")
                
                # 自动为ticket_prices添加train_type字段
                cursor.execute("PRAGMA table_info(ticket_prices)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'train_type' not in columns:
                    cursor.execute("ALTER TABLE ticket_prices ADD COLUMN train_type VARCHAR(10)")
                    conn.commit()
                    print("✅ ticket_prices表已添加train_type字段")
                
                # 自动创建多站测试账号（如果只有少量用户）
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
                
                if user_count <= 3:
                    print(f"⚠️  只有 {user_count} 个用户，正在创建多站测试账号...")
                    test_users = [
                        ('seller003', '上海站售票员', 'SHH', '201号口'),
                        ('seller004', '北京站售票员', 'BJP', '301号口'),
                        ('seller005', '广州站售票员', 'GZQ', '401号口'),
                        ('seller006', '武汉站售票员', 'WHN', '501号口'),
                    ]
                    for emp_no, name, station_code, window_no in test_users:
                        cursor.execute("SELECT user_id FROM users WHERE employee_no = ?", (emp_no,))
                        if not cursor.fetchone():
                            password_hash = generate_password_hash('123456')
                            cursor.execute("""
                                INSERT INTO users (employee_no, password_hash, name, role, window_no, station_code, status, ticket_limit)
                                VALUES (?, ?, ?, 'seller', ?, ?, 'active', 200)
                            """, (emp_no, password_hash, name, window_no, station_code))
                    conn.commit()
                    print("✅ 多站测试账号创建完成")
                
                # 自动创建 simulation_config 表
                if 'simulation_config' not in existing_tables:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS simulation_config (
                            key TEXT PRIMARY KEY,
                            value TEXT,
                            description TEXT
                        )
                    ''')
                    default_config = [
                        ('speed', 'normal', '模拟速度: slow/normal/fast'),
                        ('sell_weight', '80', '售票概率权重'),
                        ('refund_weight', '15', '退票概率权重'),
                        ('shift_weight', '5', '开班概率权重'),
                        ('auto_start', 'false', '应用启动时是否自动开始模拟'),
                    ]
                    for key, value, desc in default_config:
                        cursor.execute('INSERT OR IGNORE INTO simulation_config (key, value, description) VALUES (?, ?, ?)',
                                     (key, value, desc))
                    conn.commit()
                    print("✅ 自动补表: simulation_config")
                
                cursor.close()
                conn.close()
                return
            cursor.close()
            conn.close()
        except Exception:
            pass  # 数据库损坏，重新初始化
    
    # 数据库不存在或损坏，自动执行初始化
    print("⚠️  数据库不存在或不完整，正在自动初始化...")
    init_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts', 'init_db.py')
    if os.path.exists(init_script):
        import importlib.util
        spec = importlib.util.spec_from_file_location("init_db", init_script)
        init_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(init_module)
        if hasattr(init_module, 'init_database'):
            init_module.init_database()
            print("✅ 数据库自动初始化完成！")
    else:
        print("❌ 找不到初始化脚本 scripts/init_db.py，请手动运行: python scripts/init_db.py")

ensure_database_initialized()

# ==================== 全局模板函数 ====================

@app.context_processor
def inject_utils():
    """注入全局模板函数和变量"""
    # 全局注入 pending_registrations，避免每个路由都要手动传
    pending_registrations = 0
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM registration_applications WHERE status='pending'")
            row = cursor.fetchone()
            pending_registrations = row['cnt'] if row else 0
            cursor.close()
            conn.close()
    except Exception:
        pass
    
    return {
        'getTrainTypeName': getTrainTypeName,
        'system_name': config.SYSTEM_NAME,
        'pending_registrations': pending_registrations
    }

# ==================== 数据库连接函数 ====================

def get_db_connection():
    """获取数据库连接"""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def get_db_dict_connection():
    """获取返回字典的数据库连接"""
    conn = get_db_connection()
    if not conn:
        return None
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    return conn

# ==================== 辅助函数 ====================

def getTrainTypeName(type_code):
    """获取车型名称"""
    types = {
        'G': '高速动车组',
        'D': '动车组',
        'C': '城际动车组',
        'Z': '直达特快',
        'T': '特快',
        'K': '快速'
    }
    return types.get(type_code, type_code)

def get_user_by_employee_no(employee_no):
    """根据工号获取用户"""
    conn = get_db_dict_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE employee_no = ?", (employee_no,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    except Exception as e:
        print(f"查询用户失败: {e}")
        if conn:
            conn.close()
        return None

def update_user_machine_code(user_id, machine_code, status='active'):
    """更新用户机器码"""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET machine_code = ?, status = ?, last_login = ?
            WHERE user_id = ?
        """, (machine_code, status, datetime.now().isoformat(), user_id))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"更新用户机器码失败: {e}")
        conn.rollback()
        conn.close()
        return False

def add_risk_control_record(user_id, employee_no, machine_code, risk_type, description):
    """添加风控记录"""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO risk_controls (user_id, username, risk_type, machine_code, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, employee_no, risk_type, machine_code, description, datetime.now().isoformat()))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"添加风控记录失败: {e}")
        conn.rollback()
        conn.close()
        return False

def check_machine_code(user, current_machine_code):
    """
    检查机器码是否匹配
    返回: (is_valid, message)
    """
    if not user:
        return False, "用户不存在"
    
    # pending状态
    if user.get('status') == 'pending':
        return False, "您的注册申请正在审核中，请耐心等待管理员审批"
    
    # frozen状态
    if user.get('status') == 'frozen':
        return False, "该工号因异地登录已被风控冻结，请联系管理员"
    
    # inactive状态
    if user.get('status') == 'inactive':
        return False, "该工号已被禁用，请联系管理员"
    
    # 首次登录或没有记录机器码，直接设置
    if not user.get('machine_code'):
        return True, None
    
    # 检查机器码是否匹配
    if user['machine_code'] != current_machine_code:
        return False, "机器码不匹配，检测到异地登录"
    
    return True, None

def get_next_ticket_id():
    """获取下一张票号"""
    conn = get_db_connection()
    if not conn:
        return 'A000001'
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT current_value, prefix FROM counters WHERE counter_name = 'ticket'")
        row = cursor.fetchone()
        
        if row:
            new_value = row[0] + 1
            prefix = row[1] or 'A'
        else:
            new_value = 1
            prefix = 'A'
        
        cursor.execute("""
            INSERT OR REPLACE INTO counters (counter_name, current_value, prefix, updated_at)
            VALUES ('ticket', ?, ?, ?)
        """, (new_value, prefix, datetime.now().isoformat()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return f"{prefix}{new_value:06d}"
    except Exception as e:
        print(f"获取票号失败: {e}")
        conn.rollback()
        conn.close()
        return 'A000001'

def search_stations(pinyin_code):
    """搜索车站（按拼音码或站名）"""
    if not pinyin_code or len(pinyin_code) < 1:
        return []
    
    pinyin_code = pinyin_code.upper()
    conn = get_db_dict_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT station_code, station_name, station_pinyin, pinyin_code
            FROM stations
            WHERE (pinyin_code LIKE ? OR station_code LIKE ? OR station_name LIKE ? OR station_pinyin LIKE ?)
            LIMIT 10
        """, (f'{pinyin_code}%', f'{pinyin_code}%', f'%{pinyin_code}%', f'{pinyin_code}%'))
        
        stations = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [{'code': s['station_code'], 'name': s['station_name'], 
                 'pinyin': s['station_pinyin'], 'pinyin_code': s['pinyin_code']} for s in stations]
    except Exception as e:
        print(f"搜索车站失败: {e}")
        if conn:
            conn.close()
        return []

def calculate_price(from_station, to_station, seat_type, train_type=None):
    """计算票价
    
    Args:
        from_station: 出发站station_code
        to_station: 到达站station_code
        seat_type: 席别类型
        train_type: 车型（可选，用于精确匹配票价）
    """
    conn = get_db_dict_connection()
    if not conn:
        return 200
    
    try:
        cursor = conn.cursor()
        
        # 优先按 train_type + from_station + to_station + seat_type 查询
        if train_type:
            cursor.execute("""
                SELECT base_price FROM ticket_prices
                WHERE from_station = ? AND to_station = ? AND seat_type = ? AND train_type = ?
            """, (from_station, to_station, seat_type, train_type))
            price = cursor.fetchone()
            if price:
                cursor.close()
                conn.close()
                return price['base_price']
        
        # 退化为按 from_station + to_station + seat_type 查询
        cursor.execute("""
            SELECT base_price FROM ticket_prices
            WHERE from_station = ? AND to_station = ? AND seat_type = ?
        """, (from_station, to_station, seat_type))
        price = cursor.fetchone()
        
        if price:
            cursor.close()
            conn.close()
            return price['base_price']
        
        # 如果没有固定票价，按距离计算
        cursor.execute("""
            SELECT distance_from_start FROM train_stops WHERE station_code = ? LIMIT 1
        """, (from_station,))
        from_stop = cursor.fetchone()
        
        cursor.execute("""
            SELECT distance_from_start FROM train_stops WHERE station_code = ? LIMIT 1
        """, (to_station,))
        to_stop = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if from_stop and to_stop and from_stop['distance_from_start'] and to_stop['distance_from_start']:
            distance = abs(to_stop['distance_from_start'] - from_stop['distance_from_start'])
            base_rate = 0.46
            
            seat_config = config.SEAT_TYPES.get(seat_type, {})
            coefficient = seat_config.get('coefficient', 1.0)
            
            return round(distance * base_rate * coefficient, 2)
        
        default_prices = {
            'business': 800, 'first': 500, 'second': 300,
            'soft_seat': 250, 'hard_seat': 150,
            'soft_sleeper': 400, 'hard_sleeper': 280
        }
        return default_prices.get(seat_type, 200)
    except Exception as e:
        print(f"计算票价失败: {e}")
        if conn:
            conn.close()
        return 200

def calculate_refund_fee(ticket_price, travel_date, departure_time, refund_time=None):
    """计算退票手续费"""
    if refund_time is None:
        refund_time = datetime.now()
    
    try:
        travel_datetime = datetime.strptime(f"{travel_date} {departure_time}", '%Y-%m-%d %H:%M')
        hours_until_departure = (travel_datetime - refund_time).total_seconds() / 3600
    except:
        return 0.0
    
    if hours_until_departure >= 360:
        return 0.0
    elif hours_until_departure >= 48:
        return round(ticket_price * 0.05, 2)
    elif hours_until_departure >= 24:
        return round(ticket_price * 0.10, 2)
    elif hours_until_departure >= 0:
        return round(ticket_price * 0.20, 2)
    else:
        return ticket_price

def generate_seat_number(seat_type):
    """生成座位号"""
    if seat_type in ['business', 'first', 'second']:
        carriage = random.randint(1, 16)
        row = random.randint(1, 20)
        pos = random.choice(['A', 'B', 'C', 'D', 'F'])
        return f"{carriage:02d}{row:02d}{pos}"
    elif seat_type in ['soft_seat', 'hard_seat']:
        carriage = random.randint(1, 16)
        seat = random.randint(1, 100)
        return f"{carriage:02d}{seat:03d}"
    else:
        carriage = random.randint(1, 10)
        berth = random.randint(1, 60)
        pos = random.choice(['上', '中', '下'])
        return f"{carriage:02d}{berth:02d}{pos}"

def calculate_duration(start, end):
    """计算行程时长"""
    try:
        s = datetime.strptime(start, '%H:%M')
        e = datetime.strptime(end, '%H:%M')
        if e < s:
            e += timedelta(days=1)
        diff = e - s
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        return f"{hours}小时{minutes}分钟"
    except:
        return ""

def get_current_shift():
    """获取当前班次"""
    if 'shift_id' in session:
        conn = get_db_dict_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM shifts WHERE shift_id = ?", (session['shift_id'],))
                shift = cursor.fetchone()
                cursor.close()
                conn.close()
                return shift
            except:
                conn.close()
                return None
    return None

def log_operation(operation_type, ticket_id=None, details=None):
    """记录操作日志"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO operation_logs (shift_id, employee_no, operation_type, ticket_id, details, ip_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session.get('shift_id'),
            session.get('employee_no'),
            operation_type,
            ticket_id,
            json.dumps(details, ensure_ascii=False) if details else None,
            request.remote_addr,
            datetime.now().isoformat()
        ))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"记录操作日志失败: {e}")
        if conn:
            conn.rollback()
            conn.close()

def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # API请求返回JSON，页面请求重定向
            if request.path.startswith('/api/'):
                return jsonify({'status': 'error', 'message': '请先登录'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """管理端登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            # API请求返回JSON，页面请求重定向
            if request.path.startswith('/admin/api/'):
                return jsonify({'status': 'error', 'message': '请先登录管理员账号'}), 401
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def generate_captcha():
    """
    生成简单数字验证码
    返回: (code, image_base64)
    """
    import base64
    from io import BytesIO
    
    code = ''.join([str(random.randint(0, 9)) for _ in range(4)])
    
    try:
        from PIL import Image, ImageDraw, ImageFont
        width, height = 120, 40
        img = Image.new('RGB', (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        for _ in range(3):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            draw.line([(x1, y1), (x2, y2)], fill=(200, 200, 200))
        
        for i, char in enumerate(code):
            x = 20 + i * 25
            y = random.randint(5, 15)
            draw.text((x, y), char, fill=(0, 82, 165))
        
        for _ in range(50):
            x = random.randint(0, width-1)
            y = random.randint(0, height-1)
            draw.point((x, y), fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        return code, f'data:image/png;base64,{img_base64}'
    except ImportError:
        return code, None

def get_user_role(user):
    """获取用户角色"""
    if not user:
        return 'seller'
    return user.get('role', 'seller')

def check_ticket_limit(user_id, shift_id):
    """检查票额限售"""
    conn = get_db_dict_connection()
    if not conn:
        return True, 200, 0
    
    try:
        cursor = conn.cursor()
        
        # 获取用户个人限额
        cursor.execute("SELECT ticket_limit FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        user_limit = user_row['ticket_limit'] if user_row else config.TICKET_LIMIT_PER_SHIFT
        
        # 获取当前班次已售票数
        cursor.execute("""
            SELECT COUNT(*) as count FROM tickets 
            WHERE shift_id = ? AND status = 'sold'
        """, (shift_id,))
        count_row = cursor.fetchone()
        current_count = count_row['count'] if count_row else 0
        
        cursor.close()
        conn.close()
        
        # 检查是否超限
        if current_count >= user_limit:
            return False, user_limit, current_count
        
        return True, user_limit, current_count
    except Exception as e:
        print(f"检查票额限售失败: {e}")
        if conn:
            conn.close()
        return True, config.TICKET_LIMIT_PER_SHIFT, 0

# ==================== 路由 ====================

@app.route('/')
def index():
    """首页/登录页"""
    if 'user_id' in session:
        # 根据角色分流
        role = session.get('user_role', 'seller')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif 'shift_id' in session:
            return redirect(url_for('main'))
        else:
            return redirect(url_for('shift_select'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if 'user_id' in session:
        role = session.get('user_role', 'seller')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('shift_select'))
    
    error = None
    
    captcha_code, captcha_image = generate_captcha()
    session['captcha_code'] = captcha_code.lower()
    
    if request.method == 'POST':
        employee_no = request.form.get('employee_no', '').strip()
        password = request.form.get('password', '').strip()
        machine_code = request.form.get('machine_code', '').strip()
        captcha_input = request.form.get('captcha', '').strip().lower()
        
        stored_captcha = session.get('captcha_code', '')
        # 验证码暂时跳过（开发调试）
        if False and (not captcha_input or captcha_input != stored_captcha):
            error = '验证码错误，请重新输入'
            captcha_code, captcha_image = generate_captcha()
            session['captcha_code'] = captcha_code.lower()
            return render_template('login.html', error=error, captcha_image=captcha_image, 
                                   system_name=config.SYSTEM_NAME, employee_no=employee_no)
        
        session.pop('captcha_code', None)
        
        locked_key = f'login_locked_{employee_no}'
        locked_time = session.get(locked_key)
        if locked_time:
            lock_elapsed = time.time() - locked_time
            if lock_elapsed < 900:
                remaining = int(900 - lock_elapsed)
                error = f'账号已锁定，请{int(remaining//60)}分{remaining%60}秒后重试'
                captcha_code, captcha_image = generate_captcha()
                session['captcha_code'] = captcha_code.lower()
                return render_template('login.html', error=error, captcha_image=captcha_image,
                                       system_name=config.SYSTEM_NAME, employee_no=employee_no)
            else:
                session.pop(locked_key, None)
                failed_key = f'login_failed_{employee_no}'
                session.pop(failed_key, None)
        
        if not employee_no or not password:
            error = '请输入工号和密码'
        else:
            user = get_user_by_employee_no(employee_no)
            
            if user:
                stored_hash = user.get('password_hash', '')
                if check_password_hash(stored_hash, password):
                    is_valid, message = check_machine_code(user, machine_code)
                    
                    if not is_valid:
                        error = message
                        if message == "机器码不匹配，检测到异地登录":
                            update_user_machine_code(user['user_id'], user.get('machine_code', ''), 'frozen')
                            add_risk_control_record(
                                user['user_id'], 
                                employee_no, 
                                machine_code, 
                                'machine_code_mismatch',
                                f"异地登录：原机器码={user.get('machine_code', 'N/A')}，新机器码={machine_code}"
                            )
                            error = "该工号因异地登录已被风控冻结，请联系管理员"
                    else:
                        if not user.get('machine_code') and machine_code:
                            update_user_machine_code(user['user_id'], machine_code, 'active')
                        
                        session['user_id'] = user['user_id']
                        session['employee_no'] = user['employee_no']
                        session['user_name'] = user.get('name', '') or ''
                        session['window_no'] = user.get('window_no') or config.DEFAULT_WINDOW_NO
                        session['station_code'] = user.get('station_code') or 'ZZO'
                        session['station_name'] = user.get('station_name', '郑州站')
                        session['user_role'] = user.get('role', 'seller')
                        session.permanent = True
                        
                        next_ticket = get_next_ticket_id()
                        session['next_ticket_id'] = next_ticket
                        
                        failed_key = f'login_failed_{employee_no}'
                        session.pop(failed_key, None)
                        
                        log_operation('login')
                        
                        # 根据角色分流
                        role = session['user_role']
                        if role == 'admin':
                            session['admin_logged_in'] = True
                            session['admin_username'] = 'admin'
                            return redirect(url_for('admin_dashboard'))
                        
                        return redirect(url_for('shift_select'))
                else:
                    failed_key = f'login_failed_{employee_no}'
                    failed_count = session.get(failed_key, 0) + 1
                    session[failed_key] = failed_count
                    
                    if failed_count >= 3:
                        session[locked_key] = time.time()
                        session.pop(failed_key, None)
                        error = '连续输错3次密码，账号锁定15分钟'
                    else:
                        error = f'工号或密码错误，还可尝试{3-failed_count}次'
            else:
                error = '工号或密码错误'
    
    # 使用flash传递错误信息，避免表单重新提交问题
    if error:
        flash(error, 'error')
    return render_template('login.html', error=error, captcha_image=captcha_image, 
                           system_name=config.SYSTEM_NAME)

@app.route('/logout')
def logout():
    """退出登录"""
    if 'user_id' in session:
        log_operation('logout')
    session.clear()
    flash('已退出系统', 'info')
    return redirect(url_for('login'))

# ==================== 管理端路由 ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """管理端登录页面"""
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        admin_username = os.getenv('ADMIN_USERNAME', config.ADMIN_USERNAME)
        admin_password = os.getenv('ADMIN_PASSWORD', config.ADMIN_PASSWORD)
        
        if username == admin_username and password == admin_password:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['login_time'] = datetime.now().isoformat()
            flash('管理员登录成功', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('admin/login.html', system_name=config.SYSTEM_NAME)

@app.route('/admin/logout')
def admin_logout():
    """管理端登出"""
    session.clear()
    flash('已退出管理系统', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    """管理端首页"""
    conn = get_db_dict_connection()
    
    stats = {
        'total_users': 0,
        'active_users': 0,
        'pending_registrations': 0,
        'pending_refunds': 0
    }
    active_sellers = []
    recent_logs = []
    today_stats = {
        'total_tickets': 0,
        'total_refunds': 0,
        'total_amount': 0,
        'refund_amount': 0,
        'net_amount': 0
    }
    
    if conn:
        cursor = conn.cursor()
        
        # 统计用户
        cursor.execute("SELECT COUNT(*) as cnt FROM users")
        stats['total_users'] = (lambda r: r['cnt'] if r else 0)(cursor.fetchone())
        
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE status = 'active'")
        stats['active_users'] = (lambda r: r['cnt'] if r else 0)(cursor.fetchone())
        
        # 统计待审核注册
        cursor.execute("SELECT COUNT(*) as cnt FROM registration_applications WHERE status = 'pending'")
        stats['pending_registrations'] = (lambda r: r['cnt'] if r else 0)(cursor.fetchone())
        
        # 统计待审批退票
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM pending_refunds WHERE status = 'pending'
        """)
        stats['pending_refunds'] = (lambda r: r['cnt'] if r else 0)(cursor.fetchone())
        
        # 获取活跃售票员
        cursor.execute("""
            SELECT s.*, u.employee_no, u.name, u.window_no, u.ticket_limit,
                   COUNT(t.ticket_id) as ticket_count,
                   COALESCE(SUM(t.price), 0) as total_amount,
                   MAX(t.created_at) as last_ticket_time
            FROM shifts s
            LEFT JOIN users u ON s.employee_no = u.employee_no
            LEFT JOIN tickets t ON s.shift_id = t.shift_id AND t.status = 'sold'
            WHERE s.status = 'active'
            GROUP BY s.shift_id
        """)
        shifts = cursor.fetchall()
        
        for shift in shifts:
            # 检查是否异常（5分钟内出票超过阈值）
            anomaly = False
            if shift.get('last_ticket_time'):
                try:
                    last_time = datetime.fromisoformat(shift['last_ticket_time'])
                    diff_minutes = (datetime.now() - last_time).total_seconds() / 60
                    if diff_minutes <= 5:
                        # 检查5分钟内的出票数
                        cursor.execute("""
                            SELECT COUNT(*) as cnt FROM tickets
                            WHERE shift_id = ? AND status = 'sold'
                            AND created_at >= ?
                        """, (shift['shift_id'], (datetime.now() - timedelta(minutes=5)).isoformat()))
                        recent_count = (lambda r: r['cnt'] if r else 0)(cursor.fetchone())
                        if recent_count >= config.TICKET_ANOMALY_THRESHOLD:
                            anomaly = True
                except:
                    pass
            
            active_sellers.append({
                'shift_id': shift['shift_id'],
                'employee_no': shift['employee_no'],
                'name': shift.get('name'),
                'window_no': shift.get('window_no') or '未知',
                'shift_type': shift['shift_type'],
                'shift_name': config.SHIFT_TYPES.get(shift['shift_type'], {}).get('name', shift['shift_type']),
                'ticket_count': shift['ticket_count'] or 0,
                'ticket_limit': shift.get('ticket_limit') or config.TICKET_LIMIT_PER_SHIFT,
                'total_amount': shift['total_amount'] or 0,
                'last_ticket_time': shift['last_ticket_time'][:16] if shift.get('last_ticket_time') else None,
                'anomaly': anomaly
            })
        
        # 今日统计
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT t.ticket_id) as total_tickets,
                SUM(t.price) as total_amount
            FROM tickets t
            JOIN shifts s ON t.shift_id = s.shift_id
            WHERE t.status = 'sold' AND DATE(t.created_at) = ?
        """, (today,))
        today_row = cursor.fetchone()
        today_stats['total_tickets'] = (today_row['total_tickets'] or 0) if today_row else 0
        today_stats['total_amount'] = (today_row['total_amount'] or 0) if today_row else 0
        
        cursor.execute("""
            SELECT COUNT(*) as cnt, SUM(actual_refund) as amount
            FROM refunds
            WHERE DATE(created_at) = ?
        """, (today,))
        refund_row = cursor.fetchone()
        today_stats['total_refunds'] = (refund_row['cnt'] or 0) if refund_row else 0
        today_stats['refund_amount'] = (refund_row['amount'] or 0) if refund_row else 0
        today_stats['net_amount'] = (today_stats['total_amount'] or 0) - (today_stats['refund_amount'] or 0)
        
        # 最近操作日志
        cursor.execute("""
            SELECT * FROM operation_logs
            ORDER BY created_at DESC
            LIMIT 10
        """)
        recent_logs = cursor.fetchall()
        
        cursor.close()
        conn.close()
    
    return render_template('admin/dashboard.html',
                           system_name=config.SYSTEM_NAME,
                           system_version=config.SYSTEM_VERSION,
                           stats=stats,
                           active_sellers=active_sellers,
                           recent_logs=recent_logs,
                           today_stats=today_stats,
                           refresh_interval=config.MONITOR_REFRESH_INTERVAL,
                           pending_registrations=stats['pending_registrations'],
                           pending_refunds=stats['pending_refunds'])

@app.route('/admin/registrations')
@admin_required
def admin_registrations():
    """注册审核列表"""
    status_filter = request.args.get('status', 'all')
    search = request.args.get('search', '').strip()
    
    conn = get_db_dict_connection()
    applications = []
    pending_count = 0
    
    if conn:
        cursor = conn.cursor()
        
        query = """
            SELECT id, real_name, id_card, email, station_code, username, window_no,
                   machine_code, created_at, status, reject_reason, reviewed_at
            FROM registration_applications
            WHERE 1=1
        """
        params = []
        
        if status_filter != 'all':
            query += " AND status = ?"
            params.append(status_filter)
        
        if search:
            query += " AND (real_name LIKE ? OR id_card LIKE ? OR email LIKE ? OR username LIKE ?)"
            search_pattern = f'%{search}%'
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        applications = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) as cnt FROM registration_applications WHERE status = 'pending'")
        row = cursor.fetchone()
        pending_count = row['cnt'] if row else 0
        
        cursor.close()
        conn.close()
    
    return render_template('admin/registrations.html',
                           system_name=config.SYSTEM_NAME,
                           applications=applications,
                           status_filter=status_filter,
                           search=search,
                           pending_registrations=pending_count,
                           pending_refunds=0)

@app.route('/admin/refund-approvals')
@admin_required
def admin_refund_approvals():
    """退票审批页面"""
    status_filter = request.args.get('status', 'all')
    
    conn = get_db_dict_connection()
    refunds = []
    
    if conn:
        cursor = conn.cursor()
        
        query = """
            SELECT * FROM pending_refunds
            WHERE 1=1
        """
        params = []
        
        if status_filter != 'all':
            query += " AND status = ?"
            params.append(status_filter)
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        refunds = cursor.fetchall()
        
        cursor.close()
        conn.close()
    
    # 获取待审批数量
    pending_count = 0
    conn2 = get_db_connection()
    if conn2:
        cursor = conn2.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM pending_refunds WHERE status = 'pending'")
        pending_count = (lambda r: r[0] if r else 0)(cursor.fetchone())
        cursor.close()
        conn2.close()
    
    return render_template('admin/refund_approvals.html',
                           system_name=config.SYSTEM_NAME,
                           refunds=refunds,
                           status_filter=status_filter,
                           pending_refunds=pending_count,
                           pending_registrations=0)

@app.route('/admin/logs')
@admin_required
def admin_logs():
    """操作日志页面"""
    employee_no = request.args.get('employee_no', '').strip()
    operation_type = request.args.get('operation_type', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 50
    
    conn = get_db_dict_connection()
    logs = []
    total_logs = 0
    
    if conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM operation_logs WHERE 1=1"
        params = []
        
        if employee_no:
            query += " AND employee_no LIKE ?"
            params.append(f'%{employee_no}%')
        
        if operation_type:
            query += " AND operation_type = ?"
            params.append(operation_type)
        
        if start_date:
            query += " AND DATE(created_at) >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND DATE(created_at) <= ?"
            params.append(end_date)
        
        # 统计总数
        count_query = query.replace('SELECT *', 'SELECT COUNT(*) as cnt')
        cursor.execute(count_query, params)
        total_logs = (lambda r: r['cnt'] if r else 0)(cursor.fetchone())
        
        # 分页查询
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor.execute(query, params)
        logs = cursor.fetchall()
        
        cursor.close()
        conn.close()
    
    total_pages = (total_logs + per_page - 1) // per_page
    
    # 构建查询字符串
    query_params = []
    if employee_no: query_params.append(f'employee_no={employee_no}')
    if operation_type: query_params.append(f'operation_type={operation_type}')
    if start_date: query_params.append(f'start_date={start_date}')
    if end_date: query_params.append(f'end_date={end_date}')
    query_string = '&'.join(query_params)
    
    return render_template('admin/logs.html',
                           system_name=config.SYSTEM_NAME,
                           logs=logs,
                           filters={
                               'employee_no': employee_no,
                               'operation_type': operation_type,
                               'start_date': start_date,
                               'end_date': end_date
                           },
                           page=page,
                           per_page=per_page,
                           total_pages=total_pages,
                           total_logs=total_logs,
                           query_string=query_string,
                           pending_registrations=0,
                           pending_refunds=0)

@app.route('/admin/daily-reports')
@admin_required
def admin_daily_reports():
    """对账单列表页面"""
    employee_no = request.args.get('employee_no', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    shift_type = request.args.get('shift_type', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 20
    
    conn = get_db_dict_connection()
    reports = []
    summary = {
        'total_shifts': 0,
        'total_tickets': 0,
        'total_refunds': 0,
        'total_amount': 0,
        'refund_amount': 0,
        'net_amount': 0
    }
    
    if conn:
        cursor = conn.cursor()
        
        # 查询已关闭的班次作为对账单
        query = """
            SELECT s.*, u.employee_no, u.name as user_name, u.window_no
            FROM shifts s
            LEFT JOIN users u ON s.employee_no = u.employee_no
            WHERE s.status = 'closed'
        """
        params = []
        
        if employee_no:
            query += " AND (s.employee_no LIKE ? OR u.employee_no LIKE ?)"
            params.extend([f'%{employee_no}%', f'%{employee_no}%'])
        
        if shift_type:
            query += " AND s.shift_type = ?"
            params.append(shift_type)
        
        # 统计汇总
        count_query = query.replace('SELECT s.*, u.employee_no, u.name as user_name, u.window_no', 
                                     'SELECT COUNT(*) as cnt')
        cursor.execute(count_query, params)
        total_reports = (lambda r: r['cnt'] if r else 0)(cursor.fetchone())
        
        # 汇总统计
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_shifts,
                COALESCE(SUM(total_tickets), 0) as total_tickets,
                COALESCE(SUM(total_refunds), 0) as total_refunds,
                COALESCE(SUM(total_amount), 0) as total_amount,
                COALESCE(SUM(refund_amount), 0) as refund_amount
            FROM shifts WHERE status = 'closed'
        """)
        sum_row = cursor.fetchone()
        summary['total_shifts'] = sum_row['total_shifts'] if sum_row else 0
        summary['total_tickets'] = sum_row['total_tickets'] if sum_row else 0
        summary['total_refunds'] = sum_row['total_refunds'] if sum_row else 0
        summary['total_amount'] = sum_row['total_amount'] if sum_row else 0
        summary['refund_amount'] = sum_row['refund_amount'] if sum_row else 0
        summary['net_amount'] = summary['total_amount'] - summary['refund_amount']
        
        # 分页查询
        query += " ORDER BY s.start_time DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor.execute(query, params)
        reports = cursor.fetchall()
        
        # 处理日期显示
        for report in reports:
            if report.get('start_time'):
                report['report_date'] = report['start_time'][:10]
            else:
                report['report_date'] = '-'
        
        cursor.close()
        conn.close()
    
    total_pages = (total_reports + per_page - 1) // per_page if 'total_reports' in locals() else 1
    
    query_params = []
    if employee_no: query_params.append(f'employee_no={employee_no}')
    if start_date: query_params.append(f'start_date={start_date}')
    if end_date: query_params.append(f'end_date={end_date}')
    if shift_type: query_params.append(f'shift_type={shift_type}')
    query_string = '&'.join(query_params)
    
    return render_template('admin/daily_reports.html',
                           system_name=config.SYSTEM_NAME,
                           reports=reports,
                           summary=summary,
                           filters={
                               'employee_no': employee_no,
                               'start_date': start_date,
                               'end_date': end_date,
                               'shift_type': shift_type
                           },
                           page=page,
                           per_page=per_page,
                           total_pages=total_pages,
                           total_reports=len(reports),
                           query_string=query_string,
                           pending_registrations=0,
                           pending_refunds=0)

@app.route('/admin/income-stats')
@admin_required
def admin_income_stats():
    """收入统计页面"""
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    group_by = request.args.get('group_by', 'daily')
    
    conn = get_db_dict_connection()
    stats = []
    summary = {
        'total_tickets': 0,
        'total_refunds': 0,
        'total_amount': 0,
        'refund_amount': 0,
        'net_amount': 0,
        'cash_amount': 0,
        'electronic_amount': 0
    }
    chart_labels = []
    chart_ticket_data = []
    chart_amount_data = []
    chart_refund_data = []
    
    if conn:
        cursor = conn.cursor()
        
        # 根据分组方式查询
        if group_by == 'daily':
            cursor.execute("""
                SELECT DATE(t.created_at) as period,
                       COUNT(DISTINCT t.ticket_id) as total_tickets,
                       SUM(t.price) as total_amount,
                       0 as total_refunds,
                       0 as refund_amount,
                       SUM(t.price) as net_amount
                FROM tickets t
                WHERE t.status = 'sold' AND DATE(t.created_at) BETWEEN ? AND ?
                GROUP BY DATE(t.created_at)
                ORDER BY period
            """, (start_date, end_date))
            stats = cursor.fetchall()
            chart_labels = [s['period'] for s in stats]
            chart_ticket_data = [s['total_tickets'] for s in stats]
            chart_amount_data = [float(s['total_amount'] or 0) for s in stats]
            chart_refund_data = [0] * len(stats)
            
        elif group_by == 'monthly':
            cursor.execute("""
                SELECT STRFTIME('%Y-%m', t.created_at) as period,
                       COUNT(DISTINCT t.ticket_id) as total_tickets,
                       SUM(t.price) as total_amount
                FROM tickets t
                WHERE t.status = 'sold'
                GROUP BY STRFTIME('%Y-%m', t.created_at)
                ORDER BY period
            """)
            stats = cursor.fetchall()
            chart_labels = [s['period'] for s in stats]
            chart_ticket_data = [s['total_tickets'] for s in stats]
            chart_amount_data = [float(s['total_amount'] or 0) for s in stats]
            chart_refund_data = [0] * len(stats)
            
        elif group_by == 'seller':
            cursor.execute("""
                SELECT s.employee_no, u.name,
                       COUNT(DISTINCT t.ticket_id) as total_tickets,
                       SUM(t.price) as total_amount
                FROM shifts s
                LEFT JOIN tickets t ON s.shift_id = t.shift_id AND t.status = 'sold'
                LEFT JOIN users u ON s.employee_no = u.employee_no
                GROUP BY s.employee_no
                ORDER BY total_amount DESC
            """)
            stats = cursor.fetchall()
            chart_labels = [s['employee_no'] for s in stats]
            chart_ticket_data = [s['total_tickets'] for s in stats]
            chart_amount_data = [float(s['total_amount'] or 0) for s in stats]
            chart_refund_data = [0] * len(stats)
            
        elif group_by == 'seat_type':
            cursor.execute("""
                SELECT seat_type,
                       COUNT(*) as total_tickets,
                       SUM(price) as total_amount
                FROM tickets
                WHERE status = 'sold'
                GROUP BY seat_type
                ORDER BY total_amount DESC
            """)
            stats = cursor.fetchall()
            chart_labels = [s['seat_type'] for s in stats]
            chart_ticket_data = [s['total_tickets'] for s in stats]
            chart_amount_data = [float(s['total_amount'] or 0) for s in stats]
            chart_refund_data = [0] * len(stats)
        
        # 汇总统计
        cursor.execute("""
            SELECT 
                COUNT(*) as total_tickets,
                SUM(price) as total_amount
            FROM tickets
            WHERE status = 'sold'
        """)
        sum_row = cursor.fetchone()
        summary['total_tickets'] = sum_row['total_tickets'] if sum_row else 0
        summary['total_amount'] = float(sum_row['total_amount'] or 0)
        summary['net_amount'] = summary['total_amount'] - summary['refund_amount']
        
        cursor.close()
        conn.close()
    
    return render_template('admin/income_stats.html',
                           system_name=config.SYSTEM_NAME,
                           stats=stats,
                           summary=summary,
                           filters={
                               'start_date': start_date,
                               'end_date': end_date,
                               'group_by': group_by
                           },
                           chart_labels=json.dumps(chart_labels),
                           chart_ticket_data=json.dumps(chart_ticket_data),
                           chart_amount_data=json.dumps(chart_amount_data),
                           chart_refund_data=json.dumps(chart_refund_data),
                           pending_registrations=0,
                           pending_refunds=0)

@app.route('/admin/users')
@admin_required
def admin_users():
    """用户管理页面"""
    search = request.args.get('search', '').strip()
    role = request.args.get('role', '').strip()
    status = request.args.get('status', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 20
    
    conn = get_db_dict_connection()
    users = []
    
    if conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM users WHERE 1=1"
        params = []
        
        if search:
            query += " AND (employee_no LIKE ? OR name LIKE ?)"
            params.extend([f'%{search}%', f'%{search}%'])
        
        if role:
            query += " AND role = ?"
            params.append(role)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        # 统计总数
        count_query = query.replace('SELECT *', 'SELECT COUNT(*) as cnt')
        cursor.execute(count_query, params)
        total_users = (lambda r: r['cnt'] if r else 0)(cursor.fetchone())
        
        # 分页查询
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor.execute(query, params)
        users = cursor.fetchall()
        
        # 获取待审核数量
        cursor.execute("SELECT COUNT(*) as cnt FROM registration_applications WHERE status = 'pending'")
        pending_count = (lambda r: r['cnt'] if r else 0)(cursor.fetchone())
        
        cursor.close()
        conn.close()
    else:
        pending_count = 0
        total_users = 0
    
    total_pages = (total_users + per_page - 1) // per_page if total_users else 1
    
    query_params = []
    if search: query_params.append(f'search={search}')
    if role: query_params.append(f'role={role}')
    if status: query_params.append(f'status={status}')
    query_string = '&'.join(query_params)
    
    return render_template('admin/users.html',
                           system_name=config.SYSTEM_NAME,
                           users=users,
                           filters={
                               'search': search,
                               'role': role,
                               'status': status
                           },
                           page=page,
                           per_page=per_page,
                           total_pages=total_pages,
                           total_users=total_users,
                           pending_count=pending_count,
                           query_string=query_string,
                           pending_registrations=pending_count,
                           pending_refunds=0)

@app.route('/admin/ticket-limits')
@admin_required
def admin_ticket_limits():
    """票额限售管理页面"""
    conn = get_db_dict_connection()
    sellers = []
    
    # 获取默认配置
    cursor = conn.cursor() if conn else None
    default_limit = config.TICKET_LIMIT_PER_SHIFT
    warning_ratio = config.TICKET_WARNING_RATIO
    
    cursor.execute("SELECT value FROM system_settings WHERE key = 'ticket_limit_per_shift'")
    setting = cursor.fetchone()
    if setting:
        default_limit = int(setting['value'])
    
    cursor.execute("SELECT value FROM system_settings WHERE key = 'ticket_warning_ratio'")
    setting = cursor.fetchone()
    if setting:
        warning_ratio = float(setting['value'])
    
    # 获取所有售票员及其当前班次状态
    cursor.execute("""
        SELECT u.user_id, u.employee_no, u.name, u.station_code,
               u.window_no, u.ticket_limit, u.role,
               s.shift_id as current_shift, s.shift_type
        FROM users u
        LEFT JOIN shifts s ON u.employee_no = s.employee_no AND s.status = 'active'
        WHERE u.role != 'admin' OR u.role IS NULL
    """)
    rows = cursor.fetchall()
    
    for row in rows:
        ticket_count = 0
        if row.get('current_shift'):
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM tickets
                WHERE shift_id = ? AND status = 'sold'
            """, (row['current_shift'],))
            count_row = cursor.fetchone()
            ticket_count = count_row['cnt'] if count_row else 0
        
        sellers.append({
            'user_id': row['user_id'],
            'employee_no': row['employee_no'],
            'name': row['name'],
            'station_code': row['station_code'],
            'window_no': row['window_no'],
            'ticket_limit': row['ticket_limit'] or default_limit,
            'current_shift': row.get('current_shift'),
            'shift_type': row['shift_type'],
            'shift_name': config.SHIFT_TYPES.get(row['shift_type'], {}).get('name', '-') if row['shift_type'] else None,
            'current_tickets': ticket_count
        })
    
    cursor.close()
    conn.close()
    
    return render_template('admin/ticket_limits.html',
                           system_name=config.SYSTEM_NAME,
                           sellers=sellers,
                           default_limit=default_limit,
                           warning_ratio=warning_ratio,
                           pending_registrations=0,
                           pending_refunds=0)

@app.route('/admin/settings')
@admin_required
def admin_settings():
    """系统设置页面"""
    conn = get_db_connection()
    settings = {
        'refund_approval_threshold': config.REFUND_APPROVAL_THRESHOLD,
        'ticket_limit_per_shift': config.TICKET_LIMIT_PER_SHIFT,
        'ticket_warning_ratio': config.TICKET_WARNING_RATIO,
        'ticket_anomaly_threshold': config.TICKET_ANOMALY_THRESHOLD,
        'monitor_refresh_interval': config.MONITOR_REFRESH_INTERVAL,
        'log_retention_days': 90
    }
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM system_settings")
        for row in cursor.fetchall():
            key = row[0]
            value = row[1]
            if key in settings:
                if key in ['refund_approval_threshold', 'ticket_limit_per_shift', 'ticket_anomaly_threshold', 'monitor_refresh_interval', 'log_retention_days']:
                    settings[key] = int(value)
                elif key in ['ticket_warning_ratio']:
                    settings[key] = float(value)
        cursor.close()
        conn.close()
    
    return render_template('admin/settings.html',
                           system_name=config.SYSTEM_NAME,
                           system_version=config.SYSTEM_VERSION,
                           settings=settings,
                           pending_registrations=0,
                           pending_refunds=0)

# ==================== 注册审核 & 风控 API ====================

@app.route('/admin/risk')
@admin_required
def admin_risk():
    """风控管理页面"""
    conn = get_db_dict_connection()
    records = []
    pending_count = 0
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rc.*, u.name, u.employee_no
            FROM risk_controls rc
            LEFT JOIN users u ON rc.user_id = u.user_id
            ORDER BY rc.created_at DESC
            LIMIT 100
        """)
        records = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) as cnt FROM registration_applications WHERE status = 'pending'")
        row = cursor.fetchone()
        pending_count = row['cnt'] if row else 0
        
        cursor.close()
        conn.close()
    
    return render_template('admin/risk.html',
                           system_name=config.SYSTEM_NAME,
                           records=records,
                           pending_registrations=pending_count,
                           pending_refunds=0)


@app.route('/admin/api/approve-application', methods=['POST'])
@admin_required
def api_approve_application():
    """审核通过注册申请"""
    data = request.get_json()
    application_id = data.get('id')
    
    if not application_id:
        return jsonify({'status': 'error', 'message': '缺少申请ID'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT real_name, id_card, email, station_code, username, window_no, 
               password_hash, machine_code
        FROM registration_applications
        WHERE id = ? AND status = 'pending'
    """, (application_id,))
    app = cursor.fetchone()
    
    if not app:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '申请不存在或已审核'})
    
    try:
        cursor.execute("""
            INSERT INTO users 
            (employee_no, name, password_hash, id_card, email, role, station_code, 
             window_no, machine_code, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'seller', ?, ?, ?, 'active', ?)
        """, (
            app['username'], app['real_name'], app['password_hash'], app['id_card'],
            app['email'], app['station_code'], app['window_no'], app['machine_code'],
            datetime.now().isoformat()
        ))
        
        user_id = cursor.lastrowid
        
        cursor.execute("""
            UPDATE registration_applications
            SET status = 'approved', reviewed_at = ?, reviewed_by = 0
            WHERE id = ?
        """, (datetime.now().isoformat(), application_id))
        
        cursor.execute("""
            INSERT OR REPLACE INTO machine_bindings (user_id, machine_code, bound_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, app['machine_code'], datetime.now().isoformat(), datetime.now().isoformat()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': '申请已通过，用户已创建'})
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': f'操作失败: {str(e)}'})


@app.route('/admin/api/reject-application', methods=['POST'])
@admin_required
def api_reject_application():
    """拒绝注册申请"""
    data = request.get_json()
    application_id = data.get('id')
    reason = data.get('reason', '').strip()
    
    if not application_id:
        return jsonify({'status': 'error', 'message': '缺少申请ID'})
    
    if not reason:
        return jsonify({'status': 'error', 'message': '请输入拒绝原因'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE registration_applications
            SET status = 'rejected', reject_reason = ?, reviewed_at = ?, reviewed_by = 0
            WHERE id = ? AND status = 'pending'
        """, (reason, datetime.now().isoformat(), application_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': '申请已拒绝'})
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': f'操作失败: {str(e)}'})


@app.route('/admin/api/freeze-user', methods=['POST'])
@admin_required
def api_freeze_user():
    """冻结用户"""
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'error', 'message': '缺少用户ID'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status = 'frozen' WHERE user_id = ?", (user_id,))
        
        cursor.execute("""
            INSERT INTO risk_controls (user_id, username, original_machine_code, new_machine_code, action, reason, operated_by, created_at)
            SELECT user_id, employee_no, machine_code, '', 'manual_freeze', '管理员手动冻结', 0, ?
            FROM users WHERE user_id = ?
        """, (datetime.now().isoformat(), user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': '用户已冻结'})
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': f'操作失败: {str(e)}'})


@app.route('/admin/api/unfreeze-user', methods=['POST'])
@admin_required
def api_unfreeze_user():
    """解冻用户"""
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'error', 'message': '缺少用户ID'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status = 'active' WHERE user_id = ?", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': '用户已解冻'})
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': f'操作失败: {str(e)}'})


# ==================== 管理端 API 路由 ====================

@app.route('/admin/api/refund/<int:refund_id>/approve', methods=['POST'])
@admin_required
def api_approve_refund(refund_id):
    """审批通过退票"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        
        # 更新退票申请状态
        cursor.execute("""
            UPDATE pending_refunds 
            SET status = 'approved', processed_at = ?, processed_by = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), session['user_id'], refund_id))
        
        # 获取退票信息
        cursor.execute("SELECT * FROM pending_refunds WHERE id = ?", (refund_id,))
        refund = cursor.fetchone()
        
        if refund:
            # 更新原票状态
            cursor.execute("""
                UPDATE tickets SET status = 'refunded' WHERE ticket_id = ?
            """, (refund['ticket_id'],))
            
            # 添加退款记录
            cursor.execute("""
                INSERT INTO refunds (ticket_id, actual_refund, refund_fee, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (refund['ticket_id'], refund['refund_amount'], refund['refund_fee'], refund['reason'], datetime.now().isoformat()))
            
            # 记录操作日志
            cursor.execute("""
                INSERT INTO operation_logs (shift_id, employee_no, operation_type, ticket_id, details, ip_address, created_at)
                VALUES (?, ?, 'refund', ?, ?, ?, ?)
            """, (session.get('shift_id'), session['admin_username'], refund['ticket_id'], 
                  json.dumps({'amount': refund['refund_amount'], 'approved_by': session['admin_username']}),
                  request.remote_addr, datetime.now().isoformat()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': '退票申请已通过'})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/api/refund/<int:refund_id>/reject', methods=['POST'])
@admin_required
def api_reject_refund(refund_id):
    """拒绝退票申请"""
    data = request.get_json()
    reason = data.get('reason', '')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE pending_refunds 
            SET status = 'rejected', processed_at = ?, processed_by = ?, reject_reason = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), session['user_id'], reason, refund_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': '已拒绝退票申请'})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/api/log/<int:log_id>')
@admin_required
def api_get_log(log_id):
    """获取日志详情"""
    conn = get_db_dict_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM operation_logs WHERE log_id = ?", (log_id,))
        log = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if log:
            return jsonify({'status': 'success', 'log': log})
        else:
            return jsonify({'status': 'error', 'message': '日志不存在'})
    except Exception as e:
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/api/report/<int:report_id>')
@admin_required
def api_get_report(report_id):
    """获取对账单详情"""
    conn = get_db_dict_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        
        # 获取班次信息
        cursor.execute("""
            SELECT s.*, u.employee_no, u.name, u.window_no
            FROM shifts s
            LEFT JOIN users u ON s.employee_no = u.employee_no
            WHERE s.shift_id = ?
        """, (report_id,))
        shift = cursor.fetchone()
        
        if not shift:
            cursor.close()
            conn.close()
            return jsonify({'status': 'error', 'message': '对账单不存在'})
        
        # 获取售票记录
        cursor.execute("""
            SELECT * FROM tickets
            WHERE shift_id = ? AND status = 'sold'
        """, (report_id,))
        tickets = cursor.fetchall()
        
        # 获取退票记录
        cursor.execute("""
            SELECT * FROM tickets
            WHERE shift_id = ? AND status = 'refunded'
        """, (report_id,))
        refunds = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # 渲染HTML
        html = render_template('admin/report_detail_partial.html',
                              shift=shift,
                              tickets=tickets,
                              refunds=refunds)
        
        return jsonify({'status': 'success', 'html': html})
    except Exception as e:
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/api/report/<int:report_id>/print')
@admin_required
def api_print_report(report_id):
    """打印对账单"""
    conn = get_db_dict_connection()
    if not conn:
        return "数据库连接失败", 500
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT s.*, u.employee_no, u.name, u.window_no
            FROM shifts s
            LEFT JOIN users u ON s.employee_no = u.employee_no
            WHERE s.shift_id = ?
        """, (report_id,))
        shift = cursor.fetchone()
        
        cursor.execute("SELECT * FROM tickets WHERE shift_id = ? AND status = 'sold'", (report_id,))
        tickets = cursor.fetchall()
        
        cursor.execute("SELECT * FROM tickets WHERE shift_id = ? AND status = 'refunded'", (report_id,))
        refunds = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('admin/report_print.html',
                              shift=shift,
                              tickets=tickets,
                              refunds=refunds,
                              system_name=config.SYSTEM_NAME)
    except Exception as e:
        conn.close()
        return f"获取对账单失败: {str(e)}", 500

@app.route('/admin/api/user/<int:user_id>')
@admin_required
def api_get_user(user_id):
    """获取用户详情"""
    conn = get_db_dict_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            return jsonify({'status': 'success', 'user': user})
        else:
            return jsonify({'status': 'error', 'message': '用户不存在'})
    except Exception as e:
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/api/user/<int:user_id>/ticket_limit', methods=['POST'])
@admin_required
def api_update_ticket_limit(user_id):
    """更新用户票额限制"""
    data = request.get_json()
    ticket_limit = data.get('ticket_limit')
    
    if not ticket_limit:
        return jsonify({'status': 'error', 'message': '票额限制不能为空'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET ticket_limit = ? WHERE user_id = ?", (ticket_limit, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': '票额限制已更新'})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/api/user/<int:user_id>/status', methods=['POST'])
@admin_required
def api_update_user_status(user_id):
    """更新用户状态"""
    data = request.get_json()
    status = data.get('status')
    
    if not status:
        return jsonify({'status': 'error', 'message': '状态不能为空'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': f'用户状态已更新为{status}'})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/api/settings', methods=['POST'])
@admin_required
def api_update_settings():
    """更新系统设置"""
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        
        for key, value in data.items():
            if key in ['refund_approval_threshold', 'ticket_limit_per_shift', 'ticket_warning_ratio', 
                      'ticket_anomaly_threshold', 'monitor_refresh_interval']:
                cursor.execute("""
                    INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                """, (key, str(value), datetime.now().isoformat()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': '设置已保存'})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/api/logs/cleanup', methods=['POST'])
@admin_required
def api_cleanup_logs():
    """清理过期日志"""
    days = int(request.args.get('days', 90))
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM operation_logs WHERE DATE(created_at) < ?", (cutoff_date,))
        deleted = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'deleted': deleted, 'message': f'已清理{deleted}条过期日志'})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/api/logs/export')
@admin_required
def api_export_logs():
    """导出日志"""
    ids = request.args.getlist('ids')
    
    conn = get_db_dict_connection()
    if not conn:
        return "数据库连接失败", 500
    
    try:
        if ids:
            placeholders = ','.join(['?'] * len(ids))
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM operation_logs WHERE log_id IN ({placeholders}) ORDER BY created_at DESC", ids)
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT 1000")
        
        logs = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # 生成CSV
        csv_content = "ID,时间,工号,操作类型,票号,详情,IP地址\n"
        for log in logs:
            csv_content += f"{log['log_id']},{log['created_at']},{log['employee_no']},{log['operation_type']},{log['ticket_id'] or ''},{log['details'] or ''},{log['ip_address'] or ''}\n"
        
        from flask import Response
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=operation_logs.csv'}
        )
    except Exception as e:
        conn.close()
        return f"导出失败: {str(e)}", 500

# ==================== 数据修复 API ====================

@app.route('/admin/api/fill-seats', methods=['POST'])
@admin_required
def api_fill_seats():
    """一键填充默认票额"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 车型默认票额配置
        seat_defaults = {
            'G': {'seat_business': 20, 'seat_first': 50, 'seat_second': 500},
            'D': {'seat_first': 60, 'seat_second': 600},
            'C': {'seat_first': 40, 'seat_second': 400},
            'Z': {'seat_soft_sleeper': 30, 'seat_hard_sleeper': 200, 'seat_hard': 500},
            'T': {'seat_soft_sleeper': 20, 'seat_hard_sleeper': 150, 'seat_hard': 400},
            'K': {'seat_soft_sleeper': 15, 'seat_hard_sleeper': 100, 'seat_hard': 300},
        }
        
        cursor.execute("SELECT train_id, train_number, train_type FROM trains")
        trains = cursor.fetchall()
        train_count = len(trains)
        updated_count = 0
        
        for train_id, train_number, train_type in trains:
            defaults = seat_defaults.get(train_type, seat_defaults.get(train_number[0] if train_number else 'K', {}))
            if not defaults:
                defaults = {'seat_hard': 200}
            
            # 检查是否需要更新
            cursor.execute("""
                SELECT COUNT(*) FROM train_stops 
                WHERE train_id = ? AND (seat_business > 0 OR seat_first > 0 OR seat_second > 0 
                    OR seat_soft > 0 OR seat_hard > 0 OR seat_soft_sleeper > 0 OR seat_hard_sleeper > 0)
            """, (train_id,))
            has_seats = cursor.fetchone()[0]
            
            if has_seats == 0:
                for seat_field, seat_count in defaults.items():
                    cursor.execute(f"""
                        UPDATE train_stops SET {seat_field} = ?
                        WHERE train_id = ? AND ({seat_field} IS NULL OR {seat_field} = 0)
                    """, (seat_count, train_id))
                updated_count += 1
        
        conn.commit()
        
        # 记录日志
        log_operation('admin_fill_seats', details={'train_count': train_count, 'updated_count': updated_count})
        
        return jsonify({
            'status': 'success',
            'train_count': train_count,
            'updated_count': updated_count,
            'message': f'处理 {train_count} 个车次，填充 {updated_count} 个车次的座席'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/api/fill-running-days', methods=['POST'])
@admin_required
def api_fill_running_days():
    """填充开行日期"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE trains SET running_days = '1234567' 
            WHERE running_days IS NULL OR running_days = ''
        """)
        count = cursor.rowcount
        conn.commit()
        
        # 记录日志
        log_operation('admin_fill_days', details={'count': count})
        
        return jsonify({
            'status': 'success',
            'count': count,
            'message': f'已为 {count} 个车次设置每日开行'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/api/create-test-users', methods=['POST'])
@admin_required
def api_create_test_users():
    """创建多站测试账号"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    test_users = [
        ('seller003', '上海站售票员', 'SHH', '201号口'),
        ('seller004', '北京站售票员', 'BJP', '301号口'),
        ('seller005', '广州站售票员', 'GZQ', '401号口'),
        ('seller006', '武汉站售票员', 'WHN', '501号口'),
    ]
    
    try:
        created = 0
        users_info = []
        
        for emp_no, name, station_code, window_no in test_users:
            cursor.execute("SELECT user_id FROM users WHERE employee_no = ?", (emp_no,))
            if cursor.fetchone():
                continue
            
            password_hash = generate_password_hash('123456')
            cursor.execute("""
                INSERT INTO users (employee_no, password_hash, name, role, window_no, station_code, status, ticket_limit)
                VALUES (?, ?, ?, 'seller', ?, ?, 'active', 200)
            """, (emp_no, password_hash, name, window_no, station_code))
            created += 1
            users_info.append(f'{emp_no}/123456 ({name})')
        
        conn.commit()
        
        # 记录日志
        log_operation('admin_create_users', details={'created': created})
        
        return jsonify({
            'status': 'success',
            'created': created,
            'users': users_info,
            'message': f'成功创建 {created} 个测试账号'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


# ==================== 售票端路由 ====================

@app.route('/shift_select', methods=['GET', 'POST'])
@login_required
def shift_select():
    """班次选择页面"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 管理员不能进入售票端
    if session.get('user_role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        shift_type = request.form.get('shift_type', 'day')
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO shifts (employee_no, shift_type, start_time, status, created_at)
                    VALUES (?, ?, ?, 'active', ?)
                """, (session['employee_no'], shift_type, datetime.now().isoformat(), datetime.now().isoformat()))
                shift_id = cursor.lastrowid
                conn.commit()
                cursor.close()
                conn.close()
                
                session['shift_id'] = shift_id
                session['shift_type'] = shift_type
                session['shift_name'] = config.SHIFT_TYPES[shift_type]['name']
                
                log_operation('shift_open', details={'shift_type': shift_type})
                
                return redirect(url_for('main'))
            except Exception as e:
                print(f"创建班次失败: {e}")
                if conn:
                    conn.rollback()
                    conn.close()
    
    current_hour = datetime.now().hour
    default_shift = 'night' if 12 <= current_hour < 24 else 'day'
    
    return render_template('shift_select.html', 
                           default_shift=default_shift,
                           shift_types=config.SHIFT_TYPES,
                           system_name=config.SYSTEM_NAME)

@app.route('/main')
@login_required
def main():
    """主页面"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 检查票额限售
    if 'shift_id' in session:
        can_sell, limit, current = check_ticket_limit(session['user_id'], session['shift_id'])
        if not can_sell:
            flash('您已达到本班次票额上限，请结班', 'warning')
    
    return render_template('index.html', 
                           system_name=config.SYSTEM_NAME,
                           version=config.SYSTEM_VERSION)

@app.route('/sell', methods=['GET', 'POST'])
@login_required
def sell():
    """售票页面"""
    if request.method == 'POST':
        train_no = request.form.get('train_no', '').strip()
        date = request.form.get('date', '')
        from_station = request.form.get('from_station', '').strip()
        to_station = request.form.get('to_station', '').strip()
        seat_type = request.form.get('seat_type', '')
        
        if not all([train_no, date, from_station, to_station, seat_type]):
            return render_template('sell.html', 
                                   error='请填写完整信息',
                                   system_name=config.SYSTEM_NAME)
        
        return render_template('sell.html',
                               success='售票功能开发中',
                               system_name=config.SYSTEM_NAME)
    
    return render_template('sell.html', system_name=config.SYSTEM_NAME)

@app.route('/query')
@login_required
def query():
    """查询页面"""
    return render_template('query.html', system_name=config.SYSTEM_NAME)

@app.route('/refund')
@login_required
def refund():
    """退票页面"""
    return render_template('refund.html', system_name=config.SYSTEM_NAME)

@app.route('/close_shift', methods=['POST'])
@login_required
def close_shift():
    """关闭班次"""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # 统计本班次数据
            cursor.execute("""
                SELECT COUNT(*) as cnt, SUM(price) as amount
                FROM tickets WHERE shift_id = ? AND status = 'sold'
            """, (session['shift_id'],))
            ticket_stats = cursor.fetchone()
            
            cursor.execute("""
                SELECT COUNT(*) as cnt, SUM(actual_refund) as amount
                FROM refunds WHERE shift_id = ?
            """, (session['shift_id'],))
            refund_stats = cursor.fetchone()
            
            # 更新班次记录
            cursor.execute("""
                UPDATE shifts SET 
                    status = 'closed', 
                    end_time = ?,
                    total_tickets = ?,
                    total_amount = ?,
                    total_refunds = ?,
                    actual_refund = ?
                WHERE shift_id = ?
            """, (
                datetime.now().isoformat(),
                ticket_stats[0] or 0,
                ticket_stats[1] or 0,
                refund_stats[0] or 0,
                refund_stats[1] or 0,
                session['shift_id']
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            log_operation('shift_close')
            
            session.pop('shift_id', None)
            session.pop('shift_type', None)
            session.pop('shift_name', None)
            
            flash('班次已关闭', 'info')
        except Exception as e:
            print(f"关闭班次失败: {e}")
            flash('关闭班次失败', 'error')
    
    return redirect(url_for('shift_select'))

# ==================== API 路由 ====================

@app.route('/api/stations')
def api_stations():
    """获取车站列表"""
    query = request.args.get('q', '').strip()
    stations = search_stations(query)
    return jsonify({'status': 'success', 'data': stations})

@app.route('/api/captcha')
def api_captcha():
    """获取新的验证码图片"""
    captcha_code, captcha_image = generate_captcha()
    session['captcha_code'] = captcha_code.lower()
    return jsonify({'code': captcha_code, 'image': captcha_image})

@app.route('/api/search-stations')
@login_required
def api_search_stations():
    """搜索车站（支持拼音首字母）"""
    query = request.args.get('q', '').strip()
    if not query or len(query) < 1:
        return jsonify({'status': 'success', 'data': []})
    
    stations = search_stations(query)
    return jsonify({'status': 'success', 'data': stations})

@app.route('/api/train-detail')
@login_required
def api_train_detail():
    """获取车次详情（经停站、票价）"""
    train_number = request.args.get('train_id', '').strip()
    from_code = request.args.get('from', '').strip()
    to_code = request.args.get('to', '').strip()
    
    if not train_number:
        return jsonify({'status': 'error', 'message': '请提供车次号'})
    
    conn = get_db_dict_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        
        # 获取车次基本信息（支持train_id数字或train_number字符串）
        train_param = request.args.get('train_id', '').strip()
        if train_param.isdigit():
            cursor.execute("""
                SELECT train_id, train_number, train_type, start_station, end_station, start_time, end_time
                FROM trains WHERE train_id = ?
            """, (int(train_param),))
        else:
            cursor.execute("""
                SELECT train_id, train_number, train_type, start_station, end_station, start_time, end_time
                FROM trains WHERE train_number = ?
            """, (train_param,))
        train = cursor.fetchone()
        if not train:
            cursor.close()
            conn.close()
            return jsonify({'status': 'error', 'message': '未找到该车次'})
        
        # 获取经停站（train_stops用train_id关联，需要JOIN stations获取站名）
        cursor.execute("""
            SELECT ts.stop_sequence, ts.station_code, s.station_name, 
                   ts.arrival_time, ts.departure_time, ts.distance_from_start,
                   ts.seat_business, ts.seat_first, ts.seat_second, 
                   ts.seat_soft, ts.seat_hard, ts.seat_soft_sleeper, ts.seat_hard_sleeper
            FROM train_stops ts 
            LEFT JOIN stations s ON ts.station_code = s.station_code
            WHERE ts.train_id = ?
            ORDER BY ts.stop_sequence
        """, (train['train_id'],))
        stops = []
        for s in cursor.fetchall():
            stop = dict(s)
            stops.append(stop)
        
        # 获取票价（ticket_prices是全局的，按from_station/to_station）
        prices = {}
        if from_code and to_code:
            cursor.execute("""
                SELECT seat_type, base_price FROM ticket_prices
                WHERE from_station = ? AND to_station = ?
            """, (from_code, to_code))
            price_rows = cursor.fetchall()
            for p in price_rows:
                prices[p['seat_type']] = round(p['base_price'], 2) if p['base_price'] else 0
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'data': {
                'train_id': train['train_id'],
                'train_number': train['train_number'],
                'train_type': train['train_type'],
                'start_station': train['start_station'],
                'end_station': train['end_station'],
                'start_time': train['start_time'],
                'end_time': train['end_time'],
                'stops': stops,
                'prices': prices
            }
        })
    except Exception as e:
        print(f"获取车次详情失败: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.close()
        return jsonify({'status': 'error', 'message': '获取车次详情失败'})

@app.route('/api/search-trains')
@login_required
def api_search_trains():
    """搜索车次（支持车次号和拼音首字母）"""
    query = request.args.get('q', '').strip().upper()
    from_station = request.args.get('from', '').strip()
    to_station = request.args.get('to', '').strip()
    
    conn = get_db_dict_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        
        if query:
            # 按车次号搜索
            cursor.execute("""
                SELECT train_id, train_number, train_type, start_station, end_station, start_time, end_time
                FROM trains
                WHERE train_number LIKE ? OR train_number LIKE ?
                ORDER BY 
                    CASE WHEN train_number = ? THEN 0
                         WHEN train_number LIKE ? THEN 1
                         ELSE 2 END,
                    train_number
                LIMIT 20
            """, (f'{query}%', f'%{query}%', query, f'{query}%'))
            trains = [dict(t) for t in cursor.fetchall()]
        elif from_station and to_station:
            # 按发到站搜索（train_stops用train_id关联）
            cursor.execute("""
                SELECT DISTINCT t.train_id, t.train_number, t.train_type, t.start_station, t.end_station, t.start_time, t.end_time
                FROM trains t
                JOIN train_stops ts1 ON t.train_id = ts1.train_id AND ts1.station_code = ?
                JOIN train_stops ts2 ON t.train_id = ts2.train_id AND ts2.station_code = ?
                WHERE ts1.stop_sequence < ts2.stop_sequence
                ORDER BY t.train_number
                LIMIT 30
            """, (from_station, to_station))
            trains = [dict(t) for t in cursor.fetchall()]
        else:
            trains = []
        
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'data': trains})
    except Exception as e:
        print(f"搜索车次失败: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.close()
        return jsonify({'status': 'error', 'message': '搜索车次失败'})

@app.route('/api/ticket-limit')
@login_required
def api_ticket_limit():
    """检查票额限售"""
    if 'shift_id' not in session:
        return jsonify({'status': 'error', 'message': '请先选择班次'})
    
    can_sell, limit, current = check_ticket_limit(session['user_id'], session['shift_id'])
    
    return jsonify({
        'status': 'success',
        'can_sell': can_sell,
        'limit': limit,
        'current': current,
        'remaining': limit - current,
        'warning_ratio': config.TICKET_WARNING_RATIO
    })

@app.route('/daily_report')
@login_required
def daily_report():
    """售票员每日对账单"""
    if 'shift_id' not in session:
        return redirect(url_for('shift_select'))
    
    conn = get_db_dict_connection()
    if not conn:
        return render_template('error.html', error='数据库连接失败', system_name=config.SYSTEM_NAME)
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM shifts WHERE shift_id = ?", (session['shift_id'],))
        shift = cursor.fetchone()
        
        if not shift:
            return render_template('error.html', error='班次不存在', system_name=config.SYSTEM_NAME)
        
        cursor.execute("""
            SELECT * FROM tickets 
            WHERE shift_id = ? AND status = 'sold'
            ORDER BY created_at DESC
        """, (session['shift_id'],))
        tickets = cursor.fetchall()
        
        cursor.execute("""
            SELECT * FROM tickets 
            WHERE shift_id = ? AND status = 'refunded'
            ORDER BY created_at DESC
        """, (session['shift_id'],))
        refunds = cursor.fetchall()
        
        total_tickets = len(tickets)
        total_refunds = len(refunds)
        total_amount = sum(float(t.get('price', 0) or 0) for t in tickets)
        refund_amount = sum(float(t.get('refund_fee', 0) or 0) for t in refunds)
        cash_amount = sum(float(t.get('price', 0) or 0) for t in tickets if t.get('payment_method') == 'cash')
        electronic_amount = total_amount - cash_amount
        net_amount = total_amount - refund_amount
        
        seat_stats = {}
        for t in tickets:
            seat_type = t.get('seat_type', 'unknown')
            if seat_type not in seat_stats:
                seat_stats[seat_type] = {'count': 0, 'amount': 0}
            seat_stats[seat_type]['count'] += 1
            seat_stats[seat_type]['amount'] += float(t.get('price', 0) or 0)
        
        report_data = {
            'shift': shift,
            'total_tickets': total_tickets,
            'total_refunds': total_refunds,
            'total_amount': round(total_amount, 2),
            'refund_amount': round(refund_amount, 2),
            'cash_amount': round(cash_amount, 2),
            'electronic_amount': round(electronic_amount, 2),
            'net_amount': round(net_amount, 2),
            'seat_stats': seat_stats,
            'tickets': tickets[:20] if tickets else [],
            'refunds': refunds[:10] if refunds else []
        }
        
        cursor.close()
        conn.close()
        
        return render_template('daily_report.html', report=report_data, system_name=config.SYSTEM_NAME)
    except Exception as e:
        print(f"生成对账单失败: {e}")
        if conn:
            conn.close()
        return render_template('error.html', error=f'生成对账单失败: {str(e)}', system_name=config.SYSTEM_NAME)

# ==================== 旅客副屏路由 ====================

@app.route('/passenger-display')
def passenger_display():
    """旅客副屏（无需登录）"""
    return render_template('passenger_display.html')

# ==================== 售票/退票 API ====================

@app.route('/api/sell-ticket', methods=['POST'])
@login_required
def api_sell_ticket():
    """售票 API"""
    if 'shift_id' not in session:
        return jsonify({'status': 'error', 'message': '请先选择班次'})
    
    train_number = request.form.get('train_number', '').strip()
    train_id = request.form.get('train_id', '').strip()
    date = request.form.get('date', '').strip()
    from_station = request.form.get('from_station', '').strip()
    from_station_name = request.form.get('from_station_name', '').strip()
    to_station = request.form.get('to_station', '').strip()
    to_station_name = request.form.get('to_station_name', '').strip()
    seat_type = request.form.get('seat_type', '').strip()
    ticket_type = request.form.get('ticket_type', 'adult').strip()
    price = float(request.form.get('price', 0))
    payment = float(request.form.get('payment', 0))
    
    if not all([train_number, date, from_station, to_station, seat_type]):
        return jsonify({'status': 'error', 'message': '信息不完整'})
    
    if payment < price:
        return jsonify({'status': 'error', 'message': '收款金额不足'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        
        # 生成票号
        ticket_no = get_next_ticket_id()
        
        # 插入票记录 - 使用实际数据库字段
        cursor.execute("""
            INSERT INTO tickets (
                ticket_id, shift_id, train_number, train_id,
                from_station, to_station,
                travel_date, departure_time,
                seat_type, ticket_type, price,
                passenger_name, id_number,
                status, payment_method, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_no,
            session['shift_id'],
            train_number,
            train_id or None,
            from_station,
            to_station,
            date,
            '',  # departure_time
            seat_type,
            ticket_type,
            price,
            '',  # passenger_name
            '',  # id_number
            'sold',
            'cash' if payment > price else 'electronic',
            datetime.now().isoformat()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # 记录日志
        log_operation('sell', ticket_id=ticket_no, details={
            'train': train_number,
            'from': from_station,
            'to': to_station,
            'seat': seat_type,
            'price': price,
            'payment': payment
        })
        
        return jsonify({
            'status': 'success',
            'message': '出票成功',
            'ticket_no': ticket_no
        })
        
    except Exception as e:
        print(f"售票失败: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({'status': 'error', 'message': f'售票失败: {str(e)}'})

@app.route('/api/query-ticket')
@login_required
def api_query_ticket():
    """查询票信息"""
    # 同时支持 ticket_no 和 ticket_id 参数名
    ticket_no = request.args.get('ticket_no', request.args.get('ticket_id', '')).strip()
    
    if not ticket_no:
        return jsonify({'status': 'error', 'message': '请提供票号'})
    
    conn = get_db_dict_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tickets WHERE ticket_id = ?
        """, (ticket_no,))
        ticket = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not ticket:
            return jsonify({'status': 'error', 'message': '未找到该票'})
        
        return jsonify({'status': 'success', 'data': ticket})
        
    except Exception as e:
        print(f"查询票失败: {e}")
        if conn:
            conn.close()
        return jsonify({'status': 'error', 'message': '查询失败'})

@app.route('/api/process-refund', methods=['POST'])
@login_required
def api_process_refund():
    """处理退票"""
    if 'shift_id' not in session:
        return jsonify({'status': 'error', 'message': '请先选择班次'})
    
    ticket_no = request.form.get('ticket_no', '').strip()
    reason = request.form.get('reason', '').strip()
    refund_fee = float(request.form.get('refund_fee', 0))
    actual_refund = float(request.form.get('actual_refund', 0))
    
    if not ticket_no:
        return jsonify({'status': 'error', 'message': '请提供票号'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        
        # 获取原票信息
        cursor.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_no,))
        ticket = cursor.fetchone()
        
        if not ticket:
            cursor.close()
            conn.close()
            return jsonify({'status': 'error', 'message': '未找到该票'})
        
        if ticket['status'] == 'refunded':
            cursor.close()
            conn.close()
            return jsonify({'status': 'error', 'message': '该票已退过'})
        
        # 更新票状态
        cursor.execute("""
            UPDATE tickets SET status = 'refunded' WHERE ticket_id = ?
        """, (ticket_no,))
        
        # 插入退款记录 - 使用实际数据库字段
        cursor.execute("""
            INSERT INTO refunds (
                ticket_id, shift_id, refund_amount, refund_fee,
                refund_reason, refund_type, refund_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_no,
            session['shift_id'],
            actual_refund,
            refund_fee,
            reason,
            'window',  # refund_type
            datetime.now().isoformat()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # 记录日志
        log_operation('refund', ticket_id=ticket_no, details={
            'original_price': ticket['price'],
            'refund_fee': refund_fee,
            'actual_refund': actual_refund,
            'reason': reason
        })
        
        return jsonify({
            'status': 'success',
            'message': '退票成功',
            'actual_refund': actual_refund
        })
        
    except Exception as e:
        print(f"退票失败: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({'status': 'error', 'message': f'退票失败: {str(e)}'})

# ==================== 全国开行班列管理模块 ====================

@app.route('/admin/trains')
@admin_required
def admin_trains():
    """班列总览"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 统计各车型数量
    cursor.execute('''
        SELECT train_type, COUNT(*) as count 
        FROM trains 
        GROUP BY train_type
    ''')
    type_stats = {row[0]: row[1] for row in cursor.fetchall()}
    
    # 总车次数
    cursor.execute('SELECT COUNT(*) FROM trains')
    total_trains = cursor.fetchone()[0]
    
    # 今日新增（简化判断）
    cursor.execute('SELECT COUNT(*) FROM trains WHERE status = ?', ('active',))
    active_trains = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    return render_template('admin/trains.html',
                         total_trains=total_trains,
                         type_stats=type_stats,
                         active_trains=active_trains)

@app.route('/admin/trains/add', methods=['GET', 'POST'])
@admin_required
def admin_train_add():
    """新增车次"""
    if request.method == 'GET':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT station_code, station_name FROM stations WHERE status = "active" ORDER BY station_name')
        stations = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('admin/train_add.html', stations=stations)
    
    # POST处理
    train_number = request.form.get('train_number', '').strip().upper()
    train_type = request.form.get('train_type', 'G')
    start_station = request.form.get('start_station', '').strip()
    end_station = request.form.get('end_station', '').strip()
    start_time = request.form.get('start_time', '08:00')
    end_time = request.form.get('end_time', '12:00')
    
    if not train_number or not start_station or not end_station:
        flash('请填写完整的车次信息', 'danger')
        return redirect(url_for('admin_train_add'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 计算总里程
        total_distance = 0
        
        # 插入车次
        cursor.execute('''
            INSERT INTO trains (train_number, train_type, start_station, end_station, 
                              start_time, end_time, total_distance, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
        ''', (train_number, train_type, start_station, end_station, start_time, end_time, total_distance))
        
        train_id = cursor.lastrowid
        
        # 处理经停站
        stop_sequences = request.form.getlist('stop_sequence[]')
        station_codes = request.form.getlist('stop_station[]')
        arrival_times = request.form.getlist('arrival_time[]')
        departure_times = request.form.getlist('departure_time[]')
        distances = request.form.getlist('distance[]')
        
        for i, station_code in enumerate(station_codes):
            if not station_code:
                continue
            seq = int(stop_sequences[i]) if i < len(stop_sequences) else i + 1
            arrival = arrival_times[i] if i < len(arrival_times) else ''
            departure = departure_times[i] if i < len(departure_times) else ''
            dist = int(distances[i]) if i < len(distances) and distances[i] else 0
            
            if dist > total_distance:
                total_distance = dist
            
            # 席别数量
            seat_business = int(request.form.get(f'seat_business_{i}', 0) or 0)
            seat_first = int(request.form.get(f'seat_first_{i}', 0) or 0)
            seat_second = int(request.form.get(f'seat_second_{i}', 0) or 0)
            seat_soft = int(request.form.get(f'seat_soft_{i}', 0) or 0)
            seat_hard = int(request.form.get(f'seat_hard_{i}', 0) or 0)
            seat_soft_sleeper = int(request.form.get(f'seat_soft_sleeper_{i}', 0) or 0)
            seat_hard_sleeper = int(request.form.get(f'seat_hard_sleeper_{i}', 0) or 0)
            
            cursor.execute('''
                INSERT INTO train_stops (train_id, station_code, stop_sequence, 
                                        arrival_time, departure_time, distance_from_start,
                                        seat_business, seat_first, seat_second, seat_soft,
                                        seat_hard, seat_soft_sleeper, seat_hard_sleeper)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (train_id, station_code, seq, arrival, departure, dist,
                  seat_business, seat_first, seat_second, seat_soft,
                  seat_hard, seat_soft_sleeper, seat_hard_sleeper))
        
        # 更新总里程
        cursor.execute('UPDATE trains SET total_distance = ? WHERE train_id = ?', (total_distance, train_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash(f'车次 {train_number} 创建成功', 'success')
        return redirect(url_for('admin_train_detail', train_id=train_id))
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        flash(f'创建车次失败: {str(e)}', 'danger')
        return redirect(url_for('admin_train_add'))

@app.route('/admin/trains/<int:train_id>')
@admin_required
def admin_train_detail(train_id):
    """车次详情"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 车次信息
    cursor.execute('SELECT * FROM trains WHERE train_id = ?', (train_id,))
    train = cursor.fetchone()
    
    if not train:
        cursor.close()
        conn.close()
        flash('车次不存在', 'danger')
        return redirect(url_for('admin_trains'))
    
    # 经停站信息
    cursor.execute('''
        SELECT ts.*, s.station_name 
        FROM train_stops ts
        LEFT JOIN stations s ON ts.station_code = s.station_code
        WHERE ts.train_id = ?
        ORDER BY ts.stop_sequence
    ''', (train_id,))
    stops = cursor.fetchall()
    
    # 票价信息
    cursor.execute('''
        SELECT tp.*, fs.station_name as from_name, ts.station_name as to_name
        FROM ticket_prices tp
        LEFT JOIN stations fs ON tp.from_station = fs.station_code
        LEFT JOIN stations ts ON tp.to_station = ts.station_code
        WHERE tp.from_station IN (SELECT station_code FROM train_stops WHERE train_id = ?)
          AND tp.to_station IN (SELECT station_code FROM train_stops WHERE train_id = ?)
        ORDER BY tp.from_station, tp.to_station
    ''', (train_id, train_id))
    prices = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin/train_detail.html', train=train, stops=stops, prices=prices)

@app.route('/admin/trains/<int:train_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_train_edit(train_id):
    """编辑车次"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM trains WHERE train_id = ?', (train_id,))
    train = cursor.fetchone()
    
    if not train:
        cursor.close()
        conn.close()
        flash('车次不存在', 'danger')
        return redirect(url_for('admin_trains'))
    
    if request.method == 'GET':
        cursor.execute('SELECT station_code, station_name FROM stations WHERE status = "active" ORDER BY station_name')
        stations = cursor.fetchall()
        cursor.execute('''
            SELECT ts.*, s.station_name 
            FROM train_stops ts
            LEFT JOIN stations s ON ts.station_code = s.station_code
            WHERE ts.train_id = ?
            ORDER BY ts.stop_sequence
        ''', (train_id,))
        stops = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('admin/train_edit.html', train=train, stations=stations, stops=stops)
    
    # POST处理
    train_number = request.form.get('train_number', '').strip().upper()
    train_type = request.form.get('train_type', 'G')
    start_time = request.form.get('start_time', '08:00')
    end_time = request.form.get('end_time', '12:00')
    
    try:
        cursor.execute('''
            UPDATE trains SET train_number = ?, train_type = ?, 
                            start_time = ?, end_time = ?
            WHERE train_id = ?
        ''', (train_number, train_type, start_time, end_time, train_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f'车次 {train_number} 更新成功', 'success')
        return redirect(url_for('admin_train_detail', train_id=train_id))
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        flash(f'更新失败: {str(e)}', 'danger')
        return redirect(url_for('admin_train_edit', train_id=train_id))

@app.route('/admin/trains/<int:train_id>/toggle-status', methods=['POST'])
@admin_required
def admin_train_toggle_status(train_id):
    """停运/恢复车次"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT train_id, train_number, status FROM trains WHERE train_id = ?', (train_id,))
    train = cursor.fetchone()
    
    if not train:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '车次不存在'})
    
    new_status = 'running' if train['status'] == 'active' else 'active'
    
    cursor.execute('UPDATE trains SET status = ? WHERE train_id = ?', (new_status, train_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'message': f"车次 {train['train_number']} 已{'恢复开行' if new_status == 'active' else '停运'}",
        'new_status': new_status
    })

@app.route('/admin/trains/<int:train_id>/seats', methods=['GET', 'POST'])
@admin_required
def admin_train_seats(train_id):
    """票额管理"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM trains WHERE train_id = ?', (train_id,))
    train = cursor.fetchone()
    
    if not train:
        cursor.close()
        conn.close()
        flash('车次不存在', 'danger')
        return redirect(url_for('admin_trains'))
    
    if request.method == 'POST':
        # 批量更新票额
        stop_ids = request.form.getlist('stop_id[]')
        for stop_id in stop_ids:
            seat_business = int(request.form.get(f'seat_business_{stop_id}', 0) or 0)
            seat_first = int(request.form.get(f'seat_first_{stop_id}', 0) or 0)
            seat_second = int(request.form.get(f'seat_second_{stop_id}', 0) or 0)
            seat_soft = int(request.form.get(f'seat_soft_{stop_id}', 0) or 0)
            seat_hard = int(request.form.get(f'seat_hard_{stop_id}', 0) or 0)
            seat_soft_sleeper = int(request.form.get(f'seat_soft_sleeper_{stop_id}', 0) or 0)
            seat_hard_sleeper = int(request.form.get(f'seat_hard_sleeper_{stop_id}', 0) or 0)
            
            cursor.execute('''
                UPDATE train_stops SET 
                    seat_business = ?, seat_first = ?, seat_second = ?,
                    seat_soft = ?, seat_hard = ?, 
                    seat_soft_sleeper = ?, seat_hard_sleeper = ?
                WHERE stop_id = ?
            ''', (seat_business, seat_first, seat_second, seat_soft, seat_hard,
                  seat_soft_sleeper, seat_hard_sleeper, stop_id))
        
        conn.commit()
        flash('票额设置已保存', 'success')
    
    # 获取经停站信息
    cursor.execute('''
        SELECT ts.*, s.station_name 
        FROM train_stops ts
        LEFT JOIN stations s ON ts.station_code = s.station_code
        WHERE ts.train_id = ?
        ORDER BY ts.stop_sequence
    ''', (train_id,))
    stops = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin/train_seats.html', train=train, stops=stops)

@app.route('/admin/trains/import', methods=['GET', 'POST'])
@admin_required
def admin_train_import():
    """批量导入"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('请选择要上传的文件', 'danger')
            return redirect(url_for('admin_train_import'))
        
        file = request.files['file']
        if file.filename == '':
            flash('请选择要上传的文件', 'danger')
            return redirect(url_for('admin_train_import'))
        
        if not file.filename.endswith('.csv'):
            flash('只支持CSV格式文件', 'danger')
            return redirect(url_for('admin_train_import'))
        
        import csv
        from io import StringIO
        
        content = file.read().decode('utf-8-sig')
        reader = csv.reader(StringIO(content))
        rows = list(reader)
        
        if len(rows) < 2:
            flash('CSV文件格式错误或数据为空', 'danger')
            return redirect(url_for('admin_train_import'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 创建导入记录
        cursor.execute('''
            INSERT INTO import_logs (import_type, filename, total_rows, status, operator)
            VALUES ('train', ?, ?, 'processing', ?)
        ''', (file.filename, len(rows) - 1, session.get('admin_username', 'admin')))
        import_id = cursor.lastrowid
        
        success_count = 0
        fail_count = 0
        skip_count = 0
        errors = []
        
        # 获取站名到站码的映射
        cursor.execute('SELECT station_name, station_code FROM stations')
        station_map = {row[0]: row[1] for row in cursor.fetchall()}
        
        for i, row in enumerate(rows[1:], 1):
            try:
                if len(row) < 6:
                    errors.append(f'第{i+1}行: 数据列数不足')
                    fail_count += 1
                    continue
                
                train_number = row[0].strip().upper()
                train_type = row[1].strip()
                start_station = station_map.get(row[2].strip(), '')
                end_station = station_map.get(row[3].strip(), '')
                start_time = row[4].strip()
                end_time = row[5].strip()
                
                if not start_station or not end_station:
                    errors.append(f'第{i+1}行: 站名无法识别({row[2]}/{row[3]})')
                    fail_count += 1
                    continue
                
                # 检查车次是否存在
                cursor.execute('SELECT train_id FROM trains WHERE train_number = ?', (train_number,))
                existing = cursor.fetchone()
                
                if existing:
                    errors.append(f'第{i+1}行: 车次{train_number}已存在，跳过')
                    skip_count += 1
                    continue
                
                # 插入车次
                cursor.execute('''
                    INSERT INTO trains (train_number, train_type, start_station, end_station,
                                      start_time, end_time, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'active')
                ''', (train_number, train_type, start_station, end_station, start_time, end_time))
                train_id = cursor.lastrowid
                
                success_count += 1
                
            except Exception as e:
                errors.append(f'第{i+1}行: {str(e)}')
                fail_count += 1
        
        # 更新导入记录
        cursor.execute('''
            UPDATE import_logs SET 
                success_count = ?, fail_count = ?, skip_count = ?,
                status = 'completed', error_details = ?
            WHERE id = ?
        ''', (success_count, fail_count, skip_count, json.dumps(errors[:50]), import_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash(f'导入完成: 成功{success_count}条, 失败{fail_count}条, 跳过{skip_count}条', 
              'success' if fail_count == 0 else 'warning')
        return redirect(url_for('admin_train_import'))
    
    return render_template('admin/train_import.html')

@app.route('/admin/trains/import-logs')
@admin_required
def admin_import_logs():
    """导入日志"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM import_logs 
        ORDER BY created_at DESC 
        LIMIT 50
    ''')
    logs = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin/import_logs.html', logs=logs)

@app.route('/admin/trains/sync', methods=['GET', 'POST'])
@admin_required
def admin_train_sync():
    """数据同步"""
    if request.method == 'POST':
        sync_type = request.form.get('sync_type', 'incremental')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 创建同步记录
        cursor.execute('''
            INSERT INTO data_sync_status (sync_type, triggered_by, status)
            VALUES (?, ?, 'running')
        ''', (sync_type, session.get('admin_username', 'admin')))
        sync_id = cursor.lastrowid
        
        try:
            # 统计信息
            cursor.execute('SELECT COUNT(*) FROM trains WHERE status = "active"')
            train_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT station_code) FROM users WHERE role = "seller"')
            station_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM users WHERE role = "seller"')
            seller_count = cursor.fetchone()[0]
            
            # 清空旧缓存
            cursor.execute('DELETE FROM seller_train_cache')
            
            # 根据train_stops生成新的缓存
            cursor.execute('''
                INSERT INTO seller_train_cache (station_code, train_id, train_number, sync_id)
                SELECT DISTINCT ts.station_code, ts.train_id, t.train_number, ?
                FROM train_stops ts
                JOIN trains t ON ts.train_id = t.train_id
                WHERE t.status = 'active'
            ''', (sync_id,))
            
            # 更新同步记录
            cursor.execute('''
                UPDATE data_sync_status SET 
                    train_count = ?, station_count = ?, seller_count = ?,
                    status = 'completed', completed_at = ?
                WHERE sync_id = ?
            ''', (train_count, station_count, seller_count, datetime.now().isoformat(), sync_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            flash(f'数据同步完成: {train_count}个车次已同步到{station_count}个车站', 'success')
            
        except Exception as e:
            cursor.execute('''
                UPDATE data_sync_status SET 
                    status = 'failed',
                    details = ?
                WHERE sync_id = ?
            ''', (str(e), sync_id))
            conn.commit()
            cursor.close()
            conn.close()
            flash(f'同步失败: {str(e)}', 'danger')
        
        return redirect(url_for('admin_train_sync'))
    
    # GET请求
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 最新同步状态
    cursor.execute('''
        SELECT * FROM data_sync_status 
        ORDER BY started_at DESC 
        LIMIT 1
    ''')
    last_sync = cursor.fetchone()
    
    # 同步历史
    cursor.execute('''
        SELECT * FROM data_sync_status 
        ORDER BY started_at DESC 
        LIMIT 20
    ''')
    sync_history = cursor.fetchall()
    
    # 各车站同步状态
    cursor.execute('''
        SELECT stc.station_code, s.station_name, COUNT(*) as train_count, MAX(stc.updated_at) as last_sync
        FROM seller_train_cache stc
        LEFT JOIN stations s ON stc.station_code = s.station_code
        GROUP BY stc.station_code
        ORDER BY s.station_name
    ''')
    station_sync_status = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin/train_sync.html', 
                         last_sync=last_sync,
                         sync_history=sync_history,
                         station_sync_status=station_sync_status)

# ==================== API接口 ====================

@app.route('/admin/api/trains')
@admin_required
def admin_api_trains():
    """车次列表API"""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    search = request.args.get('search', '')
    train_type = request.args.get('type', '')
    status = request.args.get('status', '')
    
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    where_clauses = []
    params = []
    
    if search:
        where_clauses.append('(train_number LIKE ? OR start_station LIKE ? OR end_station LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    
    if train_type:
        where_clauses.append('train_type = ?')
        params.append(train_type)
    
    if status:
        where_clauses.append('status = ?')
        params.append(status)
    
    where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'
    
    # 总数
    cursor.execute(f'SELECT COUNT(*) FROM trains WHERE {where_sql}', params)
    total = cursor.fetchone()[0]
    
    # 数据
    cursor.execute(f'''
        SELECT t.*, 
               ss.station_name as start_name,
               es.station_name as end_name
        FROM trains t
        LEFT JOIN stations ss ON t.start_station = ss.station_code
        LEFT JOIN stations es ON t.end_station = es.station_code
        WHERE {where_sql}
        ORDER BY t.train_number
        LIMIT ? OFFSET ?
    ''', params + [per_page, offset])
    
    trains = [dict(row) for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'data': trains,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    })

@app.route('/admin/api/trains/<int:train_id>')
@admin_required
def admin_api_train(train_id):
    """车次详情API"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT t.*, 
               ss.station_name as start_name,
               es.station_name as end_name
        FROM trains t
        LEFT JOIN stations ss ON t.start_station = ss.station_code
        LEFT JOIN stations es ON t.end_station = es.station_code
        WHERE t.train_id = ?
    ''', (train_id,))
    train = cursor.fetchone()
    
    if not train:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '车次不存在'})
    
    cursor.execute('''
        SELECT ts.*, s.station_name 
        FROM train_stops ts
        LEFT JOIN stations s ON ts.station_code = s.station_code
        WHERE ts.train_id = ?
        ORDER BY ts.stop_sequence
    ''', (train_id,))
    stops = [dict(row) for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'data': dict(train),
        'stops': stops
    })

@app.route('/admin/api/sync/status')
@admin_required
def admin_api_sync_status():
    """同步状态API"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM data_sync_status 
        ORDER BY started_at DESC 
        LIMIT 10
    ''')
    history = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('''
        SELECT COUNT(*) FROM seller_train_cache
    ''')
    cached_trains = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'history': history,
        'cached_trains': cached_trains
    })

# ==================== 模拟售票器 ====================

import threading
import time as time_module

# 百家姓
SIMUL_SURNAMES = [
    '王', '李', '张', '刘', '陈', '杨', '赵', '黄', '周', '吴', '徐', '孙', '胡', '朱', '高',
    '林', '何', '郭', '马', '罗', '梁', '宋', '郑', '谢', '韩', '唐', '冯', '于', '董', '萧',
    '程', '曹', '袁', '邓', '许', '傅', '沈', '曾', '彭', '吕', '苏', '卢', '蒋', '蔡', '贾',
    '丁', '魏', '薛', '叶', '阎', '余', '潘', '杜', '戴', '夏', '钟', '汪', '田', '任', '姜'
]

# 常用名
SIMUL_GIVEN_NAMES = [
    '伟', '芳', '娜', '秀英', '敏', '静', '丽', '强', '磊', '军', '洋', '勇', '艳', '杰', '涛',
    '明', '超', '秀兰', '霞', '平', '刚', '桂英', '芬', '玲', '建国', '建华', '志强', '欣', '怡',
    '宇', '翔', '鑫', '雅', '诗', '涵', '子轩', '梓涵', '欣悦', '子瑶', '梦琪', '语汐', '俊杰',
    '子豪', '天宇', '宇航', '晨曦', '子墨', '嘉兴', '思琪', '雨桐', '雨涵', '欣怡', '佳怡', '可欣'
]

# 退票原因
SIMUL_REFUND_REASONS = [
    '旅客个人原因', '行程变更', '改签其他车次', '身体不适', '工作安排变化', '天气原因'
]

# 地区码
SIMUL_AREA_CODES = [
    '110100', '310100', '320100', '330100', '440100', '420100', '500100', '610100'
]

# 模拟器全局状态
simulation_state = {
    'running': False,
    'thread': None,
    'total_sold': 0,
    'total_refunded': 0,
    'total_revenue': 0.0,
    'started_at': None,
    'recent_operations': [],
    'lock': threading.Lock()
}

def generate_sim_passenger_name():
    """生成随机中文姓名"""
    surname = random.choice(SIMUL_SURNAMES)
    given_name = random.choice(SIMUL_GIVEN_NAMES)
    if len(given_name) == 1 and random.random() > 0.3:
        given_name += random.choice(SIMUL_GIVEN_NAMES[:20])
    return surname + given_name

def calculate_sim_id_checksum(id17):
    """计算身份证校验码"""
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_codes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
    total = sum(int(id17[i]) * weights[i] for i in range(17))
    return check_codes[total % 11]

def generate_sim_id_number():
    """生成随机身份证号"""
    area_code = random.choice(SIMUL_AREA_CODES)
    year = random.randint(1980, 2005)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    birth_date = f"{year:04d}{month:02d}{day:02d}"
    seq_code = f"{random.randint(1, 500):03d}"
    id17 = area_code + birth_date + seq_code
    return id17 + calculate_sim_id_checksum(id17)

def generate_sim_ticket_id():
    """生成票号"""
    now = datetime.now()
    return f"TK{now.strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

def get_seat_type_name_cn(seat_type):
    """席别中文名"""
    names = {
        'business': '商务座', 'first': '一等座', 'second': '二等座',
        'soft_seat': '软座', 'hard_seat': '硬座',
        'soft_sleeper': '软卧', 'hard_sleeper': '硬卧'
    }
    return names.get(seat_type, seat_type)

def get_sim_active_sellers():
    """获取活跃售票员"""
    conn = get_db_dict_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, employee_no, name, station_code, window_no 
            FROM users WHERE role = 'seller' AND status = 'active'
        """)
        sellers = cursor.fetchall()
        cursor.close()
        conn.close()
        return sellers
    except:
        if conn:
            conn.close()
        return []

def get_sim_random_train():
    """随机选择车次"""
    conn = get_db_dict_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT train_id, train_number, train_type FROM trains 
            WHERE train_type IN ('G', 'D', 'C', 'Z', 'T', 'K')
            ORDER BY RANDOM() LIMIT 1
        """)
        train = cursor.fetchone()
        if not train:
            cursor.close()
            conn.close()
            return None
        
        cursor.execute("""
            SELECT station_code, station_name, arrival_time, departure_time
            FROM train_stops WHERE train_id = ? ORDER BY stop_order
        """, (train['train_id'],))
        stops = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if len(stops) < 2:
            return None
        
        from_idx = random.randint(0, len(stops) - 2)
        to_idx = random.randint(from_idx + 1, len(stops) - 1)
        
        return {'train': train, 'from_stop': stops[from_idx], 'to_stop': stops[to_idx]}
    except:
        if conn:
            conn.close()
        return None

def get_sim_random_seat_type(train_type):
    """随机席别"""
    seat_types = {
        'G': ['business', 'first', 'second'],
        'D': ['first', 'second'],
        'C': ['first', 'second'],
        'Z': ['soft_sleeper', 'hard_sleeper', 'soft_seat', 'hard_seat'],
        'T': ['soft_sleeper', 'hard_sleeper', 'soft_seat', 'hard_seat'],
        'K': ['soft_sleeper', 'hard_sleeper', 'hard_seat']
    }
    return random.choice(seat_types.get(train_type, ['second']))

def get_sim_price(from_station, to_station, seat_type, train_type=None):
    """计算票价"""
    conn = get_db_dict_connection()
    if not conn:
        return 300.0
    try:
        cursor = conn.cursor()
        if train_type:
            cursor.execute("""
                SELECT base_price FROM ticket_prices
                WHERE from_station = ? AND to_station = ? AND seat_type = ? AND train_type = ?
            """, (from_station, to_station, seat_type, train_type))
            row = cursor.fetchone()
            if row:
                cursor.close()
                conn.close()
                return float(row['base_price'])
        
        cursor.execute("""
            SELECT base_price FROM ticket_prices
            WHERE from_station = ? AND to_station = ? AND seat_type = ?
        """, (from_station, to_station, seat_type))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return float(row['base_price'])
        
        defaults = {'business': 800, 'first': 500, 'second': 300,
                   'soft_seat': 250, 'hard_seat': 150, 'soft_sleeper': 400, 'hard_sleeper': 280}
        return defaults.get(seat_type, 200)
    except:
        if conn:
            conn.close()
        return 200.0

def calc_sim_refund_fee(price):
    """计算退票费"""
    fee_ratio = random.choice([0, 0.05, 0.10, 0.20])
    return round(price * fee_ratio, 2)

def sim_open_shift(seller):
    """开班"""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        now = datetime.now()
        cursor.execute("""
            INSERT INTO shifts (seller_id, seller_name, employee_no, station_code, 
                window_no, shift_date, start_time, status, ticket_count, revenue)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (seller['user_id'], seller['name'], seller['employee_no'], seller['station_code'],
              seller['window_no'], now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'),
              'open', 0, 0.0))
        shift_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return shift_id
    except:
        if conn:
            conn.rollback()
            conn.close()
        return None

def sim_close_shift(shift_id):
    """结班"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE shifts SET status = 'closed', end_time = ?
            WHERE shift_id = ?
        """, (datetime.now().strftime('%H:%M:%S'), shift_id))
        conn.commit()
        cursor.close()
        conn.close()
    except:
        if conn:
            conn.rollback()
            conn.close()

def sim_update_shift(shift_id, ticket_delta=0, revenue_delta=0.0):
    """更新班次统计"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE shifts SET ticket_count = ticket_count + ?, revenue = revenue + ?
            WHERE shift_id = ?
        """, (ticket_delta, revenue_delta, shift_id))
        conn.commit()
        cursor.close()
        conn.close()
    except:
        if conn:
            conn.rollback()
            conn.close()

def sim_sell_ticket(seller, shift_id):
    """模拟售票"""
    train_info = get_sim_random_train()
    if not train_info:
        return None
    
    train = train_info['train']
    from_stop = train_info['from_stop']
    to_stop = train_info['to_stop']
    seat_type = get_sim_random_seat_type(train['train_type'])
    price = get_sim_price(from_stop['station_code'], to_stop['station_code'], seat_type, train['train_type'])
    
    passenger_name = generate_sim_passenger_name()
    id_number = generate_sim_id_number()
    ticket_id = generate_sim_ticket_id()
    travel_date = (datetime.now() + timedelta(days=random.randint(0, 3))).strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tickets (
                ticket_id, shift_id, train_number, train_id,
                from_station, to_station, from_station_name, to_station_name,
                travel_date, departure_time, arrival_time,
                seat_type, seat_number, ticket_type, 
                passenger_name, id_number, phone,
                price, status, seller_id, window_no, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_id, shift_id, train['train_number'], train['train_id'],
            from_stop['station_code'], to_stop['station_code'],
            from_stop['station_name'], to_stop['station_name'],
            travel_date, from_stop['departure_time'], to_stop['arrival_time'],
            seat_type, f"{random.randint(1, 16):02d}{random.randint(1, 20):02d}{random.choice('ABCDF')}",
            'simulation', passenger_name, id_number, f"1{random.randint(3,9)}{random.randint(10000000, 99999999)}",
            price, 'sold', seller['user_id'], seller['window_no'], datetime.now().isoformat()
        ))
        
        cursor.execute("""
            INSERT INTO operation_logs (shift_id, employee_no, operation_type, ticket_id, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (shift_id, seller['employee_no'], 'simulation_sell', ticket_id,
              json.dumps({'train': train['train_number'], 'from': from_stop['station_name'],
                         'to': to_stop['station_name'], 'seat': seat_type, 'price': price,
                         'passenger': passenger_name}, ensure_ascii=False),
              datetime.now().isoformat()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        sim_update_shift(shift_id, 1, price)
        
        return {
            'type': 'sell', 'seller': seller['employee_no'], 'seller_name': seller['name'],
            'ticket_id': ticket_id, 'train_number': train['train_number'],
            'from_station': from_stop['station_name'], 'to_station': to_stop['station_name'],
            'seat_type': seat_type, 'price': price, 'passenger': passenger_name
        }
    except Exception as e:
        print(f"模拟售票失败: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return None

def sim_refund_ticket(seller, shift_id):
    """模拟退票"""
    conn = get_db_dict_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticket_id, train_number, from_station, to_station,
                   from_station_name, to_station_name, seat_type, price, train_id, travel_date
            FROM tickets WHERE status = 'sold' AND ticket_type = 'simulation'
            ORDER BY RANDOM() LIMIT 1
        """)
        ticket = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not ticket:
            return None
        
        refund_fee = calc_sim_refund_fee(ticket['price'])
        refund_amount = ticket['price'] - refund_fee
        
        conn2 = get_db_connection()
        if not conn2:
            return None
        try:
            cursor = conn2.cursor()
            cursor.execute("""
                INSERT INTO refunds (ticket_id, shift_id, refund_amount, refund_fee,
                    refund_reason, refund_type, status, operated_by, operated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ticket['ticket_id'], shift_id, refund_amount, refund_fee,
                  random.choice(SIMUL_REFUND_REASONS), 'simulation', 'approved',
                  seller['user_id'], datetime.now().isoformat()))
            
            cursor.execute("UPDATE tickets SET status = 'refunded' WHERE ticket_id = ?",
                          (ticket['ticket_id'],))
            
            cursor.execute("""
                INSERT INTO operation_logs (shift_id, employee_no, operation_type, ticket_id, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (shift_id, seller['employee_no'], 'simulation_refund', ticket['ticket_id'],
                  json.dumps({'train': ticket['train_number'], 'from': ticket['from_station_name'],
                             'to': ticket['to_station_name'], 'seat': ticket['seat_type'],
                             'price': ticket['price'], 'refund_fee': refund_fee}, ensure_ascii=False),
                  datetime.now().isoformat()))
            
            conn2.commit()
            cursor.close()
            conn2.close()
            
            sim_update_shift(shift_id, 0, -refund_amount)
            
            return {
                'type': 'refund', 'seller': seller['employee_no'], 'seller_name': seller['name'],
                'ticket_id': ticket['ticket_id'], 'train_number': ticket['train_number'],
                'from_station': ticket['from_station_name'], 'to_station': ticket['to_station_name'],
                'seat_type': ticket['seat_type'], 'price': ticket['price'],
                'refund_fee': refund_fee, 'refund_amount': refund_amount
            }
        except:
            if conn2:
                conn2.rollback()
                conn2.close()
            return None
    except:
        if conn:
            conn.close()
        return None

def simulation_worker():
    """模拟工作线程"""
    sellers = get_sim_active_sellers()
    if not sellers:
        print("❌ 模拟器: 没有活跃售票员")
        simulation_state['running'] = False
        return
    
    print(f"✅ 模拟器: 找到 {len(sellers)} 个活跃售票员")
    
    # 获取速度配置
    conn = get_db_dict_connection()
    speed = 'normal'
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM simulation_config WHERE key = 'speed'")
            row = cursor.fetchone()
            if row:
                speed = row.get('value', 'normal')
            cursor.close()
            conn.close()
        except:
            if conn:
                conn.close()
    
    speed_config = {
        'slow': {'sell': (12, 20), 'refund': (40, 70)},
        'normal': {'sell': (4, 10), 'refund': (20, 45)},
        'fast': {'sell': (1, 3), 'refund': (8, 18)}
    }
    cfg = speed_config.get(speed, speed_config['normal'])
    
    current_shifts = {}
    ticket_counts = {}
    
    while simulation_state['running']:
        try:
            seller = random.choice(sellers)
            
            # 确保开班
            if seller['user_id'] not in current_shifts:
                sid = sim_open_shift(seller)
                if sid:
                    current_shifts[seller['user_id']] = sid
                    ticket_counts[seller['user_id']] = 0
                    record_sim_op('simulation_shift_open', seller['employee_no'])
                    print(f"🚂 模拟器: [{seller['employee_no']}] 开班")
            
            if seller['user_id'] not in current_shifts:
                time_module.sleep(1)
                continue
            
            shift_id = current_shifts[seller['user_id']]
            
            # 选择操作
            action = random.choices(['sell', 'sell', 'sell', 'sell', 'refund', 'shift'],
                                   weights=[40, 40, 40, 40, 15, 5])[0]
            
            if action == 'sell':
                result = sim_sell_ticket(seller, shift_id)
                if result:
                    ticket_counts[seller['user_id']] += 1
                    simulation_state['total_sold'] += 1
                    simulation_state['total_revenue'] += result['price']
                    record_sim_op('simulation_sell', seller['employee_no'], result)
                    print(f"🎫 模拟器: [{datetime.now().strftime('%H:%M:%S')}] {seller['employee_no']} "
                          f"售 {result['train_number']} {result['from_station']}→{result['to_station']} "
                          f"{get_seat_type_name_cn(result['seat_type'])} ¥{result['price']:.0f}")
                    
                    if ticket_counts[seller['user_id']] >= random.randint(30, 80):
                        sim_close_shift(shift_id)
                        record_sim_op('simulation_shift_close', seller['employee_no'],
                                     {'ticket_count': ticket_counts[seller['user_id']]})
                        print(f"🏁 模拟器: [{seller['employee_no']}] 结班({ticket_counts[seller['user_id']]}张)")
                        del current_shifts[seller['user_id']]
                        del ticket_counts[seller['user_id']]
                time_module.sleep(random.uniform(*cfg['sell']))
            
            elif action == 'refund':
                result = sim_refund_ticket(seller, shift_id)
                if result:
                    simulation_state['total_refunded'] += 1
                    simulation_state['total_revenue'] -= result['refund_fee']
                    record_sim_op('simulation_refund', seller['employee_no'], result)
                    print(f"💰 模拟器: [{datetime.now().strftime('%H:%M:%S')}] {seller['employee_no']} "
                          f"退 {result['train_number']} 退票费¥{result['refund_fee']:.0f}")
                time_module.sleep(random.uniform(*cfg['refund']))
            
            else:  # shift
                if seller['user_id'] in current_shifts:
                    sim_close_shift(current_shifts[seller['user_id']])
                    record_sim_op('simulation_shift_close', seller['employee_no'],
                                 {'ticket_count': ticket_counts[seller['user_id']]})
                    print(f"🏁 模拟器: [{seller['employee_no']}] 主动结班")
                    del current_shifts[seller['user_id']]
                    del ticket_counts[seller['user_id']]
                sid = sim_open_shift(seller)
                if sid:
                    current_shifts[seller['user_id']] = sid
                    ticket_counts[seller['user_id']] = 0
                    record_sim_op('simulation_shift_open', seller['employee_no'])
                    print(f"🚂 模拟器: [{seller['employee_no']}] 重新开班")
                time_module.sleep(2)
                
        except Exception as e:
            print(f"模拟线程异常: {e}")
            time_module.sleep(5)
    
    # 退出时结班
    for sid in current_shifts.values():
        sim_close_shift(sid)
    print("🏁 模拟器已停止")

def record_sim_op(op_type, seller_no, data=None):
    """记录最近操作"""
    with simulation_state['lock']:
        op = {
            'type': op_type,
            'seller': seller_no,
            'time': datetime.now().strftime('%H:%M:%S'),
            'data': data or {}
        }
        simulation_state['recent_operations'].insert(0, op)
        simulation_state['recent_operations'] = simulation_state['recent_operations'][:20]

@app.route('/admin/simulation')
@admin_required
def admin_simulation():
    """模拟监控页面"""
    return render_template('admin/simulation.html', running=simulation_state['running'])

@app.route('/admin/api/simulation/start', methods=['POST'])
@admin_required
def admin_simulation_start():
    """启动模拟"""
    speed = request.json.get('speed', 'normal') if request.is_json else 'normal'
    
    with simulation_state['lock']:
        if simulation_state['running']:
            return jsonify({'status': 'error', 'message': '模拟已在运行'})
        
        simulation_state['running'] = True
        simulation_state['thread'] = threading.Thread(target=simulation_worker, daemon=True)
        simulation_state['thread'].start()
        simulation_state['started_at'] = datetime.now().isoformat()
        simulation_state['total_sold'] = 0
        simulation_state['total_refunded'] = 0
        simulation_state['total_revenue'] = 0.0
        simulation_state['recent_operations'] = []
    
    return jsonify({'status': 'success', 'message': f'模拟已启动(速度:{speed})'})

@app.route('/admin/api/simulation/stop', methods=['POST'])
@admin_required
def admin_simulation_stop():
    """停止模拟"""
    with simulation_state['lock']:
        if not simulation_state['running']:
            return jsonify({'status': 'error', 'message': '模拟未在运行'})
        simulation_state['running'] = False
    
    return jsonify({'status': 'success', 'message': '模拟已停止'})

@app.route('/admin/api/simulation/status')
@admin_required
def admin_simulation_status():
    """获取模拟状态"""
    return jsonify({
        'status': 'success',
        'running': simulation_state['running'],
        'total_sold': simulation_state['total_sold'],
        'total_refunded': simulation_state['total_refunded'],
        'total_revenue': simulation_state['total_revenue'],
        'started_at': simulation_state['started_at'],
        'recent_operations': simulation_state['recent_operations']
    })

@app.route('/admin/api/simulation/stats')
@admin_required
def admin_simulation_stats():
    """获取模拟统计数据"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        
        # 今日统计
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT COUNT(*) FROM tickets 
            WHERE ticket_type = 'simulation' AND DATE(created_at) = ?
        """, (today,))
        today_sold = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT COUNT(*) FROM refunds 
            WHERE refund_type = 'simulation' AND DATE(operated_at) = ?
        """, (today,))
        today_refunded = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT COALESCE(SUM(price), 0) FROM tickets 
            WHERE ticket_type = 'simulation' AND DATE(created_at) = ?
        """, (today,))
        today_revenue = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT COALESCE(SUM(refund_fee), 0) FROM refunds 
            WHERE refund_type = 'simulation' AND DATE(operated_at) = ?
        """, (today,))
        today_refund_fee = cursor.fetchone()[0] or 0
        
        # 活跃售票员
        cursor.execute("""
            SELECT COUNT(DISTINCT seller_id) FROM shifts 
            WHERE DATE(shift_date) = ? AND status = 'open'
        """, (today,))
        active_sellers = cursor.fetchone()[0] or 0
        
        # 车次热度TOP10
        cursor.execute("""
            SELECT train_number, COUNT(*) as cnt 
            FROM tickets 
            WHERE ticket_type = 'simulation' AND DATE(created_at) = ?
            GROUP BY train_number 
            ORDER BY cnt DESC LIMIT 10
        """, (today,))
        top_trains = [{'train': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # 班次状态
        cursor.execute("""
            SELECT s.employee_no, s.seller_name, s.window_no, s.ticket_count, s.revenue, s.status
            FROM shifts s
            WHERE DATE(s.shift_date) = ?
            ORDER BY s.start_time DESC
            LIMIT 20
        """, (today,))
        shifts = [{'employee_no': row[0], 'name': row[1], 'window': row[2],
                  'tickets': row[3], 'revenue': row[4], 'status': row[5]} for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'today_sold': today_sold,
            'today_refunded': today_refunded,
            'today_revenue': today_revenue - today_refund_fee,
            'active_sellers': active_sellers,
            'top_trains': top_trains,
            'shifts': shifts
        })
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/api/simulation/config', methods=['GET', 'POST'])
@admin_required
def admin_simulation_config():
    """模拟器配置"""
    if request.method == 'POST':
        key = request.form.get('key')
        value = request.form.get('value')
        if key and value:
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO simulation_config (key, value) VALUES (?, ?)
                    """, (key, value))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    return jsonify({'status': 'success', 'message': '配置已更新'})
                except:
                    if conn:
                        conn.close()
        return jsonify({'status': 'error', 'message': '更新失败'})
    
    # GET
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value, description FROM simulation_config")
            config = [{'key': row[0], 'value': row[1], 'desc': row[2]} for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return jsonify({'status': 'success', 'config': config})
        except:
            if conn:
                conn.close()
    return jsonify({'status': 'error', 'message': '获取配置失败'})

# ==================== 启动应用 ====================

if __name__ == '__main__':
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
