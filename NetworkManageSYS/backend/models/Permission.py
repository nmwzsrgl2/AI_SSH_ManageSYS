from datetime import datetime
from . import db

class Permission(db.Model):
    __tablename__ = "permission"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200))

    roles = db.relationship(
        "Role",
        secondary='role_permission',
        back_populates="permissions"
    )
