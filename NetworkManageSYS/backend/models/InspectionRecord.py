from datetime import datetime
from . import db
import pytz

tz = pytz.timezone('Asia/Shanghai')
# 巡检记录模型
class InspectionRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    device_name = db.Column(db.String(100), nullable=False)
    result = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz))

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'device_name': self.device_name,
            'result': self.result,
            'created_at': self.created_at.isoformat()
        }