from datetime import datetime
from . import db

class Role(db.Model):
    __tablename__ = "role"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))

    permissions = db.relationship(
        "Permission",
        secondary='role_permission',
        back_populates="roles"
    )
