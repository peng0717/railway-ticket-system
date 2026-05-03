# -*- coding: utf-8 -*-
"""
注册审核系统工具函数
包含身份证校验、邮箱验证等
"""

import re
import random
import string
from datetime import datetime, timedelta


def validate_id_card(id_card):
    """
    验证身份证号（完整校验码算法）
    返回: True/False
    """
    if not id_card or len(id_card) != 18:
        return False
    
    # 验证格式：17位数字 + 1位数字或X
    if not re.match(r'^\d{17}[\dXx]$', id_card):
        return False
    
    # 加权因子
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_codes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
    
    # 计算校验码
    total = sum(int(id_card[i]) * weights[i] for i in range(17))
    check_code = check_codes[total % 11]
    
    return id_card[17].upper() == check_code


def validate_email(email):
    """
    验证邮箱格式
    返回: True/False
    """
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password(password):
    """
    验证密码强度（8-20位，包含字母和数字）
    返回: True/False
    """
    if not password:
        return False
    if len(password) < 8 or len(password) > 20:
        return False
    if not re.search(r'[A-Za-z]', password):
        return False
    if not re.search(r'[0-9]', password):
        return False
    return True


def validate_username(username):
    """
    验证工号格式：字母开头，4-20位，允许字母、数字、下划线、短横线
    返回: True/False
    """
    if not username:
        return False
    # 字母开头，4-20位，允许字母、数字、下划线、短横线
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]{3,19}$', username):
        return False
    # 保留词检查
    reserved = ['admin', 'root', 'system', 'test', 'administrator']
    if username.lower() in reserved:
        return False
    return True


def generate_verification_code():
    """生成6位验证码"""
    return ''.join(random.choices(string.digits, k=6))


def mask_id_card(id_card):
    """脱敏身份证号"""
    if not id_card or len(id_card) != 18:
        return id_card
    return f"{id_card[:6]}****{id_card[-4:]}"


def mask_email(email):
    """脱敏邮箱"""
    if not email or '@' not in email:
        return email
    parts = email.split('@')
    username = parts[0]
    if len(username) <= 2:
        masked = username[0] + '*'
    else:
        masked = username[0] + '*' * (len(username) - 2) + username[-1]
    return f"{masked}@{parts[1]}"


def get_id_card_info(id_card):
    """
    从身份证号提取基本信息
    返回: dict {birth_date, gender, age}
    """
    if not id_card or len(id_card) != 18:
        return None
    
    try:
        birth_date_str = id_card[6:14]
        birth_date = datetime.strptime(birth_date_str, '%Y%m%d')
        gender_code = int(id_card[16])
        gender = '男' if gender_code % 2 == 1 else '女'
        age = (datetime.now() - birth_date).days // 365
        
        return {
            'birth_date': birth_date.strftime('%Y-%m-%d'),
            'gender': gender,
            'age': age,
            'province_code': id_card[:2]
        }
    except:
        return None


def format_datetime(dt):
    """格式化日期时间"""
    if not dt:
        return ''
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return dt
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def is_code_expired(expires_at):
    """检查验证码是否过期"""
    if not expires_at:
        return True
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        except:
            return True
    return datetime.now() > expires_at
