# -*- coding: utf-8 -*-
"""
铁路客票系统 - 自动模拟售票引擎
直接操作数据库模拟售票员办理旅客的买票、退票等业务
"""

import os
import sys
import json
import random
import sqlite3
import time
import argparse
import threading
from datetime import datetime, timedelta
from threading import Lock

# ==================== 配置 ====================

# 百家姓
SURNAMES = [
    '王', '李', '张', '刘', '陈', '杨', '赵', '黄', '周', '吴', '徐', '孙', '胡', '朱', '高',
    '林', '何', '郭', '马', '罗', '梁', '宋', '郑', '谢', '韩', '唐', '冯', '于', '董', '萧',
    '程', '曹', '袁', '邓', '许', '傅', '沈', '曾', '彭', '吕', '苏', '卢', '蒋', '蔡', '贾',
    '丁', '魏', '薛', '叶', '阎', '余', '潘', '杜', '戴', '夏', '钟', '汪', '田', '任', '姜',
    '范', '方', '石', '姚', '谭', '廖', '邹', '熊', '金', '陆', '郝', '孔', '白', '崔', '康',
    '毛', '邱', '秦', '江', '史', '顾', '侯', '邵', '孟', '龙', '万', '段', '漕', '钱', '汤',
    '尹', '黎', '易', '常', '武', '乔', '贺', '赖', '龚', '文'
]

# 常用名
GIVEN_NAMES = [
    '伟', '芳', '娜', '秀英', '敏', '静', '丽', '强', '磊', '军', '洋', '勇', '艳', '杰', '涛',
    '明', '超', '秀兰', '霞', '平', '刚', '桂英', '芬', '玲', '建国', '建华', '志强', '志强',
    '秀珍', '志明', '婷婷', '浩', '宇', '欣', '雨', '晨', '心', '怡', '然', '思', '远', '翔',
    '鑫', '雅', '诗', '涵', '子轩', '梓涵', '子涵', '一诺', '浩然', '博文', '思远', '子墨',
    '欣怡', '佳怡', '子萱', '欣悦', '子瑶', '梓萱', '可欣', '思琪', '梦琪', '语汐', '诗涵',
    '俊杰', '子豪', '子晨', '天宇', '浩然', '宇航', '浩然', '晨曦', '子墨', '嘉豪', '嘉辉',
    '嘉诚', '嘉瑞', '嘉峻', '嘉轩', '嘉琪', '嘉慧', '嘉兴', '嘉惠', '嘉玲', '嘉欣', '嘉怡',
    '雨桐', '雨涵', '雨萱', '雨欣', '雨晨', '雨轩', '雨泽', '雨彤', '语桐', '语涵', '语萱'
]

# 退票原因
REFUND_REASONS = [
    '旅客个人原因', '行程变更', '改签其他车次', '身体不适', '工作安排变化',
    '天气原因取消行程', '其他交通方式', '陪同人员行程变化', '紧急事务'
]

# 地区码（前6位身份证）
AREA_CODES = [
    '110100', '110101', '110102', '110105', '110106', '110107', '110108', '110109', '110111',
    '310100', '310101', '310104', '310105', '310107', '310109', '310110', '310112', '310113',
    '320100', '320101', '320102', '320103', '320104', '320105', '320106', '320111', '320113',
    '330100', '330101', '330102', '330103', '330104', '330105', '330106', '330108', '330110',
    '440100', '440101', '440103', '440104', '440105', '440106', '440107', '440111', '440112',
    '420100', '420101', '420102', '420103', '420104', '420105', '420106', '420111', '420112',
    '500100', '500101', '500102', '500103', '500104', '500105', '500106', '500107', '500108',
    '610100', '610101', '610102', '610103', '610104', '610112', '610113', '610114', '610115'
]

# ==================== 全局状态 ====================

simulation_state = {
    'running': False,
    'thread': None,
    'total_sold': 0,
    'total_refunded': 0,
    'total_revenue': 0.0,
    'started_at': None,
    'current_shift': None,
    'recent_operations': [],  # 最近20条操作
    'lock': Lock()
}

# ==================== 数据库操作 ====================

def get_db_path():
    """获取数据库路径"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, '..', 'data', 'railway.db')

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

def get_dict_connection():
    """获取返回字典的数据库连接"""
    conn = get_db_connection()
    if not conn:
        return None
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    return conn

# ==================== 模拟数据生成 ====================

def generate_passenger_name():
    """生成随机中文姓名"""
    surname = random.choice(SURNAMES)
    given_name = random.choice(GIVEN_NAMES)
    if len(given_name) == 1 and random.random() > 0.3:
        given_name += random.choice(GIVEN_NAMES[:30])
    return surname + given_name

def calculate_id_checksum(id17):
    """计算身份证校验码"""
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_codes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
    total = sum(int(id17[i]) * weights[i] for i in range(17))
    return check_codes[total % 11]

def generate_id_number():
    """生成随机身份证号"""
    area_code = random.choice(AREA_CODES)
    
    # 生成18位生日（1980-2005年）
    year = random.randint(1980, 2005)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    birth_date = f"{year:04d}{month:02d}{day:02d}"
    
    # 顺序码（001-999，奇数男偶数女）
    seq_code = f"{random.randint(1, 500):03d}"
    
    id17 = area_code + birth_date + seq_code
    checksum = calculate_id_checksum(id17)
    
    return id17 + checksum

def generate_phone_number():
    """生成随机手机号"""
    prefixes = ['130', '131', '132', '133', '134', '135', '136', '137', '138', '139',
                '145', '147', '149', '150', '151', '152', '153', '155', '156', '157',
                '158', '159', '166', '170', '171', '172', '173', '175', '176', '177',
                '178', '180', '181', '182', '183', '184', '185', '186', '187', '188',
                '189', '191', '195', '196', '197', '198', '199']
    prefix = random.choice(prefixes)
    suffix = ''.join([str(random.randint(0, 9)) for _ in range(8)])
    return prefix + suffix

def generate_ticket_id():
    """生成票号 TK+日期时间+序号"""
    now = datetime.now()
    date_part = now.strftime('%Y%m%d')
    time_part = now.strftime('%H%M%S')
    seq = random.randint(1, 999)
    return f"TK{date_part}{time_part}{seq:03d}"

def get_seat_type_name(seat_type):
    """席别中文名"""
    names = {
        'business': '商务座',
        'first': '一等座',
        'second': '二等座',
        'soft_seat': '软座',
        'hard_seat': '硬座',
        'soft_sleeper': '软卧',
        'hard_sleeper': '硬卧'
    }
    return names.get(seat_type, seat_type)

# ==================== 数据查询 ====================

def get_active_sellers():
    """获取活跃的售票员"""
    conn = get_dict_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, employee_no, name, station_code, window_no 
            FROM users 
            WHERE role = 'seller' AND status = 'active'
        """)
        sellers = cursor.fetchall()
        cursor.close()
        conn.close()
        return sellers
    except Exception as e:
        print(f"获取售票员失败: {e}")
        if conn:
            conn.close()
        return []

def get_random_train():
    """随机选择一个车次及其停站信息"""
    conn = get_dict_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        
        # 随机选一个车次
        cursor.execute("""
            SELECT train_id, train_number, train_type 
            FROM trains 
            WHERE train_type IN ('G', 'D', 'C', 'Z', 'T', 'K')
            ORDER BY RANDOM() LIMIT 1
        """)
        train = cursor.fetchone()
        
        if not train:
            cursor.close()
            conn.close()
            return None
        
        # 获取该车次的停站（至少需要2个站）
        cursor.execute("""
            SELECT station_code, station_name, arrival_time, departure_time, distance_from_start
            FROM train_stops
            WHERE train_id = ?
            ORDER BY stop_order
        """, (train['train_id'],))
        stops = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        if len(stops) < 2:
            return None
        
        # 随机选择出发站和到达站
        max_idx = len(stops) - 1
        from_idx = random.randint(0, max_idx - 1)
        to_idx = random.randint(from_idx + 1, max_idx)
        
        return {
            'train': train,
            'from_stop': stops[from_idx],
            'to_stop': stops[to_idx],
            'all_stops': stops
        }
    except Exception as e:
        print(f"获取车次失败: {e}")
        if conn:
            conn.close()
        return None

def get_random_seat_type(train_type):
    """根据车型获取随机席别"""
    seat_types = {
        'G': ['business', 'first', 'second'],
        'D': ['first', 'second'],
        'C': ['first', 'second'],
        'Z': ['soft_sleeper', 'hard_sleeper', 'soft_seat', 'hard_seat'],
        'T': ['soft_sleeper', 'hard_sleeper', 'soft_seat', 'hard_seat'],
        'K': ['soft_sleeper', 'hard_sleeper', 'hard_seat']
    }
    return random.choice(seat_types.get(train_type, ['second']))

def calculate_price(from_station, to_station, seat_type, train_type=None):
    """计算票价"""
    conn = get_dict_connection()
    if not conn:
        return 300.0
    
    try:
        cursor = conn.cursor()
        
        # 优先按 train_type + from_station + to_station + seat_type 查询
        if train_type:
            cursor.execute("""
                SELECT base_price FROM ticket_prices
                WHERE from_station = ? AND to_station = ? AND seat_type = ? AND train_type = ?
            """, (from_station, to_station, seat_type, train_type))
            price = cursor.fetchone()
            if price:
                cursor.close()
                conn.close()
                return float(price['base_price'])
        
        # 退化为按 from_station + to_station + seat_type 查询
        cursor.execute("""
            SELECT base_price FROM ticket_prices
            WHERE from_station = ? AND to_station = ? AND seat_type = ?
        """, (from_station, to_station, seat_type))
        price = cursor.fetchone()
        
        if price:
            cursor.close()
            conn.close()
            return float(price['base_price'])
        
        cursor.close()
        conn.close()
        
        # 默认价格
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
        return 200.0

def calculate_refund_fee(ticket_price, departure_time_str):
    """计算退票手续费（距离开车时间）"""
    try:
        # 假设出发时间是今天的一个随机时间点
        today = datetime.now().strftime('%Y-%m-%d')
        dep_time = datetime.strptime(f"{today} {departure_time_str}", '%Y-%m-%d %H:%M')
        now = datetime.now()
        hours_until = (dep_time - now).total_seconds() / 3600
    except:
        hours_until = 72  # 默认72小时
    
    if hours_until >= 360:
        return 0.0
    elif hours_until >= 48:
        return round(ticket_price * 0.05, 2)
    elif hours_until >= 24:
        return round(ticket_price * 0.10, 2)
    else:
        return round(ticket_price * 0.20, 2)

def update_seat_inventory(train_id, travel_date, seat_type, change=1):
    """更新座席库存"""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        
        # 查找或创建库存记录
        cursor.execute("""
            SELECT id, available_seats FROM train_seat_inventory
            WHERE train_id = ? AND travel_date = ? AND seat_type = ?
        """, (train_id, travel_date, seat_type))
        inventory = cursor.fetchone()
        
        if inventory:
            new_available = inventory['available_seats'] - change
            if new_available >= 0:
                cursor.execute("""
                    UPDATE train_seat_inventory
                    SET sold_seats = sold_seats + ?, available_seats = ?,
                        updated_at = ?
                    WHERE train_id = ? AND travel_date = ? AND seat_type = ?
                """, (change, new_available, datetime.now().isoformat(),
                      train_id, travel_date, seat_type))
            else:
                cursor.close()
                conn.close()
                return False
        else:
            # 创建新记录
            cursor.execute("""
                INSERT INTO train_seat_inventory
                (train_id, travel_date, seat_type, total_seats, sold_seats, available_seats, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (train_id, travel_date, seat_type, 100, change, 100 - change, datetime.now().isoformat()))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"更新库存失败: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

# ==================== 班次管理 ====================

def open_shift(seller):
    """开班"""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        
        # 创建新班次
        now = datetime.now()
        shift_date = now.strftime('%Y-%m-%d')
        
        cursor.execute("""
            INSERT INTO shifts (seller_id, seller_name, employee_no, station_code, 
                               window_no, shift_date, start_time, status, ticket_count, revenue)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            seller['user_id'],
            seller['name'],
            seller['employee_no'],
            seller['station_code'],
            seller['window_no'],
            shift_date,
            now.strftime('%H:%M:%S'),
            'open',
            0,
            0.0
        ))
        
        shift_id = cursor.lastrowid
        
        # 更新班次计数
        cursor.execute("""
            INSERT INTO counters (counter_name, current_value, prefix, updated_at)
            VALUES ('shift', 1, 'SD', ?)
            ON CONFLICT(counter_name) DO UPDATE SET current_value = current_value + 1
        """, (now.isoformat(),))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return shift_id
    except Exception as e:
        print(f"开班失败: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return None

def close_shift(shift_id):
    """结班"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        
        # 获取班次统计
        cursor.execute("""
            SELECT ticket_count, revenue FROM shifts WHERE shift_id = ?
        """, (shift_id,))
        shift = cursor.fetchone()
        
        if shift:
            cursor.execute("""
                UPDATE shifts
                SET status = 'closed', end_time = ?, ticket_count = ?, revenue = ?
                WHERE shift_id = ?
            """, (
                datetime.now().strftime('%H:%M:%S'),
                shift['ticket_count'] or 0,
                shift['revenue'] or 0.0,
                shift_id
            ))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"结班失败: {e}")
        if conn:
            conn.rollback()
            conn.close()

def update_shift_stats(shift_id, ticket_count_delta=0, revenue_delta=0.0):
    """更新班次统计"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE shifts
            SET ticket_count = ticket_count + ?, revenue = revenue + ?
            WHERE shift_id = ?
        """, (ticket_count_delta, revenue_delta, shift_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"更新班次统计失败: {e}")
        if conn:
            conn.rollback()
            conn.close()

# ==================== 售票/退票操作 ====================

def sell_ticket(seller, shift_id):
    """模拟售票"""
    # 选择车次和区间
    train_info = get_random_train()
    if not train_info:
        return None
    
    train = train_info['train']
    from_stop = train_info['from_stop']
    to_stop = train_info['to_stop']
    
    # 选择席别
    seat_type = get_random_seat_type(train['train_type'])
    
    # 计算票价
    price = calculate_price(
        from_stop['station_code'], 
        to_stop['station_code'], 
        seat_type,
        train['train_type']
    )
    
    # 生成旅客信息
    passenger_name = generate_passenger_name()
    id_number = generate_id_number()
    phone = generate_phone_number()
    
    # 生成票号
    ticket_id = generate_ticket_id()
    
    # 旅行日期（今天或明天）
    travel_date = (datetime.now() + timedelta(days=random.randint(0, 3))).strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        # 插入票记录
        cursor.execute("""
            INSERT INTO tickets (
                ticket_id, shift_id, train_number, train_id,
                from_station, to_station, from_station_name, to_station_name,
                travel_date, departure_time, arrival_time,
                seat_type, seat_number, ticket_type, 
                passenger_name, id_number, phone,
                price, status, seller_id, window_no, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_id,
            shift_id,
            train['train_number'],
            train['train_id'],
            from_stop['station_code'],
            to_stop['station_code'],
            from_stop['station_name'],
            to_stop['station_name'],
            travel_date,
            from_stop['departure_time'],
            to_stop['arrival_time'],
            seat_type,
            f"{random.randint(1, 16):02d}{random.randint(1, 20):02d}{random.choice('ABCDF')}",
            'simulation',  # ticket_type 标记为模拟
            passenger_name,
            id_number,
            phone,
            price,
            'sold',
            seller['user_id'],
            seller['window_no'],
            datetime.now().isoformat()
        ))
        
        # 记录操作日志
        cursor.execute("""
            INSERT INTO operation_logs (
                shift_id, employee_no, operation_type, ticket_id, 
                details, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            shift_id,
            seller['employee_no'],
            'simulation_sell',
            ticket_id,
            json.dumps({
                'train': train['train_number'],
                'from': from_stop['station_name'],
                'to': to_stop['station_name'],
                'seat': seat_type,
                'price': price,
                'passenger': passenger_name
            }, ensure_ascii=False),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # 更新班次统计
        update_shift_stats(shift_id, 1, price)
        
        # 更新座席库存
        update_seat_inventory(train['train_id'], travel_date, seat_type, 1)
        
        return {
            'type': 'sell',
            'seller': seller,
            'ticket_id': ticket_id,
            'train_number': train['train_number'],
            'from_station': from_stop['station_name'],
            'to_station': to_stop['station_name'],
            'seat_type': seat_type,
            'price': price,
            'passenger': passenger_name
        }
    except Exception as e:
        print(f"售票失败: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return None

def refund_ticket(seller, shift_id):
    """模拟退票"""
    conn = get_dict_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        # 随机选择一张已售出的模拟票
        cursor.execute("""
            SELECT ticket_id, train_number, from_station, to_station,
                   from_station_name, to_station_name, seat_type, 
                   price, departure_time, travel_date
            FROM tickets
            WHERE status = 'sold' AND ticket_type = 'simulation'
            ORDER BY RANDOM() LIMIT 1
        """)
        ticket = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not ticket:
            return None
        
        # 计算退票费
        refund_fee = calculate_refund_fee(ticket['price'], ticket['departure_time'])
        refund_amount = ticket['price'] - refund_fee
        
        # 生成退票记录
        refund_id = f"RF{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"
        
        conn2 = get_db_connection()
        if not conn2:
            return None
        
        try:
            cursor = conn2.cursor()
            
            # 插入退票记录
            cursor.execute("""
                INSERT INTO refunds (
                    ticket_id, shift_id, refund_amount, refund_fee,
                    refund_reason, refund_type, status,
                    operated_by, operated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket['ticket_id'],
                shift_id,
                refund_amount,
                refund_fee,
                random.choice(REFUND_REASONS),
                'simulation',
                'approved',
                seller['user_id'],
                datetime.now().isoformat()
            ))
            
            # 更新票状态
            cursor.execute("""
                UPDATE tickets SET status = 'refunded' WHERE ticket_id = ?
            """, (ticket['ticket_id'],))
            
            # 记录操作日志
            cursor.execute("""
                INSERT INTO operation_logs (
                    shift_id, employee_no, operation_type, ticket_id,
                    details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                shift_id,
                seller['employee_no'],
                'simulation_refund',
                ticket['ticket_id'],
                json.dumps({
                    'train': ticket['train_number'],
                    'from': ticket['from_station_name'],
                    'to': ticket['to_station_name'],
                    'seat': ticket['seat_type'],
                    'price': ticket['price'],
                    'refund_fee': refund_fee,
                    'refund_amount': refund_amount
                }, ensure_ascii=False),
                datetime.now().isoformat()
            ))
            
            conn2.commit()
            cursor.close()
            conn2.close()
            
            # 更新班次统计（退票减少营收）
            update_shift_stats(shift_id, 0, -refund_amount)
            
            # 更新座席库存
            update_seat_inventory(ticket['train_id'], ticket['travel_date'], ticket['seat_type'], -1)
            
            return {
                'type': 'refund',
                'seller': seller,
                'ticket_id': ticket['ticket_id'],
                'train_number': ticket['train_number'],
                'from_station': ticket['from_station_name'],
                'to_station': ticket['to_station_name'],
                'seat_type': ticket['seat_type'],
                'price': ticket['price'],
                'refund_fee': refund_fee,
                'refund_amount': refund_amount
            }
        except Exception as e:
            print(f"退票处理失败: {e}")
            if conn2:
                conn2.rollback()
                conn2.close()
            return None
    except Exception as e:
        print(f"查询退票失败: {e}")
        if conn:
            conn.close()
        return None

# ==================== 模拟工作线程 ====================

def simulation_worker(speed='normal'):
    """模拟工作线程"""
    # 速度配置
    speed_config = {
        'slow': {'sell': (15, 25), 'refund': (40, 80)},
        'normal': {'sell': (5, 12), 'refund': (25, 50)},
        'fast': {'sell': (1, 4), 'refund': (10, 20)}
    }
    
    config = speed_config.get(speed, speed_config['normal'])
    
    # 获取售票员
    sellers = get_active_sellers()
    if not sellers:
        print("❌ 没有找到活跃的售票员")
        return
    
    print(f"✅ 找到 {len(sellers)} 个活跃售票员")
    
    # 当前班次
    current_shift = {}
    shift_ticket_count = {}
    
    while simulation_state['running']:
        try:
            # 随机选择操作类型
            action = random.choices(
                ['sell', 'sell', 'sell', 'sell', 'refund', 'shift'],
                weights=[40, 40, 40, 40, 15, 5]
            )[0]
            
            # 随机选择售票员
            seller = random.choice(sellers)
            
            # 确保售票员有开班
            if seller['user_id'] not in current_shift:
                shift_id = open_shift(seller)
                if shift_id:
                    current_shift[seller['user_id']] = shift_id
                    shift_ticket_count[seller['user_id']] = 0
                    record_operation('simulation_shift_open', seller, shift_id=shift_id)
                    print(f"🚂 [{seller['employee_no']}] 开班，班次ID: {shift_id}")
                else:
                    continue
            
            shift_id = current_shift[seller['user_id']]
            
            if action == 'sell':
                # 售票
                result = sell_ticket(seller, shift_id)
                if result:
                    shift_ticket_count[seller['user_id']] += 1
                    simulation_state['total_sold'] += 1
                    simulation_state['total_revenue'] += result['price']
                    record_operation('simulation_sell', seller, **result)
                    print(f"🎫 [{datetime.now().strftime('%H:%M:%S')}] {seller['employee_no']}({seller['window_no']}) "
                          f"售出 {result['train_number']} {result['from_station']}→{result['to_station']} "
                          f"{get_seat_type_name(result['seat_type'])} ¥{result['price']:.2f} 旅客:{result['passenger']}")
                    
                    # 检查是否需要结班（售出30-80张后）
                    if shift_ticket_count[seller['user_id']] >= random.randint(30, 80):
                        close_shift(shift_id)
                        record_operation('simulation_shift_close', seller, shift_id=shift_id,
                                        ticket_count=shift_ticket_count[seller['user_id']])
                        print(f"🏁 [{seller['employee_no']}] 结班，共售出 {shift_ticket_count[seller['user_id']]} 张")
                        del current_shift[seller['user_id']]
                        del shift_ticket_count[seller['user_id']]
                        continue
                else:
                    print(f"⚠️ 售票失败（可能无余票）")
            
            elif action == 'refund':
                # 退票
                result = refund_ticket(seller, shift_id)
                if result:
                    simulation_state['total_refunded'] += 1
                    simulation_state['total_revenue'] -= result['refund_fee']
                    record_operation('simulation_refund', seller, **result)
                    print(f"💰 [{datetime.now().strftime('%H:%M:%S')}] {seller['employee_no']}({seller['window_no']}) "
                          f"退票 {result['train_number']} {result['from_station']}→{result['to_station']} "
                          f"{get_seat_type_name(result['seat_type'])} 退票费{result['refund_fee']:.2f}元")
                else:
                    print(f"⚠️ 退票失败（可能无可退票）")
            
            elif action == 'shift':
                # 随机结班并重新开班
                if seller['user_id'] in current_shift:
                    close_shift(current_shift[seller['user_id']])
                    record_operation('simulation_shift_close', seller, shift_id=shift_id,
                                    ticket_count=shift_ticket_count[seller['user_id']])
                    print(f"🏁 [{seller['employee_no']}] 结班（主动）")
                    del current_shift[seller['user_id']]
                    del shift_ticket_count[seller['user_id']]
                
                shift_id = open_shift(seller)
                if shift_id:
                    current_shift[seller['user_id']] = shift_id
                    shift_ticket_count[seller['user_id']] = 0
                    record_operation('simulation_shift_open', seller, shift_id=shift_id)
                    print(f"🚂 [{seller['employee_no']}] 重新开班")
            
            # 休眠
            if action == 'sell':
                sleep_time = random.uniform(*config['sell'])
            elif action == 'refund':
                sleep_time = random.uniform(*config['refund'])
            else:
                sleep_time = random.uniform(*config['sell'])
            
            time.sleep(sleep_time)
            
        except Exception as e:
            print(f"模拟线程异常: {e}")
            time.sleep(5)
    
    # 退出前关闭所有班次
    for seller_id, shift_id in current_shift.items():
        close_shift(shift_id)
    print("🏁 模拟引擎已停止，所有班次已结班")

def record_operation(op_type, seller, **kwargs):
    """记录最近操作"""
    with simulation_state['lock']:
        op = {
            'type': op_type,
            'seller': seller['employee_no'],
            'time': datetime.now().strftime('%H:%M:%S'),
            **kwargs
        }
        simulation_state['recent_operations'].insert(0, op)
        # 只保留最近20条
        simulation_state['recent_operations'] = simulation_state['recent_operations'][:20]

# ==================== 控制接口 ====================

def start_simulation(speed='normal'):
    """启动模拟"""
    with simulation_state['lock']:
        if simulation_state['running']:
            return False, "模拟已在运行"
        
        simulation_state['running'] = True
        simulation_state['thread'] = threading.Thread(
            target=simulation_worker,
            args=(speed,),
            daemon=True
        )
        simulation_state['thread'].start()
        simulation_state['started_at'] = datetime.now().isoformat()
        simulation_state['total_sold'] = 0
        simulation_state['total_refunded'] = 0
        simulation_state['total_revenue'] = 0.0
        simulation_state['recent_operations'] = []
    
    return True, "模拟已启动"

def stop_simulation():
    """停止模拟"""
    with simulation_state['lock']:
        if not simulation_state['running']:
            return False, "模拟未在运行"
        
        simulation_state['running'] = False
    
    if simulation_state['thread']:
        simulation_state['thread'].join(timeout=5)
    
    return True, "模拟已停止"

def get_simulation_status():
    """获取模拟状态"""
    return {
        'running': simulation_state['running'],
        'total_sold': simulation_state['total_sold'],
        'total_refunded': simulation_state['total_refunded'],
        'total_revenue': simulation_state['total_revenue'],
        'started_at': simulation_state['started_at'],
        'recent_operations': simulation_state['recent_operations']
    }

# ==================== 主入口 ====================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='铁路客票系统 - 模拟售票引擎')
    parser.add_argument('--duration', type=int, default=0, help='运行时长（秒），0为无限运行')
    parser.add_argument('--speed', choices=['slow', 'normal', 'fast'], default='normal',
                       help='模拟速度: slow(慢)/normal(普通)/fast(快)')
    parser.add_argument('--stop', action='store_true', help='停止正在运行的模拟')
    
    args = parser.parse_args()
    
    if args.stop:
        print("正在停止模拟...")
        # 通过数据库信号通知停止（简化实现）
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                    VALUES ('simulation_stop', 'true', ?)
                """, (datetime.now().isoformat(),))
                conn.commit()
                cursor.close()
            except:
                pass
            conn.close()
        print("停止信号已发送")
        sys.exit(0)
    
    print("=" * 50)
    print("🚂 铁路客票系统 - 自动模拟售票引擎")
    print("=" * 50)
    print(f"速度模式: {args.speed}")
    print(f"运行时长: {'无限' if args.duration == 0 else f'{args.duration}秒'}")
    print("-" * 50)
    
    # 启动模拟
    success, msg = start_simulation(args.speed)
    if not success:
        print(f"❌ {msg}")
        sys.exit(1)
    
    print(f"✅ {msg}")
    print("按 Ctrl+C 停止模拟")
    print("-" * 50)
    
    # 运行指定时长或无限运行
    try:
        if args.duration > 0:
            time.sleep(args.duration)
            stop_simulation()
            print(f"\n⏰ 定时停止，已运行 {args.duration} 秒")
        else:
            while simulation_state['running']:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n⚠️  用户中断")
        stop_simulation()
        print("✅ 模拟已停止")
    
    print("\n📊 最终统计:")
    print(f"   售票数: {simulation_state['total_sold']}")
    print(f"   退票数: {simulation_state['total_refunded']}")
    print(f"   净营收: ¥{simulation_state['total_revenue']:.2f}")
