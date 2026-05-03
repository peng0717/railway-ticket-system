# -*- coding: utf-8 -*-
"""
注册审核系统路由
集成到铁路售票系统 Blueprint
"""

import os
import sqlite3
import random
import string
import re
from datetime import datetime, timedelta
from functools import wraps

from flask import render_template, request, jsonify, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from . import register_bp
from .utils import (
    validate_id_card, validate_email, validate_password, validate_username,
    generate_verification_code, mask_id_card, is_code_expired
)


# ==================== 数据库连接 ====================

def get_db_connection():
    """获取SQLite数据库连接"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'railway.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_dict_connection():
    """获取返回字典的数据库连接"""
    conn = get_db_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    return conn


# ==================== 管理员认证装饰器 ====================

def admin_required(f):
    """管理员登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('register_bp.admin_login'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== 公开页面路由 ====================

@register_bp.route('/')
def index():
    """注册页面入口"""
    return render_template('register.html')


@register_bp.route('/check-db')
def check_db():
    """检查数据库连接"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.close()
        conn.close()
        return jsonify({
            'status': 'success',
            'message': '数据库连接正常'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'数据库连接失败: {str(e)}'
        })


# ==================== 注册API ====================

@register_bp.route('/api/check-id-card', methods=['POST'])
def check_id_card():
    """检查身份证号是否已注册"""
    data = request.get_json()
    id_card = data.get('id_card', '').strip()
    
    if not validate_id_card(id_card):
        return jsonify({'status': 'error', 'message': '身份证号格式不正确'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 检查已注册用户
    cursor.execute("SELECT id FROM users WHERE id_card = ?", (id_card,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '该身份证号已注册'})
    
    # 检查待审核申请
    cursor.execute("SELECT id FROM registration_applications WHERE id_card = ? AND status != 'rejected'", (id_card,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '该身份证号已有待审核的申请'})
    
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success', 'message': '身份证号可用'})


@register_bp.route('/api/check-email', methods=['POST'])
def check_email():
    """检查邮箱是否已注册"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    
    if not validate_email(email):
        return jsonify({'status': 'error', 'message': '邮箱格式不正确'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 检查已注册用户
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '该邮箱已注册'})
    
    # 检查待审核申请
    cursor.execute("SELECT id FROM registration_applications WHERE email = ? AND status != 'rejected'", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '该邮箱已有待审核的申请'})
    
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success', 'message': '邮箱可用'})


@register_bp.route('/api/send-verification-code', methods=['POST'])
def send_verification_code():
    """发送邮箱验证码"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    
    if not validate_email(email):
        return jsonify({'status': 'error', 'message': '邮箱格式不正确'})
    
    # 生成6位验证码
    code = generate_verification_code()
    expires_at = datetime.now() + timedelta(minutes=5)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 删除该邮箱的旧验证码
    cursor.execute("DELETE FROM email_verifications WHERE email = ?", (email,))
    
    # 插入新验证码
    cursor.execute("""
        INSERT INTO email_verifications (email, code, expires_at)
        VALUES (?, ?, ?)
    """, (email, code, expires_at.isoformat()))
    
    conn.commit()
    
    # 开发模式：直接返回验证码
    # 生产环境可以配置邮件发送
    mail_server = os.getenv('MAIL_SERVER')
    if mail_server:
        # 实际发送邮件的逻辑可以在这里实现
        message = '验证码已发送到您的邮箱'
    else:
        message = f'开发模式: 验证码是 {code}'
        print(f"[开发模式] 向 {email} 发送验证码: {code}")
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'message': message,
        'dev_code': code if not mail_server else None
    })


@register_bp.route('/api/verify-code', methods=['POST'])
def verify_code():
    """验证邮箱验证码"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id FROM email_verifications
        WHERE email = ? AND code = ? AND verified = 0
        ORDER BY created_at DESC LIMIT 1
    """, (email, code))
    record = cursor.fetchone()
    
    if record:
        # 检查是否过期
        cursor.execute("SELECT expires_at FROM email_verifications WHERE id = ?", (record['id'],))
        expires_str = cursor.fetchone()['expires_at']
        
        if is_code_expired(expires_str):
            cursor.close()
            conn.close()
            return jsonify({'status': 'error', 'message': '验证码已过期'})
        
        # 标记为已验证
        cursor.execute("UPDATE email_verifications SET verified = 1 WHERE id = ?", (record['id'],))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'message': '验证成功'})
    
    cursor.close()
    conn.close()
    return jsonify({'status': 'error', 'message': '验证码无效或已过期'})


@register_bp.route('/api/search-stations', methods=['GET'])
def search_stations():
    """搜索车站"""
    keyword = request.args.get('q', '').strip()
    
    if len(keyword) < 1:
        return jsonify({'status': 'error', 'message': '请输入搜索关键词'})
    
    conn = get_db_dict_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT station_name, station_code, COALESCE(pinyin_code, '') as pinyin_code
        FROM stations
        WHERE (station_name LIKE ? OR pinyin_code LIKE ? OR station_code LIKE ?)
        ORDER BY 
            CASE WHEN station_name LIKE ? THEN 0 ELSE 1 END,
            CASE WHEN pinyin_code LIKE ? THEN 0 ELSE 1 END
        LIMIT 20
    """, (f'%{keyword}%', f'{keyword}%', f'{keyword}%', f'{keyword}%', f'{keyword}%'))
    
    stations = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success', 'data': list(stations)})


@register_bp.route('/api/check-username', methods=['POST'])
def check_username():
    """检查工号是否可用"""
    data = request.get_json()
    username = data.get('username', '').strip().upper()
    
    # 验证格式
    if not validate_username(username):
        return jsonify({'status': 'error', 'message': '工号格式不正确，应为 XXX-XX-000 格式'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 检查已注册用户
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '该工号已被使用'})
    
    # 检查待审核申请
    cursor.execute("SELECT id FROM registration_applications WHERE username = ? AND status != 'rejected'", (username,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '该工号已有待审核的申请'})
    
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success', 'message': '工号可用'})


@register_bp.route('/api/check-window', methods=['POST'])
def check_window():
    """检查窗口号是否可用"""
    data = request.get_json()
    station_code = data.get('station_code', '').strip()
    window_no = data.get('window_no', 0)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id FROM users 
        WHERE station_code = ? AND window_no = ? AND status = 'active'
    """, (station_code, window_no))
    exists = cursor.fetchone()
    
    if exists:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '该窗口已被占用'})
    
    cursor.close()
    conn.close()
    return jsonify({'status': 'success', 'message': '窗口可用'})


@register_bp.route('/api/submit-registration', methods=['POST'])
def submit_registration():
    """提交注册申请"""
    data = request.get_json()
    
    # 验证所有必填字段
    required_fields = ['real_name', 'id_card', 'email', 'station_code', 
                       'username', 'window_no', 'password', 'machine_code']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'status': 'error', 'message': f'缺少必填字段: {field}'})
    
    # 验证身份证号
    if not validate_id_card(data['id_card']):
        return jsonify({'status': 'error', 'message': '身份证号格式不正确'})
    
    # 验证邮箱
    if not validate_email(data['email']):
        return jsonify({'status': 'error', 'message': '邮箱格式不正确'})
    
    # 验证密码
    if not validate_password(data['password']):
        return jsonify({'status': 'error', 'message': '密码必须8-20位，包含字母和数字'})
    
    # 验证工号格式
    username = data['username'].strip().upper()
    if not validate_username(username):
        return jsonify({'status': 'error', 'message': '工号格式不正确，应为 XXX-XX-000 格式'})
    
    # 验证窗口号
    window_no = int(data['window_no'])
    if window_no < 1 or window_no > 20:
        return jsonify({'status': 'error', 'message': '窗口号必须在1-20之间'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 检查重复 - 用户表
    cursor.execute("SELECT id FROM users WHERE id_card = ? OR email = ? OR username = ?",
                   (data['id_card'], data['email'].lower(), username))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '身份证号、邮箱或工号已存在'})
    
    # 检查注册申请
    cursor.execute("""
        SELECT id FROM registration_applications 
        WHERE (id_card = ? OR email = ? OR username = ?) AND status != 'rejected'
    """, (data['id_card'], data['email'].lower(), username))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '您已有待审核或已通过的申请'})
    
    # 检查窗口号占用
    cursor.execute("""
        SELECT id FROM users 
        WHERE station_code = ? AND window_no = ? AND status = 'active'
    """, (data['station_code'], window_no))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '该窗口已被占用'})
    
    # 生成密码哈希
    password_hash = generate_password_hash(data['password'])
    
    # 插入注册申请
    try:
        cursor.execute("""
            INSERT INTO registration_applications 
            (real_name, id_card, email, station_code, username, window_no, password_hash, machine_code, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            data['real_name'],
            data['id_card'],
            data['email'].lower(),
            data['station_code'],
            username,
            window_no,
            password_hash,
            data['machine_code'],
            datetime.now().isoformat()
        ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': f'注册失败: {str(e)}'})
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'message': '注册申请已提交，请等待管理员审核',
        'username': username
    })


# ==================== 管理端路由 ====================

@register_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """管理端登录"""
    if session.get('admin_logged_in'):
        return redirect(url_for('register_bp.admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        admin_username = os.getenv('ADMIN_USERNAME', 'admin')
        admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
        
        if username == admin_username and password == admin_password:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return redirect(url_for('register_bp.admin_dashboard'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('admin/login.html')


@register_bp.route('/admin/logout')
def admin_logout():
    """管理端登出"""
    session.clear()
    return redirect(url_for('register_bp.admin_login'))


@register_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """管理首页"""
    conn = get_db_dict_connection()
    
    stats = {}
    recent = []
    
    if conn:
        cursor = conn.cursor()
        
        # 统计待审核
        cursor.execute("SELECT COUNT(*) as cnt FROM registration_applications WHERE status = 'pending'")
        stats['pending'] = cursor.fetchone().get('cnt', 0) if cursor.fetchone() else 0
        
        # 统计已通过
        cursor.execute("SELECT COUNT(*) as cnt FROM registration_applications WHERE status = 'approved'")
        stats['approved'] = cursor.fetchone().get('cnt', 0) if cursor.fetchone() else 0
        
        # 统计已拒绝
        cursor.execute("SELECT COUNT(*) as cnt FROM registration_applications WHERE status = 'rejected'")
        stats['rejected'] = cursor.fetchone().get('cnt', 0) if cursor.fetchone() else 0
        
        # 统计已冻结
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE status = 'frozen'")
        stats['frozen'] = cursor.fetchone().get('cnt', 0) if cursor.fetchone() else 0
        
        # 最近申请
        cursor.execute("""
            SELECT id, real_name, id_card, email, station_code, username, window_no, 
                   machine_code, created_at, status
            FROM registration_applications
            ORDER BY created_at DESC
            LIMIT 10
        """)
        recent = cursor.fetchall()
        
        cursor.close()
        conn.close()
    
    return render_template('admin/dashboard.html', stats=stats, recent=recent)


@register_bp.route('/admin/applications')
@admin_required
def admin_applications():
    """审核列表"""
    status_filter = request.args.get('status', 'all')
    search = request.args.get('search', '').strip()
    
    conn = get_db_dict_connection()
    applications = []
    
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
        
        cursor.close()
        conn.close()
    
    return render_template('admin/applications.html', 
                           applications=applications, 
                           status_filter=status_filter,
                           search=search)


@register_bp.route('/admin/api/approve-application', methods=['POST'])
@admin_required
def approve_application():
    """审核通过申请"""
    data = request.get_json()
    application_id = data.get('id')
    
    if not application_id:
        return jsonify({'status': 'error', 'message': '缺少申请ID'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 获取申请信息
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
        # 创建用户
        cursor.execute("""
            INSERT INTO users 
            (username, password_hash, real_name, id_card, email, role, station_code, 
             window_no, machine_code, status)
            VALUES (?, ?, ?, ?, ?, 'seller', ?, ?, ?, 'active')
        """, (
            app['username'], app['password_hash'], app['real_name'], app['id_card'],
            app['email'], app['station_code'], app['window_no'], app['machine_code']
        ))
        
        # 获取新创建用户的ID
        user_id = cursor.lastrowid
        
        # 更新申请状态
        cursor.execute("""
            UPDATE registration_applications
            SET status = 'approved', reviewed_at = ?, reviewed_by = 0
            WHERE id = ?
        """, (datetime.now().isoformat(), application_id))
        
        # 绑定机器码
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


@register_bp.route('/admin/api/reject-application', methods=['POST'])
@admin_required
def reject_application():
    """拒绝申请"""
    data = request.get_json()
    application_id = data.get('id')
    reason = data.get('reason', '').strip()
    
    if not application_id:
        return jsonify({'status': 'error', 'message': '缺少申请ID'})
    
    if not reason:
        return jsonify({'status': 'error', 'message': '请输入拒绝原因'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
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


@register_bp.route('/admin/risk')
@admin_required
def admin_risk():
    """风控管理"""
    conn = get_db_dict_connection()
    records = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rc.*, u.real_name, u.username
            FROM risk_controls rc
            LEFT JOIN users u ON rc.user_id = u.id
            ORDER BY rc.created_at DESC
            LIMIT 100
        """)
        records = cursor.fetchall()
        cursor.close()
        conn.close()
    
    return render_template('admin/risk.html', records=records)


@register_bp.route('/admin/api/unfreeze-user', methods=['POST'])
@admin_required
def unfreeze_user():
    """解冻用户"""
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'error', 'message': '缺少用户ID'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE users SET status = 'active' WHERE id = ?", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'success', 'message': '用户已解冻'})
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': f'操作失败: {str(e)}'})


@register_bp.route('/admin/users')
@admin_required
def admin_users():
    """用户管理"""
    search = request.args.get('search', '').strip()
    
    conn = get_db_dict_connection()
    users = []
    
    if conn:
        cursor = conn.cursor()
        
        if search:
            cursor.execute("""
                SELECT id, username, real_name, station_code, window_no, role, status, machine_code, last_login
                FROM users
                WHERE username LIKE ? OR real_name LIKE ? OR station_code LIKE ?
                ORDER BY id DESC
                LIMIT 100
            """, (f'%{search}%', f'%{search}%', f'%{search}%'))
        else:
            cursor.execute("""
                SELECT id, username, real_name, station_code, window_no, role, status, machine_code, last_login
                FROM users
                ORDER BY id DESC
                LIMIT 100
            """)
        
        users = cursor.fetchall()
        cursor.close()
        conn.close()
    
    return render_template('admin/users.html', users=users, search=search)


@register_bp.route('/admin/api/freeze-user', methods=['POST'])
@admin_required
def freeze_user():
    """冻结用户"""
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'status': 'error', 'message': '缺少用户ID'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE users SET status = 'frozen' WHERE id = ?", (user_id,))
        
        # 记录风控
        cursor.execute("""
            INSERT INTO risk_controls (user_id, username, original_machine_code, new_machine_code, action, reason, created_at)
            SELECT id, username, machine_code, '', 'manual_freeze', '管理员手动冻结', ?
            FROM users WHERE id = ?
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
