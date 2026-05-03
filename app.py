# -*- coding: utf-8 -*-
"""
WebTRS 应用入口
模拟铁路车站人工售票系统
"""

from flask import Flask, render_template, session, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import json

# 导入配置
import config

# 创建Flask应用
app = Flask(__name__)
app.config.from_object(config)

# 确保数据目录存在
os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)

# 初始化数据库
db = SQLAlchemy(app)

# 初始化登录管理器
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==================== 数据模型 ====================

class User(UserMixin, db.Model):
    """用户/售票员模型"""
    __tablename__ = 'users'
    
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_no = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='seller')
    window_no = db.Column(db.String(10))
    station_code = db.Column(db.String(6))
    status = db.Column(db.String(10), default='active')
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def get_id(self):
        return str(self.user_id)

class Station(db.Model):
    """车站模型"""
    __tablename__ = 'stations'
    
    station_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    station_code = db.Column(db.String(6), unique=True, nullable=False)
    station_name = db.Column(db.String(50), nullable=False)
    station_pinyin = db.Column(db.String(100))
    region = db.Column(db.String(20))
    line_name = db.Column(db.String(50))
    is_major = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(10), default='active')
    created_at = db.Column(db.DateTime, default=datetime.now)

class Train(db.Model):
    """车次模型"""
    __tablename__ = 'trains'
    
    train_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    train_number = db.Column(db.String(10), unique=True, nullable=False)
    train_type = db.Column(db.String(10), nullable=False)
    start_station = db.Column(db.String(50), nullable=False)
    end_station = db.Column(db.String(50), nullable=False)
    running_days = db.Column(db.String(7), default='1234567')
    start_time = db.Column(db.String(10))
    end_time = db.Column(db.String(10))
    total_distance = db.Column(db.Integer)
    status = db.Column(db.String(10), default='active')
    created_at = db.Column(db.DateTime, default=datetime.now)

class TrainStop(db.Model):
    """车次经停站模型"""
    __tablename__ = 'train_stops'
    
    stop_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    train_id = db.Column(db.Integer, db.ForeignKey('trains.train_id'), nullable=False)
    station_code = db.Column(db.String(6), db.ForeignKey('stations.station_code'), nullable=False)
    stop_sequence = db.Column(db.Integer, nullable=False)
    arrival_time = db.Column(db.String(10))
    departure_time = db.Column(db.String(10))
    distance_from_start = db.Column(db.Integer)
    
    # 各席别余票数量
    seat_business = db.Column(db.Integer, default=10)
    seat_first = db.Column(db.Integer, default=50)
    seat_second = db.Column(db.Integer, default=200)
    seat_soft = db.Column(db.Integer, default=30)
    seat_hard = db.Column(db.Integer, default=100)
    seat_soft_sleeper = db.Column(db.Integer, default=30)
    seat_hard_sleeper = db.Column(db.Integer, default=60)
    
    train = db.relationship('Train', backref='stops')
    station = db.relationship('Station', backref='stops')

class TicketPrice(db.Model):
    """票价模型"""
    __tablename__ = 'ticket_prices'
    
    price_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    from_station = db.Column(db.String(6), db.ForeignKey('stations.station_code'), nullable=False)
    to_station = db.Column(db.String(6), db.ForeignKey('stations.station_code'), nullable=False)
    seat_type = db.Column(db.String(20), nullable=False)
    base_price = db.Column(db.Float, nullable=False)
    price_per_km = db.Column(db.Float)
    effective_date = db.Column(db.Date, default=datetime.now().date)
    
    from_station_obj = db.relationship('Station', foreign_keys=[from_station])
    to_station_obj = db.relationship('Station', foreign_keys=[to_station])

class Ticket(db.Model):
    """车票模型"""
    __tablename__ = 'tickets'
    
    ticket_id = db.Column(db.String(10), primary_key=True)
    train_id = db.Column(db.Integer, db.ForeignKey('trains.train_id'))
    train_number = db.Column(db.String(10), nullable=False)
    passenger_name = db.Column(db.String(50))
    id_number = db.Column(db.String(30))
    id_type = db.Column(db.String(10), default='id_card')
    
    from_station = db.Column(db.String(50), nullable=False)
    to_station = db.Column(db.String(50), nullable=False)
    travel_date = db.Column(db.String(10), nullable=False)
    departure_time = db.Column(db.String(10), nullable=False)
    
    carriage = db.Column(db.String(5))
    seat_number = db.Column(db.String(10))
    seat_type = db.Column(db.String(20), nullable=False)
    
    price = db.Column(db.Float, nullable=False)
    ticket_type = db.Column(db.String(10), default='adult')
    
    status = db.Column(db.String(20), default='valid')
    ticket_class = db.Column(db.String(20), default='normal')
    
    seller_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    window_no = db.Column(db.String(10))
    sold_at = db.Column(db.DateTime, default=datetime.now)
    
    train = db.relationship('Train', backref='tickets')
    seller = db.relationship('User', backref='tickets')

class Refund(db.Model):
    """退票记录模型"""
    __tablename__ = 'refunds'
    
    refund_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.String(10), db.ForeignKey('tickets.ticket_id'), nullable=False)
    refund_amount = db.Column(db.Float, nullable=False)
    refund_fee = db.Column(db.Float, default=0)
    refund_reason = db.Column(db.String(10), default='voluntary')
    refund_type = db.Column(db.String(20), default='normal')
    operator_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    refund_time = db.Column(db.DateTime, default=datetime.now)
    remark = db.Column(db.Text)
    
    ticket = db.relationship('Ticket', backref='refunds')
    operator = db.relationship('User', backref='refunds')

class SupplementTicket(db.Model):
    """补票记录模型"""
    __tablename__ = 'supplement_tickets'
    
    supp_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    original_ticket_id = db.Column(db.String(20))
    passenger_name = db.Column(db.String(50))
    id_number = db.Column(db.String(30))
    id_type = db.Column(db.String(10))
    
    from_station = db.Column(db.String(50))
    to_station = db.Column(db.String(50), nullable=False)
    seat_type = db.Column(db.String(20))
    amount = db.Column(db.Float, nullable=False)
    fine = db.Column(db.Float, default=0)
    
    supp_type = db.Column(db.String(20), nullable=False)
    
    operator_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    window_no = db.Column(db.String(10))
    supp_time = db.Column(db.DateTime, default=datetime.now)
    remark = db.Column(db.Text)
    
    operator = db.relationship('User', backref='supplements')

class Shift(db.Model):
    """班次记录模型"""
    __tablename__ = 'shifts'
    
    shift_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_no = db.Column(db.String(20), nullable=False)
    shift_type = db.Column(db.String(10), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    ticket_count = db.Column(db.Integer, default=0)
    refund_count = db.Column(db.Integer, default=0)
    waste_count = db.Column(db.Integer, default=0)
    revenue = db.Column(db.Float, default=0)
    refund_amount = db.Column(db.Float, default=0)
    actual_amount = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='active')
    closed_by = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.now)

class OperationLog(db.Model):
    """操作日志模型"""
    __tablename__ = 'operation_logs'
    
    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.shift_id'))
    employee_no = db.Column(db.String(20), nullable=False)
    operation_type = db.Column(db.String(50), nullable=False)
    operation_time = db.Column(db.DateTime, default=datetime.now)
    ticket_id = db.Column(db.String(10))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

class Counter(db.Model):
    """票号计数器模型"""
    __tablename__ = 'counters'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    counter_name = db.Column(db.String(20), unique=True, nullable=False)
    current_value = db.Column(db.Integer, default=0)
    prefix = db.Column(db.String(5), default='A')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

# ==================== 辅助函数 ====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_next_ticket_id():
    """获取下一张票号"""
    counter = Counter.query.filter_by(counter_name='ticket').first()
    if not counter:
        counter = Counter(counter_name='ticket', current_value=1, prefix='A')
        db.session.add(counter)
    else:
        counter.current_value += 1
    
    ticket_id = f"{counter.prefix}{counter.current_value:06d}"
    db.session.commit()
    return ticket_id

def get_current_shift():
    """获取当前班次"""
    if 'shift_id' in session:
        return Shift.query.get(session['shift_id'])
    return None

def log_operation(operation_type, ticket_id=None, details=None):
    """记录操作日志"""
    log = OperationLog(
        shift_id=session.get('shift_id'),
        employee_no=session.get('employee_no'),
        operation_type=operation_type,
        ticket_id=ticket_id,
        details=json.dumps(details, ensure_ascii=False) if details else None,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()

def search_stations(pinyin_code):
    """搜索车站（按拼音码）"""
    if not pinyin_code or len(pinyin_code) < 1:
        return []
    
    pinyin_code = pinyin_code.upper()
    stations = Station.query.filter(
        db.or_(
            Station.station_code.like(f'{pinyin_code}%'),
            Station.station_pinyin.like(f'{pinyin_code}%')
        ),
        Station.status == 'active'
    ).limit(10).all()
    
    return [{'code': s.station_code, 'name': s.station_name, 'pinyin': s.station_pinyin} for s in stations]

def calculate_price(from_station, to_station, seat_type):
    """计算票价"""
    price = TicketPrice.query.filter_by(
        from_station=from_station,
        to_station=to_station,
        seat_type=seat_type
    ).first()
    
    if price:
        return price.base_price
    
    # 如果没有固定票价，按距离计算
    from_stop = TrainStop.query.join(Station).filter(Station.station_code == from_station).first()
    to_stop = TrainStop.query.join(Station).filter(Station.station_code == to_station).first()
    
    if from_stop and to_stop and from_stop.distance_from_start and to_stop.distance_from_start:
        distance = abs(to_stop.distance_from_start - from_stop.distance_from_start)
        base_rate = 0.46  # 基础单价 元/公里
        
        seat_config = config.SEAT_TYPES.get(seat_type, {})
        coefficient = seat_config.get('coefficient', 1.0)
        
        return round(distance * base_rate * coefficient, 2)
    
    return 0.0

def calculate_refund_fee(ticket, refund_time):
    """计算退票手续费"""
    travel_datetime = datetime.strptime(f"{ticket.travel_date} {ticket.departure_time}", '%Y-%m-%d %H:%M')
    hours_until_departure = (travel_datetime - refund_time).total_seconds() / 3600
    
    for rule in config.REFUND_RULES:
        if hours_until_departure >= rule['hours']:
            return round(ticket.price * rule['rate'], 2)
    
    return ticket.price  # 开车后不退

def generate_seat_number(seat_type):
    """生成座位号"""
    import random
    
    if seat_type in ['business', 'first', 'second']:
        carriage = random.randint(1, 16)
        row = random.randint(1, 20)
        pos = random.choice(['A', 'B', 'C', 'D', 'F'])
        return f"{carriage:02d}{row:02d}{pos}"
    elif seat_type in ['soft_seat', 'hard_seat']:
        carriage = random.randint(1, 16)
        seat = random.randint(1, 100)
        return f"{carriage:02d}{seat:03d}"
    else:  # 卧铺
        carriage = random.randint(1, 10)
        berth = random.randint(1, 60)
        pos = random.choice(['上', '中', '下'])
        return f"{carriage:02d}{berth:02d}{pos}"

# ==================== 路由 ====================

@app.route('/')
def index():
    """首页/登录页"""
    if current_user.is_authenticated:
        if 'shift_id' not in session:
            return redirect(url_for('shift_select'))
        return redirect(url_for('main'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if current_user.is_authenticated:
        return redirect(url_for('shift_select'))
    
    error = None
    
    if request.method == 'POST':
        employee_no = request.form.get('employee_no', '').strip()
        password = request.form.get('password', '')
        
        if not employee_no or not password:
            error = '请输入工号和密码'
        else:
            user = User.query.filter_by(employee_no=employee_no).first()
            
            if user and check_password_hash(user.password_hash, password):
                if user.status != 'active':
                    error = '用户已被禁用'
                else:
                    login_user(user)
                    user.last_login = datetime.now()
                    db.session.commit()
                    
                    session['employee_no'] = user.employee_no
                    session['user_name'] = user.name
                    session['window_no'] = user.window_no or config.DEFAULT_WINDOW_NO
                    session['station_code'] = user.station_code or 'ZZO'  # 默认郑州
                    session['station_name'] = '郑州站'
                    
                    # 获取下一张票号
                    counter = Counter.query.filter_by(counter_name='ticket').first()
                    next_ticket = f"{counter.prefix if counter else 'A'}{(counter.current_value + 1 if counter else 1):06d}"
                    session['next_ticket_id'] = next_ticket
                    
                    log_operation('login')
                    return redirect(url_for('shift_select'))
            else:
                error = '工号或密码错误'
    
    return render_template('login.html', error=error, system_name=config.SYSTEM_NAME)

@app.route('/logout')
@login_required
def logout():
    """退出登录"""
    log_operation('logout')
    logout_user()
    session.clear()
    flash('已退出系统', 'info')
    return redirect(url_for('login'))

@app.route('/shift_select', methods=['GET', 'POST'])
@login_required
def shift_select():
    """班次选择页面"""
    if request.method == 'POST':
        shift_type = request.form.get('shift_type', 'day')
        
        # 创建班次记录
        shift = Shift(
            employee_no=session['employee_no'],
            shift_type=shift_type,
            start_time=datetime.now()
        )
        db.session.add(shift)
        db.session.commit()
        
        session['shift_id'] = shift.shift_id
        session['shift_type'] = shift_type
        session['shift_name'] = config.SHIFT_TYPES[shift_type]['name']
        
        log_operation('shift_open', details={'shift_type': shift_type})
        
        return redirect(url_for('main'))
    
    # 确定当前班次
    current_hour = datetime.now().hour
    default_shift = 'night' if 12 <= current_hour < 24 else 'day'
    
    return render_template('shift_select.html', 
                         default_shift=default_shift,
                         shift_types=config.SHIFT_TYPES)

@app.route('/main')
@login_required
def main():
    """主售票界面"""
    if 'shift_id' not in session:
        return redirect(url_for('shift_select'))
    
    current_shift = get_current_shift()
    
    return render_template('tickets/sell.html',
                         system_name=config.SYSTEM_NAME,
                         station_name=session.get('station_name', '郑州站'),
                         window_no=session.get('window_no', '101号口'),
                         shift_name=session.get('shift_name', '白班'),
                         next_ticket_id=session.get('next_ticket_id', 'A000001'),
                         current_time=datetime.now().strftime('%H:%M:%S'),
                         current_date=datetime.now().strftime('%Y-%m-%d'),
                         seat_types=config.SEAT_TYPES,
                         ticket_types=config.TICKET_TYPES,
                         ticket_purpose=config.TICKET_PURPOSE)

# ==================== API路由 ====================

@app.route('/api/stations/search')
def api_search_stations():
    """搜索车站API"""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    
    stations = search_stations(q)
    return jsonify(stations)

@app.route('/api/trains/search')
def api_search_trains():
    """搜索车次API"""
    date = request.args.get('date', '')
    from_station = request.args.get('from', '')
    to_station = request.args.get('to', '')
    
    query = Train.query.filter(Train.status == 'active')
    
    if from_station and to_station:
        # 按发到站查询
        trains = query.join(TrainStop, Train.train_id == TrainStop.train_id).filter(
            TrainStop.station_code == from_station
        ).all()
        
        result = []
        for train in trains:
            stops = TrainStop.query.filter(
                TrainStop.train_id == train.train_id,
                TrainStop.station_code == to_station
            ).first()
            
            if stops:
                from_stop = TrainStop.query.filter(
                    TrainStop.train_id == train.train_id,
                    TrainStop.station_code == from_station
                ).first()
                
                if from_stop and from_stop.stop_sequence < stops.stop_sequence:
                    result.append({
                        'train_id': train.train_id,
                        'train_number': train.train_number,
                        'train_type': train.train_type,
                        'from_station': from_station,
                        'to_station': to_station,
                        'departure_time': from_stop.departure_time,
                        'arrival_time': stops.arrival_time,
                        'duration': calculate_duration(from_stop.departure_time, stops.arrival_time)
                    })
    else:
        trains = query.all()
        result = [{'train_id': t.train_id, 'train_number': t.train_number, 
                   'train_type': t.train_type, 'start_station': t.start_station,
                   'end_station': t.end_station, 'start_time': t.start_time,
                   'end_time': t.end_time} for t in trains]
    
    return jsonify(result)

def calculate_duration(start, end):
    """计算行程时长"""
    try:
        s = datetime.strptime(start, '%H:%M')
        e = datetime.strptime(end, '%H:%M')
        if e < s:
            e += timedelta(days=1)
        diff = e - s
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        return f"{hours}小时{minutes}分钟"
    except:
        return ""

@app.route('/api/trains/<int:train_id>/availability')
def api_train_availability(train_id):
    """获取车次余票信息"""
    date = request.args.get('date', '')
    from_station = request.args.get('from', '')
    to_station = request.args.get('to', '')
    
    if not train_id:
        return jsonify({'error': '缺少车次ID'}), 400
    
    train = Train.query.get(train_id)
    if not train:
        return jsonify({'error': '车次不存在'}), 404
    
    # 获取经停站信息
    from_stop = TrainStop.query.filter(
        TrainStop.train_id == train_id,
        TrainStop.station_code == from_station
    ).first()
    
    to_stop = TrainStop.query.filter(
        TrainStop.train_id == train_id,
        TrainStop.station_code == to_station
    ).first()
    
    if not from_stop or not to_stop:
        return jsonify({'error': '车站不在该车次经停站中'}), 400
    
    # 计算票价
    prices = {}
    for seat_type, config in config.SEAT_TYPES.items():
        price = calculate_price(from_station, to_station, seat_type)
        prices[config['name']] = {
            'price': price,
            'available': True,
            'count': getattr(from_stop, f'seat_{seat_type}', 0)
        }
    
    return jsonify({
        'train_number': train.train_number,
        'train_type': train.train_type,
        'departure_time': from_stop.departure_time,
        'arrival_time': to_stop.arrival_time,
        'from_station': from_station,
        'to_station': to_station,
        'prices': prices
    })

@app.route('/api/tickets/sell', methods=['POST'])
def api_sell_ticket():
    """售票API"""
    if 'shift_id' not in session:
        return jsonify({'success': False, 'error': '请先选择班次'}), 401
    
    data = request.get_json()
    
    required_fields = ['train_id', 'from_station', 'to_station', 'seat_type', 'travel_date']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400
    
    try:
        train = Train.query.get(data['train_id'])
        if not train:
            return jsonify({'success': False, 'error': '车次不存在'}), 404
        
        # 获取经停站信息
        from_stop = TrainStop.query.filter(
            TrainStop.train_id == data['train_id'],
            TrainStop.station_code == data['from_station']
        ).first()
        
        to_stop = TrainStop.query.filter(
            TrainStop.train_id == data['train_id'],
            TrainStop.station_code == data['to_station']
        ).first()
        
        if not from_stop or not to_stop:
            return jsonify({'success': False, 'error': '车站不在该车次经停站中'}), 400
        
        # 计算票价
        ticket_type = data.get('ticket_type', 'adult')
        base_price = calculate_price(data['from_station'], data['to_station'], data['seat_type'])
        
        if ticket_type == 'child':
            price = round(base_price * 0.5, 2)
        elif ticket_type == 'student':
            price = round(base_price * 0.5, 2)
        else:
            price = base_price
        
        # 生成票号和座位号
        ticket_id = get_next_ticket_id()
        seat_number = generate_seat_number(data['seat_type'])
        carriage = seat_number[:2]
        
        # 创建车票记录
        ticket = Ticket(
            ticket_id=ticket_id,
            train_id=data['train_id'],
            train_number=train.train_number,
            passenger_name=data.get('passenger_name', ''),
            id_number=data.get('id_number', ''),
            id_type=data.get('id_type', 'id_card'),
            from_station=data['from_station'],
            to_station=data['to_station'],
            travel_date=data['travel_date'],
            departure_time=from_stop.departure_time,
            carriage=carriage,
            seat_number=seat_number,
            seat_type=data['seat_type'],
            price=price,
            ticket_type=ticket_type,
            status='valid',
            seller_id=current_user.user_id,
            window_no=session.get('window_no')
        )
        
        db.session.add(ticket)
        
        # 更新班次统计
        current_shift = get_current_shift()
        if current_shift:
            current_shift.ticket_count += 1
            current_shift.revenue += price
        
        # 更新session中的下一张票号
        session['next_ticket_id'] = get_next_ticket_id()
        
        db.session.commit()
        
        # 记录操作日志
        log_operation('sell', ticket_id, {
            'train_number': train.train_number,
            'from_station': data['from_station'],
            'to_station': data['to_station'],
            'seat_type': data['seat_type'],
            'price': price
        })
        
        return jsonify({
            'success': True,
            'ticket': {
                'ticket_id': ticket_id,
                'train_number': train.train_number,
                'from_station': data['from_station'],
                'to_station': data['to_station'],
                'travel_date': data['travel_date'],
                'departure_time': from_stop.departure_time,
                'carriage': carriage,
                'seat_number': seat_number,
                'seat_type': data['seat_type'],
                'price': price,
                'passenger_name': data.get('passenger_name', ''),
                'id_number': data.get('id_number', '')
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tickets/<ticket_id>')
def api_get_ticket(ticket_id):
    """获取车票信息"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'error': '车票不存在'}), 404
    
    return jsonify({
        'ticket_id': ticket.ticket_id,
        'train_number': ticket.train_number,
        'from_station': ticket.from_station,
        'to_station': ticket.to_station,
        'travel_date': ticket.travel_date,
        'departure_time': ticket.departure_time,
        'carriage': ticket.carriage,
        'seat_number': ticket.seat_number,
        'seat_type': ticket.seat_type,
        'price': ticket.price,
        'ticket_type': ticket.ticket_type,
        'status': ticket.status,
        'passenger_name': ticket.passenger_name,
        'id_number': ticket.id_number,
        'sold_at': ticket.sold_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.sold_at else ''
    })

@app.route('/api/tickets/<ticket_id>/refund', methods=['POST'])
def api_refund_ticket(ticket_id):
    """退票API"""
    if 'shift_id' not in session:
        return jsonify({'success': False, 'error': '请先选择班次'}), 401
    
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'success': False, 'error': '车票不存在'}), 404
    
    if ticket.status != 'valid':
        return jsonify({'success': False, 'error': '车票状态不允许退票'}), 400
    
    try:
        refund_fee = calculate_refund_fee(ticket, datetime.now())
        refund_amount = round(ticket.price - refund_fee, 2)
        
        refund = Refund(
            ticket_id=ticket_id,
            refund_amount=refund_amount,
            refund_fee=refund_fee,
            refund_reason='voluntary',
            operator_id=current_user.user_id
        )
        
        ticket.status = 'refunded'
        
        # 更新班次统计
        current_shift = get_current_shift()
        if current_shift:
            current_shift.refund_count += 1
            current_shift.refund_amount += refund_amount
        
        db.session.add(refund)
        db.session.commit()
        
        # 记录操作日志
        log_operation('refund', ticket_id, {
            'refund_amount': refund_amount,
            'refund_fee': refund_fee
        })
        
        return jsonify({
            'success': True,
            'refund': {
                'refund_amount': refund_amount,
                'refund_fee': refund_fee,
                'original_price': ticket.price
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/supplements', methods=['POST'])
def api_create_supplement():
    """创建补票API"""
    if 'shift_id' not in session:
        return jsonify({'success': False, 'error': '请先选择班次'}), 401
    
    data = request.get_json()
    
    required_fields = ['to_station', 'supp_type']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400
    
    try:
        # 计算补票费用
        from_station = data.get('from_station', 'ZZO')  # 默认从郑州
        seat_type = data.get('seat_type', 'hard_seat')
        
        base_price = calculate_price(from_station, data['to_station'], seat_type)
        
        # 加上罚款
        fine = data.get('fine', 0)
        if data['supp_type'] == 'no_ticket':
            fine = round(base_price * 0.5, 2)  # 50%罚款
        elif data['supp_type'] == 'over_station':
            fine = 0
        elif data['supp_type'] == 'over_class':
            fine = 0
        
        service_fee = 2.0  # 手续费
        total_amount = round(base_price + fine + service_fee, 2)
        
        supplement = SupplementTicket(
            original_ticket_id=data.get('original_ticket_id'),
            passenger_name=data.get('passenger_name', ''),
            id_number=data.get('id_number', ''),
            id_type=data.get('id_type', 'id_card'),
            from_station=from_station,
            to_station=data['to_station'],
            seat_type=seat_type,
            amount=total_amount,
            fine=fine,
            supp_type=data['supp_type'],
            operator_id=current_user.user_id,
            window_no=session.get('window_no'),
            remark=data.get('remark', '')
        )
        
        db.session.add(supplement)
        
        # 更新班次统计
        current_shift = get_current_shift()
        if current_shift:
            current_shift.ticket_count += 1
            current_shift.revenue += total_amount
        
        db.session.commit()
        
        # 记录操作日志
        log_operation('supplement', details={
            'supp_type': data['supp_type'],
            'amount': total_amount
        })
        
        return jsonify({
            'success': True,
            'supplement': {
                'amount': total_amount,
                'base_price': base_price,
                'fine': fine,
                'service_fee': service_fee
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/shift/summary')
def api_shift_summary():
    """获取班次统计"""
    if 'shift_id' not in session:
        return jsonify({'error': '请先选择班次'}), 401
    
    shift = get_current_shift()
    if not shift:
        return jsonify({'error': '班次不存在'}), 404
    
    return jsonify({
        'shift_id': shift.shift_id,
        'employee_no': shift.employee_no,
        'shift_type': shift.shift_type,
        'shift_name': config.SHIFT_TYPES[shift.shift_type]['name'],
        'start_time': shift.start_time.strftime('%Y-%m-%d %H:%M:%S'),
        'end_time': shift.end_time.strftime('%Y-%m-%d %H:%M:%S') if shift.end_time else '',
        'ticket_count': shift.ticket_count,
        'refund_count': shift.refund_count,
        'waste_count': shift.waste_count,
        'revenue': shift.revenue,
        'refund_amount': shift.refund_amount,
        'actual_amount': shift.revenue - shift.refund_amount,
        'status': shift.status
    })

@app.route('/api/shift/close', methods=['POST'])
def api_shift_close():
    """交班API"""
    if 'shift_id' not in session:
        return jsonify({'success': False, 'error': '请先选择班次'}), 401
    
    shift = get_current_shift()
    if not shift:
        return jsonify({'success': False, 'error': '班次不存在'}), 404
    
    try:
        shift.end_time = datetime.now()
        shift.status = 'closed'
        shift.actual_amount = shift.revenue - shift.refund_amount
        
        db.session.commit()
        
        # 记录操作日志
        log_operation('shift_close', details={
            'ticket_count': shift.ticket_count,
            'revenue': shift.revenue,
            'actual_amount': shift.actual_amount
        })
        
        # 清空session中的班次信息
        session.pop('shift_id', None)
        session.pop('shift_type', None)
        session.pop('shift_name', None)
        
        return jsonify({
            'success': True,
            'message': '交班成功'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/operations/logs')
def api_operation_logs():
    """获取操作日志"""
    if 'shift_id' not in session:
        return jsonify([]), 401
    
    logs = OperationLog.query.filter_by(
        shift_id=session['shift_id']
    ).order_by(OperationLog.operation_time.desc()).limit(100).all()
    
    return jsonify([{
        'log_id': log.log_id,
        'operation_type': log.operation_type,
        'operation_time': log.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
        'ticket_id': log.ticket_id,
        'details': log.details
    } for log in logs])

# ==================== 页面路由 ====================

@app.route('/ticket/preview')
def ticket_preview():
    """车票预览页面"""
    ticket_id = request.args.get('ticket_id', '')
    ticket = Ticket.query.get(ticket_id)
    
    if not ticket:
        return render_template('error.html', message='车票不存在')
    
    return render_template('ticket_preview.html', ticket=ticket)

@app.route('/refund')
def refund_page():
    """退票页面"""
    if 'shift_id' not in session:
        return redirect(url_for('shift_select'))
    
    return render_template('refunds/refund.html',
                         system_name=config.SYSTEM_NAME,
                         station_name=session.get('station_name', '郑州站'),
                         window_no=session.get('window_no', '101号口'),
                         shift_name=session.get('shift_name', '白班'),
                         current_time=datetime.now().strftime('%H:%M:%S'))

@app.route('/supplement')
def supplement_page():
    """到达补票页面"""
    if 'shift_id' not in session:
        return redirect(url_for('shift_select'))
    
    return render_template('supplements/supplement.html',
                         system_name=config.SYSTEM_NAME,
                         station_name=session.get('station_name', '郑州站'),
                         window_no=session.get('window_no', '101号口'),
                         shift_name=session.get('shift_name', '白班'),
                         current_time=datetime.now().strftime('%H:%M:%S'),
                         seat_types=config.SEAT_TYPES)

@app.route('/query')
def query_page():
    """余票查询页面"""
    if 'shift_id' not in session:
        return redirect(url_for('shift_select'))
    
    return render_template('queries/query.html',
                         system_name=config.SYSTEM_NAME,
                         station_name=session.get('station_name', '郑州站'),
                         window_no=session.get('window_no', '101号口'),
                         shift_name=session.get('shift_name', '白班'),
                         current_time=datetime.now().strftime('%H:%M:%S'),
                         seat_types=config.SEAT_TYPES)

@app.route('/shift')
def shift_page():
    """交班页面"""
    if 'shift_id' not in session:
        return redirect(url_for('shift_select'))
    
    return render_template('shifts/close.html',
                         system_name=config.SYSTEM_NAME,
                         station_name=session.get('station_name', '郑州站'),
                         window_no=session.get('window_no', '101号口'),
                         shift_name=session.get('shift_name', '白班'),
                         current_time=datetime.now().strftime('%H:%M:%S'))

@app.route('/api/tickets/sold')
def api_sold_tickets():
    """获取已售车票列表"""
    if 'shift_id' not in session:
        return jsonify([])
    
    tickets = Ticket.query.filter_by(
        seller_id=current_user.user_id,
        travel_date=datetime.now().strftime('%Y-%m-%d')
    ).order_by(Ticket.sold_at.desc()).limit(50).all()
    
    return jsonify([{
        'ticket_id': t.ticket_id,
        'train_number': t.train_number,
        'from_station': t.from_station,
        'to_station': t.to_station,
        'travel_date': t.travel_date,
        'departure_time': t.departure_time,
        'seat_type': t.seat_type,
        'price': t.price,
        'status': t.status,
        'sold_at': t.sold_at.strftime('%H:%M:%S') if t.sold_at else ''
    } for t in tickets])

# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', message='页面不存在'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', message='服务器错误'), 500

# ==================== 启动应用 ====================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
