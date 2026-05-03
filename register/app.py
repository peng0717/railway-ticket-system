# -*- coding: utf-8 -*-
"""
铁路客票系统工号注册与审核管理网站
独立Flask应用 - 端口5001
"""

import os
import sqlite3
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# ============== Flask应用配置 ==============
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = secrets.token_hex(32)
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), '..', 'data', 'railway.db')

# 邮件配置
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.qq.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')

# 判断是否为开发模式（未配置邮件）
DEV_MODE = not bool(app.config['MAIL_USERNAME'])


# ============== 数据库工具函数 ==============
def get_db():
    """获取数据库连接"""
    db_path = app.config['DATABASE']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_shared_tables():
    """初始化共享数据库表"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 注册申请表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registration_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            real_name TEXT NOT NULL,
            id_card TEXT NOT NULL,
            email TEXT NOT NULL,
            station_code TEXT NOT NULL,
            username TEXT NOT NULL,
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
            updated_at TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()


# ============== 身份证校验 ==============
def validate_id_card(id_card):
    """校验身份证号合法性（含校验码验证）"""
    if not id_card or len(id_card) != 18:
        return False
    
    # 格式检查
    if not re.match(r'^\d{17}[\dXx]$', id_card):
        return False
    
    # 地区码校验（简化版）
    area_codes = {
        '11': '北京', '12': '天津', '13': '河北', '14': '山西', '15': '内蒙古',
        '21': '辽宁', '22': '吉林', '23': '黑龙江', '31': '上海', '32': '江苏',
        '33': '浙江', '34': '安徽', '35': '福建', '36': '江西', '37': '山东',
        '41': '河南', '42': '湖北', '43': '湖南', '44': '广东', '45': '广西',
        '46': '海南', '50': '重庆', '51': '四川', '52': '贵州', '53': '云南',
        '54': '西藏', '61': '陕西', '62': '甘肃', '63': '青海', '64': '宁夏',
        '65': '新疆', '71': '台湾', '81': '香港', '82': '澳门', '91': '国外'
    }
    if id_card[:2] not in area_codes:
        return False
    
    # 出生日期校验
    birth_date = id_card[6:14]
    try:
        birth = datetime.strptime(birth_date, '%Y%m%d')
        if birth > datetime.now():
            return False
    except:
        return False
    
    # 校验码校验
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_codes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
    
    sum_val = sum(int(id_card[i]) * weights[i] for i in range(17))
    expected_check = check_codes[sum_val % 11]
    
    return id_card[17].upper() == expected_check


def mask_id_card(id_card):
    """身份证号脱敏显示"""
    if len(id_card) == 18:
        return id_card[:3] + '**********' + id_card[-4:]
    return id_card


# ============== 车站查询 ==============
def search_stations(keyword):
    """搜索车站"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT station_id, station_code, station_name, pinyin_code, telecode
        FROM stations
        WHERE station_name LIKE ? OR pinyin_code LIKE ? OR station_code LIKE ? OR telecode LIKE ?
        ORDER BY is_major DESC, station_name
        LIMIT 50
    ''', (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'))
    stations = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return stations


def get_station_by_code(code):
    """根据车站码获取车站信息"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT station_id, station_code, station_name, pinyin_code, telecode
        FROM stations WHERE station_code = ? OR telecode = ?
    ''', (code, code))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ============== 工号生成与校验 ==============
def generate_username(station_code, letters):
    """生成工号：车站码-字母-序号"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 查询该车站已存在的最大序号
    pattern = f'{station_code}-{letters.upper()}-%'
    cursor.execute('''
        SELECT username FROM registration_applications
        WHERE username LIKE ? AND status = 'approved'
        ORDER BY username DESC LIMIT 1
    ''', (pattern,))
    row = cursor.fetchone()
    
    if row:
        # 提取现有序号
        existing = row[0]
        try:
            num = int(existing.split('-')[-1]) + 1
        except:
            num = 1
    else:
        # 查询users表
        pattern2 = f'{station_code}-{letters.upper()}-%'
        cursor.execute('''
            SELECT username FROM users
            WHERE employee_no LIKE ?
            ORDER BY employee_no DESC LIMIT 1
        ''', (pattern2,))
        row2 = cursor.fetchone()
        if row2:
            try:
                num = int(row2[0].split('-')[-1]) + 1
            except:
                num = 1
        else:
            num = 1
    
    conn.close()
    return f'{station_code}-{letters.upper()}-{num:03d}'


def check_username_exists(username):
    """检查工号是否已存在"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 检查registration_applications表
    cursor.execute('SELECT id FROM registration_applications WHERE username = ?', (username,))
    if cursor.fetchone():
        conn.close()
        return True
    
    # 检查users表
    cursor.execute('SELECT user_id FROM users WHERE employee_no = ?', (username,))
    if cursor.fetchone():
        conn.close()
        return True
    
    conn.close()
    return False


# ============== 窗口号检查 ==============
def check_window_available(station_code, window_no):
    """检查窗口号是否可用"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 检查users表
    cursor.execute('''
        SELECT user_id FROM users 
        WHERE station_code = ? AND window_no = ? AND status != 'banned'
    ''', (station_code, str(window_no)))
    if cursor.fetchone():
        conn.close()
        return False, '该窗口已被占用'
    
    # 检查pending的申请
    cursor.execute('''
        SELECT id FROM registration_applications
        WHERE station_code = ? AND window_no = ? AND status IN ('pending', 'approved')
    ''', (station_code, window_no))
    if cursor.fetchone():
        conn.close()
        return False, '该窗口有待审核的申请'
    
    conn.close()
    return True, '可用'


# ============== 邮箱验证 ==============
def send_verification_code(email):
    """发送验证码"""
    code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    expires_at = datetime.now() + timedelta(minutes=5)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # 标记旧验证码为已过期
    cursor.execute('UPDATE email_verifications SET expires_at = ? WHERE email = ?', 
                   (datetime.now() - timedelta(minutes=1), email))
    
    # 插入新验证码
    cursor.execute('''
        INSERT INTO email_verifications (email, code, expires_at)
        VALUES (?, ?, ?)
    ''', (email, code, expires_at))
    
    conn.commit()
    conn.close()
    
    return code


def verify_code(email, code):
    """验证验证码"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT code FROM email_verifications
        WHERE email = ? AND verified = 0 AND expires_at > ?
        ORDER BY id DESC LIMIT 1
    ''', (email, datetime.now()))
    row = cursor.fetchone()
    
    if row and row[0] == code:
        cursor.execute('UPDATE email_verifications SET verified = 1 WHERE email = ?', (email,))
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False


def check_email_exists(email):
    """检查邮箱是否已注册"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM registration_applications WHERE email = ?', (email,))
    if cursor.fetchone():
        conn.close()
        return True
    
    # 也检查users表
    cursor.execute('SELECT user_id FROM users WHERE name LIKE ?', (f'%{email}%',))
    if cursor.fetchone():
        conn.close()
        return True
    
    conn.close()
    return False


def check_id_card_exists(id_card):
    """检查身份证号是否已注册"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM registration_applications WHERE id_card = ?', (id_card,))
    if cursor.fetchone():
        conn.close()
        return True
    
    conn.close()
    return False


# ============== 邮件发送 ==============
def send_email(subject, to_email, body):
    """发送邮件"""
    if DEV_MODE:
        print(f"[DEV MODE] 邮件主题: {subject}")
        print(f"[DEV MODE] 收件人: {to_email}")
        print(f"[DEV MODE] 邮件内容: {body}")
        return True
    
    try:
        from flask_mail import Mail, Message
        mail = Mail(app)
        msg = Message(subject, recipients=[to_email], body=body)
        mail.send(msg)
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False


# ============== 用户创建 ==============
def create_user_from_application(app_id):
    """从申请创建正式用户"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM registration_applications WHERE id = ?', (app_id,))
    app_data = cursor.fetchone()
    
    if not app_data:
        conn.close()
        return False, '申请不存在'
    
    # 创建users表记录
    cursor.execute('''
        INSERT INTO users (employee_no, name, password_hash, role, window_no, station_code, status, created_at)
        VALUES (?, ?, ?, 'seller', ?, ?, 'active', ?)
    ''', (
        app_data['username'],
        app_data['real_name'],
        app_data['password_hash'],
        f"{app_data['window_no']}号口",
        app_data['station_code'],
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))
    
    user_id = cursor.lastrowid
    
    # 创建机器码绑定
    cursor.execute('''
        INSERT INTO machine_bindings (user_id, machine_code)
        VALUES (?, ?)
    ''', (user_id, app_data['machine_code']))
    
    # 更新申请状态
    cursor.execute('''
        UPDATE registration_applications
        SET status = 'approved', reviewed_at = ?, reviewed_by = 0
        WHERE id = ?
    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), app_id))
    
    conn.commit()
    conn.close()
    return True, user_id


# ============== 风控操作 ==============
def freeze_user(user_id, username, original_code, new_code, reason='异地登录'):
    """冻结用户"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 更新用户状态
    cursor.execute("UPDATE users SET status = 'frozen' WHERE user_id = ?", (user_id,))
    
    # 记录风控
    cursor.execute('''
        INSERT INTO risk_controls (user_id, username, original_machine_code, new_machine_code, action, reason)
        VALUES (?, ?, ?, ?, 'freeze', ?)
    ''', (user_id, username, original_code, new_code, reason))
    
    conn.commit()
    conn.close()


def unfreeze_user(user_id, operator_id=None):
    """解冻用户"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 获取用户信息
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return False, '用户不存在'
    
    # 获取最新的风控记录中的新机器码
    cursor.execute('''
        SELECT new_machine_code FROM risk_controls
        WHERE user_id = ? AND action = 'freeze'
        ORDER BY created_at DESC LIMIT 1
    ''', (user_id,))
    row = cursor.fetchone()
    new_code = row[0] if row else ''
    
    # 更新用户状态
    cursor.execute("UPDATE users SET status = 'active' WHERE user_id = ?", (user_id,))
    
    # 更新机器码绑定
    cursor.execute('''
        INSERT OR REPLACE INTO machine_bindings (user_id, machine_code, updated_at)
        VALUES (?, ?, ?)
    ''', (user_id, new_code, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    # 记录解冻操作
    cursor.execute('''
        INSERT INTO risk_controls (user_id, username, original_machine_code, new_machine_code, action, operated_by)
        VALUES (?, ?, ?, ?, 'unfreeze', ?)
    ''', (user_id, user['employee_no'], new_code, new_code, operator_id))
    
    conn.commit()
    conn.close()
    return True, '解冻成功'


def ban_user(user_id, operator_id=None):
    """永久封禁用户"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE users SET status = 'banned' WHERE user_id = ?", (user_id,))
    
    # 获取用户信息
    cursor.execute('SELECT employee_no FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    # 记录封禁操作
    if user:
        cursor.execute('''
            INSERT INTO risk_controls (user_id, username, original_machine_code, new_machine_code, action, operated_by)
            VALUES (?, ?, '', '', 'ban', ?)
        ''', (user_id, user['employee_no'], operator_id))
    
    conn.commit()
    conn.close()


def get_machine_code(user_id):
    """获取用户绑定的机器码"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT machine_code FROM machine_bindings WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


# ============== 登录验证 ==============
def verify_login_employee(employee_no, password):
    """验证员工登录"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, employee_no, name, password_hash, status, station_code, window_no, role
        FROM users WHERE employee_no = ?
    ''', (employee_no,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return None, '工号不存在'
    
    if not check_password_hash(user['password_hash'], password):
        return None, '密码错误'
    
    if user['status'] == 'banned':
        return None, '该工号已被永久封禁'
    
    if user['status'] == 'frozen':
        return None, '该工号因异地登录已被风控冻结，请联系管理员'
    
    return dict(user), None


# ============== 管理端认证装饰器 ==============
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_id'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


# ============== 路由定义 ==============

# 首页/注册页面
@app.route('/')
def index():
    return render_template('register.html', dev_mode=DEV_MODE)


# API: 搜索车站
@app.route('/api/search_stations')
def api_search_stations():
    keyword = request.args.get('q', '').strip()
    if len(keyword) < 1:
        return jsonify([])
    stations = search_stations(keyword)
    return jsonify(stations)


# API: 发送验证码
@app.route('/api/send_code', methods=['POST'])
def api_send_code():
    email = request.json.get('email', '').strip()
    
    if not email or not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        return jsonify({'success': False, 'message': '邮箱格式不正确'})
    
    if check_email_exists(email):
        return jsonify({'success': False, 'message': '该邮箱已被注册'})
    
    code = send_verification_code(email)
    
    if DEV_MODE:
        return jsonify({
            'success': True, 
            'message': f'开发模式：验证码为 {code}',
            'dev_code': code
        })
    else:
        subject = '铁路客票系统工号注册验证码'
        body = f'您的验证码是：{code}，5分钟内有效。请勿告知他人。'
        if send_email(subject, email, body):
            return jsonify({'success': True, 'message': '验证码已发送到您的邮箱'})
        else:
            return jsonify({'success': False, 'message': '邮件发送失败'})


# API: 验证验证码
@app.route('/api/verify_code', methods=['POST'])
def api_verify_code():
    email = request.json.get('email', '').strip()
    code = request.json.get('code', '').strip()
    
    if not email or not code:
        return jsonify({'success': False, 'message': '参数不完整'})
    
    if verify_code(email, code):
        return jsonify({'success': True, 'message': '验证通过'})
    else:
        return jsonify({'success': False, 'message': '验证码错误或已过期'})


# API: 验证身份证
@app.route('/api/validate_id_card', methods=['POST'])
def api_validate_id_card():
    id_card = request.json.get('id_card', '').strip()
    
    if not validate_id_card(id_card):
        return jsonify({'success': False, 'message': '身份证号格式不正确'})
    
    if check_id_card_exists(id_card):
        return jsonify({'success': False, 'message': '该身份证号已注册'})
    
    return jsonify({'success': True, 'message': '身份证验证通过'})


# API: 验证工号字母部分
@app.route('/api/check_letters', methods=['POST'])
def api_check_letters():
    station_code = request.json.get('station_code', '').strip()
    letters = request.json.get('letters', '').strip()
    
    if not station_code or not letters:
        return jsonify({'success': False, 'message': '参数不完整'})
    
    if not re.match(r'^[A-Z]{2,3}$', letters.upper()):
        return jsonify({'success': False, 'message': '工号字母必须是2-3位大写字母'})
    
    username = generate_username(station_code, letters)
    exists = check_username_exists(username)
    
    return jsonify({
        'success': True,
        'username': username,
        'exists': exists
    })


# API: 验证窗口号
@app.route('/api/check_window', methods=['POST'])
def api_check_window():
    station_code = request.json.get('station_code', '').strip()
    window_no = request.json.get('window_no')
    
    try:
        window_no = int(window_no)
        if window_no < 1 or window_no > 20:
            return jsonify({'success': False, 'message': '窗口号必须在1-20之间'})
    except:
        return jsonify({'success': False, 'message': '窗口号格式不正确'})
    
    available, msg = check_window_available(station_code, window_no)
    
    return jsonify({
        'success': available,
        'message': msg
    })


# API: 提交注册
@app.route('/api/submit_register', methods=['POST'])
def api_submit_register():
    data = request.json
    
    # 验证所有必填字段
    required = ['real_name', 'id_card', 'email', 'station_code', 'username', 
                'window_no', 'password', 'machine_code', 'code_verified']
    
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'缺少字段: {field}'})
    
    # 再次验证身份证
    if not validate_id_card(data['id_card']):
        return jsonify({'success': False, 'message': '身份证号验证失败'})
    
    if check_id_card_exists(data['id_card']):
        return jsonify({'success': False, 'message': '该身份证号已注册'})
    
    # 验证邮箱
    if check_email_exists(data['email']):
        return jsonify({'success': False, 'message': '该邮箱已被注册'})
    
    # 验证验证码
    if not verify_code(data['email'], data['code_verified']):
        return jsonify({'success': False, 'message': '验证码验证失败，请重新验证'})
    
    # 验证工号唯一性
    if check_username_exists(data['username']):
        return jsonify({'success': False, 'message': '工号已被占用'})
    
    # 验证窗口号
    available, msg = check_window_available(data['station_code'], int(data['window_no']))
    if not available:
        return jsonify({'success': False, 'message': msg})
    
    # 密码哈希
    password_hash = generate_password_hash(data['password'])
    
    # 保存申请
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO registration_applications (
            real_name, id_card, email, station_code, username, window_no,
            password_hash, machine_code, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
    ''', (
        data['real_name'],
        data['id_card'],
        data['email'],
        data['station_code'],
        data['username'],
        int(data['window_no']),
        password_hash,
        data['machine_code']
    ))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'message': '注册申请已提交，请等待管理员审核'
    })


# ============== 管理端路由 ==============

# 管理端登录
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, employee_no, password_hash, role
            FROM users WHERE employee_no = ? AND role = 'admin'
        ''', (username,))
        admin = cursor.fetchone()
        conn.close()
        
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_id'] = admin['user_id']
            session['admin_name'] = admin['employee_no']
            return redirect(url_for('admin_dashboard'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')


# 管理端登出
@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


# 管理端首页
@app.route('/admin/dashboard')
@admin_login_required
def admin_dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    # 统计
    cursor.execute("SELECT COUNT(*) FROM registration_applications WHERE status = 'pending'")
    pending_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM registration_applications WHERE status = 'approved'")
    approved_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM registration_applications WHERE status = 'rejected'")
    rejected_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'frozen'")
    frozen_count = cursor.fetchone()[0]
    
    # 最近申请
    cursor.execute('''
        SELECT ra.*, s.station_name 
        FROM registration_applications ra
        LEFT JOIN stations s ON ra.station_code = s.station_code
        ORDER BY ra.created_at DESC LIMIT 5
    ''')
    recent_applications = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('admin/dashboard.html',
                           pending_count=pending_count,
                           approved_count=approved_count,
                           rejected_count=rejected_count,
                           frozen_count=frozen_count,
                           recent_applications=recent_applications)


# 审核列表
@app.route('/admin/applications')
@app.route('/admin/applications/<status_filter>')
@admin_login_required
def admin_applications(status_filter='pending'):
    conn = get_db()
    cursor = conn.cursor()
    
    # 构建查询
    where_clause = ""
    params = []
    
    if status_filter != 'all':
        where_clause = "WHERE ra.status = ?"
        params = [status_filter]
    
    cursor.execute(f'''
        SELECT ra.*, s.station_name 
        FROM registration_applications ra
        LEFT JOIN stations s ON ra.station_code = s.station_code
        {where_clause}
        ORDER BY ra.created_at DESC
    ''', params)
    applications = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('admin/applications.html',
                           applications=applications,
                           current_filter=status_filter)


# 审核操作
@app.route('/admin/review/<int:app_id>/<action>', methods=['POST'])
@admin_login_required
def admin_review(app_id, action):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM registration_applications WHERE id = ?', (app_id,))
    app = cursor.fetchone()
    
    if not app:
        conn.close()
        return jsonify({'success': False, 'message': '申请不存在'})
    
    if action == 'approve':
        # 创建用户
        success, result = create_user_from_application(app_id)
        if success:
            flash(f'已通过申请，工号：{app["username"]}', 'success')
        else:
            flash(f'操作失败：{result}', 'error')
    
    elif action == 'reject':
        reason = request.form.get('reason', '').strip()
        cursor.execute('''
            UPDATE registration_applications
            SET status = 'rejected', reject_reason = ?, reviewed_at = ?, reviewed_by = ?
            WHERE id = ?
        ''', (reason, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session['admin_id'], app_id))
        conn.commit()
        flash(f'已拒绝申请', 'warning')
    
    conn.close()
    return redirect(url_for('admin_applications'))


# 风控管理
@app.route('/admin/risk')
@admin_login_required
def admin_risk():
    conn = get_db()
    cursor = conn.cursor()
    
    # 获取被冻结的用户
    cursor.execute('''
        SELECT u.*, mb.machine_code as bound_machine_code
        FROM users u
        LEFT JOIN machine_bindings mb ON u.user_id = mb.user_id
        WHERE u.status = 'frozen'
        ORDER BY u.user_id DESC
    ''')
    frozen_users = [dict(row) for row in cursor.fetchall()]
    
    # 获取风控记录
    cursor.execute('''
        SELECT rc.*, u.name as user_name
        FROM risk_controls rc
        LEFT JOIN users u ON rc.user_id = u.user_id
        ORDER BY rc.created_at DESC
        LIMIT 100
    ''')
    risk_records = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('admin/risk.html',
                           frozen_users=frozen_users,
                           risk_records=risk_records)


# 风控操作
@app.route('/admin/risk/<int:user_id>/<action>', methods=['POST'])
@admin_login_required
def admin_risk_action(user_id, action):
    if action == 'unfreeze':
        success, msg = unfreeze_user(user_id, session['admin_id'])
        if success:
            flash('已解冻该工号', 'success')
        else:
            flash(f'解冻失败：{msg}', 'error')
    elif action == 'ban':
        ban_user(user_id, session['admin_id'])
        flash('已永久封禁该工号', 'danger')
    
    return redirect(url_for('admin_risk'))


# 用户管理
@app.route('/admin/users')
@admin_login_required
def admin_users():
    status_filter = request.args.get('status', 'all')
    search = request.args.get('search', '').strip()
    
    conn = get_db()
    cursor = conn.cursor()
    
    where_clause = ""
    params = []
    
    conditions = []
    if status_filter != 'all':
        conditions.append("u.status = ?")
        params.append(status_filter)
    if search:
        conditions.append("(u.employee_no LIKE ? OR u.name LIKE ?)")
        params.extend([f'%{search}%', f'%{search}%'])
    
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)
    
    cursor.execute(f'''
        SELECT u.*, mb.machine_code as bound_machine_code, s.station_name
        FROM users u
        LEFT JOIN machine_bindings mb ON u.user_id = mb.user_id
        LEFT JOIN stations s ON u.station_code = s.station_code
        {where_clause}
        ORDER BY u.user_id DESC
    ''', params)
    users = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('admin/users.html',
                           users=users,
                           current_status=status_filter,
                           search=search)


# 修改用户状态
@app.route('/admin/users/<int:user_id>/status', methods=['POST'])
@admin_login_required
def admin_update_user_status(user_id):
    new_status = request.form.get('status', '').strip()
    
    if new_status not in ['active', 'frozen', 'banned']:
        return jsonify({'success': False, 'message': '无效的状态'})
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET status = ? WHERE user_id = ?', (new_status, user_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': f'状态已更新为{new_status}'})


# 重置密码
@app.route('/admin/users/<int:user_id>/reset_password', methods=['POST'])
@admin_login_required
def admin_reset_password(user_id):
    new_password = request.form.get('password', '').strip()
    
    if len(new_password) < 8:
        return jsonify({'success': False, 'message': '密码至少8位'})
    
    password_hash = generate_password_hash(new_password)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET password_hash = ? WHERE user_id = ?', (password_hash, user_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': '密码已重置'})


# ============== 启动应用 ==============
if __name__ == '__main__':
    # 初始化数据库表
    init_shared_tables()
    
    # 启动Flask应用
    port = int(os.environ.get('PORT', 5001))
    print(f"=" * 60)
    print(f"铁路客票系统工号注册与审核管理网站")
    print(f"=" * 60)
    print(f"注册页面: http://localhost:{port}/")
    print(f"管理端:    http://localhost:{port}/admin/login")
    print(f"默认管理员: admin / admin123")
    print(f"邮件模式:  {'开发模式' if DEV_MODE else '生产模式'}")
    print(f"=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=True)
