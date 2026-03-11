from datetime import datetime
from . import db

class ChatHistory(db.Model):
    __tablename__ = "chat_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_message = db.Column(db.String(200), nullable=False)
    ai_thinking = db.Column(db.String(10000), nullable=False)
    ai_message = db.Column(db.String(10000), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    user = db.relationship("User", back_populates="chat_history")

    def to_dict(self):
        return {
            "message": self.user_message,
            "ai_thinking": self.ai_thinking,
            "ai_message": self.ai_message,
            "message_type": "chat",
            "created_at": self.created_at
        }
