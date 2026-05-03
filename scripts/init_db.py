# -*- coding: utf-8 -*-
"""
数据库初始化脚本
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, User, Station, Train, TrainStop, TicketPrice, Counter
from werkzeug.security import generate_password_hash
from datetime import datetime

def init_database():
    """初始化数据库"""
    with app.app_context():
        # 创建所有表
        db.create_all()
        
        # 检查是否已有数据
        if User.query.first() is not None:
            print("数据库已有数据，跳过初始化")
            return
        
        print("开始初始化数据库...")
        
        # 创建管理员账户
        admin = User(
            employee_no='admin',
            name='系统管理员',
            password_hash=generate_password_hash('admin123'),
            role='admin',
            window_no='001号口',
            station_code='ZZO'
        )
        db.session.add(admin)
        
        # 创建售票员账户
        seller = User(
            employee_no='seller001',
            name='张三',
            password_hash=generate_password_hash('123456'),
            role='seller',
            window_no='101号口',
            station_code='ZZO'
        )
        db.session.add(seller)
        
        # 创建更多售票员
        seller2 = User(
            employee_no='seller002',
            name='李四',
            password_hash=generate_password_hash('123456'),
            role='seller',
            window_no='102号口',
            station_code='ZZO'
        )
        db.session.add(seller2)
        
        # 创建初始化票号计数器
        counter = Counter(counter_name='ticket', current_value=0, prefix='A')
        db.session.add(counter)
        
        db.session.commit()
        print("用户和计数器创建完成")
        
        # 创建车站数据
        stations_data = [
            # 京沪高铁
            {'code': 'BJN', 'name': '北京南', 'pinyin': 'beijingnan', 'region': '北京市', 'line': '京沪高铁', 'is_major': True},
            {'code': 'TJN', 'name': '天津南', 'pinyin': 'tianjinnan', 'region': '天津市', 'line': '京沪高铁', 'is_major': False},
            {'code': 'JNX', 'name': '济南西', 'pinyin': 'jinanxi', 'region': '济南市', 'line': '京沪高铁', 'is_major': True},
            {'code': 'TZX', 'name': '泰安', 'pinyin': 'taian', 'region': '泰安市', 'line': '京沪高铁', 'is_major': False},
            {'code': 'NJH', 'name': '南京南', 'pinyin': 'nanjingnan', 'region': '南京市', 'line': '京沪高铁', 'is_major': True},
            {'code': 'SHH', 'name': '上海虹桥', 'pinyin': 'shanghaihongqiao', 'region': '上海市', 'line': '京沪高铁', 'is_major': True},
            
            # 京广高铁
            {'code': 'BJX', 'name': '北京西', 'pinyin': 'beijingxi', 'region': '北京市', 'line': '京广高铁', 'is_major': True},
            {'code': 'BZD', 'name': '保定东', 'pinyin': 'baodingdong', 'region': '保定市', 'line': '京广高铁', 'is_major': False},
            {'code': 'SJZ', 'name': '石家庄', 'pinyin': 'shijiazhuang', 'region': '石家庄市', 'line': '京广高铁', 'is_major': True},
            {'code': 'XHD', 'name': '邢台东', 'pinyin': 'xingtangdong', 'region': '邢台市', 'line': '京广高铁', 'is_major': False},
            {'code': 'HZD', 'name': '邯郸东', 'pinyin': 'handandong', 'region': '邯郸市', 'line': '京广高铁', 'is_major': False},
            {'code': 'WHN', 'name': '武汉', 'pinyin': 'wuhan', 'region': '武汉市', 'line': '京广高铁', 'is_major': True},
            {'code': 'CSN', 'name': '长沙南', 'pinyin': 'changshanan', 'region': '长沙市', 'line': '京广高铁', 'is_major': True},
            {'code': 'GZN', 'name': '广州南', 'pinyin': 'guangzhounan', 'region': '广州市', 'line': '京广高铁', 'is_major': True},
            
            # 京哈铁路
            {'code': 'BJI', 'name': '北京', 'pinyin': 'beijing', 'region': '北京市', 'line': '京哈铁路', 'is_major': True},
            {'code': 'SJL', 'name': '石家庄', 'pinyin': 'shijiazhuang', 'region': '石家庄市', 'line': '京哈铁路', 'is_major': True},
            {'code': 'ZZO', 'name': '郑州', 'pinyin': 'zhengzhou', 'region': '郑州市', 'line': '京哈铁路', 'is_major': True},
            {'code': 'HRB', 'name': '哈尔滨', 'pinyin': 'haerbin', 'region': '哈尔滨市', 'line': '京哈铁路', 'is_major': True},
            
            # 京津城际
            {'code': 'TJJ', 'name': '天津', 'pinyin': 'tianjin', 'region': '天津市', 'line': '京津城际', 'is_major': True},
            
            # 其他车站
            {'code': 'XHD2', 'name': '徐州东', 'pinyin': 'xuzhoudong', 'region': '徐州市', 'line': '京沪高铁', 'is_major': True},
            {'code': 'CZD', 'name': '滁州', 'pinyin': 'chuzhou', 'region': '滁州市', 'line': '京沪高铁', 'is_major': False},
            {'code': 'BBD', 'name': '蚌埠南', 'pinyin': 'bengbunan', 'region': '蚌埠市', 'line': '京沪高铁', 'is_major': False},
            {'code': 'CBU', 'name': '苍南', 'pinyin': 'cangnan', 'region': '温州市', 'line': '京沪高铁', 'is_major': False},
            {'code': 'SHN', 'name': '上海南', 'pinyin': 'shanghainan', 'region': '上海市', 'line': '沪昆铁路', 'is_major': True},
            {'code': 'HZD2', 'name': '杭州东', 'pinyin': 'hangzhoudong', 'region': '杭州市', 'line': '沪昆高铁', 'is_major': True},
            {'code': 'XZB', 'name': '徐州', 'pinyin': 'xuzhou', 'region': '徐州市', 'line': '陇海铁路', 'is_major': True},
            {'code': 'LFZ', 'name': '洛阳龙门', 'pinyin': 'luoyanglongmen', 'region': '洛阳市', 'line': '郑西高铁', 'is_major': True},
        ]
        
        for s in stations_data:
            station = Station(
                station_code=s['code'],
                station_name=s['name'],
                station_pinyin=s['pinyin'],
                region=s['region'],
                line_name=s['line'],
                is_major=s['is_major']
            )
            db.session.add(station)
        
        db.session.commit()
        print(f"创建了 {len(stations_data)} 个车站")
        
        # 创建车次数据
        trains_data = [
            # 京沪高铁车次
            {'number': 'G1', 'type': 'G', 'start': '北京南', 'end': '上海虹桥', 'start_time': '08:00', 'end_time': '12:30', 'distance': 1318},
            {'number': 'G2', 'type': 'G', 'start': '上海虹桥', 'end': '北京南', 'start_time': '08:05', 'end_time': '12:35', 'distance': 1318},
            {'number': 'G3', 'type': 'G', 'start': '北京南', 'end': '上海虹桥', 'start_time': '09:00', 'end_time': '13:28', 'distance': 1318},
            {'number': 'G5', 'type': 'G', 'start': '北京南', 'end': '上海虹桥', 'start_time': '10:00', 'end_time': '14:28', 'distance': 1318},
            {'number': 'G7', 'type': 'G', 'start': '北京南', 'end': '上海虹桥', 'start_time': '14:00', 'end_time': '18:28', 'distance': 1318},
            {'number': 'G11', 'type': 'G', 'start': '北京南', 'end': '上海虹桥', 'start_time': '16:00', 'end_time': '20:28', 'distance': 1318},
            {'number': 'G101', 'type': 'G', 'start': '北京南', 'end': '上海虹桥', 'start_time': '07:00', 'end_time': '11:30', 'distance': 1318},
            {'number': 'G103', 'type': 'G', 'start': '北京南', 'end': '上海虹桥', 'start_time': '17:00', 'end_time': '21:30', 'distance': 1318},
            
            # 京广高铁车次
            {'number': 'G79', 'type': 'G', 'start': '北京西', 'end': '广州南', 'start_time': '08:00', 'end_time': '18:00', 'distance': 2298},
            {'number': 'G80', 'type': 'G', 'start': '广州南', 'end': '北京西', 'start_time': '08:00', 'end_time': '18:00', 'distance': 2298},
            {'number': 'G81', 'type': 'G', 'start': '北京西', 'end': '广州南', 'start_time': '09:30', 'end_time': '19:30', 'distance': 2298},
            {'number': 'G401', 'type': 'G', 'start': '北京西', 'end': '武汉', 'start_time': '07:00', 'end_time': '12:30', 'distance': 1229},
            {'number': 'G403', 'type': 'G', 'start': '北京西', 'end': '广州南', 'start_time': '08:00', 'end_time': '17:35', 'distance': 2298},
            
            # 动车车次
            {'number': 'D101', 'type': 'D', 'start': '北京南', 'end': '上海虹桥', 'start_time': '07:30', 'end_time': '15:00', 'distance': 1318},
            {'number': 'D701', 'type': 'D', 'start': '北京南', 'end': '上海虹桥', 'start_time': '09:30', 'end_time': '17:00', 'distance': 1318},
            {'number': 'D703', 'type': 'D', 'start': '北京南', 'end': '上海虹桥', 'start_time': '14:30', 'end_time': '22:00', 'distance': 1318},
            
            # 城际动车
            {'number': 'C2001', 'type': 'C', 'start': '北京南', 'end': '天津', 'start_time': '06:30', 'end_time': '07:05', 'distance': 120},
            {'number': 'C2003', 'type': 'C', 'start': '北京南', 'end': '天津', 'start_time': '07:30', 'end_time': '08:05', 'distance': 120},
            {'number': 'C2005', 'type': 'C', 'start': '北京南', 'end': '天津', 'start_time': '08:30', 'end_time': '09:05', 'distance': 120},
            {'number': 'C2007', 'type': 'C', 'start': '北京南', 'end': '天津', 'start_time': '09:30', 'end_time': '10:05', 'distance': 120},
            
            # 普快车次
            {'number': 'K101', 'type': 'K', 'start': '北京', 'end': '上海', 'start_time': '19:00', 'end_time': '06:00', 'distance': 1463},
            {'number': 'K103', 'type': 'K', 'start': '北京', 'end': '哈尔滨', 'start_time': '20:30', 'end_time': '08:30', 'distance': 1249},
            {'number': 'Z201', 'type': 'Z', 'start': '北京', 'end': '广州', 'start_time': '18:00', 'end_time': '09:30', 'distance': 2298},
            {'number': 'Z35', 'type': 'Z', 'start': '北京西', 'end': '广州', 'start_time': '23:00', 'end_time': '11:30', 'distance': 2298},
        ]
        
        train_map = {}  # 保存train_number -> train_id 的映射
        
        for t in trains_data:
            train = Train(
                train_number=t['number'],
                train_type=t['type'],
                start_station=t['start'],
                end_station=t['end'],
                start_time=t['start_time'],
                end_time=t['end_time'],
                total_distance=t['distance']
            )
            db.session.add(train)
            db.session.flush()
            train_map[t['number']] = train.train_id
        
        db.session.commit()
        print(f"创建了 {len(trains_data)} 个车次")
        
        # 创建车次经停站数据
        stops_data = {
            'G1': [
                {'station': 'BJN', 'sequence': 1, 'departure': '08:00', 'arrival': None, 'distance': 0},
                {'station': 'TJN', 'sequence': 2, 'departure': '08:15', 'arrival': '08:12', 'distance': 120},
                {'station': 'JNX', 'sequence': 3, 'departure': '09:00', 'arrival': '08:57', 'distance': 406},
                {'station': 'TZX', 'sequence': 4, 'departure': '09:20', 'arrival': '09:18', 'distance': 471},
                {'station': 'XHD2', 'sequence': 5, 'departure': '09:45', 'arrival': '09:43', 'distance': 627},
                {'station': 'NJH', 'sequence': 6, 'departure': '10:45', 'arrival': '10:42', 'distance': 1020},
                {'station': 'SHH', 'sequence': 7, 'departure': None, 'arrival': '12:30', 'distance': 1318},
            ],
            'G2': [
                {'station': 'SHH', 'sequence': 1, 'departure': '08:05', 'arrival': None, 'distance': 0},
                {'station': 'NJH', 'sequence': 2, 'departure': '09:00', 'arrival': '08:58', 'distance': 298},
                {'station': 'XHD2', 'sequence': 3, 'departure': '09:55', 'arrival': '09:53', 'distance': 691},
                {'station': 'TZX', 'sequence': 4, 'departure': '10:18', 'arrival': '10:16', 'distance': 847},
                {'station': 'JNX', 'sequence': 5, 'departure': '10:40', 'arrival': '10:38', 'distance': 912},
                {'station': 'TJN', 'sequence': 6, 'departure': '11:20', 'arrival': '11:18', 'distance': 1198},
                {'station': 'BJN', 'sequence': 7, 'departure': None, 'arrival': '12:35', 'distance': 1318},
            ],
            'G79': [
                {'station': 'BJX', 'sequence': 1, 'departure': '08:00', 'arrival': None, 'distance': 0},
                {'station': 'BZD', 'sequence': 2, 'departure': '08:45', 'arrival': '08:43', 'distance': 139},
                {'station': 'SJZ', 'sequence': 3, 'departure': '09:15', 'arrival': '09:13', 'distance': 281},
                {'station': 'HZD', 'sequence': 4, 'departure': '09:45', 'arrival': '09:43', 'distance': 428},
                {'station': 'WHN', 'sequence': 5, 'departure': '11:30', 'arrival': '11:25', 'distance': 1229},
                {'station': 'CSN', 'sequence': 6, 'departure': '13:30', 'arrival': '13:26', 'distance': 1591},
                {'station': 'GZN', 'sequence': 7, 'departure': None, 'arrival': '18:00', 'distance': 2298},
            ],
            'C2001': [
                {'station': 'BJN', 'sequence': 1, 'departure': '06:30', 'arrival': None, 'distance': 0},
                {'station': 'TJJ', 'sequence': 2, 'departure': None, 'arrival': '07:05', 'distance': 120},
            ],
            'C2003': [
                {'station': 'BJN', 'sequence': 1, 'departure': '07:30', 'arrival': None, 'distance': 0},
                {'station': 'TJJ', 'sequence': 2, 'departure': None, 'arrival': '08:05', 'distance': 120},
            ],
            'K101': [
                {'station': 'BJI', 'sequence': 1, 'departure': '19:00', 'arrival': None, 'distance': 0},
                {'station': 'XZB', 'sequence': 2, 'departure': '23:00', 'arrival': '22:55', 'distance': 689},
                {'station': 'NJH', 'sequence': 3, 'departure': '03:00', 'arrival': '02:55', 'distance': 1020},
                {'station': 'SHN', 'sequence': 4, 'departure': None, 'arrival': '06:00', 'distance': 1463},
            ],
        }
        
        # 为所有高铁和动车添加默认经停站
        default_stops = {
            'G3': [('BJN', 1, '09:00', None, 0), ('TJN', 2, '09:18', '09:15', 120), ('JNX', 3, '10:00', '09:58', 406), ('NJH', 4, '11:45', '11:42', 1020), ('SHH', 5, None, '13:28', 1318)],
            'G5': [('BJN', 1, '10:00', None, 0), ('JNX', 2, '11:00', '10:58', 406), ('NJH', 3, '12:30', '12:28', 1020), ('SHH', 4, None, '14:28', 1318)],
            'G7': [('BJN', 1, '14:00', None, 0), ('TJN', 2, '14:20', '14:17', 120), ('JNX', 3, '15:00', '14:58', 406), ('NJH', 4, '16:30', '16:28', 1020), ('SHH', 5, None, '18:28', 1318)],
            'G11': [('BJN', 1, '16:00', None, 0), ('JNX', 2, '17:00', '16:58', 406), ('NJH', 3, '18:30', '18:28', 1020), ('SHH', 4, None, '20:28', 1318)],
            'G101': [('BJN', 1, '07:00', None, 0), ('TJN', 2, '07:18', '07:16', 120), ('JNX', 3, '08:00', '07:58', 406), ('NJH', 4, '09:30', '09:28', 1020), ('SHH', 5, None, '11:30', 1318)],
            'G103': [('BJN', 1, '17:00', None, 0), ('TJN', 2, '17:18', '17:16', 120), ('JNX', 3, '18:00', '17:58', 406), ('NJH', 4, '19:30', '19:28', 1020), ('SHH', 5, None, '21:30', 1318)],
            'G80': [('GZN', 1, '08:00', None, 0), ('CSN', 2, '11:30', '11:27', 707), ('WHN', 3, '13:30', '13:27', 1069), ('HZD', 4, '15:00', '14:58', 1870), ('SJZ', 5, '15:45', '15:43', 2017), ('BJX', 6, None, '18:00', 2298)],
            'G81': [('BJX', 1, '09:30', None, 0), ('SJZ', 2, '10:45', '10:43', 281), ('WHN', 3, '13:00', '12:57', 1229), ('GZN', 4, None, '19:30', 2298)],
            'G401': [('BJX', 1, '07:00', None, 0), ('SJZ', 2, '08:00', '07:58', 281), ('HZD', 3, '08:45', '08:43', 428), ('WHN', 4, None, '12:30', 1229)],
            'G403': [('BJX', 1, '08:00', None, 0), ('BZD', 2, '08:45', '08:43', 139), ('SJZ', 3, '09:15', '09:13', 281), ('HZD', 4, '09:45', '09:43', 428), ('WHN', 5, '11:30', '11:27', 1229), ('CSN', 6, '13:30', '13:27', 1591), ('GZN', 7, None, '17:35', 2298)],
            'D101': [('BJN', 1, '07:30', None, 0), ('TJN', 2, '08:00', '07:58', 120), ('JNX', 3, '09:00', '08:58', 406), ('NJH', 4, '10:30', '10:28', 1020), ('SHH', 5, None, '15:00', 1318)],
            'D701': [('BJN', 1, '09:30', None, 0), ('TJN', 2, '10:00', '09:58', 120), ('JNX', 3, '11:00', '10:58', 406), ('NJH', 4, '12:30', '12:28', 1020), ('SHH', 5, None, '17:00', 1318)],
            'D703': [('BJN', 1, '14:30', None, 0), ('TJN', 2, '15:00', '14:58', 120), ('JNX', 3, '16:00', '15:58', 406), ('NJH', 4, '17:30', '17:28', 1020), ('SHH', 5, None, '22:00', 1318)],
            'C2005': [('BJN', 1, '08:30', None, 0), ('TJJ', 2, None, '09:05', 120)],
            'C2007': [('BJN', 1, '09:30', None, 0), ('TJJ', 2, None, '10:05', 120)],
            'K103': [('BJI', 1, '20:30', None, 0), ('SJL', 2, '23:00', '22:55', 293), ('ZZO', 3, '03:00', '02:55', 695), ('HRB', 4, None, '08:30', 1249)],
            'Z201': [('BJI', 1, '18:00', None, 0), ('SJZ', 2, '21:00', '20:55', 293), ('ZZO', 3, '01:00', '00:55', 695), ('WHN', 4, '05:00', '04:55', 1229), ('CSN', 5, '07:30', '07:25', 1591), ('GZN', 6, None, '09:30', 2298)],
            'Z35': [('BJX', 1, '23:00', None, 0), ('SJZ', 2, '02:00', '01:55', 281), ('WHN', 3, '06:00', '05:55', 1229), ('GZN', 4, None, '11:30', 2298)],
        }
        
        for train_num, stops in stops_data.items():
            train_id = train_map.get(train_num)
            if not train_id:
                continue
            
            for s in stops:
                stop = TrainStop(
                    train_id=train_id,
                    station_code=s['station'],
                    stop_sequence=s['sequence'],
                    departure_time=s['departure'],
                    arrival_time=s['arrival'],
                    distance_from_start=s['distance'],
                    seat_business=10,
                    seat_first=50,
                    seat_second=200,
                    seat_soft=30,
                    seat_hard=100,
                    seat_soft_sleeper=30,
                    seat_hard_sleeper=60
                )
                db.session.add(stop)
        
        # 添加默认经停站
        for train_num, stops in default_stops.items():
            train_id = train_map.get(train_num)
            if not train_id:
                continue
            
            for s in stops:
                stop = TrainStop(
                    train_id=train_id,
                    station_code=s[0],
                    stop_sequence=s[1],
                    departure_time=s[2],
                    arrival_time=s[3],
                    distance_from_start=s[4],
                    seat_business=10,
                    seat_first=50,
                    seat_second=200,
                    seat_soft=30,
                    seat_hard=100,
                    seat_soft_sleeper=30,
                    seat_hard_sleeper=60
                )
                db.session.add(stop)
        
        db.session.commit()
        print("车次经停站创建完成")
        
        # 创建票价数据
        prices_data = [
            # 京沪高铁票价
            {'from': 'BJN', 'to': 'TJN', 'business': 174, 'first': 88, 'second': 55, 'soft': 45},
            {'from': 'BJN', 'to': 'JNX', 'business': 694, 'first': 349, 'second': 215, 'soft': 175},
            {'from': 'BJN', 'to': 'NJH', 'business': 1333, 'first': 679, 'second': 415, 'soft': 325},
            {'from': 'BJN', 'to': 'SHH', 'business': 1748, 'first': 933, 'second': 553, 'soft': 420},
            {'from': 'TJN', 'to': 'JNX', 'business': 520, 'first': 261, 'second': 160, 'soft': 130},
            {'from': 'TJN', 'to': 'NJH', 'business': 1159, 'first': 591, 'second': 360, 'soft': 280},
            {'from': 'TJN', 'to': 'SHH', 'business': 1574, 'first': 845, 'second': 498, 'soft': 375},
            {'from': 'JNX', 'to': 'NJH', 'business': 639, 'first': 330, 'second': 200, 'soft': 150},
            {'from': 'JNX', 'to': 'SHH', 'business': 1098, 'first': 584, 'second': 338, 'soft': 245},
            {'from': 'NJH', 'to': 'SHH', 'business': 459, 'first': 254, 'second': 138, 'soft': 95},
            
            # 京广高铁票价
            {'from': 'BJX', 'to': 'BZD', 'business': 206, 'first': 105, 'second': 65, 'soft': 50},
            {'from': 'BJX', 'to': 'SJZ', 'business': 311, 'first': 156, 'second': 93, 'soft': 75},
            {'from': 'BJX', 'to': 'WHN', 'business': 1159, 'first': 588, 'second': 353, 'soft': 270},
            {'from': 'BJX', 'to': 'GZN', 'business': 1748, 'first': 933, 'second': 553, 'soft': 420},
            {'from': 'SJZ', 'to': 'WHN', 'business': 848, 'first': 432, 'second': 260, 'soft': 195},
            {'from': 'SJZ', 'to': 'GZN', 'business': 1437, 'first': 777, 'second': 460, 'soft': 345},
            {'from': 'WHN', 'to': 'CSN', 'business': 468, 'first': 234, 'second': 138, 'soft': 105},
            {'from': 'WHN', 'to': 'GZN', 'business': 919, 'first': 472, 'second': 304, 'soft': 230},
            {'from': 'CSN', 'to': 'GZN', 'business': 451, 'first': 238, 'second': 166, 'soft': 125},
            
            # 京津城际票价
            {'from': 'BJN', 'to': 'TJJ', 'business': 88, 'first': 44, 'second': 25, 'soft': 20},
            
            # 其他票价
            {'from': 'BJI', 'to': 'XZB', 'business': 0, 'first': 150, 'second': 93, 'soft': 75},
            {'from': 'BJI', 'to': 'NJH', 'business': 0, 'first': 250, 'second': 150, 'soft': 120},
            {'from': 'BJI', 'to': 'SHN', 'business': 0, 'first': 350, 'second': 200, 'soft': 150},
            {'from': 'XZB', 'to': 'NJH', 'business': 0, 'first': 150, 'second': 93, 'soft': 75},
            {'from': 'XZB', 'to': 'SHN', 'business': 0, 'first': 250, 'second': 150, 'soft': 120},
            {'from': 'BJI', 'to': 'SJL', 'business': 0, 'first': 100, 'second': 65, 'soft': 50},
            {'from': 'BJI', 'to': 'ZZO', 'business': 0, 'first': 150, 'second': 93, 'soft': 75},
            {'from': 'BJI', 'to': 'HRB', 'business': 0, 'first': 280, 'second': 165, 'soft': 130},
            {'from': 'ZZO', 'to': 'WHN', 'business': 0, 'first': 200, 'second': 120, 'soft': 95},
            {'from': 'BJX', 'to': 'SJZ', 'business': 311, 'first': 156, 'second': 93, 'soft': 75},
            {'from': 'BJX', 'to': 'HZD', 'business': 408, 'first': 206, 'second': 123, 'soft': 98},
        ]
        
        for p in prices_data:
            for seat_type, price in [('business', p['business']), ('first', p['first']), 
                                      ('second', p['second']), ('soft_seat', p['soft'])]:
                if price > 0:
                    ticket_price = TicketPrice(
                        from_station=p['from'],
                        to_station=p['to'],
                        seat_type=seat_type,
                        base_price=price
                    )
                    db.session.add(ticket_price)
        
        db.session.commit()
        print(f"创建了票价数据")
        
        print("数据库初始化完成!")

if __name__ == '__main__':
    init_database()
