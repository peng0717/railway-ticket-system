# 铁路客票系统工号注册与审核管理系统

独立的工号注册与审核管理网站，与主售票系统共享数据库。

## 项目结构

```
./铁路售票系统/register/
├── app.py              # 独立Flask应用
├── requirements.txt    # 依赖
├── templates/          # HTML模板
│   ├── base.html       # 基础模板
│   ├── register.html   # 注册页面
│   ├── login.html      # 管理端登录
│   └── admin/          # 管理端模板
│       ├── dashboard.html    # 管理首页
│       ├── applications.html # 审核列表
│       ├── risk.html         # 风控管理
│       └── users.html        # 用户管理
└── static/             # 静态资源
    ├── css/style.css   # 样式
    └── js/
        ├── fingerprint.js  # 机器码采集
        └── register.js     # 注册表单逻辑
```

## 功能特性

### 注册流程（7步骤）
1. **实名认证** - 输入真实姓名和身份证号（完整校验码验证）
2. **邮箱验证** - 发送6位数字验证码（开发模式直接显示）
3. **选择车站** - 搜索并选择车站（支持站名、拼音码、电报码搜索）
4. **注册工号** - 格式：车站码-字母-序号（如VNP-ZW-001）
5. **选择窗口号** - 1-20号窗口
6. **设置密码** - 8-20位，包含字母和数字
7. **提交注册** - 采集机器码，提交审核

### 机器码风控
- 纯JavaScript实现的机器码采集（Canvas指纹、WebGL、屏幕信息等）
- 注册时绑定机器码
- 登录时检测机器码一致性
- 异地登录自动冻结

### 管理端功能
- **首页概览** - 统计待审核、已通过、已拒绝、风控冻结数
- **审核列表** - 查看、审核（通过/拒绝）注册申请
- **风控管理** - 解冻、永久封禁工号
- **用户管理** - 查看用户、修改状态、重置密码

## 运行方式

### 安装依赖

```bash
cd ./铁路售票系统/register
pip install -r requirements.txt
```

### 启动服务

```bash
python app.py
```

默认端口：**5001**

- 注册页面：http://localhost:5001/
- 管理端：http://localhost:5001/admin/login
- 默认管理员账号：admin / admin123

### 环境变量（可选）

```bash
# 邮件配置
export MAIL_SERVER=smtp.qq.com
export MAIL_PORT=465
export MAIL_USERNAME=your_email@qq.com
export MAIL_PASSWORD=your授权码
```

未配置邮件时，系统自动进入开发模式，验证码直接显示在页面上。

## 数据库

与主售票系统共享 `../data/railway.db`，新增以下表：

- `registration_applications` - 注册申请表
- `email_verifications` - 邮箱验证码表
- `risk_controls` - 风控记录表
- `machine_bindings` - 机器码绑定表

## 与售票系统的对接

### 注册审核通过后创建用户

在 `users` 表中创建记录：
- `employee_no` - 工号
- `name` - 真实姓名
- `password_hash` - 密码哈希
- `role` - 'seller'
- `station_code` - 车站码
- `window_no` - 窗口号
- `status` - 'active' / 'frozen' / 'banned'

### 售票系统登录时检查

1. 采集当前机器码
2. 查询 `users` 表验证工号密码
3. 检查 `status` 字段
4. 如果 `status='frozen'`，拒绝登录并提示风控冻结
5. 如果机器码不匹配，更新状态为冻结，记录风控日志

## 开发说明

### 机器码采集

使用纯JavaScript实现，不依赖任何外部CDN，采集以下特征：

- Canvas指纹
- WebGL渲染器信息
- 屏幕分辨率+色深
- 时区
- 语言
- User Agent关键信息
- 字体探测
- 触控支持
- 硬件信息

所有特征组合后用SHA256生成32位机器码。

### 身份证校验

完整实现18位身份证校验码算法，包括：
- 格式校验
- 地区码校验
- 出生日期校验
- 校验码校验

## 配色方案

与售票系统保持一致的TRS深色主题：

- 页面背景：#1a2332
- 主色调：#0052a5（国铁蓝）
- 点缀色：#c9a84c（金色）
- 卡片背景：#1e2d3d
- 输入框背景：#0d1520
- 边框色：#2a3f55
- 文字色：#e0e0e0（主）、#8a9bb0（辅）
