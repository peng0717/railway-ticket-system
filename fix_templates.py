# -*- coding: utf-8 -*-
"""修复铁路售票系统模板 - 一键修复脚本"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

fixes = {
    # 修复 Jinja2 不支持 {% empty %} 的问题
    'templates/admin/registrations.html': [
        ('{% empty %}', '{% else %}'),
    ],
    'templates/admin/risk.html': [
        ('{% empty %}', '{% else %}'),
    ],
    # 修复 login.html 指向已删除的 Blueprint 路由
    'templates/login.html': [
        ("url_for('register_bp.admin_login')", "url_for('admin_login')"),
    ],
}

fixed = 0
for filepath, replacements in fixes.items():
    full_path = os.path.join(BASE, filepath)
    if not os.path.exists(full_path):
        print(f'⏭️  跳过（不存在）: {filepath}')
        continue
    
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    changed = False
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            changed = True
            print(f'🔧 {filepath}: {old} → {new}')
    
    if changed:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        fixed += 1
    else:
        print(f'✅ {filepath}: 无需修改')

# 清理 __pycache__
for root, dirs, files in os.walk(BASE):
    if '__pycache__' in dirs:
        pycache = os.path.join(root, '__pycache__')
        import shutil
        shutil.rmtree(pycache)
        print(f'🗑️  清理: {pycache}')

print(f'\n修复完成！共修复 {fixed} 个文件')
