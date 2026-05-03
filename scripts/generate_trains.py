# -*- coding: utf-8 -*-
"""
生成车次数据脚本
基于车次列表生成模拟的经停站数据
"""

import json
import re
import sqlite3
import os
import random
from datetime import datetime

# ========== 配置 ==========
DB_PATH = './data/railway.db'
STATION_DATA_PATH = './data/all_stations.json'

# 主要城市间的距离表（单位：公里）
DISTANCE_TABLE = {
    ('北京', '上海'): 1318,
    ('北京', '广州'): 2298,
    ('北京', '深圳'): 2400,
    ('北京', '武汉'): 1225,
    ('北京', '西安'): 1200,
    ('北京', '成都'): 2040,
    ('北京', '重庆'): 2380,
    ('北京', '南京'): 1157,
    ('北京', '杭州'): 1279,
    ('北京', '天津'): 120,
    ('北京', '石家庄'): 283,
    ('北京', '郑州'): 695,
    ('北京', '济南'): 500,
    ('北京', '青岛'): 880,
    ('北京', '沈阳'): 700,
    ('北京', '哈尔滨'): 1250,
    ('上海', '广州'): 1532,
    ('上海', '武汉'): 1068,
    ('上海', '西安'): 1510,
    ('上海', '成都'): 2500,
    ('上海', '南京'): 300,
    ('上海', '杭州'): 200,
    ('广州', '武汉'): 1069,
    ('广州', '深圳'): 139,
    ('广州', '成都'): 2200,
    ('广州', '重庆'): 1500,
    ('武汉', '西安'): 1033,
    ('武汉', '成都'): 1614,
    ('武汉', '重庆'): 1200,
    ('武汉', '长沙'): 350,
    ('西安', '成都'): 842,
    ('西安', '兰州'): 730,
    ('成都', '重庆'): 505,
    ('成都', '贵阳'): 500,
    ('成都', '昆明'): 1100,
    ('重庆', '贵阳'): 400,
    ('南京', '杭州'): 500,
    ('杭州', '福州'): 800,
    ('杭州', '厦门'): 1200,
    ('沈阳', '长春'): 300,
    ('沈阳', '哈尔滨'): 550,
    ('长春', '哈尔滨'): 250,
}

def load_stations():
    '''加载车站映射'''
    stations = {}
    
    if os.path.exists(STATION_DATA_PATH):
        with open(STATION_DATA_PATH, 'r', encoding='utf-8') as f:
            for item in json.load(f):
                if item.get('name') and item.get('telecode'):
                    stations[item['name']] = {
                        'code': item['telecode'],
                        'pinyin': item.get('pinyin', ''),
                        'pinyin_code': item.get('pinyin_code', '')
                    }
    
    print('加载了', len(stations), '个车站')
    return stations

def estimate_distance(start, end):
    '''估算距离'''
    key = (start, end)
    reverse_key = (end, start)
    
    if key in DISTANCE_TABLE:
        return DISTANCE_TABLE[key]
    elif reverse_key in DISTANCE_TABLE:
        return DISTANCE_TABLE[reverse_key]
    else:
        return random.randint(300, 2000)

def generate_route_stations(start, end, stations, max_stops=8):
    '''生成路线的经停站'''
    result = []
    
    start_code = stations.get(start, {}).get('code')
    if not start_code:
        return []
    result.append((start, start_code))
    
    major_cities = [
        '北京', '上海', '广州', '深圳', '武汉', '西安', '成都', '重庆', 
        '南京', '杭州', '天津', '石家庄', '郑州', '济南', '青岛', '长沙',
        '昆明', '贵阳', '南宁', '福州', '厦门', '南昌', '合肥', '太原',
        '沈阳', '长春', '哈尔滨', '大连', '兰州', '乌鲁木齐', '拉萨'
    ]
    
    middle_cities = [c for c in major_cities if c != start and c != end]
    random.shuffle(middle_cities)
    
    for city in middle_cities:
        if city in stations:
            city_code = stations[city]['code']
            if city_code:
                result.append((city, city_code))
                if len(result) >= max_stops:
                    break
    
    end_code = stations.get(end, {}).get('code')
    if end_code and (len(result) < 2 or end_code != result[-1][1]):
        result.append((end, end_code))
    
    return result

def calculate_times(train_type, stop_count):
    '''计算各站时间'''
    if train_type == 'G':
        base_interval = random.randint(8, 15)
    elif train_type == 'D':
        base_interval = random.randint(10, 20)
    elif train_type == 'C':
        base_interval = random.randint(5, 12)
    else:
        base_interval = random.randint(15, 30)
    
    current_hour = random.randint(6, 20)
    current_min = random.randint(0, 59)
    
    start_time = '%02d:%02d' % (current_hour, current_min)
    
    stop_times = []
    elapsed = 0
    
    for i in range(stop_count):
        arrive = '%02d:%02d' % (current_hour, current_min)
        
        if i == 0:
            depart_min = current_min + random.randint(1, 5)
            depart_hour = current_hour + depart_min // 60
            depart_min = depart_min % 60
            depart = '%02d:%02d' % (depart_hour, depart_min)
        elif i == stop_count - 1:
            depart = arrive
            depart_hour, depart_min = current_hour, current_min
        else:
            stop_min = random.randint(2, 10)
            elapsed += stop_min
            depart_hour = current_hour + elapsed // 60
            depart_min = current_min + elapsed % 60
            depart_hour += depart_min // 60
            depart_min = depart_min % 60
            depart = '%02d:%02d' % (depart_hour, depart_min)
        
        stop_times.append({'arrive': arrive, 'depart': depart})
        
        elapsed += base_interval
        current_hour = (current_hour * 60 + current_min + elapsed) // 60
        current_min = (current_min + elapsed) % 60
        elapsed = 0
    
    end_time = stop_times[-1]['arrive'] if stop_times else start_time
    
    return start_time, end_time, stop_times

def calculate_prices(train_type, distance, start_code, end_code):
    '''计算票价'''
    prices = {}
    
    if distance <= 0:
        return prices
    
    if train_type == 'G':
        prices['business'] = round(distance * 1.95, 2)
        prices['first'] = round(distance * 0.77, 2)
        prices['second'] = round(distance * 0.48, 2)
    elif train_type == 'D':
        prices['first'] = round(distance * 0.37, 2)
        prices['second'] = round(distance * 0.23, 2)
    elif train_type == 'C':
        prices['first'] = round(distance * 0.45, 2)
        prices['second'] = round(distance * 0.28, 2)
    else:
        prices['soft_sleeper'] = round(distance * 0.35, 2)
        prices['hard_sleeper'] = round(distance * 0.22, 2)
        prices['soft_seat'] = round(distance * 0.20, 2)
        prices['hard_seat'] = round(distance * 0.12, 2)
    
    for k in prices:
        if prices[k] < 5:
            prices[k] = 5.0
    
    return prices

def generate_train_data():
    '''生成车次数据'''
    print('='*60)
    print('开始生成车次数据...')
    print('时间:', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    stations = load_stations()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print('清空现有数据...')
    cur.execute('DELETE FROM train_stops')
    cur.execute('DELETE FROM trains')
    cur.execute('DELETE FROM ticket_prices')
    conn.commit()
    
    print('解析车次列表...')
    with open('./data/downloads/train_list.json', 'r', encoding='utf-8') as f:
        train_data = json.load(f)
    
    trains = train_data['trains']
    print('共有', len(trains), '个车次')
    
    stats = {'G': 0, 'D': 0, 'C': 0, 'K': 0, 'T': 0, 'Z': 0, 'O': 0}
    total_inserted = 0
    total_stops = 0
    total_prices = 0
    route_cache = {}
    
    for train in trains:
        train_type = train['train_type']
        station_code = train['station_train_code']
        
        match = re.match(r'([A-Z]\d+|[A-Z]{2})\((.+)-(.+)\)', station_code)
        if not match:
            continue
        
        train_no = match.group(1)
        start_name = match.group(2)
        end_name = match.group(3)
        
        start_code = stations.get(start_name, {}).get('code')
        end_code = stations.get(end_name, {}).get('code')
        
        if not start_code or not end_code:
            continue
        
        route_key = (start_name, end_name)
        if route_key not in route_cache:
            route_cache[route_key] = generate_route_stations(start_name, end_name, stations)
        
        stops = route_cache[route_key]
        if not stops:
            continue
        
        start_time, end_time, stop_times = calculate_times(train_type, len(stops))
        total_distance = estimate_distance(start_name, end_name)
        
        try:
            cur.execute('''
                INSERT INTO trains (train_number, train_type, start_station, end_station, 
                                   start_time, end_time, total_distance, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            ''', (train_no, train_type, start_name, end_name, start_time, end_time, total_distance))
            train_id = cur.lastrowid
        except:
            continue
        
        total_inserted += 1
        stats[train_type] = stats.get(train_type, 0) + 1
        
        cum_distance = 0
        segment_distance = total_distance // len(stops) if stops else 0
        
        for i, (stop_name, stop_code) in enumerate(stops):
            arrive = stop_times[i]['arrive']
            depart = stop_times[i]['depart']
            
            if i == len(stops) - 1:
                cum_distance = total_distance
            else:
                cum_distance = (i + 1) * segment_distance
            
            try:
                cur.execute('''
                    INSERT INTO train_stops (train_id, station_code, stop_sequence, 
                                           arrival_time, departure_time, distance_from_start)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (train_id, stop_code, i + 1, arrive, depart, cum_distance))
                total_stops += 1
            except:
                pass
        
        prices = calculate_prices(train_type, total_distance, start_code, end_code)
        for seat_type, price in prices.items():
            try:
                cur.execute('''
                    INSERT INTO ticket_prices (from_station, to_station, seat_type, base_price)
                    VALUES (?, ?, ?, ?)
                ''', (start_code, end_code, seat_type, price))
                total_prices += 1
            except:
                pass
        
        if total_inserted % 1000 == 0:
            conn.commit()
            print('已处理', total_inserted, '个车次...')
    
    conn.commit()
    
    cur.execute('SELECT COUNT(*) FROM trains')
    db_train_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM train_stops')
    db_stop_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM ticket_prices')
    db_price_count = cur.fetchone()[0]
    
    conn.close()
    
    print()
    print('='*60)
    print('数据生成完成!')
    print('总计插入:', total_inserted, '个车次,', total_stops, '个经停站,', total_prices, '条票价')
    print('数据库验证:', db_train_count, '个车次,', db_stop_count, '个经停站,', db_price_count, '条票价')
    print('类型分布: G=%d, D=%d, C=%d, K=%d, T=%d, Z=%d' % (stats['G'], stats['D'], stats['C'], stats['K'], stats['T'], stats['Z']))
    print('='*60)

if __name__ == '__main__':
    generate_train_data()
