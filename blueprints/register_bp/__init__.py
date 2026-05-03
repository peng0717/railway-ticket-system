# -*- coding: utf-8 -*-
"""
注册审核系统 Blueprint
集成到铁路售票系统
"""

from flask import Blueprint

# 创建 Blueprint
register_bp = Blueprint(
    'register_bp',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/register_static'
)

# 导入路由以注册视图函数
from . import routes
