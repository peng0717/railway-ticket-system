# -*- coding: utf-8 -*-
"""修复数据库 - 使用werkzeug重新生成密码hash"""
import sqlite3
import os
import sys

# 确保能导入项目依赖
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'railway.db')

if not os.path.exists(DB_PATH):
    print(f'数据库不存在: {DB_PATH}')
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

users = [
    ('admin', 'admin123'),
    ('seller001', '123456'),
    ('seller002', '123456'),
]

for emp_no, pwd in users:
    # 使用werkzeug生成hash
    new_hash = generate_password_hash(pwd)
    c.execute('UPDATE users SET password_hash = ? WHERE employee_no = ?', (new_hash, emp_no))
    
    # 验证
    c.execute('SELECT password_hash FROM users WHERE employee_no = ?', (emp_no,))
    row = c.fetchone()
    if row and check_password_hash(row[0], pwd):
        print(f'OK: {emp_no} 密码修复成功')
    else:
        print(f'FAIL: {emp_no} 密码验证失败')

# 确保admin状态正确，机器码清空
c.execute("UPDATE users SET status = 'active' WHERE employee_no IN ('admin', 'seller001', 'seller002')")
c.execute("UPDATE users SET machine_code = NULL WHERE employee_no IN ('admin', 'seller001', 'seller002')")
conn.commit()
conn.close()
print('\n数据库修复完成！')

# 修复operation_logs表缺失的列
print('\n检查表结构...')
c = conn.cursor()

# 检查operation_logs是否有shift_id列
c.execute("PRAGMA table_info(operation_logs)")
cols = [row[1] for row in c.fetchall()]
if 'shift_id' not in cols:
    c.execute("ALTER TABLE operation_logs ADD COLUMN shift_id INTEGER")
    print('OK: operation_logs 添加 shift_id 列')
if 'ticket_id' not in cols:
    c.execute("ALTER TABLE operation_logs ADD COLUMN ticket_id INTEGER")
    print('OK: operation_logs 添加 ticket_id 列')

conn.commit()
conn.close()
print('表结构修复完成！')
