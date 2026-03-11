from cryptography.fernet import Fernet
import paramiko
import threading
import time
from flask_socketio import SocketIO, emit

socketio = None

class SSHManager:
    def __init__(self,session_id):
        self.session_id = session_id
        self.ssh_client = None
        self.shell = None
        self.connected = False
        
    def connect(self, host, port, username, password=None, private_key=None):
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 详细的连接信息
            print(f"尝试连接: {username}@{host}:{port}")
            
            if private_key:
                # 使用私钥连接
                from io import StringIO
                key_file = StringIO(private_key)
                try:
                    key = paramiko.RSAKey.from_private_key(key_file)
                    #("使用RSA私钥认证")
                except:
                    try:
                        key_file.seek(0)
                        key = paramiko.DSAKey.from_private_key(key_file)
                        #("使用DSA私钥认证")
                    except:
                        try:
                            key_file.seek(0)
                            key = paramiko.ECDSAKey.from_private_key(key_file)
                            #("使用ECDSA私钥认证")
                        except:
                            key_file.seek(0)
                            key = paramiko.Ed25519Key.from_private_key(key_file)
                            #("使用Ed25519私钥认证")
                
                self.ssh_client.connect(host, port=port, username=username, pkey=key, timeout=120)
            else:
                # 使用密码连接
                print("使用密码认证")
                self.ssh_client.connect(
                    host, 
                    port=port, 
                    username=username, 
                    password=password, 
                    timeout=120,
                    allow_agent=False,
                    look_for_keys=False
                )
            
            self.shell = self.ssh_client.invoke_shell(
                term='xterm',
                width=97,
                height=38
            )
            self.shell.settimeout(0.1)
            self.connected = True
            
            print(f"SSH连接成功: {username}@{host}:{port}")
            
            # 启动输出监听线程
            threading.Thread(target=self._read_output, daemon=True).start()
            
            return True
        except paramiko.AuthenticationException as e:
            error_msg = f"认证失败: 用户名或密码错误，或服务器不允许此认证方式"
            print(f"SSH认证错误: {e}")
            socketio.emit('ssh_error', {'error': error_msg}, room=self.session_id)
            return False
        except paramiko.SSHException as e:
            error_msg = f"SSH连接错误: {str(e)}"
            print(f"SSH连接错误: {e}")
            socketio.emit('ssh_error', {'error': error_msg}, room=self.session_id)
            return False
        except Exception as e:
            error_msg = f"连接失败: {str(e)}"
            print(f"连接错误: {e}")
            socketio.emit('ssh_error', {'error': error_msg}, room=self.session_id)
            return False
    
    def _read_output(self):
        while self.connected and self.shell:
            try:
                if self.shell.recv_ready():
                    output = self.shell.recv(1024).decode('utf-8', errors='ignore')
                    socketio.emit('ssh_output', {'data': output}, room=self.session_id)
                time.sleep(0.01)
            except Exception as e:
                print(f"读取输出错误: {e}")
                break
    def resize(self, cols, rows):
        try:
            if self.shell:
                self.shell.resize_pty(
                    width=cols,
                    height=rows
                )
        except Exception as e:
            print(f"终端resize失败: {e}")

    def send_command(self, command):
        if self.shell and self.connected:
            try:
                self.shell.send(command)
                return True
            except Exception as e:
                print(f"发送命令错误: {e}")
                return False
        return False
    
    def disconnect(self):
        self.connected = False
        if self.shell:
            try:
                self.shell.close()
            except Exception as e:
                print("ssh服务端连接关闭失败:"+e)
                return False
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception as e:
                print("ssh客户端连接关闭失败:"+e)
                return False
