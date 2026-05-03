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
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """管理端登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
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
            SELECT COUNT(*) as cnt, SUM(refund_amount) as amount
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
    return redirect(url_for('register_bp.admin_applications'))

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
                INSERT INTO refunds (ticket_id, refund_amount, refund_fee, refund_reason, created_at)
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
            
            # 统计本班次数据
            cursor.execute("""
                SELECT COUNT(*) as cnt, SUM(price) as amount
                FROM tickets WHERE shift_id = ? AND status = 'sold'
            """, (session['shift_id'],))
            ticket_stats = cursor.fetchone()
            
            cursor.execute("""
                SELECT COUNT(*) as cnt, SUM(refund_amount) as amount
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
                    refund_amount = ?
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
            SELECT DISTINCT t.train_id, t.train_number, t.train_type, t.start_station, t.end_station
            FROM trains t
            JOIN train_stops ts1 ON t.train_id = ts1.train_id AND ts1.station_code = ?
            JOIN train_stops ts2 ON t.train_id = ts2.train_id AND ts2.station_code = ?
            WHERE ts1.stop_sequence < ts2.stop_sequence
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

# ==================== 启动应用 ====================

if __name__ == '__main__':
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
