"""
数据库初始化脚本
为现有的SSH连接项目添加用户认证功能
"""

import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# 添加后端目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import db, User, SSHConnection, hash_password,Role, Permission

def init_database():
    """初始化数据库"""
    print("🔧 正在初始化数据库...")

    # with app.app_context():
    try:
        # 1️⃣ 创建表
        db.create_all()
        print("✅ 数据库表创建成功")

        # 2️⃣ 初始化 RBAC（必须先）
        init_rbac()
        print("✅ RBAC 初始化完成")

        # 4️⃣ 确保存在默认管理员用户 
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@localhost',
                password_hash=hash_password('admin123'),
                is_active=True,
                role_id=1   # ✅ 关键：绑定对象，而不是 role_id
            )
            db.session.add(admin_user)
            db.session.commit()
            print("✅ 创建默认管理员用户: admin / admin123")
        else:
            # 确保 admin 用户一定绑定 admin 角色
            admin_user.role = 1
            admin_user.is_active = 1
            db.session.commit()

        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            raise RuntimeError("❌ admin 角色不存在，RBAC 初始化失败")

        # 5️⃣ 处理孤立 SSH 连接
        orphaned_connections = SSHConnection.query.filter_by(user_id=None).all()
        if orphaned_connections:
            print(f"⚠️  发现 {len(orphaned_connections)} 个未关联用户的SSH连接")
            for conn in orphaned_connections:
                conn.user_id = admin_user.id
            db.session.commit()
            print(f"✅ 已将 SSH 连接分配给管理员用户")
        print("\n✅ 数据库初始化完成!")
        return True

    except Exception as e:
        db.session.rollback()
        print(f"❌ 数据库初始化失败: {e}")
        return False



def init_rbac():
    """
    初始化 RBAC 角色与权限（幂等）
    """
    # ---------- 权限 ----------
    permissions = {
        "user:manage": "用户管理",
        "user:view": "查看用户",
        "ssh:manage": "SSH 管理",
        "monitor:view": "监控查看",
        "zabbix:view": "Zabbix 查看",
        "ai:chat": "AI 聊天"
    }

    perm_objs = {}
    for code, desc in permissions.items():
        perm = Permission.query.filter_by(code=code).first()
        if not perm:
            perm = Permission(code=code, description=desc)
            db.session.add(perm)
        perm_objs[code] = perm

    db.session.flush()  # 确保 ID 可用

    # ---------- 角色 ----------
    def get_or_create_role(name, desc):
        role = Role.query.filter_by(name=name).first()
        if not role:
            role = Role(name=name, description=desc)
            db.session.add(role)
        return role

    admin = get_or_create_role("admin", "超级管理员")
    ops = get_or_create_role("ops", "运维人员")
    user = get_or_create_role("user", "普通用户")

    # ---------- 绑定权限 ----------
    admin.permissions = list(perm_objs.values())

    ops.permissions = [
        perm_objs["ssh:manage"],
        perm_objs["monitor:view"],
        perm_objs["zabbix:view"],
        perm_objs["ai:chat"]
    ]

    user.permissions = [
        perm_objs["ai:chat"]
    ]

    db.session.commit()
