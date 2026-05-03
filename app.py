# -*- coding: utf-8 -*-
"""
WebTRS 应用入口
模拟铁路车站人工售票系统
使用SQLite数据库
集成注册审核系统 (Flask Blueprint)
"""

import os
import json
import random
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, session, redirect, url_for, request, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# 导入配置
import config

# 创建Flask应用
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# 注册 Blueprint
from blueprints.register_bp import register_bp
app.register_blueprint(register_bp, url_prefix='/register')

# ==================== 数据库路径 ====================

def get_db_path():
    """获取数据库路径"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, 'data', 'railway.db')

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

def get_user_by_employee_no(employee_no):
    """根据工号获取用户"""
    conn = get_db_dict_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (employee_no,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
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
            SET machine_code = ?, status = ?, last_login = ?
            WHERE id = ?
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
        # SQLite: 使用事务
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

def calculate_price(from_station, to_station, seat_type):
    """计算票价"""
    conn = get_db_dict_connection()
    if not conn:
        return 200
    
    try:
        cursor = conn.cursor()
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
                        session['employee_no'] = user['username']
                        session['user_name'] = user.get('real_name') or user.get('name', '')
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
    
    # 确定当前班次
    current_hour = datetime.now().hour
    default_shift = 'night' if 12 <= current_hour < 24 else 'day'
    
    return render_template('shift_select.html', 
                           default_shift=default_shift,
                           system_name=config.SYSTEM_NAME)

@app.route('/main')
@login_required
def main():
    """主页面"""
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
        
        # 这里应该调用实际的售票逻辑
        return render_template('sell.html',
                               success='售票功能开发中',
                               system_name=config.SYSTEM_NAME)
    
    return render_template('sell.html', system_name=config.SYSTEM_NAME)

@app.route('/query')
@login_required
def query():
    """查询页面"""
    return render_template('query.html', system_name=config.SYSTEM_NAME)

@app.route('/ refund')
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
            cursor.execute("""
                UPDATE shifts SET status = 'closed', end_time = ? WHERE shift_id = ?
            """, (datetime.now().isoformat(), session['shift_id']))
            conn.commit()
            cursor.close()
            conn.close()
            
            log_operation('shift_close')
            
            # 清除班次相关session
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

@app.route('/api/search-trains')
@login_required
def api_search_trains():
    """搜索车次"""
    from_station = request.args.get('from', '').strip()
    to_station = request.args.get('to', '').strip()
    date = request.args.get('date', '').strip()
    
    if not from_station or not to_station:
        return jsonify({'status': 'error', 'message': '请选择出发地和目的地'})
    
    conn = get_db_dict_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': '数据库连接失败'})
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT t.train_no, t.train_type, t.start_station, t.end_station
            FROM trains t
            JOIN train_stops ts1 ON t.train_no = ts1.train_no AND ts1.station_code = ?
            JOIN train_stops ts2 ON t.train_no = ts2.train_no AND ts2.station_code = ?
            WHERE ts1.stop_order < ts2.stop_order
            LIMIT 20
        """, (from_station, to_station))
        
        trains = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'data': list(trains)})
    except Exception as e:
        print(f"搜索车次失败: {e}")
        if conn:
            conn.close()
        return jsonify({'status': 'error', 'message': '搜索车次失败'})

# ==================== 启动应用 ====================

if __name__ == '__main__':
    # 确保数据目录存在
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    # 运行应用
    app.run(host='0.0.0.0', port=5000, debug=True)
