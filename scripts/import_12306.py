# -*- coding: utf-8 -*-
"""
从12306官方接口导入全国车次数据
"""

import requests
import sqlite3
import json
import time
import re
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore

# 配置
DB_PATH = './data/railway.db'
STATIONS_JSON = './data/all_stations.json'
OUTPUT_DIR = './data/downloads'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 12306请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.12306.cn/',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# 信号量：限制并发数
SEMAPHORE = Semaphore(15)  # 15个线程并发

def parse_station_data(text):
    """解析车站数据
    格式：@bjb|北京北|VAP|beijingbei|bjb|0|0357|北京|||@bjd|...
    """
    stations = []
    # 分割每个车站
    parts = text.split('@')
    for part in parts:
        if not part.strip():
            continue
        fields = part.split('|')
        if len(fields) >= 5:
            station = {
                'name': fields[1],
                'telecode': fields[2],
                'pinyin': fields[3],
                'pinyin_code': fields[4].upper(),
            }
            stations.append(station)
    print(f"解析到 {len(stations)} 个车站")
    return stations

def download_stations():
    """下载12306车站数据"""
    print("=" * 50)
    print("步骤1: 下载车站数据...")
    
    url = 'https://kyfw.12306.cn/otn/resources/js/framework/station_name.js'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.encoding = 'utf-8'
        
        # 提取JSON部分
        match = re.search(r"station_names\s*='(.+)'", resp.text)
        if match:
            station_text = match.group(1)
            stations = parse_station_data(station_text)
            
            # 保存
            with open(f'{OUTPUT_DIR}/stations_12306.json', 'w', encoding='utf-8') as f:
                json.dump(stations, f, ensure_ascii=False, indent=2)
            print(f"车站数据已保存到 {OUTPUT_DIR}/stations_12306.json")
            return stations
    except Exception as e:
        print(f"下载车站数据失败: {e}")
    return []

def download_train_list():
    """下载车次列表"""
    print("=" * 50)
    print("步骤2: 下载车次列表...")
    
    url = 'https://kyfw.12306.cn/otn/resources/js/query/train_list.js'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=120)
        resp.encoding = 'utf-8'
        
        # 提取JSON部分
        match = re.search(r'var train_list\s*=\s*(.+)', resp.text)
        if match:
            train_data = json.loads(match.group(1))
            
            # 获取第一个日期的数据
            dates = sorted(train_data.keys())
            if dates:
                latest_date = dates[-1]
                print(f"使用日期: {latest_date}")
                day_trains = train_data[latest_date]
                
                all_trains = []
                for train_type, trains in day_trains.items():
                    for t in trains:
                        train_info = {
                            'train_type': train_type,
                            'train_no': t.get('train_no', ''),
                            'station_train_code': t.get('station_train_code', ''),
                        }
                        all_trains.append(train_info)
                
                # 去重（按train_no）
                seen = set()
                unique_trains = []
                for t in all_trains:
                    if t['train_no'] not in seen:
                        seen.add(t['train_no'])
                        unique_trains.append(t)
                
                print(f"车次总数: {len(all_trains)}, 去重后: {len(unique_trains)}")
                
                # 按类型统计
                type_count = {}
                for t in unique_trains:
                    tp = t['train_type']
                    type_count[tp] = type_count.get(tp, 0) + 1
                print(f"类型分布: {type_count}")
                
                # 保存
                with open(f'{OUTPUT_DIR}/train_list.json', 'w', encoding='utf-8') as f:
                    json.dump({
                        'date': latest_date,
                        'trains': unique_trains
                    }, f, ensure_ascii=False, indent=2)
                print(f"车次列表已保存到 {OUTPUT_DIR}/train_list.json")
                return unique_trains
    except Exception as e:
        print(f"下载车次列表失败: {e}")
    return []

def parse_train_code(code_str):
    """解析车次代码字符串
    格式: "G1(北京-上海)" -> (G1, 北京, 上海)
    """
    match = re.match(r'([A-Z]\d+)\((.+)-(.+)\)', code_str)
    if match:
        return match.group(1), match.group(2), match.group(3)
    return None, None, None

def get_train_detail(train_info):
    """获取单个车次详情"""
    train_no = train_info['train_no']
    station_train_code = train_info['station_train_code']
    train_type = train_info['train_type']
    
    # 解析始发终到站
    code, start, end = parse_train_code(station_train_code)
    if not code:
        return None
    
    # 跳过一些无法处理的站名
    if not start or not end:
        return None
    
    # 获取详细时刻表
    url = f'https://kyfw.12306.cn/otn/czxx/queryByTrainNo'
    params = {
        'train_no': train_no,
        'depart_date': datetime.now().strftime('%Y-%m-%d')
    }
    
    with SEMAPHORE:
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == True:
                    stops = data.get('data', {}).get('data', [])
                    if stops:
                        return {
                            'train_no': train_no,
                            'train_number': code,
                            'train_type': train_type,
                            'start_station': start,
                            'end_station': end,
                            'stops': stops
                        }
        except Exception as e:
            pass
    
    return None

def download_train_details(trains, max_workers=15, max_trains=None):
    """下载所有车次详情（多线程）"""
    print("=" * 50)
    print(f"步骤3: 下载车次详情 (并发数: {max_workers})...")
    
    # 只处理G/D/C类型（Gao铁/Dong车/C城际）
    priority_trains = [t for t in trains if t['train_type'] in ['G', 'D', 'C']]
    other_trains = [t for t in trains if t['train_type'] not in ['G', 'D', 'C']]
    
    if max_trains:
        priority_trains = priority_trains[:max_trains]
    
    print(f"G/D/C车次: {len(priority_trains)}, 其他: {len(other_trains)}")
    
    all_details = []
    completed = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(get_train_detail, t): t for t in priority_trains}
        
        for future in as_completed(futures):
            completed += 1
            if completed % 50 == 0:
                print(f"进度: {completed}/{len(priority_trains)}, 成功: {len(all_details)}, 失败: {failed}")
            
            result = future.result()
            if result:
                all_details.append(result)
            else:
                failed += 1
            
            # 每10个请求暂停一下，避免触发反爬
            if completed % 10 == 0:
                time.sleep(0.5)
    
    print(f"G/D/C车次完成: 成功 {len(all_details)}, 失败 {failed}")
    
    # 处理其他车次（较少）
    if other_trains:
        other_trains = other_trains[:1000]  # 限制数量
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(get_train_detail, t): t for t in other_trains}
            
            for future in as_completed(futures):
                completed += 1
                result = future.result()
                if result:
                    all_details.append(result)
    
    # 保存
    with open(f'{OUTPUT_DIR}/train_details.json', 'w', encoding='utf-8') as f:
        json.dump(all_details, f, ensure_ascii=False, indent=2)
    print(f"车次详情已保存到 {OUTPUT_DIR}/train_details.json (共{len(all_details)}个车次)")
    
    return all_details

def load_station_map():
    """加载车站映射表"""
    print("=" * 50)
    print("步骤4: 加载车站映射表...")
    
    station_map = {}  # name -> telecode
    
    # 从数据库加载现有车站
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT station_name, station_code FROM stations")
    for row in cur.fetchall():
        name, code = row
        station_map[name] = code
    conn.close()
    
    print(f"从数据库加载了 {len(station_map)} 个车站")
    
    # 从12306下载补充
    try:
        resp = requests.get('https://kyfw.12306.cn/otn/resources/js/framework/station_name.js', 
                          headers=HEADERS, timeout=30)
        resp.encoding = 'utf-8'
        match = re.search(r"station_names\s*='(.+)'", resp.text)
        if match:
            stations = parse_station_data(match.group(1))
            for s in stations:
                if s['name'] not in station_map:
                    station_map[s['name']] = s['telecode']
            print(f"补充后共 {len(station_map)} 个车站")
    except Exception as e:
        print(f"补充车站失败: {e}")
    
    return station_map

def estimate_price(train_type, distance):
    """估算票价"""
    prices = {}
    
    if train_type == 'G':  # 高铁
        if distance > 0:
            prices['business'] = round(distance * 1.95, 2)
            prices['first'] = round(distance * 0.77, 2)
            prices['second'] = round(distance * 0.48, 2)
    elif train_type == 'D':  # 动车
        if distance > 0:
            prices['first'] = round(distance * 0.37, 2)
            prices['second'] = round(distance * 0.23, 2)
    elif train_type == 'C':  # 城际
        if distance > 0:
            prices['first'] = round(distance * 0.45, 2)
            prices['second'] = round(distance * 0.28, 2)
    else:  # K/T/Z普快
        if distance > 0:
            prices['soft_sleeper'] = round(distance * 0.35, 2)
            prices['hard_sleeper'] = round(distance * 0.22, 2)
            prices['soft_seat'] = round(distance * 0.20, 2)
            prices['hard_seat'] = round(distance * 0.12, 2)
    
    # 确保最小票价
    for k in prices:
        if prices[k] < 5:
            prices[k] = 5.0
    
    return prices

def update_database(train_details, station_map):
    """更新数据库"""
    print("=" * 50)
    print("步骤5: 更新数据库...")
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 清空现有车次数据（保留车站和用户）
    print("清空现有车次数据...")
    cur.execute("DELETE FROM train_stops")
    cur.execute("DELETE FROM trains")
    cur.execute("DELETE FROM ticket_prices")
    
    # 插入车次和经停站
    train_count = 0
    stop_count = 0
    price_count = 0
    
    for train in train_details:
        train_number = train['train_number']
        train_type = train['train_type']
        start_station = train['start_station']
        end_station = train['end_station']
        stops = train['stops']
        
        # 获取首末站电报码
        start_code = station_map.get(start_station)
        end_code = station_map.get(end_station)
        
        if not start_code or not end_code:
            continue
        
        # 获取发车时间和到达时间
        first_stop = stops[0] if stops else {}
        last_stop = stops[-1] if stops else {}
        start_time = first_stop.get('start_time', '') or first_stop.get('arrive_time', '')
        end_time = last_stop.get('arrive_time', '') or last_stop.get('start_time', '')
        
        # 计算总里程
        total_distance = 0
        if last_stop.get('distance'):
            try:
                total_distance = int(last_stop.get('distance', 0))
            except:
                total_distance = 0
        
        # 插入车次
        try:
            cur.execute("""
                INSERT INTO trains (train_number, train_type, start_station, end_station, 
                                   start_time, end_time, total_distance, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            """, (train_number, train_type, start_station, end_station, 
                  start_time, end_time, total_distance))
            train_id = cur.lastrowid
            train_count += 1
        except Exception as e:
            # 车次可能已存在
            cur.execute("SELECT train_id FROM trains WHERE train_number = ?", (train_number,))
            row = cur.fetchone()
            if row:
                train_id = row[0]
            else:
                continue
        
        # 累计距离
        cum_distance = 0
        
        for i, stop in enumerate(stops):
            station_name = stop.get('station_name', '')
            station_code = station_map.get(station_name)
            
            if not station_code:
                continue
            
            arrive = stop.get('arrive_time', '') or stop.get('start_time', '')
            depart = stop.get('start_time', '') or stop.get('arrive_time', '')
            seq = i + 1
            
            # 距离
            dist = stop.get('distance')
            if dist:
                try:
                    cum_distance = int(dist)
                    dist_from_start = cum_distance
                except:
                    dist_from_start = cum_distance
            else:
                dist_from_start = cum_distance
            
            try:
                cur.execute("""
                    INSERT INTO train_stops (train_id, station_code, stop_sequence, 
                                            arrival_time, departure_time, distance_from_start)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (train_id, station_code, seq, arrive, depart, dist_from_start))
                stop_count += 1
            except Exception as e:
                pass
        
        # 生成票价
        if total_distance > 0:
            prices = estimate_price(train_type, total_distance)
            for seat_type, price in prices.items():
                try:
                    cur.execute("""
                        INSERT INTO ticket_prices (from_station, to_station, seat_type, base_price, price_per_km)
                        VALUES (?, ?, ?, ?, ?)
                    """, (start_code, end_code, seat_type, price, price / total_distance if total_distance else 0))
                    price_count += 1
                except:
                    pass
    
    conn.commit()
    
    print(f"插入完成: {train_count} 个车次, {stop_count} 个经停站, {price_count} 条票价")
    
    # 验证数据
    cur.execute("SELECT COUNT(*) FROM trains")
    print(f"数据库现有车次: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM train_stops")
    print(f"数据库现有经停站: {cur.fetchone()[0]}")
    
    conn.close()
    
    return train_count, stop_count

def main():
    """主函数"""
    print("=" * 60)
    print("12306数据导入工具")
    print("=" * 60)
    start_time = datetime.now()
    
    # 1. 下载车站数据
    stations = download_stations()
    
    # 2. 下载车次列表
    trains = download_train_list()
    
    if trains:
        # 3. 下载车次详情（优先G/D/C，约4000趟）
        train_details = download_train_details(trains, max_workers=15, max_trains=5000)
        
        # 4. 加载车站映射
        station_map = load_station_map()
        
        # 5. 更新数据库
        update_database(train_details, station_map)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    print("=" * 60)
    print(f"导入完成! 耗时: {elapsed:.1f} 秒")
    print("=" * 60)

if __name__ == '__main__':
    main()
