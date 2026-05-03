# -*- coding: utf-8 -*-
"""修复数据库 - 重新生成密码hash"""
import sqlite3
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def generate_password_hash(password):
    """生成 werkzeug 兼容的密码 hash"""
    # 使用 PBKDF2 + SHA256
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return f"pbkdf2:sha256:100000${salt.hex()}${key.hex()}"

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
c = conn.cursor()

users = [
    ('admin', 'admin123'),
    ('seller001', '123456'),
    ('seller002', '123456'),
]

for emp_no, pwd in users:
    new_hash = generate_password_hash(pwd)
    c.execute('UPDATE users SET password_hash = ? WHERE employee_no = ?', (new_hash, emp_no))
    c.execute('SELECT password_hash FROM users WHERE employee_no = ?', (emp_no,))
    row = c.fetchone()
    if row and check_password_hash(row[0], pwd):
        print(f'OK: {emp_no} 密码修复成功')
    else:
        print(f'FAIL: {emp_no} 密码验证失败')

# 确保admin状态正确
c.execute("UPDATE users SET status = 'active' WHERE employee_no = 'admin'")
c.execute("UPDATE users SET machine_code = NULL WHERE employee_no IN ('admin', 'seller001', 'seller002')")
conn.commit()
conn.close()
print('数据库修复完成')
