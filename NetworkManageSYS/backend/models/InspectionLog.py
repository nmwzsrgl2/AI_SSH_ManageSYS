from datetime import datetime
from . import db
import pytz
import json

tz = pytz.timezone('Asia/Shanghai')
class InspectionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(tz))
    end_time = db.Column(db.DateTime, nullable=True)
    total_devices = db.Column(db.Integer, default=0)
    successful_devices = db.Column(db.Integer, default=0)
    failed_devices = db.Column(db.Integer, default=0)
    total_duration = db.Column(db.Float, default=0)  # 以秒为单位
    details = db.Column(db.Text, nullable=True)  # JSON格式存储详情
    status = db.Column(db.String(20), default='进行中')  # 进行中/已完成/已取消

    def to_dict(self):
        return {
            'id': self.id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'total_devices': self.total_devices,
            'successful_devices': self.successful_devices,
            'failed_devices': self.failed_devices,
            'total_duration': self.total_duration,
            'details': json.loads(self.details) if self.details else [],
            'status': self.status
        }