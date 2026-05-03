# -*- coding: utf-8 -*-
"""
数据库初始化脚本
"""

import sys
import os
import re
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, User, Station, Train, TrainStop, TicketPrice, Counter
from werkzeug.security import generate_password_hash
from datetime import datetime

def generate_pinyin_code(pinyin):
    """从拼音生成拼音码（每个音节首字母）"""
    matches = re.findall(r'[bcdfghjklmnpqrstwxyz]+', pinyin.lower())
    return ''.join([m[0].upper() for m in matches if m])[:4]

def load_all_stations():
    """加载所有车站数据"""
    stations_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'all_stations.json')
    
    with open(stations_file, 'r', encoding='utf-8') as f:
        all_stations = json.load(f)
    
    # 为每个站添加拼音码
    for s in all_stations:
        s['pinyin_code'] = generate_pinyin_code(s['pinyin'])
    
    return all_stations

def init_database():
    """初始化数据库"""
    with app.app_context():
        # 删除旧数据库重新创建
        db.drop_all()
        db.create_all()
        
        print("开始初始化数据库...")
        
        # 创建管理员账户
        admin = User(
            employee_no='admin',
            name='系统管理员',
            password_hash=generate_password_hash('admin123'),
            role='admin',
            window_no='001号口',
            station_code='ZZF'  # 郑州站电报码
        )
        db.session.add(admin)
        
        # 创建售票员账户
        seller = User(
            employee_no='seller001',
            name='张三',
            password_hash=generate_password_hash('123456'),
            role='seller',
            window_no='101号口',
            station_code='ZZF'
        )
        db.session.add(seller)
        
        # 创建更多售票员
        seller2 = User(
            employee_no='seller002',
            name='李四',
            password_hash=generate_password_hash('123456'),
            role='seller',
            window_no='102号口',
            station_code='ZZF'
        )
        db.session.add(seller2)
        
        # 创建初始化票号计数器
        counter = Counter(counter_name='ticket', current_value=0, prefix='A')
        db.session.add(counter)
        
        db.session.commit()
        print("用户和计数器创建完成")
        
        # 加载并创建所有车站
        all_stations = load_all_stations()
        
        # 建立站名到车站信息的映射
        name_to_station = {s['name']: s for s in all_stations}
        
        # 为现有27个车站分配线路信息
        line_assignments = {
            "北京南": {"line": "京沪高铁", "is_major": True, "region": "北京市"},
            "天津南": {"line": "京沪高铁", "is_major": False, "region": "天津市"},
            "济南西": {"line": "京沪高铁", "is_major": True, "region": "济南市"},
            "泰安": {"line": "京沪高铁", "is_major": False, "region": "泰安市"},
            "南京南": {"line": "京沪高铁", "is_major": True, "region": "南京市"},
            "上海虹桥": {"line": "京沪高铁", "is_major": True, "region": "上海市"},
            "北京西": {"line": "京广高铁", "is_major": True, "region": "北京市"},
            "保定东": {"line": "京广高铁", "is_major": False, "region": "保定市"},
            "石家庄": {"line": "京广高铁", "is_major": True, "region": "石家庄市"},
            "邢台东": {"line": "京广高铁", "is_major": False, "region": "邢台市"},
            "邯郸东": {"line": "京广高铁", "is_major": False, "region": "邯郸市"},
            "武汉": {"line": "京广高铁", "is_major": True, "region": "武汉市"},
            "长沙南": {"line": "京广高铁", "is_major": True, "region": "长沙市"},
            "广州南": {"line": "京广高铁", "is_major": True, "region": "广州市"},
            "北京": {"line": "京哈铁路", "is_major": True, "region": "北京市"},
            "天津": {"line": "京津城际", "is_major": True, "region": "天津市"},
            "哈尔滨": {"line": "京哈铁路", "is_major": True, "region": "哈尔滨市"},
            "郑州": {"line": "京哈铁路", "is_major": True, "region": "郑州市"},
            "徐州东": {"line": "京沪高铁", "is_major": True, "region": "徐州市"},
            "滁州": {"line": "京沪高铁", "is_major": False, "region": "滁州市"},
            "蚌埠南": {"line": "京沪高铁", "is_major": False, "region": "蚌埠市"},
            "苍南": {"line": "杭深铁路", "is_major": False, "region": "温州市"},
            "上海南": {"line": "沪昆铁路", "is_major": True, "region": "上海市"},
            "杭州东": {"line": "沪昆高铁", "is_major": True, "region": "杭州市"},
            "徐州": {"line": "陇海铁路", "is_major": True, "region": "徐州市"},
            "洛阳龙门": {"line": "郑西高铁", "is_major": True, "region": "洛阳市"},
            "长沙": {"line": "京广铁路", "is_major": True, "region": "长沙市"},
        }
        
        # 创建所有车站（使用电报码作为station_code）
        for s in all_stations:
            name = s['name']
            info = line_assignments.get(name, {})
            
            station = Station(
                station_code=s['telecode'],  # 使用电报码作为station_code
                station_name=name,
                station_pinyin=s['pinyin'],
                pinyin_code=s['pinyin_code'],
                telecode=s['telecode'],
                region=info.get('region', ''),
                line_name=info.get('line', ''),
                is_major=info.get('is_major', False)
            )
            db.session.add(station)
        
        db.session.commit()
        print(f"创建了 {len(all_stations)} 个车站")
        
        # 建立站名到电报码的映射
        name_to_telecode = {s['name']: s['telecode'] for s in all_stations}
        
        def get_telecode(name):
            """获取站名的电报码"""
            return name_to_telecode.get(name, None)
        
        # 创建车次数据（使用站名）
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
        
        # 创建车次经停站数据（使用电报码）
        # 电报码映射
        tc = {
            '北京南': 'VNP', '天津南': 'TIP', '济南西': 'JGK', '泰安': 'TMK',
            '南京南': 'NKH', '上海虹桥': 'AOH', '北京西': 'BXP', '保定东': 'BMP',
            '石家庄': 'SJP', '邢台东': 'EDP', '邯郸东': 'HPP', '武汉': 'WHN',
            '长沙南': 'CWQ', '广州南': 'IZQ', '北京': 'BJP', '天津': 'TJP',
            '哈尔滨': 'HBB', '郑州': 'ZZF', '徐州东': 'UUH', '滁州': 'CXH',
            '蚌埠南': 'BMH', '苍南': 'CEH', '上海南': 'SNH', '杭州东': 'HGH',
            '徐州': 'XCH', '洛阳龙门': 'LLF', '长沙': 'CSQ', '上海': 'SHH',
            '广州': 'GZQ'
        }
        
        stops_data = {
            'G1': [
                {'station': tc['北京南'], 'sequence': 1, 'departure': '08:00', 'arrival': None, 'distance': 0},
                {'station': tc['天津南'], 'sequence': 2, 'departure': '08:15', 'arrival': '08:12', 'distance': 120},
                {'station': tc['济南西'], 'sequence': 3, 'departure': '09:00', 'arrival': '08:57', 'distance': 406},
                {'station': tc['泰安'], 'sequence': 4, 'departure': '09:20', 'arrival': '09:18', 'distance': 471},
                {'station': tc['徐州东'], 'sequence': 5, 'departure': '09:45', 'arrival': '09:43', 'distance': 627},
                {'station': tc['南京南'], 'sequence': 6, 'departure': '10:45', 'arrival': '10:42', 'distance': 1020},
                {'station': tc['上海虹桥'], 'sequence': 7, 'departure': None, 'arrival': '12:30', 'distance': 1318},
            ],
            'G2': [
                {'station': tc['上海虹桥'], 'sequence': 1, 'departure': '08:05', 'arrival': None, 'distance': 0},
                {'station': tc['南京南'], 'sequence': 2, 'departure': '09:00', 'arrival': '08:58', 'distance': 298},
                {'station': tc['徐州东'], 'sequence': 3, 'departure': '09:55', 'arrival': '09:53', 'distance': 691},
                {'station': tc['泰安'], 'sequence': 4, 'departure': '10:18', 'arrival': '10:16', 'distance': 847},
                {'station': tc['济南西'], 'sequence': 5, 'departure': '10:40', 'arrival': '10:38', 'distance': 912},
                {'station': tc['天津南'], 'sequence': 6, 'departure': '11:20', 'arrival': '11:18', 'distance': 1198},
                {'station': tc['北京南'], 'sequence': 7, 'departure': None, 'arrival': '12:35', 'distance': 1318},
            ],
            'G79': [
                {'station': tc['北京西'], 'sequence': 1, 'departure': '08:00', 'arrival': None, 'distance': 0},
                {'station': tc['保定东'], 'sequence': 2, 'departure': '08:45', 'arrival': '08:43', 'distance': 139},
                {'station': tc['石家庄'], 'sequence': 3, 'departure': '09:15', 'arrival': '09:13', 'distance': 281},
                {'station': tc['邢台东'], 'sequence': 4, 'departure': '09:45', 'arrival': '09:43', 'distance': 428},
                {'station': tc['邯郸东'], 'sequence': 5, 'departure': '10:15', 'arrival': '10:13', 'distance': 528},
                {'station': tc['武汉'], 'sequence': 6, 'departure': '11:30', 'arrival': '11:25', 'distance': 1229},
                {'station': tc['长沙南'], 'sequence': 7, 'departure': '13:30', 'arrival': '13:26', 'distance': 1591},
                {'station': tc['广州南'], 'sequence': 8, 'departure': None, 'arrival': '18:00', 'distance': 2298},
            ],
            'C2001': [
                {'station': tc['北京南'], 'sequence': 1, 'departure': '06:30', 'arrival': None, 'distance': 0},
                {'station': tc['天津'], 'sequence': 2, 'departure': None, 'arrival': '07:05', 'distance': 120},
            ],
            'C2003': [
                {'station': tc['北京南'], 'sequence': 1, 'departure': '07:30', 'arrival': None, 'distance': 0},
                {'station': tc['天津'], 'sequence': 2, 'departure': None, 'arrival': '08:05', 'distance': 120},
            ],
            'K101': [
                {'station': tc['北京'], 'sequence': 1, 'departure': '19:00', 'arrival': None, 'distance': 0},
                {'station': tc['徐州'], 'sequence': 2, 'departure': '23:00', 'arrival': '22:55', 'distance': 689},
                {'station': tc['南京南'], 'sequence': 3, 'departure': '03:00', 'arrival': '02:55', 'distance': 1020},
                {'station': tc['上海'], 'sequence': 4, 'departure': None, 'arrival': '06:00', 'distance': 1463},
            ],
        }
        
        # 为所有高铁和动车添加默认经停站（使用电报码）
        default_stops = {
            'G3': [
                (tc['北京南'], 1, '09:00', None, 0), 
                (tc['天津南'], 2, '09:18', '09:15', 120), 
                (tc['济南西'], 3, '10:00', '09:58', 406), 
                (tc['南京南'], 4, '11:45', '11:42', 1020), 
                (tc['上海虹桥'], 5, None, '13:28', 1318)
            ],
            'G5': [
                (tc['北京南'], 1, '10:00', None, 0), 
                (tc['济南西'], 2, '11:00', '10:58', 406), 
                (tc['南京南'], 3, '12:30', '12:28', 1020), 
                (tc['上海虹桥'], 4, None, '14:28', 1318)
            ],
            'G7': [
                (tc['北京南'], 1, '14:00', None, 0), 
                (tc['天津南'], 2, '14:20', '14:17', 120), 
                (tc['济南西'], 3, '15:00', '14:58', 406), 
                (tc['南京南'], 4, '16:30', '16:28', 1020), 
                (tc['上海虹桥'], 5, None, '18:28', 1318)
            ],
            'G11': [
                (tc['北京南'], 1, '16:00', None, 0), 
                (tc['济南西'], 2, '17:00', '16:58', 406), 
                (tc['南京南'], 3, '18:30', '18:28', 1020), 
                (tc['上海虹桥'], 4, None, '20:28', 1318)
            ],
            'G101': [
                (tc['北京南'], 1, '07:00', None, 0), 
                (tc['天津南'], 2, '07:18', '07:16', 120), 
                (tc['济南西'], 3, '08:00', '07:58', 406), 
                (tc['南京南'], 4, '09:30', '09:28', 1020), 
                (tc['上海虹桥'], 5, None, '11:30', 1318)
            ],
            'G103': [
                (tc['北京南'], 1, '17:00', None, 0), 
                (tc['天津南'], 2, '17:18', '17:16', 120), 
                (tc['济南西'], 3, '18:00', '17:58', 406), 
                (tc['南京南'], 4, '19:30', '19:28', 1020), 
                (tc['上海虹桥'], 5, None, '21:30', 1318)
            ],
            'G80': [
                (tc['广州南'], 1, '08:00', None, 0), 
                (tc['长沙南'], 2, '11:30', '11:27', 707), 
                (tc['武汉'], 3, '13:30', '13:27', 1069), 
                (tc['邯郸东'], 4, '15:00', '14:58', 1870), 
                (tc['石家庄'], 5, '15:45', '15:43', 2017), 
                (tc['北京西'], 6, None, '18:00', 2298)
            ],
            'G81': [
                (tc['北京西'], 1, '09:30', None, 0), 
                (tc['石家庄'], 2, '10:45', '10:43', 281), 
                (tc['武汉'], 3, '13:00', '12:57', 1229), 
                (tc['广州南'], 4, None, '19:30', 2298)
            ],
            'G401': [
                (tc['北京西'], 1, '07:00', None, 0), 
                (tc['石家庄'], 2, '08:00', '07:58', 281), 
                (tc['邯郸东'], 3, '08:45', '08:43', 428), 
                (tc['武汉'], 4, None, '12:30', 1229)
            ],
            'G403': [
                (tc['北京西'], 1, '08:00', None, 0), 
                (tc['保定东'], 2, '08:45', '08:43', 139), 
                (tc['石家庄'], 3, '09:15', '09:13', 281), 
                (tc['邢台东'], 4, '09:45', '09:43', 428), 
                (tc['武汉'], 5, '11:30', '11:27', 1229), 
                (tc['长沙南'], 6, '13:30', '13:27', 1591), 
                (tc['广州南'], 7, None, '17:35', 2298)
            ],
            'D101': [
                (tc['北京南'], 1, '07:30', None, 0), 
                (tc['天津南'], 2, '08:00', '07:58', 120), 
                (tc['济南西'], 3, '09:00', '08:58', 406), 
                (tc['南京南'], 4, '10:30', '10:28', 1020), 
                (tc['上海虹桥'], 5, None, '15:00', 1318)
            ],
            'D701': [
                (tc['北京南'], 1, '09:30', None, 0), 
                (tc['天津南'], 2, '10:00', '09:58', 120), 
                (tc['济南西'], 3, '11:00', '10:58', 406), 
                (tc['南京南'], 4, '12:30', '12:28', 1020), 
                (tc['上海虹桥'], 5, None, '17:00', 1318)
            ],
            'D703': [
                (tc['北京南'], 1, '14:30', None, 0), 
                (tc['天津南'], 2, '15:00', '14:58', 120), 
                (tc['济南西'], 3, '16:00', '15:58', 406), 
                (tc['南京南'], 4, '17:30', '17:28', 1020), 
                (tc['上海虹桥'], 5, None, '22:00', 1318)
            ],
            'C2005': [
                (tc['北京南'], 1, '08:30', None, 0), 
                (tc['天津'], 2, None, '09:05', 120)
            ],
            'C2007': [
                (tc['北京南'], 1, '09:30', None, 0), 
                (tc['天津'], 2, None, '10:05', 120)
            ],
            'K103': [
                (tc['北京'], 1, '20:30', None, 0), 
                (tc['石家庄'], 2, '23:00', '22:55', 293), 
                (tc['郑州'], 3, '03:00', '02:55', 695), 
                (tc['哈尔滨'], 4, None, '08:30', 1249)
            ],
            'Z201': [
                (tc['北京'], 1, '18:00', None, 0), 
                (tc['石家庄'], 2, '21:00', '20:55', 293), 
                (tc['郑州'], 3, '01:00', '00:55', 695), 
                (tc['武汉'], 4, '05:00', '04:55', 1229), 
                (tc['长沙'], 5, '07:30', '07:25', 1591), 
                (tc['广州'], 6, None, '09:30', 2298)
            ],
            'Z35': [
                (tc['北京西'], 1, '23:00', None, 0), 
                (tc['石家庄'], 2, '02:00', '01:55', 281), 
                (tc['武汉'], 3, '06:00', '05:55', 1229), 
                (tc['广州'], 4, None, '11:30', 2298)
            ],
        }
        
        # 插入所有经停站
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
        
        # 创建票价数据（使用电报码）
        prices_data = [
            # 京沪高铁票价
            {'from': tc['北京南'], 'to': tc['天津南'], 'business': 174, 'first': 88, 'second': 55, 'soft': 45},
            {'from': tc['北京南'], 'to': tc['济南西'], 'business': 694, 'first': 349, 'second': 215, 'soft': 175},
            {'from': tc['北京南'], 'to': tc['南京南'], 'business': 1333, 'first': 679, 'second': 415, 'soft': 325},
            {'from': tc['北京南'], 'to': tc['上海虹桥'], 'business': 1748, 'first': 933, 'second': 553, 'soft': 420},
            {'from': tc['天津南'], 'to': tc['济南西'], 'business': 520, 'first': 261, 'second': 160, 'soft': 130},
            {'from': tc['天津南'], 'to': tc['南京南'], 'business': 1159, 'first': 591, 'second': 360, 'soft': 280},
            {'from': tc['天津南'], 'to': tc['上海虹桥'], 'business': 1574, 'first': 845, 'second': 498, 'soft': 375},
            {'from': tc['济南西'], 'to': tc['南京南'], 'business': 639, 'first': 330, 'second': 200, 'soft': 150},
            {'from': tc['济南西'], 'to': tc['上海虹桥'], 'business': 1098, 'first': 584, 'second': 338, 'soft': 245},
            {'from': tc['南京南'], 'to': tc['上海虹桥'], 'business': 459, 'first': 254, 'second': 138, 'soft': 95},
            
            # 京广高铁票价
            {'from': tc['北京西'], 'to': tc['保定东'], 'business': 206, 'first': 105, 'second': 65, 'soft': 50},
            {'from': tc['北京西'], 'to': tc['石家庄'], 'business': 311, 'first': 156, 'second': 93, 'soft': 75},
            {'from': tc['北京西'], 'to': tc['武汉'], 'business': 1159, 'first': 588, 'second': 353, 'soft': 270},
            {'from': tc['北京西'], 'to': tc['广州南'], 'business': 1748, 'first': 933, 'second': 553, 'soft': 420},
            {'from': tc['石家庄'], 'to': tc['武汉'], 'business': 848, 'first': 432, 'second': 260, 'soft': 195},
            {'from': tc['石家庄'], 'to': tc['广州南'], 'business': 1437, 'first': 777, 'second': 460, 'soft': 345},
            {'from': tc['武汉'], 'to': tc['长沙南'], 'business': 468, 'first': 234, 'second': 138, 'soft': 105},
            {'from': tc['武汉'], 'to': tc['广州南'], 'business': 919, 'first': 472, 'second': 304, 'soft': 230},
            {'from': tc['长沙南'], 'to': tc['广州南'], 'business': 451, 'first': 238, 'second': 166, 'soft': 125},
            
            # 京津城际票价
            {'from': tc['北京南'], 'to': tc['天津'], 'business': 88, 'first': 44, 'second': 25, 'soft': 20},
            
            # 其他票价
            {'from': tc['北京'], 'to': tc['徐州'], 'business': 0, 'first': 150, 'second': 93, 'soft': 75},
            {'from': tc['北京'], 'to': tc['南京南'], 'business': 0, 'first': 250, 'second': 150, 'soft': 120},
            {'from': tc['北京'], 'to': tc['上海'], 'business': 0, 'first': 350, 'second': 200, 'soft': 150},
            {'from': tc['徐州'], 'to': tc['南京南'], 'business': 0, 'first': 150, 'second': 93, 'soft': 75},
            {'from': tc['徐州'], 'to': tc['上海'], 'business': 0, 'first': 250, 'second': 150, 'soft': 120},
            {'from': tc['北京'], 'to': tc['石家庄'], 'business': 0, 'first': 100, 'second': 65, 'soft': 50},
            {'from': tc['北京'], 'to': tc['郑州'], 'business': 0, 'first': 150, 'second': 93, 'soft': 75},
            {'from': tc['北京'], 'to': tc['哈尔滨'], 'business': 0, 'first': 280, 'second': 165, 'soft': 130},
            {'from': tc['郑州'], 'to': tc['武汉'], 'business': 0, 'first': 200, 'second': 120, 'soft': 95},
            {'from': tc['北京西'], 'to': tc['石家庄'], 'business': 311, 'first': 156, 'second': 93, 'soft': 75},
            {'from': tc['北京西'], 'to': tc['邯郸东'], 'business': 408, 'first': 206, 'second': 123, 'soft': 98},
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
