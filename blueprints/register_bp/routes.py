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
import smtplib
from datetime import datetime, timedelta
from functools import wraps
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

from flask import render_template, request, jsonify, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from . import register_bp
from .utils import (
    validate_id_card, validate_email, validate_password, validate_username,
    generate_verification_code, mask_id_card, is_code_expired
)


# ==================== 邮件配置 ====================

# 邮件发送配置（从环境变量读取或使用默认值）
MAIL_CONFIG = {
    'smtp_server': os.getenv('MAIL_SMTP_SERVER', 'smtp.qq.com'),
    'smtp_port': int(os.getenv('MAIL_SMTP_PORT', '465')),
    'sender': os.getenv('MAIL_SENDER', '2790885462@qq.com'),
    'password': os.getenv('MAIL_PASSWORD', 'fncwiptujvaydhba'),
    'sender_name': os.getenv('MAIL_SENDER_NAME', '铁路客票系统'),
    'enabled': os.getenv('MAIL_ENABLED', 'true').lower() == 'true'
}


def send_email_code(to_email, code):
    """
    发送邮箱验证码邮件
    
    Args:
        to_email: 收件人邮箱
        code: 验证码
    
    Returns:
        bool: 发送是否成功
    """
    if not MAIL_CONFIG['enabled']:
        print(f"[邮件功能未启用] 跳过向 {to_email} 发送验证码: {code}")
        return False
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = '铁路客票系统注册验证码'
    msg['From'] = formataddr((MAIL_CONFIG['sender_name'], MAIL_CONFIG['sender']))
    msg['To'] = to_email
    
    html = f'''
<div style="max-width:500px;margin:0 auto;font-family:'Microsoft YaHei',Arial,sans-serif;">
  <!-- 票面头部 -->
  <div style="background:#c0392b;color:#fff;padding:15px 20px;border-radius:8px 8px 0 0;display:flex;align-items:center;justify-content:space-between;">
    <div style="font-size:18px;font-weight:bold;letter-spacing:2px;">🚄 铁路客票系统</div>
    <div style="font-size:12px;opacity:0.8;">注册验证</div>
  </div>
  
  <!-- 票面主体 -->
  <div style="background:#fff;border:1px solid #ddd;border-top:none;padding:25px 30px;position:relative;">
    <!-- 左侧半圆撕口 -->
    <div style="position:absolute;left:-10px;top:50%;transform:translateY(-50%);width:20px;height:20px;background:#f5f5f5;border-radius:50%;border:1px solid #ddd;"></div>
    <!-- 右侧半圆撕口 -->
    <div style="position:absolute;right:-10px;top:50%;transform:translateY(-50%);width:20px;height:20px;background:#f5f5f5;border-radius:50%;border:1px solid #ddd;"></div>
    
    <!-- 虚线分割 -->
    <div style="border-top:2px dashed #ccc;margin:15px 0;position:relative;">
      <div style="position:absolute;left:-40px;top:-8px;font-size:12px;color:#999;">✂</div>
    </div>
    
    <!-- 验证码区域 -->
    <div style="text-align:center;margin:20px 0;">
      <p style="color:#333;font-size:14px;margin-bottom:10px;">您的验证码为</p>
      <div style="display:inline-block;background:#fef9f0;border:2px solid #c9a84c;border-radius:6px;padding:12px 30px;">
        <span style="font-size:32px;font-weight:bold;color:#c0392b;letter-spacing:8px;font-family:'Courier New',monospace;">{code}</span>
      </div>
    </div>
    
    <!-- 信息区 -->
    <div style="background:#fafafa;border-radius:4px;padding:15px;margin:15px 0;font-size:13px;color:#666;">
      <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
        <span>有效期</span>
        <span style="color:#c0392b;font-weight:bold;">5分钟</span>
      </div>
      <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
        <span>用途</span>
        <span>工号注册验证</span>
      </div>
      <div style="display:flex;justify-content:space-between;">
        <span>安全提示</span>
        <span>请勿泄露给他人</span>
      </div>
    </div>
    
    <p style="color:#999;font-size:12px;text-align:center;margin:10px 0 0;">如非本人操作，请忽略此邮件</p>
  </div>
  
  <!-- 底部条形码装饰 -->
  <div style="background:#fff;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;padding:12px 20px;text-align:center;">
    <div style="font-family:'Courier New',monospace;font-size:11px;color:#ccc;letter-spacing:2px;">
      ║║║║ ║║║ ║║║║║ ║║ ║║║║ ║║║ ║║║║ ║║ ║║║║ ║║║ ║║║║║
    </div>
    <div style="font-size:10px;color:#999;margin-top:4px;">RAWAY-VERIFY-{code}</div>
  </div>
</div>
'''
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL(MAIL_CONFIG['smtp_server'], MAIL_CONFIG['smtp_port']) as server:
            server.login(MAIL_CONFIG['sender'], MAIL_CONFIG['password'])
            server.sendmail(MAIL_CONFIG['sender'], [to_email], msg.as_string())
        print(f"[邮件发送成功] 向 {to_email} 发送验证码: {code}")
        return True
    except Exception as e:
        print(f"[邮件发送失败] 向 {to_email} 发送验证码失败: {e}")
        return False


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


# ==================== 管理员认证已迁移到主app ====================


# ==================== 公开页面路由 ====================

@register_bp.route('/')
def index():
    """注册页面入口"""
    return render_template('register/register.html')


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
    cursor.execute("SELECT user_id FROM users WHERE id_card = ?", (id_card,))
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
    cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
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
    
    # 尝试发送邮件
    email_sent = send_email_code(email, code)
    
    if email_sent:
        message = '验证码已发送到您的邮箱，请查收'
    else:
        message = '邮件发送失败，请检查邮箱地址或稍后重试'
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'status': 'success' if email_sent else 'error',
        'message': message
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
    username = data.get('username', '').strip()
    
    # 验证格式
    if not validate_username(username):
        return jsonify({'status': 'error', 'message': '工号格式不正确：新格式为XXX-YY-NNNN，旧格式为4-20位字母开头'})
    
    # 保留词检查（区分大小写存储，统一转小写比较）
    reserved = ['admin', 'root', 'system', 'test', 'administrator']
    if username.lower() in reserved:
        return jsonify({'status': 'error', 'message': '该工号为系统保留词，不可使用'})
    
    # 统一转小写存储
    username_lower = username.lower()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 检查已注册用户（不区分大小写）- 同时检查username和employee_no字段
    cursor.execute("SELECT user_id FROM users WHERE LOWER(employee_no) = ?", (username_lower,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '该工号已被使用'})
    
    # 检查待审核申请（不区分大小写）
    cursor.execute("SELECT id FROM registration_applications WHERE LOWER(username) = ? AND status != 'rejected'", (username_lower,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': '该工号已有待审核的申请'})
    
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success', 'message': '工号可用'})


@register_bp.route('/api/generate-username', methods=['POST'])
def generate_username():
    """生成结构化工号 XXX-YY-NNNN 或 XXX-YYY-NNNN"""
    data = request.get_json()
    station_code = data.get('station_code', '').strip().upper()
    custom_letters = data.get('custom_letters', '').strip().upper()
    
    # 验证车站电报码
    if not station_code or len(station_code) < 2:
        return jsonify({'status': 'error', 'message': '车站电报码无效'})
    
    # 验证自定义缩写
    if not custom_letters or len(custom_letters) < 2 or len(custom_letters) > 3:
        return jsonify({'status': 'error', 'message': '自定义缩写需2-3位字母'})
    if not re.match(r'^[A-Z]+$', custom_letters):
        return jsonify({'status': 'error', 'message': '缩写只能包含大写字母'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 尝试生成不重复的随机4位数（最多10次）
    for _ in range(10):
        random_num = str(random.randint(1000, 9999))
        username = f"{station_code}-{custom_letters}-{random_num}"
        
        # 检查是否已存在于users表
        cursor.execute("SELECT user_id FROM users WHERE employee_no = ?", (username,))
        if not cursor.fetchone():
            # 检查是否存在于registration_applications表
            cursor.execute("SELECT id FROM registration_applications WHERE username = ? AND status != 'rejected'", (username,))
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'status': 'success', 'username': username})
    
    cursor.close()
    conn.close()
    return jsonify({'status': 'error', 'message': '无法生成唯一工号，请更换缩写重试'})


@register_bp.route('/api/check-window', methods=['POST'])
def check_window():
    """检查窗口号是否可用"""
    data = request.get_json()
    station_code = data.get('station_code', '').strip()
    window_no = data.get('window_no', 0)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT user_id FROM users 
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
    username = data['username'].strip()
    if not validate_username(username):
        return jsonify({'status': 'error', 'message': '工号格式不正确：新格式为XXX-YY-NNNN（如BJP-CZW-7283），旧格式为4-20位字母开头'})
    
    # 验证窗口号
    window_no = int(data['window_no'])
    if window_no < 1 or window_no > 20:
        return jsonify({'status': 'error', 'message': '窗口号必须在1-20之间'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 检查重复 - 用户表（检查id_card, email, employee_no）
    cursor.execute("""
        SELECT user_id FROM users 
        WHERE id_card = ? OR email = ? OR employee_no = ?
    """, (data['id_card'], data['email'].lower(), username))
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
        SELECT user_id FROM users 
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
