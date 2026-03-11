import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///ssh_connections.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SSH配置
    SSH_TIMEOUT = 10
    SSH_KEEPALIVE = 30
    
    # WebSocket配置
    SOCKETIO_ASYNC_MODE = 'eventlet'
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"
    
    # 安全配置
    ENCRYPT_PASSWORDS = True
    MAX_CONNECTIONS_PER_USER = 5 