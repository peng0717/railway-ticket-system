# -*- coding: utf-8 -*-
"""
WebTRS 应用入口
模拟铁路车站人工售票系统
使用PostgreSQL (Supabase)
"""

import os
import json
import random
import hashlib
from datetime import datetime, timedelta
from functools import wraps

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, session, redirect, url_for, request, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# 导入配置
import config

# 加载dotenv
from dotenv import load_dotenv
load_dotenv()

# 创建Flask应用
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# 数据库配置
DATABASE_URL = config.DATABASE_URL

# ==================== 数据库连接函数 ====================

def get_db_connection():
    """获取数据库连接"""
    if not DATABASE_URL:
        return None
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def get_db_dict_connection():
    """获取返回字典的数据库连接"""
    if not DATABASE_URL:
        return None
    try:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

# ==================== 辅助函数 ====================

def get_user_by_employee_no(employee_no):
    """根据工号获取用户"""
    conn = get_db_dict_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE employee_no = %s", (employee_no,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(user) if user else None
    except Exception as e:
        print(f"查询用户失败: {e}")
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
            SET machine_code = %s, status = %s, last_login = %s
            WHERE id = %s
        """, (machine_code, status, datetime.now(), user_id))
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
            INSERT INTO risk_controls (user_id, employee_no, risk_type, machine_code, description, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, employee_no, risk_type, machine_code, description, datetime.now()))
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
        # PostgreSQL: 使用RETURNING
        cursor.execute("""
            INSERT INTO counters (counter_name, current_value, prefix, updated_at)
            VALUES ('ticket', 1, 'A', %s)
            ON CONFLICT (counter_name) 
            DO UPDATE SET current_value = counters.current_value + 1, updated_at = %s
            RETURNING prefix, current_value
        """, (datetime.now(), datetime.now()))
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        if result:
            prefix = result[0] or 'A'
            current_value = result[1]
            return f"{prefix}{current_value:06d}"
        return 'A000001'
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
            WHERE (pinyin_code ILIKE %s OR station_code ILIKE %s OR station_name ILIKE %s OR station_pinyin ILIKE %s)
            AND status = 'active'
            LIMIT 10
        """, (f'{pinyin_code}%', f'{pinyin_code}%', f'%{pinyin_code}%', f'{pinyin_code}%'))
        
        stations = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [{'code': s['station_code'], 'name': s['station_name'], 
                 'pinyin': s['station_pinyin'], 'pinyin_code': s['pinyin_code']} for s in stations]
    except Exception as e:
        print(f"搜索车站失败: {e}")
        conn.close()
        return []

def calculate_price(from_station, to_station, seat_type):
    """计算票价"""
    conn = get_db_dict_connection()
    if not conn:
        return 200
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT base_price FROM ticket_prices
            WHERE from_station = %s AND to_station = %s AND seat_type = %s
        """, (from_station, to_station, seat_type))
        price = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if price:
            return price['base_price']
        
        # 如果没有固定票价，按距离计算
        cursor = conn.cursor()
        cursor.execute("""
            SELECT distance_from_start FROM train_stops WHERE station_code = %s LIMIT 1
        """, (from_station,))
        from_stop = cursor.fetchone()
        
        cursor.execute("""
            SELECT distance_from_start FROM train_stops WHERE station_code = %s LIMIT 1
        """, (to_station,))
        to_stop = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if from_stop and to_stop and from_stop['distance_from_start'] and to_stop['distance_from_start']:
            distance = abs(to_stop['distance_from_start'] - from_stop['distance_from_start'])
            base_rate = 0.46  # 基础单价 元/公里
            
            seat_config = config.SEAT_TYPES.get(seat_type, {})
            coefficient = seat_config.get('coefficient', 1.0)
            
            return round(distance * base_rate * coefficient, 2)
        
        # 如果没有距离信息，使用默认价格
        default_prices = {
            'business': 800, 'first': 500, 'second': 300,
            'soft_seat': 250, 'hard_seat': 150,
            'soft_sleeper': 400, 'hard_sleeper': 280
        }
        return default_prices.get(seat_type, 200)
    except Exception as e:
        print(f"计算票价失败: {e}")
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
    
    # 退票手续费规则（按开车前时间）
    if hours_until_departure >= 360:  # 15天以上
        return 0.0
    elif hours_until_departure >= 48:  # 48小时以上
        return round(ticket_price * 0.05, 2)
    elif hours_until_departure >= 24:  # 24-48小时
        return round(ticket_price * 0.10, 2)
    elif hours_until_departure >= 0:  # 24小时内
        return round(ticket_price * 0.20, 2)
    else:  # 开车后不退
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
    else:  # 卧铺
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
                cursor.execute("SELECT * FROM shifts WHERE shift_id = %s", (session['shift_id'],))
                shift = cursor.fetchone()
                cursor.close()
                conn.close()
                return dict(shift) if shift else None
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
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            session.get('shift_id'),
            session.get('employee_no'),
            operation_type,
            ticket_id,
            json.dumps(details, ensure_ascii=False) if details else None,
            request.remote_addr,
            datetime.now()
        ))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"记录操作日志失败: {e}")
        conn.rollback()
        conn.close()

def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== 路由 ====================

@app.route('/')
def index():
    """首页/登录页"""
    if 'user_id' in session:
        if 'shift_id' not in session:
            return redirect(url_for('shift_select'))
        return redirect(url_for('main'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if 'user_id' in session:
        return redirect(url_for('shift_select'))
    
    error = None
    
    if request.method == 'POST':
        employee_no = request.form.get('employee_no', '').strip()
        password = request.form.get('password', '')
        machine_code = request.form.get('machine_code', '').strip()
        
        if not employee_no or not password:
            error = '请输入工号和密码'
        else:
            # 获取用户
            user = get_user_by_employee_no(employee_no)
            
            if user:
                # 验证密码
                stored_hash = user.get('password_hash', '')
                if check_password_hash(stored_hash, password):
                    # 检查状态和机器码
                    is_valid, message = check_machine_code(user, machine_code)
                    
                    if not is_valid:
                        error = message
                        # 如果是机器码不匹配但状态正常，记录风控
                        if message == "机器码不匹配，检测到异地登录":
                            # 冻结账户
                            update_user_machine_code(user['id'], user.get('machine_code', ''), 'frozen')
                            # 记录风控
                            add_risk_control_record(
                                user['id'], 
                                employee_no, 
                                machine_code, 
                                'machine_code_mismatch',
                                f"异地登录：原机器码={user.get('machine_code', 'N/A')}，新机器码={machine_code}"
                            )
                            error = "该工号因异地登录已被风控冻结，请联系管理员"
                    else:
                        # 首次登录，设置机器码
                        if not user.get('machine_code') and machine_code:
                            update_user_machine_code(user['id'], machine_code, 'active')
                        
                        # 登录成功
                        session['user_id'] = user['id']
                        session['employee_no'] = user['employee_no']
                        session['user_name'] = user['name']
                        session['window_no'] = user.get('window_no') or config.DEFAULT_WINDOW_NO
                        session['station_code'] = user.get('station_code') or 'ZZO'
                        session['station_name'] = '郑州站'
                        
                        # 获取下一张票号
                        next_ticket = get_next_ticket_id()
                        session['next_ticket_id'] = next_ticket
                        
                        log_operation('login')
                        return redirect(url_for('shift_select'))
                else:
                    error = '工号或密码错误'
            else:
                error = '工号或密码错误'
    
    return render_template('login.html', error=error, system_name=config.SYSTEM_NAME)

@app.route('/logout')
def logout():
    """退出登录"""
    if 'user_id' in session:
        log_operation('logout')
    session.clear()
    flash('已退出系统', 'info')
    return redirect(url_for('login'))

@app.route('/shift_select', methods=['GET', 'POST'])
def shift_select():
    """班次选择页面"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        shift_type = request.form.get('shift_type', 'day')
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO shifts (employee_no, shift_type, start_time, status, created_at)
                    VALUES (%s, %s, %s, 'active', %s)
                    RETURNING shift_id
                """, (session['employee_no'], shift_type, datetime.now(), datetime.now()))
                shift_id = cursor.fetchone()[0]
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
    
    # 确定当前班次
    current_hour = datetime.now().hour
    default_shift = 'night' if 12 <= current_hour < 24 else 'day'
    
    return render_template('shift_select.html', 
                           default_shift=default_shift,
                           shift_types=config.SHIFT_TYPES)

@app.route('/main')
def main():
    """主售票界面"""
    if 'user_id' not in session or 'shift_id' not in session:
        return redirect(url_for('shift_select'))
    
    return render_template('tickets/sell.html',
                         system_name=config.SYSTEM_NAME,
                         station_name=session.get('station_name', '郑州站'),
                         window_no=session.get('window_no', '101号口'),
                         shift_name=session.get('shift_name', '白班'),
                         next_ticket_id=session.get('next_ticket_id', 'A000001'),
                         current_time=datetime.now().strftime('%H:%M:%S'),
                         current_date=datetime.now().strftime('%Y-%m-%d'),
                         seat_types=config.SEAT_TYPES,
                         ticket_types=config.TICKET_TYPES,
                         ticket_purpose=config.TICKET_PURPOSE)

# ==================== API路由 ====================

@app.route('/api/stations/search')
def api_search_stations():
    """搜索车站API"""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    
    stations = search_stations(q)
    return jsonify(stations)

@app.route('/api/trains/search')
def api_search_trains():
    """搜索车次API"""
    train_code = request.args.get('train', '').strip().upper()
    from_station = request.args.get('from', '').strip()
    to_station = request.args.get('to', '').strip()
    
    conn = get_db_dict_connection()
    if not conn:
        return jsonify([])
    
    try:
        cursor = conn.cursor()
        
        if train_code:
            # 车次号模糊搜索
            import re
            match = re.match(r'^([A-Z]+)(\d+)$', train_code)
            if match:
                prefix = match.group(1)
                number = match.group(2)
                cursor.execute("""
                    SELECT train_id, train_number, train_type, start_station, end_station,
                           start_time, end_time, total_distance
                    FROM trains
                    WHERE status = 'active'
                    AND train_number ~ %s
                    AND (train_number = %s OR train_number LIKE %s)
                    LIMIT 100
                """, (r'^' + prefix + number, train_code, prefix + number + '%'))
            else:
                cursor.execute("""
                    SELECT train_id, train_number, train_type, start_station, end_station,
                           start_time, end_time, total_distance
                    FROM trains
                    WHERE status = 'active' AND train_number LIKE %s
                    LIMIT 100
                """, (train_code + '%',))
        else:
            cursor.execute("""
                SELECT train_id, train_number, train_type, start_station, end_station,
                       start_time, end_time, total_distance
                FROM trains
                WHERE status = 'active'
                LIMIT 100
            """)
        
        trains = cursor.fetchall()
        cursor.close()
        
        result = []
        for train in trains:
            if from_station and to_station:
                # 按发到站查询
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ts.*, s.station_name
                    FROM train_stops ts
                    JOIN stations s ON ts.station_code = s.station_code
                    WHERE ts.train_id = %s AND ts.station_code IN (%s, %s)
                    ORDER BY ts.stop_sequence
                """, (train['train_id'], from_station, to_station))
                stops = cursor.fetchall()
                cursor.close()
                
                if len(stops) >= 2 and stops[0]['stop_sequence'] < stops[1]['stop_sequence']:
                    from_stop = stops[0]
                    to_stop = stops[1]
                    result.append({
                        'train_id': train['train_id'],
                        'train_number': train['train_number'],
                        'train_type': train['train_type'],
                        'start_station': train['start_station'],
                        'end_station': train['end_station'],
                        'from_station': from_station,
                        'to_station': to_station,
                        'departure_time': from_stop['arrival_time'] or from_stop['departure_time'],
                        'arrival_time': to_stop['arrival_time'],
                        'duration': calculate_duration(from_stop['arrival_time'] or from_stop['departure_time'], to_stop['arrival_time']),
                        'distance': (to_stop['distance_from_start'] or 0) - (from_stop['distance_from_start'] or 0)
                    })
            else:
                result.append({
                    'train_id': train['train_id'],
                    'train_number': train['train_number'],
                    'train_type': train['train_type'],
                    'start_station': train['start_station'],
                    'end_station': train['end_station'],
                    'start_time': train['start_time'],
                    'end_time': train['end_time'],
                    'total_distance': train['total_distance']
                })
        
        conn.close()
        return jsonify(result)
    except Exception as e:
        print(f"搜索车次失败: {e}")
        conn.close()
        return jsonify([])

@app.route('/api/trains/<int:train_id>/availability')
def api_train_availability(train_id):
    """获取车次余票信息"""
    date = request.args.get('date', '')
    from_station = request.args.get('from', '')
    to_station = request.args.get('to', '')
    
    if not train_id:
        return jsonify({'error': '缺少车次ID'}), 400
    
    conn = get_db_dict_connection()
    if not conn:
        return jsonify({'error': '数据库连接失败'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trains WHERE train_id = %s", (train_id,))
        train = cursor.fetchone()
        
        if not train:
            cursor.close()
            conn.close()
            return jsonify({'error': '车次不存在'}), 404
        
        # 获取经停站信息
        if not from_station:
            from_station = train['start_station']
        if not to_station:
            to_station = train['end_station']
        
        cursor.execute("""
            SELECT * FROM train_stops WHERE train_id = %s AND station_code = %s
        """, (train_id, from_station))
        from_stop = cursor.fetchone()
        
        cursor.execute("""
            SELECT * FROM train_stops WHERE train_id = %s AND station_code = %s
        """, (train_id, to_station))
        to_stop = cursor.fetchone()
        
        if not from_stop:
            cursor.execute("""
                SELECT * FROM train_stops WHERE train_id = %s ORDER BY stop_sequence LIMIT 1
            """, (train_id,))
            from_stop = cursor.fetchone()
        
        if not to_stop:
            cursor.execute("""
                SELECT * FROM train_stops WHERE train_id = %s ORDER BY stop_sequence DESC LIMIT 1
            """, (train_id,))
            to_stop = cursor.fetchone()
        
        # 计算票价
        prices = {}
        for seat_type, seat_config in config.SEAT_TYPES.items():
            price = calculate_price(from_station, to_station, seat_type)
            seat_column = f'seat_{seat_type}'
            count = 0
            if from_stop and seat_column in from_stop:
                count = from_stop[seat_column] or 0
            prices[seat_config['name']] = {
                'price': price,
                'available': count > 0,
                'count': count
            }
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'train_id': train['train_id'],
            'train_number': train['train_number'],
            'train_type': train['train_type'],
            'start_station': train['start_station'],
            'end_station': train['end_station'],
            'departure_time': from_stop['arrival_time'] or from_stop['departure_time'] if from_stop else train['start_time'],
            'arrival_time': to_stop['arrival_time'] if to_stop else train['end_time'],
            'from_station': from_station,
            'to_station': to_station,
            'prices': prices
        })
    except Exception as e:
        print(f"获取余票失败: {e}")
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tickets/sell', methods=['POST'])
def api_sell_ticket():
    """售票API"""
    if 'shift_id' not in session:
        return jsonify({'success': False, 'error': '请先选择班次'}), 401
    
    data = request.get_json()
    
    required_fields = ['train_id', 'from_station', 'to_station', 'seat_type', 'travel_date']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'}), 500
    
    try:
        cursor = conn.cursor()
        
        # 获取车次信息
        cursor.execute("SELECT * FROM trains WHERE train_id = %s", (data['train_id'],))
        train = cursor.fetchone()
        if not train:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': '车次不存在'}), 404
        
        # 获取经停站信息
        cursor.execute("""
            SELECT * FROM train_stops WHERE train_id = %s AND station_code = %s
        """, (data['train_id'], data['from_station']))
        from_stop = cursor.fetchone()
        
        cursor.execute("""
            SELECT * FROM train_stops WHERE train_id = %s AND station_code = %s
        """, (data['train_id'], data['to_station']))
        to_stop = cursor.fetchone()
        
        departure_time = train[7] or '08:00'  # start_time
        if from_stop and from_stop[4]:  # arrival_time or departure_time
            departure_time = from_stop[4] or from_stop[5]
        
        # 计算票价
        ticket_type = data.get('ticket_type', 'adult')
        base_price = calculate_price(data['from_station'], data['to_station'], data['seat_type'])
        
        if ticket_type == 'child':
            price = round(base_price * 0.5, 2)
        elif ticket_type == 'student':
            price = round(base_price * 0.5, 2)
        else:
            price = base_price
        
        # 生成票号和座位号
        ticket_id = get_next_ticket_id()
        seat_number = generate_seat_number(data['seat_type'])
        carriage = seat_number[:2]
        
        # 票额用途
        ticket_purpose = data.get('ticket_purpose', 'public')
        ticket_class_map = {'public': 'normal', 'flexible': 'flex', 'student': 'student', 'forbidden': 'blocked'}
        ticket_class = ticket_class_map.get(ticket_purpose, 'normal')
        
        # 创建车票记录
        cursor.execute("""
            INSERT INTO tickets (ticket_id, train_id, train_number, passenger_name, id_number, id_type,
                from_station, to_station, travel_date, departure_time, carriage, seat_number, seat_type,
                price, ticket_type, status, ticket_class, seller_id, window_no, sold_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ticket_id, data['train_id'], train[2],  # train_number
            data.get('passenger_name', ''), data.get('id_number', ''), data.get('id_type', 'id_card'),
            data['from_station'], data['to_station'], data['travel_date'], departure_time,
            carriage, seat_number, data['seat_type'], price, ticket_type, 'valid', ticket_class,
            session['user_id'], session.get('window_no'), datetime.now()
        ))
        
        # 更新班次统计
        cursor.execute("""
            UPDATE shifts SET ticket_count = ticket_count + 1, revenue = revenue + %s
            WHERE shift_id = %s
        """, (price, session['shift_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # 记录操作日志
        log_operation('sell', ticket_id, {
            'train_number': train[2],
            'from_station': data['from_station'],
            'to_station': data['to_station'],
            'seat_type': data['seat_type'],
            'price': price,
            'ticket_purpose': ticket_purpose
        })
        
        return jsonify({
            'success': True,
            'ticket': {
                'ticket_id': ticket_id,
                'train_number': train[2],
                'from_station': data['from_station'],
                'to_station': data['to_station'],
                'travel_date': data['travel_date'],
                'departure_time': departure_time,
                'carriage': carriage,
                'seat_number': seat_number,
                'seat_type': data['seat_type'],
                'price': price,
                'passenger_name': data.get('passenger_name', ''),
                'id_number': data.get('id_number', '')
            }
        })
        
    except Exception as e:
        print(f"售票失败: {e}")
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tickets/<ticket_id>')
def api_get_ticket(ticket_id):
    """获取车票信息"""
    conn = get_db_dict_connection()
    if not conn:
        return jsonify({'error': '数据库连接失败'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE ticket_id = %s", (ticket_id,))
        ticket = cursor.fetchone()
        
        if not ticket:
            cursor.close()
            conn.close()
            return jsonify({'error': '车票不存在'}), 404
        
        # 获取车站名称
        from_station_name = ticket['from_station']
        to_station_name = ticket['to_station']
        
        cursor.execute("""
            SELECT station_name FROM stations 
            WHERE station_code = %s OR station_name = %s LIMIT 1
        """, (ticket['from_station'], ticket['from_station']))
        from_st = cursor.fetchone()
        
        cursor.execute("""
            SELECT station_name FROM stations 
            WHERE station_code = %s OR station_name = %s LIMIT 1
        """, (ticket['to_station'], ticket['to_station']))
        to_st = cursor.fetchone()
        
        if from_st:
            from_station_name = from_st['station_name']
        if to_st:
            to_station_name = to_st['station_name']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'ticket_id': ticket['ticket_id'],
            'train_number': ticket['train_number'],
            'from_station': from_station_name,
            'from_station_code': ticket['from_station'],
            'to_station': to_station_name,
            'to_station_code': ticket['to_station'],
            'travel_date': ticket['travel_date'],
            'departure_time': ticket['departure_time'],
            'carriage': ticket['carriage'],
            'seat_number': ticket['seat_number'],
            'seat_type': ticket['seat_type'],
            'price': ticket['price'],
            'ticket_type': ticket['ticket_type'],
            'status': ticket['status'],
            'passenger_name': ticket['passenger_name'],
            'id_number': ticket['id_number'],
            'sold_at': ticket['sold_at'].strftime('%Y-%m-%d %H:%M:%S') if ticket['sold_at'] else ''
        })
    except Exception as e:
        print(f"获取车票失败: {e}")
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tickets/<ticket_id>/refund', methods=['POST'])
def api_refund_ticket(ticket_id):
    """退票API"""
    if 'shift_id' not in session:
        return jsonify({'success': False, 'error': '请先选择班次'}), 401
    
    conn = get_db_dict_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE ticket_id = %s", (ticket_id,))
        ticket = cursor.fetchone()
        
        if not ticket:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': '车票不存在'}), 404
        
        if ticket['status'] != 'valid':
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': '车票状态不允许退票'}), 400
        
        data = request.get_json() or {}
        refund_reason = data.get('refund_reason', '24hours_less')
        
        # 根据退票原因计算手续费
        rates = {
            '15days': 0.0,
            '48hours': 0.05,
            '24hours': 0.10,
            '24hours_less': 0.20,
            'after_departure': 1.0
        }
        rate = rates.get(refund_reason, 0.20)
        
        refund_fee = round(ticket['price'] * rate, 2)
        refund_amount = round(ticket['price'] - refund_fee, 2)
        
        # 开车后不允许退票
        if refund_reason == 'after_departure' or refund_amount < 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': '开车后不办理退票'}), 400
        
        # 创建退票记录
        cursor.execute("""
            INSERT INTO refunds (ticket_id, refund_amount, refund_fee, refund_reason, refund_type, operator_id, refund_time)
            VALUES (%s, %s, %s, %s, 'normal', %s, %s)
        """, (ticket_id, refund_amount, refund_fee, refund_reason, session['user_id'], datetime.now()))
        
        # 更新车票状态
        cursor.execute("UPDATE tickets SET status = 'refunded' WHERE ticket_id = %s", (ticket_id,))
        
        # 更新班次统计
        cursor.execute("""
            UPDATE shifts SET refund_count = refund_count + 1, refund_amount = refund_amount + %s
            WHERE shift_id = %s
        """, (refund_amount, session['shift_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # 记录操作日志
        log_operation('refund', ticket_id, {
            'refund_amount': refund_amount,
            'refund_fee': refund_fee,
            'refund_reason': refund_reason
        })
        
        return jsonify({
            'success': True,
            'refund': {
                'refund_amount': refund_amount,
                'refund_fee': refund_fee,
                'original_price': ticket['price']
            }
        })
        
    except Exception as e:
        print(f"退票失败: {e}")
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/supplements', methods=['POST'])
def api_create_supplement():
    """创建补票API"""
    if 'shift_id' not in session:
        return jsonify({'success': False, 'error': '请先选择班次'}), 401
    
    data = request.get_json()
    
    required_fields = ['to_station', 'supp_type']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'}), 500
    
    try:
        cursor = conn.cursor()
        
        # 获取前端传来的费用数据
        base_price = data.get('base_price', 0)
        fine = data.get('fine', 0)
        service_fee = 2.0  # 固定手续费
        
        # 如果前端没有传来，使用计算
        if base_price == 0:
            from_station = data.get('from_station', 'ZZO')
            seat_type = data.get('seat_type', 'hard_seat')
            base_price = calculate_price(from_station, data['to_station'], seat_type)
        
        # 根据补票类型调整罚款
        if data['supp_type'] == 'no_ticket' and fine == 0:
            fine = round(base_price * 0.5, 2)
        elif data['supp_type'] == 'over_station':
            fine = fine if fine > 0 else base_price
        elif data['supp_type'] == 'over_class':
            fine = fine if fine > 0 else round(base_price * 0.3, 2)
        
        total_amount = round(base_price + fine + service_fee, 2)
        
        from_station = data.get('from_station', '郑州')
        seat_type = data.get('seat_type', 'hard_seat')
        
        cursor.execute("""
            INSERT INTO supplement_tickets (original_ticket_id, passenger_name, id_number, id_type,
                from_station, to_station, seat_type, amount, fine, supp_type, operator_id, window_no, supp_time, remark)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get('original_ticket_id'),
            data.get('passenger_name', ''),
            data.get('id_number', ''),
            data.get('id_type', 'id_card'),
            from_station, data['to_station'], seat_type, total_amount, fine, data['supp_type'],
            session['user_id'], session.get('window_no'), datetime.now(), data.get('remark', '')
        ))
        
        # 更新班次统计
        cursor.execute("""
            UPDATE shifts SET ticket_count = ticket_count + 1, revenue = revenue + %s
            WHERE shift_id = %s
        """, (total_amount, session['shift_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # 记录操作日志
        log_operation('supplement', details={
            'supp_type': data['supp_type'],
            'from_station': from_station,
            'to_station': data['to_station'],
            'amount': total_amount
        })
        
        return jsonify({
            'success': True,
            'supplement': {
                'amount': total_amount,
                'base_price': base_price,
                'fine': fine,
                'service_fee': service_fee
            }
        })
        
    except Exception as e:
        print(f"创建补票失败: {e}")
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/shift/summary')
def api_shift_summary():
    """获取班次统计"""
    if 'shift_id' not in session:
        return jsonify({'error': '请先选择班次'}), 401
    
    conn = get_db_dict_connection()
    if not conn:
        return jsonify({'error': '数据库连接失败'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shifts WHERE shift_id = %s", (session['shift_id'],))
        shift = cursor.fetchone()
        
        if not shift:
            cursor.close()
            conn.close()
            return jsonify({'error': '班次不存在'}), 404
        
        # 获取本班次补票统计
        cursor.execute("""
            SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
            FROM supplement_tickets
            WHERE operator_id = %s AND DATE(supp_time) = CURRENT_DATE
        """, (session['user_id'],))
        supp_stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        supplement_count = supp_stats['count'] if supp_stats else 0
        supplement_amount = float(supp_stats['total']) if supp_stats else 0
        
        return jsonify({
            'shift_id': shift['shift_id'],
            'employee_no': shift['employee_no'],
            'shift_type': shift['shift_type'],
            'shift_name': config.SHIFT_TYPES[shift['shift_type']]['name'],
            'start_time': shift['start_time'].strftime('%Y-%m-%d %H:%M:%S') if shift['start_time'] else '',
            'end_time': shift['end_time'].strftime('%Y-%m-%d %H:%M:%S') if shift['end_time'] else '',
            'ticket_count': shift['ticket_count'] or 0,
            'refund_count': shift['refund_count'] or 0,
            'waste_count': shift['waste_count'] or 0,
            'revenue': shift['revenue'] or 0,
            'refund_amount': shift['refund_amount'] or 0,
            'supplement_count': supplement_count,
            'supplement_amount': supplement_amount,
            'actual_amount': (shift['revenue'] or 0) - (shift['refund_amount'] or 0) + supplement_amount,
            'status': shift['status']
        })
    except Exception as e:
        print(f"获取班次统计失败: {e}")
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/shift/close', methods=['POST'])
def api_shift_close():
    """交班API"""
    if 'shift_id' not in session:
        return jsonify({'success': False, 'error': '请先选择班次'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE shifts SET end_time = %s, status = 'closed', 
            actual_amount = revenue - refund_amount
            WHERE shift_id = %s
        """, (datetime.now(), session['shift_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # 记录操作日志
        log_operation('shift_close', details={
            'ticket_count': 0,
            'revenue': 0,
            'actual_amount': 0
        })
        
        # 清空session中的班次信息
        session.pop('shift_id', None)
        session.pop('shift_type', None)
        session.pop('shift_name', None)
        
        return jsonify({
            'success': True,
            'message': '交班成功'
        })
        
    except Exception as e:
        print(f"交班失败: {e}")
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/operations/logs')
def api_operation_logs():
    """获取操作日志"""
    if 'shift_id' not in session:
        return jsonify([]), 401
    
    conn = get_db_dict_connection()
    if not conn:
        return jsonify([]), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM operation_logs 
            WHERE shift_id = %s
            ORDER BY operation_time DESC
            LIMIT 100
        """, (session['shift_id'],))
        
        logs = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify([{
            'log_id': log['log_id'],
            'operation_type': log['operation_type'],
            'operation_time': log['operation_time'].strftime('%Y-%m-%d %H:%M:%S') if log['operation_time'] else '',
            'ticket_id': log['ticket_id'],
            'details': log['details']
        } for log in logs])
    except Exception as e:
        print(f"获取操作日志失败: {e}")
        conn.close()
        return jsonify([]), 500

# ==================== 页面路由 ====================

@app.route('/ticket/preview')
def ticket_preview():
    """车票预览页面"""
    ticket_id = request.args.get('ticket_id', '')
    
    conn = get_db_dict_connection()
    if not conn:
        return render_template('error.html', message='数据库连接失败')
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE ticket_id = %s", (ticket_id,))
        ticket = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not ticket:
            return render_template('error.html', message='车票不存在')
        
        return render_template('ticket_preview.html', ticket=ticket)
    except Exception as e:
        conn.close()
        return render_template('error.html', message=str(e))

@app.route('/refund')
def refund_page():
    """退票页面"""
    if 'shift_id' not in session:
        return redirect(url_for('shift_select'))
    
    return render_template('refunds/refund.html',
                         system_name=config.SYSTEM_NAME,
                         station_name=session.get('station_name', '郑州站'),
                         window_no=session.get('window_no', '101号口'),
                         shift_name=session.get('shift_name', '白班'),
                         current_time=datetime.now().strftime('%H:%M:%S'))

@app.route('/supplement')
def supplement_page():
    """到达补票页面"""
    if 'shift_id' not in session:
        return redirect(url_for('shift_select'))
    
    return render_template('supplements/supplement.html',
                         system_name=config.SYSTEM_NAME,
                         station_name=session.get('station_name', '郑州站'),
                         window_no=session.get('window_no', '101号口'),
                         shift_name=session.get('shift_name', '白班'),
                         current_time=datetime.now().strftime('%H:%M:%S'),
                         seat_types=config.SEAT_TYPES)

@app.route('/query')
def query_page():
    """余票查询页面"""
    if 'shift_id' not in session:
        return redirect(url_for('shift_select'))
    
    return render_template('queries/query.html',
                         system_name=config.SYSTEM_NAME,
                         station_name=session.get('station_name', '郑州站'),
                         window_no=session.get('window_no', '101号口'),
                         shift_name=session.get('shift_name', '白班'),
                         current_time=datetime.now().strftime('%H:%M:%S'),
                         seat_types=config.SEAT_TYPES)

@app.route('/shift')
def shift_page():
    """交班页面"""
    if 'shift_id' not in session:
        return redirect(url_for('shift_select'))
    
    return render_template('shifts/close.html',
                         system_name=config.SYSTEM_NAME,
                         station_name=session.get('station_name', '郑州站'),
                         window_no=session.get('window_no', '101号口'),
                         shift_name=session.get('shift_name', '白班'),
                         current_time=datetime.now().strftime('%H:%M:%S'))

@app.route('/api/tickets/sold')
def api_sold_tickets():
    """获取已售车票列表"""
    if 'shift_id' not in session:
        return jsonify([])
    
    date = request.args.get('date', '')
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_db_dict_connection()
    if not conn:
        return jsonify([])
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*, s.station_name as from_station_name, e.station_name as to_station_name
            FROM tickets t
            LEFT JOIN stations s ON t.from_station = s.station_code
            LEFT JOIN stations e ON t.to_station = e.station_code
            WHERE t.seller_id = %s AND t.travel_date = %s
            ORDER BY t.sold_at DESC
            LIMIT 100
        """, (session['user_id'], date))
        
        tickets = cursor.fetchall()
        cursor.close()
        conn.close()
        
        result = []
        for t in tickets:
            result.append({
                'ticket_id': t['ticket_id'],
                'train_number': t['train_number'],
                'from_station': t['from_station_name'] or t['from_station'],
                'to_station': t['to_station_name'] or t['to_station'],
                'travel_date': t['travel_date'],
                'departure_time': t['departure_time'],
                'seat_type': t['seat_type'],
                'price': t['price'],
                'status': t['status'],
                'sold_at': t['sold_at'].strftime('%H:%M:%S') if t['sold_at'] else ''
            })
        
        return jsonify(result)
    except Exception as e:
        print(f"获取已售车票失败: {e}")
        conn.close()
        return jsonify([])

# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', message='页面不存在'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', message='服务器错误'), 500

# ==================== 启动应用 ====================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
