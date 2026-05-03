# -*- coding: utf-8 -*-
"""
WebTRS 工具函数模块
"""

from datetime import datetime, timedelta

def format_date(date_str, fmt='%Y-%m-%d'):
    """格式化日期字符串"""
    if not date_str:
        return ''
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.strftime('%m月%d日')
    except:
        return date_str

def format_time(time_str):
    """格式化时间字符串"""
    if not time_str:
        return ''
    return time_str

def mask_id_number(id_number):
    """脱敏身份证号"""
    if not id_number or len(id_number) < 8:
        return id_number
    return id_number[:6] + '****' + id_number[-4:]

def calculate_hours_diff(time1, time2):
    """计算两个时间点的小时差"""
    try:
        t1 = datetime.strptime(time1, '%H:%M')
        t2 = datetime.strptime(time2, '%H:%M')
        diff = abs((t2 - t1).total_seconds() / 3600)
        return diff
    except:
        return 0

def generate_carriage_number(seat_type):
    """生成车厢号"""
    import random
    if seat_type in ['business']:
        return random.randint(1, 8)
    elif seat_type in ['first', 'second']:
        return random.randint(1, 16)
    else:
        return random.randint(1, 12)

def generate_seat_position(seat_type):
    """生成座位位置"""
    import random
    if seat_type in ['business', 'first', 'second']:
        row = random.randint(1, 20)
        pos = random.choice(['A', 'B', 'C', 'D', 'F'])
        return f"{row:02d}{pos}"
    elif seat_type in ['soft_seat', 'hard_seat']:
        return str(random.randint(1, 100)).zfill(3)
    else:  # 卧铺
        berth = random.randint(1, 60)
        pos = random.choice(['上', '中', '下'])
        return f"{berth:02d}{pos}"

def get_seat_type_name(code):
    """获取席别名称"""
    names = {
        'business': '商务座',
        'first': '一等座',
        'second': '二等座',
        'soft_seat': '软座',
        'hard_seat': '硬座',
        'soft_sleeper': '软卧',
        'hard_sleeper': '硬卧'
    }
    return names.get(code, code)

def get_train_type_name(code):
    """获取车次类型名称"""
    names = {
        'G': '高铁',
        'D': '动车',
        'C': '城际',
        'K': '快速',
        'Z': '直达',
        'T': '特快'
    }
    return names.get(code, code)
