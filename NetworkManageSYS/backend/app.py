from flask import Flask, Response, request, jsonify, render_template, session, url_for, redirect, send_file
from flask_socketio import SocketIO, emit, disconnect
from flask_cors import CORS
import io
import socket
import paramiko
import json
import requests
import hashlib
import secrets
import os
import psutil
import logging
import sys
from datetime import datetime
import pytz
import time
import threading
import platform
import subprocess # nosec B404
from cryptography.fernet import Fernet
import netmiko
import pandas as pd
import zipfile
from agent import Dify_agent
import asyncio
from dotenv import load_dotenv
load_dotenv()

"""下面是自定模块"""
from zabbix import zabbix_api
import init_db 
# 导入自定义的SSH管理模块
import SSHM
from SSHM import SSHManager
#导入数据库模型
from models import db,User,SSHConnection,ChatHistory,Role, Permission,Device,InspectionRecord,InspectionLog

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

SSHM.socketio = socketio

# ========================
# 加密密钥管理
# ========================
def get_or_create_encryption_key():
    key_file = os.path.join(os.path.dirname(__file__), 'instance', 'encryption.key')
    
    # 确保instance目录存在
    os.makedirs(os.path.dirname(key_file), exist_ok=True)
    
    if os.path.exists(key_file):
        # 读取现有密钥
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        # 生成新密钥并保存
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

ENCRYPTION_KEY = get_or_create_encryption_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# 密码哈希函数
def hash_password(password):
    """使用SHA256哈希密码"""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{hashed}"

def verify_password(password, hashed_password):
    """验证密码"""
    try:
        salt, hash_value = hashed_password.split(':')
        return hashlib.sha256((password + salt).encode()).hexdigest() == hash_value
    except:
        return False


# 存储活跃的SSH连接
active_connections = {}

# ========================
# 认证装饰器
# ========================
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """获取当前登录用户"""
    user_id = session.get('user_id')
    if user_id:
        return db.session.get(User, user_id)
    return None

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    """检查登录状态"""
    try:
        user = get_current_user()
        if user:
            return jsonify({
                'authenticated': True,
                'user': user.to_dict()
            })
        else:
            session.clear()
            return redirect(url_for('login'))
    except Exception as e:
        print(f"检查认证状态错误: {e}")
        session.clear()
        return redirect(url_for('login'))
    

# ========================
# 页面路由
# ========================
@app.route('/', methods=['GET'])
@login_required
def index():
        return render_template('index.html')

@app.route('/index', methods=['GET'])
@login_required
def index_page():
        return render_template('index.html')

@app.route('/login',methods=['GET'])
def login():
    if get_current_user():
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/ssh_mam', methods=['GET'])
@login_required
def ssh_mam():
        return render_template('ssh_mam.html')

@app.route('/inspection', methods=['GET'])
@login_required
def inspection():
        return send_file('templates/inspection.html')

# ========================
#"""SSH 连接管理"""
# ========================
#获取SSH连接列表
@app.route('/api/connections', methods=['GET'])
@login_required
def get_connections():
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': '用户未找到'}), 404
        
        connections = SSHConnection.query.filter_by(user_id=user.id).all()
        result = []
        for conn in connections:
            result.append({
                'id': conn.id,
                'name': conn.name,
                'host': conn.host,
                'port': conn.port,
                'username': conn.username,
                'created_at': conn.created_at.isoformat(),
                'updated_at': conn.updated_at.isoformat()
            })
        return jsonify(result)
    except Exception as e:
        print(f"获取连接列表错误: {e}")
        return jsonify([])

@app.route('/api/connections', methods=['POST'])
@login_required
def create_connection():
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': '用户未找到'}), 404
        
        data = request.get_json()
        
        # 加密敏感数据
        encrypted_password = None
        if data.get('password'):
            encrypted_password = cipher_suite.encrypt(data['password'].encode()).decode()
        
        encrypted_private_key = None
        if data.get('private_key'):
            encrypted_private_key = cipher_suite.encrypt(data['private_key'].encode()).decode()
        
        connection = SSHConnection(
            name=data['name'],
            host=data['host'],
            port=data.get('port', 22),
            username=data['username'],
            password=encrypted_password,
            private_key=encrypted_private_key,
            user_id=user.id  # 关联当前用户
        )
        db.session.add(connection)
        db.session.commit()
        
        return jsonify({
            'id': connection.id,
            'name': connection.name,
            'host': connection.host,
            'port': connection.port,
            'username': connection.username,
            'created_at': connection.created_at.isoformat()
        }), 201
    except Exception as e:
        print(f"创建连接错误: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/connections/<int:conn_id>', methods=['DELETE'])
@login_required
def delete_connection(conn_id):
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': '用户未找到'}), 404
        
        connection = db.session.get(SSHConnection, conn_id)
        if not connection:
            return jsonify({'error': '连接不存在'}), 404
        
        # 确保只能删除自己的连接
        if connection.user_id != user.id:
            return jsonify({'error': '无权限删除此连接'}), 403
        
        db.session.delete(connection)
        db.session.commit()
        return '', 204
    except Exception as e:
        print(f"删除连接错误: {e}")
        return jsonify({'error': str(e)}), 500

# 测试SSH连接路由
@app.route('/api/connections/test', methods=['POST'])
@login_required
def test_connection():
    """测试SSH连接"""
    try:
        data = request.get_json()
        host = data.get('host')
        port = data.get('port', 22)
        username = data.get('username')
        password = data.get('password', '')
        private_key = data.get('private_key', '')
        
        if not host or not username:
            return jsonify({'success': False, 'error': '主机地址和用户名不能为空'}), 400
        
        # 创建SSH客户端进行测试
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # 尝试连接
            if private_key:
                # 使用私钥认证
                key_file = io.StringIO(private_key)
                try:
                    pkey = paramiko.RSAKey.from_private_key(key_file)
                except:
                    try:
                        key_file.seek(0)
                        pkey = paramiko.Ed25519Key.from_private_key(key_file)
                    except:
                        try:
                            key_file.seek(0)
                            pkey = paramiko.ECDSAKey.from_private_key(key_file)
                        except:
                            key_file.seek(0)
                            pkey = paramiko.DSSKey.from_private_key(key_file)
                
                ssh_client.connect(
                    hostname=host,
                    port=port,
                    username=username,
                    pkey=pkey,
                    timeout=10
                )
            else:
                # 使用密码认证
                ssh_client.connect(
                    hostname=host,
                    port=port,
                    username=username,
                    password=password,
                    timeout=120
                )
            TEST_COMMANDS = {
                'test_connection': 'echo "Connection test successful"',
                'system_info': 'uname -a'
            }
            stdin, stdout, stderr = ssh_client.exec_command(TEST_COMMANDS['test_connection']) # nosec B601
            output = stdout.read().decode('utf-8').strip()
            
            stdin, stdout, stderr = ssh_client.exec_command(TEST_COMMANDS['system_info']) # nosec B601
            system_info = stdout.read().decode('utf-8').strip()
            
            ssh_client.close()
            
            return jsonify({
                'success': True,
                'message': '连接测试成功！',
                'system_info': system_info,
                'details': {
                    'host': host,
                    'port': port,
                    'username': username,
                    'auth_method': '私钥认证' if private_key else '密码认证'
                }
            })
            
        except paramiko.AuthenticationException:
            return jsonify({
                'success': False,
                'error': '认证失败',
                'suggestions': [
                    '检查用户名和密码是否正确',
                    '确认服务器允许密码认证',
                    '尝试使用普通用户而不是root用户',
                    '检查服务器SSH配置'
                ]
            }), 401
            
        except paramiko.SSHException as e:
            return jsonify({
                'success': False,
                'error': f'SSH连接错误: {str(e)}',
                'suggestions': [
                    '检查网络连接是否正常',
                    '确认SSH服务是否运行',
                    '检查防火墙设置'
                ]
            }), 500
            
        except socket.timeout:
            return jsonify({
                'success': False,
                'error': '连接超时',
                'suggestions': [
                    '检查主机地址是否正确',
                    '确认网络连接是否正常',
                    '检查防火墙是否阻止连接'
                ]
            }), 408
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'连接失败: {str(e)}',
                'suggestions': [
                    '检查所有连接参数是否正确',
                    '确认服务器是否可访问'
                ]
            }), 500
            
        finally:
            try:
                ssh_client.close()
            except Exception as e :
                return jsonify({
                'success': False,
                'error': f'关闭失败: {str(e)}'
            }), 500
                
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'请求处理失败: {str(e)}'
        }), 500
    
# ========================
#AI助手 Chat模块'''
# ========================
AI_URLs="http://10.0.147.66:11434/api/"
model="qwen3:4b"

def save_chat_async(user_id, user_msg,ai_thinking, ai_msg):
    with app.app_context():
        history = ChatHistory(
            user_id=user_id,
            user_message=user_msg,
            ai_thinking = ai_thinking,
            ai_message=ai_msg
        )
        db.session.add(history)
        db.session.commit()

def ollama_stream(usermessages: str, user_id: int,conversation_id:str):
    async def runner():
        ai_messages = ''
        ai_thinking = ''
        d = Dify_agent(user_query=usermessages,conversation_id = conversation_id)
        async for chunk in d.request_dify():
            chunk = json.loads(chunk)
            if chunk["conversation_id"] != "":
                yield f"data: {json.dumps({'conversation_id': chunk['conversation_id']})}\n\n"
            if chunk["content"] == True:
                yield "data: [DONE]\n\n"
                status_check_thread = threading.Thread(target=save_chat_async(
                    user_id,
                    usermessages,
                    ai_thinking,
                    ai_messages
                ) , daemon=True)
                status_check_thread.start()

            else:
                ai_thinking += chunk["thinking"]
                ai_messages += chunk['content']
                yield f"data: {json.dumps({'task_id':chunk["task_id"],'data': chunk['content'], 'thinking': chunk['thinking']}, ensure_ascii=False)}\n\n"

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    agen = runner()

    try:
        while True:
            yield loop.run_until_complete(agen.__anext__())
    except StopAsyncIteration:
        pass
    finally:
        loop.close()


@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json(silent=True)
    if not data or "message" not in data:                                   
        return jsonify({"error": "Missing message"}), 400
    user_id = session['user_id']
    messages = data["message"]
    conversation_id = data["conversation_id"]
    return Response(
        ollama_stream(messages[-1]["content"], user_id,conversation_id),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
@app.route('/api/stop',methods=["POST"])
@login_required
def stop_chat():
    data = request.get_json()
    user = data["user"]
    task_id = data["task_id"]
    dify = Dify_agent(user_query='',model='',conversation_id='',user=user,task_id=task_id)
    result = dify.stop_chat()
    return result 

@app.route('/api/tags', methods=['GET'])
@login_required
def get_models():
    """获取 Ollama 已安装的模型"""
    try:
        url = AI_URLs+"tags"
        response = requests.get(url,timeout=10)
        if response.status_code == 200:
            models = response.json()
            #这里有问题的模型数量大于1，需要后续修改
            return jsonify(models.get('models', []))
        return jsonify([])
    except:
        return jsonify([])
    
@app.route('/api/clear/history',methods=["GET"])
@login_required
def clear_history():
    try:
        user_id = session['user_id']
        # 删除记录保留最近的5条记录
        history = ChatHistory.query.filter_by(user_id=user_id).order_by(ChatHistory.id.desc()).offset(5).all()
        for h in history:
            db.session.delete(h)
        db.session.commit()
        return {'result':"seucces"}
    except Exception as e:
        print(f"获取聊天历史记录错误: {e}")
        return {"result":"error"}  
    
@app.route('/api/chat/history', methods=['GET'])
@login_required
def get_chat_history():
    """获取聊天历史记录"""
    try:
        user_id = session['user_id']
        # 取最近5条聊天记录
        history = ChatHistory.query.filter_by(user_id=user_id).order_by(ChatHistory.id.desc()).limit(5)
        result = []
        for h in history:
            result.append({
                'id': h.id,
                'user_message': h.user_message,
                'ai_message': h.ai_message,
                'ai_thinking': h.ai_thinking
            })
        #排序
        for i in range(len(result) -1 ):
            for j  in range(len(result) -1  - i):
                if result[j].get('id') > result[j+1].get("id"):
                    tmp = result[j]
                    result[j] = result[j+1]
                    result[j+1] = tmp
        

        return jsonify(result)
    except Exception as e:
        print(f"获取聊天历史记录错误: {e}")

# WebSocket事件处理
@socketio.on('connect')
def handle_connect():
    print(f'客户端连接: {request.sid}')
    emit('connected', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f'客户端断开: {request.sid}')
    if request.sid in active_connections:
        active_connections[request.sid].disconnect()
        del active_connections[request.sid]

@socketio.on('ssh_connect')
def handle_ssh_connect(data):
    session_id = request.sid
    print(f'SSH连接请求: {data}')
    
    # 如果已经有连接，先断开
    if session_id in active_connections:
        active_connections[session_id].disconnect()
    
    # 创建新的SSH管理器
    ssh_manager = SSHManager(session_id)
    
    # 连接SSH
    if ssh_manager.connect(
        data['host'], 
        data.get('port', 22), 
        data['username'], 
        password=data.get('password'),
        private_key=data.get('private_key')
    ):
        active_connections[session_id] = ssh_manager
        emit('ssh_connected', {
            'status': 'connected',
            'host': data['host'],
            'username': data['username']
        })
    else:
        emit('ssh_error', {'error': 'Failed to connect'})

@socketio.on('ssh_connect_saved')
def handle_ssh_connect_saved(data):
    """使用保存的连接配置进行连接"""
    session_id = request.sid
    conn_id = data['connection_id']
    print(f'使用保存的连接: {conn_id}')
    
    try:
        # 检查用户是否已登录
        if 'user_id' not in session:
            emit('ssh_error', {'error': '请先登录'})
            return

        user_id = session['user_id']
        connection = db.session.get(SSHConnection, conn_id)
        if not connection:
            emit('ssh_error', {'error': '连接不存在'})
            return
        
        # 确保用户只能连接自己的SSH连接
        if connection.user_id != user_id:
            emit('ssh_error', {'error': '无权限使用此连接'})
            return
        
        # 如果已经有连接，先断开
        if session_id in active_connections:
            active_connections[session_id].disconnect()
        
        # 创建新的SSH管理器
        ssh_manager = SSHManager(session_id)
        
        # 解密密码
        password = None
        if connection.password:
            try:
                password = cipher_suite.decrypt(connection.password.encode()).decode()
            except Exception as decrypt_error:
                print(f"密码解密失败: {decrypt_error}")
                emit('ssh_error', {'error': '密码解密失败，可能是加密密钥已更改。请重新保存连接。'})
                return
        
        private_key = None
        if connection.private_key:
            try:
                private_key = cipher_suite.decrypt(connection.private_key.encode()).decode()
            except Exception as decrypt_error:
                print(f"私钥解密失败: {decrypt_error}")
                emit('ssh_error', {'error': '私钥解密失败，可能是加密密钥已更改。请重新保存连接。'})
                return
        
        # 连接SSH
        if ssh_manager.connect(
            connection.host, 
            connection.port, 
            connection.username, 
            password=password,
            private_key=private_key
        ):
            active_connections[session_id] = ssh_manager
            emit('ssh_connected', {
                'status': 'connected',
                'connection_name': connection.name,
                'host': connection.host,
                'username': connection.username
            })
        else:
            emit('ssh_error', {'error': 'Failed to connect'})
    except Exception as e:
        print(f"保存连接错误: {e}")
        emit('ssh_error', {'error': str(e)})

@socketio.on('ssh_command')
def handle_ssh_command(data):
    session_id = request.sid
    if session_id in active_connections:
        active_connections[session_id].send_command(data)
# 持续化连接
@socketio.on("ping")
def handle_ping():
    emit("pong")

@socketio.on('ssh_disconnect')
def handle_ssh_disconnect():
    session_id = request.sid
    if session_id in active_connections:
        active_connections[session_id].disconnect()
        del active_connections[session_id]
        emit('ssh_disconnected', {'status': 'disconnected'})

@socketio.on("resize")
def resize(data):
    cols = data["cols"]
    rows = data["rows"]
    session_id = request.sid
    if session_id in active_connections:
        active_connections[session_id].resize(cols, rows)

#服务器运行状态监控
@app.route("/api/monitor/local")
@login_required
def local_monitor():
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent

    return jsonify({
        "cpu": round(cpu, 1),
        "memory": round(mem, 1),
        "disk": round(disk, 1)
    })

#保存服务器日志
class WebSocketLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        
    def emit(self, record):
        try:
            log_entry = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'level': record.levelname,
                'message': self.format(record),
                'logger': record.name,
                'filename': record.filename,
                'lineno': record.lineno
            }
            # 发送到WebSocket
            socketio.emit('new_log', log_entry)
        except Exception as e:
            print(f"Error emitting log: {e}")

# 设置日志配置
logger = logging.getLogger()
def setup_logging():
    '''
    setup_logging 的 作用是设置日志配置，包括日志级别、格式、输出位置等。
    '''
    # 清除现有的handlers
    logger.handlers.clear()
    
    # 设置日志级别
    logger.setLevel(logging.DEBUG)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # WebSocket Handler
    ws_handler = WebSocketLogHandler()
    ws_handler.setLevel(logging.DEBUG)
    ws_handler.setFormatter(formatter)
    logger.addHandler(ws_handler)
    
    # 控制台Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件Handler
    file_handler = logging.FileHandler('server.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    

# ========================
# Zabbix 接口
# ========================

@app.route("/api/zabbix/hosts")
@login_required
def zabbix_hosts():
    name_prefix = ['SW1']
    zabbix = zabbix_api().main(name_prefix)
    return zabbix
    

# ========================
# 用户管理,RBAC权限管理
# ========================

def has_permission(user: User, perm_code: str) -> bool:
    if  user.role_id ==1:
        return True
    return False
    # return any(p.code == perm_code for p in user.role_id.permissions)

def permission_required(permission_code):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'error': '未登录'}), 401

            if not has_permission(user, permission_code):
                return jsonify({'error': '无权限访问'}), 403

            return f(*args, **kwargs)
        return wrapper
    return decorator



"""用户认证路由,其他API接口"""
@app.route('/api/register', methods=['POST'])
@permission_required('manage')
def register():
    """用户注册"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        # 验证输入
        if not username or not email or not password:
            return jsonify({'error': '用户名、邮箱和密码不能为空'}), 400
        
        if len(username) < 3:
            return jsonify({'error': '用户名至少需要3个字符'}), 400
        
        if len(password) < 6:
            return jsonify({'error': '密码至少需要6个字符'}), 400
        
        # 检查用户名是否已存在
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({'error': '用户名已存在'}), 409
        
        # 检查邮箱是否已存在
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            return jsonify({'error': '邮箱已被注册'}), 409
        
        # 创建新用户
        password_hash = hash_password(password)
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            is_active=True,
            role_id=2
        )
        
        db.session.add(user)
        db.session.commit() 
        
        # 自动登录
        session['user_id'] = user.id
        session['username'] = user.username
        
        return jsonify({
            'message': '注册成功',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        print(f"注册错误: {e}")
        return jsonify({'error': '注册失败，请稍后重试'}), 500


#登录
@app.route('/api/login', methods=['POST'])
def loginAPI():
    """用户登录"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': '用户名和密码不能为空'}), 400
        
        # 查找用户（支持用户名或邮箱登录）
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if not user or not verify_password(password, user.password_hash):
            return jsonify({'error': '用户名或密码错误'}), 401
        
        if not user.is_active:
            return jsonify({'error': '账户已被禁用'}), 403
        
        # 设置会话
        session['user_id'] = user.id
        session['username'] = user.username
        
        return jsonify({
            'message': '登录成功',
            'url': url_for('index')
        }),200
        
    except Exception as e:
        print(f"登录错误: {e}")
        return jsonify({'error': '登录失败，请稍后重试'}), 500

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    """用户登出"""
    try:
        session.clear()
        return jsonify({'message': '已成功登出'})
    except Exception as e:
        print(f"登出错误: {e}")
        return jsonify({'error': '登出失败'}), 500


@app.route('/api/user/profile', methods=['GET'])
@login_required
def get_profile():
    """获取用户资料"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': '用户未找到'}), 404
        
        return jsonify({
            'user': user.to_dict(),
            'ssh_connections_count': len(user.ssh_connections)
        })
    except Exception as e:
        print(f"获取用户资料错误: {e}")
        return jsonify({'error': '获取用户资料失败'}), 500
    
#获取全部的用户
@app.route('/api/getusers', methods=['GET'])
@login_required
@permission_required('manage')
def admin_list_users():
    users = User.query.filter_by(is_active = True).all()
    return jsonify([u.to_dict() for u in users])


@app.route('/api/users', methods=['POST'])
@login_required
@permission_required('manage')
def admin_create_user():
    """
    后台创建用户（区别于 register）
    """
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not username or not email or not password:
            return jsonify({'error': '参数不完整'}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({'error': '用户名已存在'}), 409

        if User.query.filter_by(email=email).first():
            return jsonify({'error': '邮箱已存在'}), 409
        if User.query.filter_by(username=username).first() and User.query.filter_by(email=email).first():
            return jsonify({'success': '用户名已存在'})
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password)
        )

        db.session.add(user)
        db.session.commit()

        return jsonify(user.to_dict()), 201
    except Exception as e:
        print(f"创建用户错误: {e}")
        return jsonify({'error': '创建用户失败'}), 500

#更新用户
@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
@permission_required('manage')
def admin_update_user(user_id):
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404

        data = request.get_json()

        if 'email' in data:
            user.email = data['email'].strip()

        if 'is_active' in data:
            user.is_active = bool(data['is_active'])

        db.session.commit()
        return jsonify(user.to_dict())
    except Exception as e:
        print(f"更新用户错误: {e}")
        return jsonify({'error': '更新用户失败'}), 500
    
#s删除用户
@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@permission_required('manage')
def admin_disable_user(user_id):
    """
    软删除 / 禁用用户
    """
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404

        # 禁用而不是物理删除
        user.is_active = False
        db.session.commit()

        return jsonify({'status': 'disabled'})
    except Exception as e:
        print(f"禁用用户错误: {e}")
        return jsonify({'error': '操作失败'}), 500

#恢复用户
@app.route('/api/users/<int:user_id>/restore', methods=['POST'])
@login_required
@permission_required('manage')
def admin_restore_user(user_id):
    """
    恢复用户
    """
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404

        # 恢复用户
        user.is_active = True
        db.session.commit()

        return jsonify({'status': 'active'})
    except Exception as e:
        print(f"恢复用户错误: {e}")
        return jsonify({'error': '操作失败'}), 500
    
#更改密码
@app.route('/api/users/<int:user_id>/password', methods=['PUT'])
@login_required
@permission_required('manage')
def admin_update_password(user_id):
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404

        data = request.get_json()
        password = data.get('password', '')
        if not password:
            return jsonify({'error': '密码不能为空'}), 400
        user.password_hash = hash_password(password)
        db.session.commit()

        return jsonify({'status': 'password updated'})
    except Exception as e:
        print(f"更新密码错误: {e}")
        return jsonify({'error': '更新密码失败'}), 500


"""巡检路由"""
# 设置时区
tz = pytz.timezone('Asia/Shanghai')
import ipaddress
def check_device_status(device):
    """检查设备状态"""
    try:
        # 1. 校验 IP 地址，防止命令注入
        ip = str(ipaddress.ip_address(device.ip))
        # 2. 根据操作系统构造“参数列表”，而不是字符串命令
        if platform.system().lower() == 'windows':
            ping_cmd = ['ping', '-n', '1', '-w', '1000', ip]
        else:
            ping_cmd = ['ping', '-c', '1', '-W', '1', ip]

        # 3. 禁用 shell，设置超时
        result = subprocess.run(
            ping_cmd,
            capture_output=True,
            text=True,
            timeout=3,
            shell=False  # nosec B603
        )

        device.status = 'online' if result.returncode == 0 else 'offline'

    except (ValueError, subprocess.TimeoutExpired):
        # IP 非法或 ping 超时
        device.status = 'offline'

    except Exception as e:
        # 兜底异常，防止服务崩溃
        print(f"检查设备 {device.ip} 状态时出错: {str(e)}")
        device.status = 'offline'
        device.last_check = datetime.now(tz)
        db.session.commit()

    finally:
        device.last_check = datetime.now(tz)
        db.session.commit()


def get_device_type(device_type, protocol):
    """根据设备类型和协议返回netmiko设备类型"""
    if protocol.lower() == 'telnet':
        return f"{device_type}_telnet"
    return device_type

def check_all_devices():
    """检查所有设备状态"""
    while True:
        with app.app_context():
            devices = Device.query.all()
            for device in devices:
                check_device_status(device)
        time.sleep(30)  # 每30秒检查一次

# 启动状态检查线程
status_check_thread = threading.Thread(target=check_all_devices, daemon=True)
status_check_thread.start()

# API路由
@app.route('/api/devices', methods=['GET'])
def get_devices():
    try:
        devices = Device.query.all()
        logger.info(f"成功获取设备列表，共{len(devices)}个设备")
        return jsonify([device.to_dict() for device in devices])
    except Exception as e:
        logger.error(f"获取设备列表失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices', methods=['POST'])
def add_device():
    try:
        data = request.json
        
        # 处理commands字段，确保存储格式正确
        commands = data.get('commands', '')
        # 如果commands是JSON字符串，尝试解析并转换为逗号分隔的字符串
        try:
            if isinstance(commands, str) and commands.startswith('[') and commands.endswith(']'):
                commands_list = json.loads(commands)
                commands = ','.join([str(cmd).strip() for cmd in commands_list if cmd])
        except:
            # 如果解析失败，保持原样
            logger.warning(f"命令解析失败: {e}")
        
        device = Device(
            name=data['name'],
            ip=data['ip'],
            username=data['username'],
            password=data['password'],
            enable_password=data.get('enable_password'),
            device_type=data['device_type'],
            protocol=data['protocol'],
            commands=commands,
            group=data.get('group', '交换机')  # 新增分组字段，默认为"交换机"
        )
        db.session.add(device)
        db.session.commit()
        logger.info(f"成功添加设备: {device.name}")
        return jsonify(device.to_dict())
    except Exception as e:
        logger.error(f"添加设备失败: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices/<int:device_id>', methods=['DELETE'])
def delete_device(device_id):
    device = Device.query.get_or_404(device_id)
    db.session.delete(device)
    db.session.commit()
    return '', 204

@app.route('/api/devices/<int:device_id>', methods=['PUT'])
def update_device(device_id):
    try:
        device = Device.query.get_or_404(device_id)
        data = request.json
        
        # 处理commands字段，确保存储格式正确
        commands = data.get('commands', '')
        # 如果commands是JSON字符串，尝试解析并转换为逗号分隔的字符串
        try:
            if isinstance(commands, str) and commands.startswith('[') and commands.endswith(']'):
                commands_list = json.loads(commands)
                commands = ','.join([str(cmd).strip() for cmd in commands_list if cmd])
        except:
            # 如果解析失败，保持原样
            logger.warning(f"命令解析失败: {e}")
        
        # 更新设备信息
        device.name = data['name']
        device.ip = data['ip']
        device.username = data['username']
        device.password = data['password']
        device.enable_password = data.get('enable_password')
        device.device_type = data['device_type']
        device.protocol = data['protocol']
        device.commands = commands
        device.group = data.get('group', '交换机')  # 新增分组字段，默认为"交换机"
        
        db.session.commit()
        logger.info(f"成功更新设备: {device.name}")
        return jsonify(device.to_dict())
    except Exception as e:
        logger.error(f"更新设备失败: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices/<int:device_id>/inspect', methods=['POST'])
def inspect_device(device_id):
    device = Device.query.get_or_404(device_id)
    
    # 检查设备状态
    if device.status != 'online':
        return jsonify({
            'success': False,
            'message': f'设备 {device.name} ({device.ip}) 当前不在线，无法执行巡检'
        }), 400

    try:
        # 创建巡检日志 - 单设备巡检
        inspection_log = InspectionLog(
            total_devices=1,
            status='进行中',
            details=json.dumps([{
                'device_id': device.id,
                'device_name': device.name,
                'device_ip': device.ip,
                'status': '进行中',
                'message': '正在巡检...',
                'start_time': datetime.now(tz).isoformat()
            }])
        )
        db.session.add(inspection_log)
        db.session.commit()
        
        # 记录开始时间
        start_time = time.time()
        
        # 获取设备类型
        device_type = get_device_type(device.device_type, device.protocol)
        
        logger.info(f"开始巡检设备: {device.name} ({device.ip}), 设备类型: {device_type}")
        
        # 连接设备
        connection_params = {
            'device_type': device_type,
            'host': device.ip,
            'username': device.username,
            'password': device.password,
            'timeout': 20,
            'auth_timeout': 20,
            'banner_timeout': 20,
            'fast_cli': False
        }
        
        # 如果配置了enable密码，添加到连接参数中
        if device.enable_password and device.enable_password.strip():
            connection_params['secret'] = device.enable_password
        
        # 建立连接
        logger.info(f"正在连接设备: {device.ip}")
        connection = netmiko.ConnectHandler(**connection_params)  
        logger.info(f"成功连接到设备: {device.ip}")
        
        # 如果是Cisco IOS设备并且有enable密码，进入enable模式
        if 'cisco_ios' in device_type and device.enable_password and device.enable_password.strip():
            logger.info(f"正在进入enable模式: {device.ip}")
            connection.enable()
            logger.info(f"已进入enable模式: {device.ip}")
        elif 'ruijie_os' in device_type:
            logger.info(f"锐捷交换机设备 {device.ip} 不需要进入 enable 模式，跳过此步骤")
        
        # 解析并执行巡检命令
        results = []
        try:
            # 尝试解析命令
            try:
                if device.commands.startswith('[') and device.commands.endswith(']'):
                    # 如果命令是JSON数组格式
                    commands_list = json.loads(device.commands)
                    # 确保每个命令都是纯文本字符串
                    commands = [str(cmd).strip() for cmd in commands_list if cmd]
                else:
                    # 如果不是JSON格式，尝试按逗号分隔
                    commands = [cmd.strip() for cmd in device.commands.split(',') if cmd.strip()]
            except json.JSONDecodeError:
                # 如果JSON解析失败，尝试按逗号分隔处理
                commands = [cmd.strip() for cmd in device.commands.split(',') if cmd.strip()]
            except Exception as e:
                logger.error(f"命令解析错误: {str(e)}")
                # 如果所有尝试都失败，将整个commands作为单个命令
                commands = [device.commands] if device.commands else []
            
            # 确保commands是列表类型且每个命令都是纯文本字符串
            if not isinstance(commands, list):
                commands = [str(commands)] if commands else []
            else:
                commands = [str(cmd) for cmd in commands]
            
            # 清理命令，移除所有可能的特殊字符和格式
            cleaned_commands = []
            for cmd in commands:
                # 移除所有可能的引号（单引号和双引号）
                cmd = cmd.replace('"', '').replace("'", '')
                # 移除所有可能的方括号
                cmd = cmd.replace('[', '').replace(']', '')
                # 移除命令前后的空白字符
                cmd = cmd.strip()
                # 如果命令不为空，添加到清理后的命令列表
                if cmd:
                    cleaned_commands.append(cmd)
            
            commands = cleaned_commands
            logger.info(f"清理后的设备 {device.ip} 的巡检命令: {commands}")
            
            # 执行命令
            command_success = True  # 添加命令执行状态跟踪
            command_results = []  # 添加command_results变量定义
            for cmd in commands:
                try:
                    logger.info(f"设备 {device.ip} 执行命令: {cmd}")
                    output = connection.send_command(cmd, strip_prompt=False, strip_command=False)
                    command_results.append({
                        'command': cmd,
                        'output': output
                    })
                    logger.info(f"设备 {device.ip} 命令 {cmd} 执行成功")
                except Exception as e:
                    error_msg = f"执行命令 {cmd} 失败: {str(e)}"
                    logger.error(error_msg)
                    command_success = False
                    command_results.append({
                        'command': cmd,
                        'output': error_msg
                    })
        except Exception as e:
            error_msg = f"处理巡检命令时出错: {str(e)}"
            logger.error(error_msg)
            # 更新巡检日志
            inspection_log.end_time = datetime.now(tz)
            inspection_log.failed_devices = 1
            inspection_log.status = '已完成'
            inspection_log.total_duration = time.time() - start_time
            
            device_details = json.loads(inspection_log.details)
            device_details[0]['status'] = '失败'
            device_details[0]['message'] = error_msg
            device_details[0]['end_time'] = datetime.now(tz).isoformat()
            inspection_log.details = json.dumps(device_details)
            
            db.session.commit()
            
            return jsonify({
                'success': False,
                'message': error_msg
            }), 400
        
        # 断开连接
        connection.disconnect()
        logger.info(f"已断开与设备 {device.ip} 的连接")
        
        # 保存巡检记录
        try:
            record = InspectionRecord(
                device_id=device.id,
                device_name=device.name,
                result=json.dumps(command_results, ensure_ascii=False)
            )
            db.session.add(record)
            db.session.commit()
            logger.info(f"设备 {device.name} ({device.ip}) 巡检完成，已保存记录")
            
            # 验证记录是否成功保存
            saved_record = InspectionRecord.query.get(record.id)
            if saved_record:
                logger.info(f"巡检记录保存成功，ID: {record.id}")
            else:
                logger.error("巡检记录保存失败，无法查询到记录")
        except Exception as e:
            logger.error(f"保存巡检记录时出错: {str(e)}")
            db.session.rollback()
            raise
        
        # 更新巡检日志
        inspection_log.end_time = datetime.now(tz)
        inspection_log.successful_devices = 1 if command_success else 0
        inspection_log.failed_devices = 0 if command_success else 1
        inspection_log.status = '已完成' if command_success else '已完成但失败'
        inspection_log.total_duration = time.time() - start_time
        
        device_details = json.loads(inspection_log.details)
        device_details[0]['status'] = '成功' if command_success else '失败'
        device_details[0]['message'] = '巡检完成' if command_success else error_msg
        device_details[0]['end_time'] = datetime.now(tz).isoformat()
        inspection_log.details = json.dumps(device_details)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'results': command_results
        })
        
    except netmiko.NetMikoTimeoutException as e:
        error_msg = f'连接设备 {device.name} ({device.ip}) 超时，请检查网络连接或设备是否可达: {str(e)}'
        logger.error(error_msg)
        
        # 更新巡检日志
        inspection_log.end_time = datetime.now(tz)
        inspection_log.failed_devices = 1
        inspection_log.status = '已完成'
        inspection_log.total_duration = time.time() - start_time
        
        device_details = json.loads(inspection_log.details)
        device_details[0]['status'] = '失败'
        device_details[0]['message'] = error_msg
        device_details[0]['end_time'] = datetime.now(tz).isoformat()
        inspection_log.details = json.dumps(device_details)
        
        db.session.commit()
        
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500
    except netmiko.NetMikoAuthenticationException as e:
        error_msg = f'设备 {device.name} ({device.ip}) 认证失败，请检查用户名和密码是否正确: {str(e)}'
        logger.error(error_msg)
        
        # 更新巡检日志
        inspection_log.end_time = datetime.now(tz)
        inspection_log.failed_devices = 1
        inspection_log.status = '已完成'
        inspection_log.total_duration = time.time() - start_time
        
        device_details = json.loads(inspection_log.details)
        device_details[0]['status'] = '失败'
        device_details[0]['message'] = error_msg
        device_details[0]['end_time'] = datetime.now(tz).isoformat()
        inspection_log.details = json.dumps(device_details)
        
        db.session.commit()
        
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500
    except Exception as e:
        error_msg = f'巡检设备 {device.name} ({device.ip}) 失败: {str(e)}'
        logger.error(error_msg)
        
        # 更新巡检日志
        inspection_log.end_time = datetime.now(tz)
        inspection_log.failed_devices = 1
        inspection_log.status = '已完成'
        inspection_log.total_duration = time.time() - start_time
        
        device_details = json.loads(inspection_log.details)
        device_details[0]['status'] = '失败'
        device_details[0]['message'] = error_msg
        device_details[0]['end_time'] = datetime.now(tz).isoformat()
        inspection_log.details = json.dumps(device_details)
        
        db.session.commit()
        
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500

@app.route('/api/devices/<int:device_id>/records', methods=['GET'])
def get_device_records(device_id):
    try:
        # 检查设备是否存在
        device = Device.query.get_or_404(device_id)
        # 获取该设备的所有巡检记录，按时间倒序排序
        records = InspectionRecord.query.filter_by(device_id=device_id).order_by(InspectionRecord.created_at.desc()).all()
        logger.info(f"成功获取设备 {device.name} 的巡检记录，共 {len(records)} 条")
        return jsonify([record.to_dict() for record in records])
    except Exception as e:
        logger.error(f"获取设备 {device_id} 的巡检记录失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    try:
        # 查找巡检记录
        record = InspectionRecord.query.get_or_404(record_id)
        # 记录相关信息
        device_name = record.device_name
        device_id = record.device_id
        # 删除记录
        db.session.delete(record)
        db.session.commit()
        logger.info(f"成功删除设备 {device_name} (ID: {device_id}) 的巡检记录 (ID: {record_id})")
        return jsonify({'success': True, 'message': '巡检记录删除成功'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除巡检记录 {record_id} 失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


# 添加导入导出API
@app.route('/api/devices/export', methods=['GET'])
def export_devices():
    try:
        devices = Device.query.all()
        data = []
        for device in devices:
            data.append({
                '设备名称': device.name,
                'IP地址': device.ip,
                '用户名': device.username,
                '密码': device.password,
                'Enable密码': device.enable_password or '',
                '设备类型': device.device_type,
                '连接协议': device.protocol,
                '巡检命令': device.commands,
                '设备分组': device.group
            })
        
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='设备列表')
        
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='设备列表.xlsx'
        )
    except Exception as e:
        logger.error(f"导出设备列表失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices/import', methods=['POST'])
def import_devices():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未找到上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'}), 400
    
    if not file.filename.endswith('.xlsx'):
        return jsonify({'success': False, 'error': '只能上传.xlsx格式的文件'}), 400
    
    try:
        # 读取Excel文件
        df = pd.read_excel(file)
        
        # 检查必要的列是否存在
        required_columns = ['设备名称', 'IP地址', '用户名', '密码', '设备类型', '连接协议', '巡检命令']
        for col in required_columns:
            if col not in df.columns:
                return jsonify({'success': False, 'error': f'Excel文件缺少"{col}"列'}), 400
        
        success_count = 0
        error_count = 0
        errors = []
        
        # 遍历行并导入设备
        for index, row in df.iterrows():
            try:
                # 检查设备是否已存在（按IP地址检查）
                existing_device = Device.query.filter_by(ip=row['IP地址']).first()
                if existing_device:
                    # 更新现有设备
                    existing_device.name = row['设备名称']
                    existing_device.username = row['用户名']
                    existing_device.password = row['密码']
                    existing_device.enable_password = row['Enable密码'] if 'Enable密码' in row and not pd.isna(row['Enable密码']) else None
                    existing_device.device_type = row['设备类型']
                    existing_device.protocol = row['连接协议']
                    existing_device.commands = row['巡检命令']
                    existing_device.group = row['设备分组'] if '设备分组' in row and not pd.isna(row['设备分组']) else '交换机'
                else:
                    # 创建新设备
                    new_device = Device(
                        name=row['设备名称'],
                        ip=row['IP地址'],
                        username=row['用户名'],
                        password=row['密码'],
                        enable_password=row['Enable密码'] if 'Enable密码' in row and not pd.isna(row['Enable密码']) else None,
                        device_type=row['设备类型'],
                        protocol=row['连接协议'],
                        commands=row['巡检命令'],
                        group=row['设备分组'] if '设备分组' in row and not pd.isna(row['设备分组']) else '交换机'
                    )
                    db.session.add(new_device)
                
                success_count += 1
            except Exception as e:
                error_count += 1
                errors.append(f"行 {index+2}: {str(e)}")
        
        db.session.commit()
        logger.info(f"设备导入完成，成功: {success_count}，失败: {error_count}")
        
        return jsonify({
            'success': True,
            'message': f'导入完成，成功导入 {success_count} 个设备',
            'error_count': error_count,
            'errors': errors
        })
    except Exception as e:
        logger.error(f"导入设备数据失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/records/<int:record_id>/export', methods=['GET'])
def export_record(record_id):
    try:
        # 获取巡检记录
        record = InspectionRecord.query.get_or_404(record_id)
        
        # 获取设备信息
        device = Device.query.get(record.device_id)
        
        # 解析巡检结果
        try:
            results = json.loads(record.result)
        except Exception as e:
            logger.error(f"解析巡检结果失败: {str(e)}")
            return jsonify({'error': f"解析巡检结果失败: {str(e)}"}), 500
        
        # 将巡检结果格式化为文本
        content = []
        content.append(f"设备名称: {record.device_name}")
        content.append(f"设备IP: {device.ip if device else '未知'}")
        content.append(f"巡检时间: {record.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        content.append("="*50)
        
        for item in results:
            content.append(f"\n[命令] {item['command']}")
            content.append("-"*50)
            content.append(f"{item['output']}")
            content.append("-"*50)
        
        # 创建文件名
        device_ip = device.ip if device else "unknown"
        timestamp = record.created_at.strftime("%Y%m%d_%H%M%S")
        filename = f"{record.device_name}_{device_ip}_{timestamp}.txt"
        
        # 创建内存文件
        output = io.StringIO()
        output.write("\n".join(content))
        output.seek(0)
        
        # 发送文件
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/plain',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"导出巡检记录失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/records/batch-export', methods=['GET'])
def batch_export_records():
    try:
        # 获取要导出的记录ID列表
        record_ids = request.args.getlist('id', type=int)
        
        if not record_ids:
            return jsonify({'error': '未指定要导出的记录ID'}), 400
        
        # 创建ZIP文件
        memory_file = io.BytesIO()
        
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for record_id in record_ids:
                try:
                    # 获取巡检记录
                    record = InspectionRecord.query.get(record_id)
                    if not record:
                        logger.warning(f"巡检记录 {record_id} 不存在")
                        continue
                    
                    # 获取设备信息
                    device = Device.query.get(record.device_id)
                    
                    # 解析巡检结果
                    try:
                        results = json.loads(record.result)
                    except:
                        logger.warning(f"解析巡检记录 {record_id} 结果失败")
                        continue
                    
                    # 将巡检结果格式化为文本
                    content = []
                    content.append(f"设备名称: {record.device_name}")
                    content.append(f"设备IP: {device.ip if device else '未知'}")
                    content.append(f"巡检时间: {record.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    content.append("="*50)
                    
                    for item in results:
                        content.append(f"\n[命令] {item['command']}")
                        content.append("-"*50)
                        content.append(f"{item['output']}")
                        content.append("-"*50)
                    
                    # 创建文件名
                    device_ip = device.ip if device else "unknown"
                    timestamp = record.created_at.strftime("%Y%m%d_%H%M%S")
                    filename = f"{record.device_name}_{device_ip}_{timestamp}.txt"
                    
                    # 添加到ZIP文件
                    zf.writestr(filename, "\n".join(content))
                    
                except Exception as e:
                    logger.error(f"处理记录 {record_id} 时出错: {str(e)}")
                    continue
        
        # 准备发送ZIP文件
        memory_file.seek(0)
        timestamp = datetime.now(tz).strftime("%Y%m%d_%H%M%S")
        
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'inspection_records_{timestamp}.zip'
        )
    except Exception as e:
        logger.error(f"批量导出巡检记录失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

def save_inspect_file(filename,filecontent):
    with open(f'/var/log/huawei_xunjian/{filename}.txt',"w") as f:
        f.write(filecontent)
        f.close()


# 批量巡检API - 保持简单实现
@app.route('/api/devices/batch-inspect', methods=['POST'])
def batch_inspect_devices():
    data = request.json
    if not data or not data.get('device_ids') or not isinstance(data.get('device_ids'), list):
        return jsonify({
            'success': False,
            'message': '请提供要巡检的设备ID列表'
        }), 400
    
    device_ids = data.get('device_ids')
    try:
        devices = Device.query.filter(Device.id.in_(device_ids), Device.status == 'online').all()
        
        if not devices:
            return jsonify({
                'success': False,
                'message': '所选设备中没有在线设备，无法进行巡检'
            }), 400
        
        # 创建巡检日志
        device_details = []
        for device in devices:
            device_details.append({
                'device_id': device.id,
                'device_name': device.name,
                'device_ip': device.ip,
                'status': '等待中',
                'message': '等待巡检...',
                'start_time': None,
                'end_time': None
            })
        
        inspection_log = InspectionLog(
            total_devices=len(devices),
            status='进行中',
            details=json.dumps(device_details)
        )
        db.session.add(inspection_log)
        db.session.commit()
        
        # 执行巡检
        results = []
        successful_count = 0
        failed_count = 0
        start_time = time.time()
        device_name = None
        for idx, device in enumerate(devices):
            try:
                # 重新检查日志状态，如果已取消则中止执行
                current_log = InspectionLog.query.get(inspection_log.id)
                if current_log.status == '已取消':
                    logger.info(f"巡检任务 {inspection_log.id} 被用户取消")
                    break
                    
                # 更新当前设备状态
                device_details = json.loads(inspection_log.details)
                device_details[idx]['status'] = '进行中'
                device_details[idx]['message'] = '正在巡检...'
                device_details[idx]['start_time'] = datetime.now(tz).isoformat()
                inspection_log.details = json.dumps(device_details)
                db.session.commit()
                
                # 获取设备类型
                device_type = get_device_type(device.device_type, device.protocol)
                logger.info(f"开始巡检设备: {device.name} ({device.ip}), 设备类型: {device_type}")
                
                # 连接参数
                connection_params = {
                    'device_type': device_type,
                    'host': device.ip,
                    'username': device.username,
                    'password': device.password,
                    'timeout': 30,  # 增加超时时间
                    'auth_timeout': 30,
                    'banner_timeout': 30,
                    'fast_cli': False,
                    'session_log': None  # 关闭会话日志以减少干扰
                }
                
                if device.enable_password and device.enable_password.strip():
                    connection_params['secret'] = device.enable_password
                
                # 连接设备
                device_start_time = time.time()
                logger.info(f"尝试连接设备: {device.ip}")
                
                connection = netmiko.ConnectHandler(**connection_params)
                logger.info(f"成功连接到设备: {device.ip}")
                
                # 处理enable模式
                if 'cisco_ios' in device_type and device.enable_password and device.enable_password.strip():
                    connection.enable()
                    logger.info(f"设备 {device.ip} 进入enable模式")
                
                # 处理命令
                command_success = True  # 添加命令执行状态跟踪
                command_results = []  # 添加command_results变量定义
                if device.commands.startswith('[') and device.commands.endswith(']'):
                    try:
                        commands_list = json.loads(device.commands)
                        commands = [str(cmd).strip() for cmd in commands_list if cmd]
                    except Exception as e:
                        logger.error(f"解析命令JSON失败: {e}")
                        commands = [cmd.strip() for cmd in device.commands.split(',') if cmd.strip()]
                else:
                    commands = [cmd.strip() for cmd in device.commands.split(',') if cmd.strip()]
                
                # 清理命令
                cleaned_commands = []
                for cmd in commands:
                    cmd = cmd.replace('"', '').replace("'", '')
                    cmd = cmd.replace('[', '').replace(']', '')
                    cmd = cmd.strip()
                    if cmd:
                        cleaned_commands.append(cmd)
                
                logger.info(f"设备 {device.ip} 执行命令列表: {cleaned_commands}")
                
                # 执行命令
                for cmd in cleaned_commands:
                    try:
                        logger.info(f"设备 {device.ip} 执行命令: {cmd}")
                        output = connection.send_command(cmd, strip_prompt=False, strip_command=False)
                        command_results.append({
                            'command': cmd,
                            'output': output
                        })
                        logger.info(f"设备 {device.ip} 命令 {cmd} 执行成功")
                    except Exception as e:
                        logger.error(f"设备 {device.ip} 执行命令 {cmd} 失败: {str(e)}")
                        command_success = False
                        command_results.append({
                            'command': cmd,
                            'output': f"执行命令失败: {str(e)}"
                        })
                
                # 断开连接
                try:
                    connection.disconnect()
                    logger.info(f"设备 {device.ip} 断开连接")
                except Exception as e:
                    logger.warning(f"断开设备 {device.ip} 连接时出错: {str(e)}")
                
                # 保存巡检记录
                record = InspectionRecord(
                    device_id=device.id,
                    device_name=device.name,
                    result=json.dumps(command_results, ensure_ascii=False)
                )
                db.session.add(record)
                db.session.commit()
                threads = []
                t = threading.Thread(target=save_inspect_file, args=(device.name,str(json.dumps(command_results, ensure_ascii=False))))
                t.start()
                threads.append(t)
                for t in threads:
                    t.join()
                logger.info(f"设备 {device.ip} 巡检记录已保存")
                
                # 更新设备巡检状态
                device_details = json.loads(inspection_log.details)
                device_details[idx]['status'] = '成功' if command_success else '失败'
                device_details[idx]['message'] = '巡检完成' if command_success else 'error_msg'
                device_details[idx]['end_time'] = datetime.now(tz).isoformat()
                device_details[idx]['duration'] = time.time() - device_start_time
                
                successful_count += 1 if command_success else 0
                failed_count += 1 if not command_success else 0
                logger.info(f"设备 {device.ip} 巡检完成")
                
            except Exception as e:
                logger.error(f"设备 {device.ip} 巡检过程中出错: {str(e)}")
                # 更新设备巡检状态
                device_details = json.loads(inspection_log.details)
                device_details[idx]['status'] = '失败'
                device_details[idx]['message'] = f'巡检失败: {str(e)}'
                device_details[idx]['end_time'] = datetime.now(tz).isoformat()
                
                failed_count += 1
            
            # 更新巡检日志
            inspection_log.successful_devices = successful_count
            inspection_log.failed_devices = failed_count
            inspection_log.details = json.dumps(device_details)
            db.session.commit()
        
        # 完成所有设备巡检
        inspection_log.end_time = datetime.now(tz)
        if inspection_log.status != '已取消':
            inspection_log.status = '已完成'
        inspection_log.total_duration = time.time() - start_time
        db.session.commit()
        logger.info(f"批量巡检任务 {inspection_log.id} 已完成，成功: {successful_count}，失败: {failed_count}")
        
        return jsonify({
            'success': True,
            'message': f'批量巡检已完成，成功: {successful_count}，失败: {failed_count}',
            'log_id': inspection_log.id,
            'file_path':f"/var/log/huawei_xunjian/{device.name}.txt'"
        })
    except Exception as e:
        logger.error(f"批量巡检过程中发生未处理的异常: {str(e)}")
        # 如果已创建日志，则更新日志状态
        if 'inspection_log' in locals():
            try:
                inspection_log.end_time = datetime.now(tz)
                inspection_log.status = '已完成'  # 标记为已完成但失败
                inspection_log.total_duration = time.time() - start_time
                db.session.commit()
            except Exception as inner_e:
                logger.error(f"更新巡检日志失败: {str(inner_e)}")
                db.session.rollback()
        
        return jsonify({
            'success': False,
            'message': f'批量巡检过程中出错: {str(e)}'
        }), 500

# 巡检日志API
@app.route('/api/inspection-logs', methods=['GET'])
def get_inspection_logs():
    try:
        logs = InspectionLog.query.order_by(InspectionLog.start_time.desc()).all()
        return jsonify([log.to_dict() for log in logs])
    except Exception as e:
        logger.error(f"获取巡检日志失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inspection-logs/<int:log_id>', methods=['GET'])
def get_inspection_log(log_id):
    try:
        log = InspectionLog.query.get_or_404(log_id)
        return jsonify(log.to_dict())
    except Exception as e:
        logger.error(f"获取巡检日志详情失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inspection-logs/<int:log_id>', methods=['DELETE'])
def delete_inspection_log(log_id):
    try:
        log = InspectionLog.query.get_or_404(log_id)
        db.session.delete(log)
        db.session.commit()
        return jsonify({'success': True, 'message': '巡检日志删除成功'})
    except Exception as e:
        logger.error(f"删除巡检日志失败: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# 添加强制停止巡检API
@app.route('/api/inspection-logs/<int:log_id>/cancel', methods=['POST'])
def cancel_inspection(log_id):
    try:
        inspection_log = InspectionLog.query.get_or_404(log_id)
        
        if inspection_log.status == '已完成':
            return jsonify({
                'success': False,
                'message': '该巡检任务已完成，无法取消'
            }), 400
        
        # 更新日志状态
        inspection_log.status = '已取消'
        inspection_log.end_time = datetime.now(tz)
        
        # 更新设备巡检状态
        device_details = json.loads(inspection_log.details) if inspection_log.details else []
        for detail in device_details:
            if detail['status'] in ['进行中', '等待中']:
                detail['status'] = '已取消'
                detail['message'] = '用户取消巡检'
                detail['end_time'] = datetime.now(tz).isoformat()
        
        inspection_log.details = json.dumps(device_details)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '已取消巡检任务'
        })
    except Exception as e:
        logger.error(f"取消巡检任务失败: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    with app.app_context():
        #"初始化数据库"
        init_db.init_database()
        setup_logging()
        
    print("启动Flask Web SSH客户端...")
    print("访问地址: http://10.0.147.50:80")

    socketio.run(app, host='0.0.0.0', port=80,allow_unsafe_werkzeug=True) 