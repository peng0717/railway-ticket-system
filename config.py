# -*- coding: utf-8 -*-
"""
WebTRS 配置文件
模拟铁路车站人工售票系统
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据库配置 - 使用PostgreSQL (Supabase)
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
else:
    # 如果没有配置DATABASE_URL，使用SQLite作为后备
    DATABASE_PATH = os.path.join(BASE_DIR, 'data', 'railway.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'

SQLALCHEMY_TRACK_MODIFICATIONS = False

# Session配置
SECRET_KEY = os.getenv('SECRET_KEY', 'webtrs-secret-key-2025-railway-ticketing-system')
SESSION_TYPE = 'filesystem'
SESSION_PERMANENT = False
PERMANENT_SESSION_LIFETIME = 3600 * 8  # 8小时班次时间

# 应用配置
DEBUG = True
TESTING = False

# 售票员默认窗口号
DEFAULT_WINDOW_NO = '101号口'

# 系统名称
SYSTEM_NAME = '铁路客票发售和预订系统'
SYSTEM_VERSION = 'WebTRS v1.0'
SYSTEM_COPYRIGHT = '铁路客票发售和预订系统总体组'

# 拼音码最小匹配长度
PINYIN_MIN_LENGTH = 1

# 车票票号前缀
TICKET_PREFIX = 'A'

# 预售期天数
PRESALE_DAYS = 15

# 席别配置
SEAT_TYPES = {
    'business': {'name': '商务座', 'code': 'SWZ', 'coefficient': 4.5},
    'first': {'name': '一等座', 'code': 'YZ', 'coefficient': 2.8},
    'second': {'name': '二等座', 'code': 'EZ', 'coefficient': 1.8},
    'soft_seat': {'name': '软座', 'code': 'RZ', 'coefficient': 1.5},
    'hard_seat': {'name': '硬座', 'code': 'YZ', 'coefficient': 1.0},
    'soft_sleeper': {'name': '软卧', 'code': 'RW', 'coefficient': 2.5},
    'hard_sleeper': {'name': '硬卧', 'code': 'YW', 'coefficient': 1.8},
}

# 票种配置
TICKET_TYPES = {
    'adult': {'name': '全', 'discount': 1.0, 'min_age': 14},
    'child': {'name': '孩', 'discount': 0.5, 'min_age': 6, 'max_age': 14},
    'student': {'name': '学', 'discount': 0.5, 'require_verification': True},
}

# 退票手续费规则（按开车前时间）
REFUND_RULES = [
    {'hours': 360, 'rate': 0.00},  # 开车前15天以上
    {'hours': 48, 'rate': 0.05},   # 开车前48小时以上
    {'hours': 24, 'rate': 0.10},   # 开车前24-48小时
    {'hours': 0, 'rate': 0.20},    # 开车前24小时内
]

# 票额用途
TICKET_PURPOSE = {
    'public': {'name': '公用', 'code': 'G'},
    'flexible': {'name': '机动', 'code': 'J'},
    'forbidden': {'name': '禁售', 'code': 'F'},
    'student': {'name': '学生', 'code': 'X'},
}

# 班次类型
SHIFT_TYPES = {
    'day': {'name': '白班', 'start': '00:00', 'end': '12:00'},
    'night': {'name': '夜班', 'start': '12:00', 'end': '24:00'},
}
