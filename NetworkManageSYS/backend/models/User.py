from datetime import datetime
from . import db


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    is_active = db.Column(db.Boolean, default=True)

    # 关键：字符串 + 同一个 db
    ssh_connections = db.relationship(
        "SSHConnection",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    chat_history = db.relationship(
        "ChatHistory",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'))
    ole = db.relationship("Role")
    
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active
        }
