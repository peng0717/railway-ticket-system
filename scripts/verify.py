# -*- coding: utf-8 -*-
"""验证数据库和代码修复"""
import sqlite3
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def check_password_hash(password_hash, password):
    """验证密码 hash"""
    try:
        if password_hash.startswith('pbkdf2:sha256:'):
            parts = password_hash.split('$')
            salt = bytes.fromhex(parts[1])
            stored_key = parts[2]
            key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
            return key.hex() == stored_key
        elif password_hash.startswith('scrypt:'):
            # scrypt格式
            parts = password_hash.split('$')
            return password_hash == generate_password_hash(password)
        else:
            # 可能是旧的简单hash
            return hashlib.sha256(password.encode()).hexdigest() == password_hash
    except:
        return False

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'railway.db')
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

errors = []

# 1. 检查用户存在
c.execute('SELECT * FROM users')
users = c.fetchall()
if len(users) < 3:
    errors.append(f'用户数量不对: {len(users)}')

# 2. 检查admin
c.execute('SELECT * FROM users WHERE employee_no = ?', ('admin',))
admin = c.fetchone()
if not admin:
    errors.append('admin用户不存在')
else:
    if not check_password_hash(admin['password_hash'], 'admin123'):
        errors.append('admin密码验证失败')
    if admin['role'] != 'admin':
        errors.append(f'admin角色不对: {admin["role"]}')
    if admin['status'] != 'active':
        errors.append(f'admin状态不对: {admin["status"]}')

# 3. 检查字段名
c.execute('SELECT * FROM users LIMIT 1')
row = c.fetchone()
expected_cols = ['user_id', 'employee_no', 'name', 'password_hash', 'role', 'status']
for col in expected_cols:
    try:
        _ = row[col]
    except (KeyError, IndexError):
        errors.append(f'缺少列: {col}')

# 4. 检查seller用户
for emp_no in ['seller001', 'seller002']:
    c.execute('SELECT * FROM users WHERE employee_no = ?', (emp_no,))
    seller = c.fetchone()
    if not seller:
        errors.append(f'{emp_no} 用户不存在')
    else:
        if not check_password_hash(seller['password_hash'], '123456'):
            errors.append(f'{emp_no} 密码验证失败')

if errors:
    print('验证失败:')
    for e in errors:
        print(f'  - {e}')
    sys.exit(1)
else:
    print('所有验证通过!')

conn.close()
