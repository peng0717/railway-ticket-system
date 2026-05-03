# -*- coding: utf-8 -*-
"""
注册审核 Blueprint 初始化
"""

from flask import Blueprint

def create_register_blueprint():
    """创建注册审核蓝图"""
    from .routes import register_bp
    return register_bp
