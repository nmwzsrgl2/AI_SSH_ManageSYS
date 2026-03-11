from models import ChatHistory,db
from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS
import os

BASE_DIR = (os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'sqlite:///' + os.path.join(BASE_DIR, 'NetworkManage.db')
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# 
# 配置CORS允许所有来源
CORS(app, origins="*", resources={r"/*": {"origins": "*"}})

# 对象关系映射器
db.init_app(app)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)
def main():
    history = ChatHistory.query.filter_by(user_id="1").order_by(ChatHistory.id.desc()).limit(5)
    for h in history:
        print({
            'id': h.id,
            'user_message': h.user_message,
        })


if __name__ == '__main__':
    with app.app_context():
        #"初始化数据库"    
        main()


    print("启动Flask Web SSH客户端...")
    print("访问地址: http://10.0.147.50:80")

    socketio.run(app, host='0.0.0.0', port=8088,allow_unsafe_werkzeug=True) 