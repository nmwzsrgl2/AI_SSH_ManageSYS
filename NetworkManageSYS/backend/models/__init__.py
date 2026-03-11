from flask_sqlalchemy import SQLAlchemy

# 全项目唯一的 db 实例
db = SQLAlchemy()
dbName = "web-ssh-terminal"
# 导入模型类，触发 ORM 注册
from .User import User 
from .SSHConnection import SSHConnection
from .ChatHistory import ChatHistory
from .Role import Role
from .Permission import Permission
from .Device import Device
from .InspectionLog import InspectionLog
from .InspectionRecord import InspectionRecord

# 定义数据库表之间的关系
role_permission = db.Table(
    'role_permission',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id')),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'))
)
