from datetime import datetime
from . import db
import pytz

tz = pytz.timezone('Asia/Shanghai')
# 设备模型
class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ip = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    enable_password = db.Column(db.String(100), nullable=True)
    device_type = db.Column(db.String(100), nullable=False)
    protocol = db.Column(db.String(10), nullable=False)
    commands = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='unknown')
    last_check = db.Column(db.DateTime, nullable=True)
    group = db.Column(db.String(50), default='交换机')  # 新增分组字段
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'ip': self.ip,
            'username': self.username,
            'password': self.password,
            'enable_password': self.enable_password,
            'device_type': self.device_type,
            'protocol': self.protocol,
            'commands': self.commands,
            'status': self.status,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'group': self.group,
            'created_at': self.created_at.isoformat()
        }