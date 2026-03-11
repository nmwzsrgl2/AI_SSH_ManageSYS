from datetime import datetime
from . import db


class SSHConnection(db.Model):
    __tablename__ = "ssh_connection"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer, default=22)
    username = db.Column(db.String(100), nullable=False)

    password = db.Column(db.Text)      # 建议后续加密
    private_key = db.Column(db.Text)   # 建议后续加密

    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(
        db.DateTime,
        default=datetime.now(),
        onupdate=datetime.now()
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    user = db.relationship(
        "User",
        back_populates="ssh_connections"
    )
