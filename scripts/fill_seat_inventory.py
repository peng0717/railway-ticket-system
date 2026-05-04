# -*- coding: utf-8 -*-
"""
填充车次座席默认票额脚本（优化版）
按车型自动分配默认票额
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta
import hashlib

# 数据库路径
def get_db_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'data', 'railway.db')

def generate_password_hash(password):
    """简单的密码hash（兼容pbkdf2:sha256格式）"""
    # 使用类似werkzeug的格式
    import base64
    salt = os.urandom(32)
    salt_b64 = base64.b64encode(salt).decode()[:16]
    hash_obj = hashlib.sha256()
    hash_obj.update(salt + password.encode())
    hash_b64 = base64.b64encode(hash_obj.digest()).decode()
    return f"pbkdf2:sha256:100000${salt_b64}${hash_b64}"

# 车型默认票额配置
SEAT_DEFAULTS = {
    'G': {  # 高铁
        'seat_business': 20,
        'seat_first': 50,
        'seat_second': 500,
    },
    'D': {  # 动车
        'seat_first': 60,
        'seat_second': 600,
    },
    'C': {  # 城际
        'seat_first': 40,
        'seat_second': 400,
    },
    'Z': {  # 直达特快
        'seat_soft_sleeper': 30,
        'seat_hard_sleeper': 200,
        'seat_hard': 500,
    },
    'T': {  # 特快
        'seat_soft_sleeper': 20,
        'seat_hard_sleeper': 150,
        'seat_hard': 400,
    },
    'K': {  # 快速
        'seat_soft_sleeper': 15,
        'seat_hard_sleeper': 100,
        'seat_hard': 300,
    },
}

def fill_seat_inventory():
    """填充train_stops表的座席票额（优化版）"""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"❌ 数据库不存在: {db_path}")
        return 0
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    train_count = 0
    
    try:
        # 获取所有车次
        cursor.execute("SELECT train_id, train_number, train_type FROM trains")
        trains = cursor.fetchall()
        train_count = len(trains)
        print(f"📊 共有 {train_count} 个车次，开始填充座席票额...")
        
        # 构建车型到默认配置的映射
        for train_id, train_number, train_type in trains:
            defaults = SEAT_DEFAULTS.get(train_type, SEAT_DEFAULTS.get(train_number[0] if train_number else 'K', {}))
            
            if not defaults:
                defaults = {'seat_hard': 200}
            
            # 批量更新每种席别
            for seat_field, seat_count in defaults.items():
                cursor.execute(f"""
                    UPDATE train_stops 
                    SET {seat_field} = {seat_count}
                    WHERE train_id = ? AND (({seat_field} IS NULL OR {seat_field} = 0))
                """, (train_id,))
        
        conn.commit()
        
        # 统计已填充的车次数
        cursor.execute("""
            SELECT COUNT(DISTINCT train_id) FROM train_stops 
            WHERE seat_business > 0 OR seat_first > 0 OR seat_second > 0 
                OR seat_soft > 0 OR seat_hard > 0 OR seat_soft_sleeper > 0 OR seat_hard_sleeper > 0
        """)
        trains_with_seats = cursor.fetchone()[0]
        print(f"✅ 已为 {trains_with_seats} 个车次填充座席票额")
        
    except Exception as e:
        print(f"❌ 填充失败: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    
    return train_count


def fill_running_days():
    """填充running_days字段（每日开行）"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    affected = 0
    try:
        cursor.execute("""
            UPDATE trains 
            SET running_days = '1234567' 
            WHERE running_days IS NULL OR running_days = ''
        """)
        affected = cursor.rowcount
        conn.commit()
        print(f"✅ 填充 running_days: {affected} 个车次设为'每日开行'")
    except Exception as e:
        print(f"❌ 填充running_days失败: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    
    return affected


def add_train_type_to_prices():
    """为ticket_prices表添加train_type字段（如果不存在）"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查列是否存在
        cursor.execute("PRAGMA table_info(ticket_prices)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'train_type' not in columns:
            cursor.execute("ALTER TABLE ticket_prices ADD COLUMN train_type VARCHAR(10)")
            conn.commit()
            print("✅ ticket_prices表已添加train_type字段")
        else:
            print("ℹ️  ticket_prices表已有train_type字段")
    except Exception as e:
        print(f"❌ 添加train_type字段失败: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def create_test_users():
    """创建测试账号"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 测试账号配置
    test_users = [
        ('seller003', 'seller003', '上海站售票员', 'SHH', '201号口'),
        ('seller004', 'seller004', '北京站售票员', 'BJP', '301号口'),
        ('seller005', 'seller005', '广州站售票员', 'GZQ', '401号口'),
        ('seller006', 'seller006', '武汉站售票员', 'WHN', '501号口'),
    ]
    
    created = 0
    try:
        for emp_no, password, name, station_code, window_no in test_users:
            # 检查是否已存在
            cursor.execute("SELECT user_id FROM users WHERE employee_no = ?", (emp_no,))
            if cursor.fetchone():
                continue
            
            password_hash = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO users (employee_no, password_hash, name, role, window_no, station_code, status, ticket_limit)
                VALUES (?, ?, ?, 'seller', ?, ?, 'active', 200)
            """, (emp_no, password_hash, name, window_no, station_code))
            created += 1
            print(f"  ✅ 创建账号: {emp_no} ({name}) - 密码: {password}")
        
        conn.commit()
    except Exception as e:
        print(f"❌ 创建测试账号失败: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    
    return created


def main():
    print("=" * 50)
    print("🚄 铁路客票系统 - 数据修复脚本")
    print("=" * 50)
    print()
    
    # 1. 填充running_days
    print("📌 [1/5] 填充 running_days 字段...")
    fill_running_days()
    print()
    
    # 2. 添加train_type字段
    print("📌 [2/5] 检查/添加 ticket_prices.train_type 字段...")
    add_train_type_to_prices()
    print()
    
    # 3. 填充座席票额
    print("📌 [3/5] 填充 train_stops 座席默认票额...")
    fill_seat_inventory()
    print()
    
    # 4. 创建测试账号
    print("📌 [4/5] 创建多站测试账号...")
    created = create_test_users()
    print(f"  ✅ 新增 {created} 个测试账号")
    print()
    
    # 5. 统计
    print("📌 [5/5] 数据统计...")
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM trains")
    total_trains = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(DISTINCT train_id) FROM train_stops 
        WHERE seat_business > 0 OR seat_first > 0 OR seat_second > 0 
            OR seat_soft > 0 OR seat_hard > 0 OR seat_soft_sleeper > 0 OR seat_hard_sleeper > 0
    """)
    trains_with_seats = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM trains WHERE running_days IS NOT NULL AND running_days != ''")
    trains_with_days = cursor.fetchone()[0]
    
    print(f"  • 总车次: {total_trains}")
    print(f"  • 有座席数据的车次: {trains_with_seats}")
    print(f"  • 有开行日期的车次: {trains_with_days}")
    print(f"  • 总用户数: {total_users}")
    
    cursor.close()
    conn.close()
    
    print()
    print("=" * 50)
    print("✅ 数据修复完成!")
    print("=" * 50)


if __name__ == '__main__':
    main()
