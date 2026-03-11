import os
import sys
import time
import logging
import paramiko
from typing import Optional, Dict, Any
from fastmcp import FastMCP
from fastmcp import Client
from fastmcp.client.logging import LogMessage
from pathlib import Path
import asyncio
import zabbix_api as zabbix_api
import httpx
import json
# 配置日志
# 日志文件在 /logs/ssh_operations.log 
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

def create_logger(name, filename):
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    file_path = os.path.join("logs", filename)
    handler = logging.FileHandler(file_path)

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

mcp_tool_logger = create_logger("mcp_tool", "mcp_tool.log")
LOGGING_LEVEL_MAP = logging.getLevelNamesMapping()

async def log_handler(message: LogMessage):
    """
    处理来自 MCP 服务器的传入日志并将其转发
    到标准 Python 日志记录系统。
    """
    msg = message.data.get('msg')
    extra = message.data.get('extra')

    # 将 MCP 日志级别转换为 Python 日志级别
    level = LOGGING_LEVEL_MAP.get(message.level.upper(), logging.INFO)

    # 使用标准日志记录库记录消息
    mcp_tool_logger.log(level, msg, extra=extra)

#创建 SSH 日志对象
logger = create_logger("ssh_mcp", "ssh_operations.log")

class SSHManager:
    """SSH连接管理器"""
    
    def __init__(self):
        self.connections: Dict[str, paramiko.SSHClient] = {}
    
    def get_connection_id(self, host: str, port: int, username: str) -> str:
        """生成连接ID"""
        return f"{username}@{host}:{port}"
    
    def connect(self, host: str, port: int = 22, username: str = 'root', 
                password: Optional[str] = None, key_file: Optional[str] = None,
                timeout: int = 30) -> paramiko.SSHClient:
        """建立SSH连接
        
        Args:
            host: 主机地址
            port: SSH端口
            username: 用户名
            password: 密码（可选）
            key_file: 密钥文件路径（可选）
            timeout: 连接超时时间（秒）
            
        Returns:
            SSH客户端对象
        """
        connection_id = self.get_connection_id(host, port, username)
        
        # 检查连接是否已存在
        if connection_id in self.connections:
            client = self.connections[connection_id]
            if client.get_transport() and client.get_transport().is_active():
                logger.info(f"使用现有连接: {connection_id}")
                return client
            else:
                # 连接已关闭，删除并重新连接
                del self.connections[connection_id]
        
        try:
            logger.info(f"建立新连接: {connection_id}")
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 根据认证方式连接
            if key_file and os.path.exists(key_file):
                logger.info(f"使用密钥文件认证: {key_file}")
                client.connect(
                    hostname=host,
                    port=port,
                    username=username,
                    key_filename=key_file,
                    timeout=timeout
                )
            else:
                logger.info("使用密码认证")
                client.connect(
                    hostname=host,
                    port=port,
                    username=username,
                    password=password,
                    timeout=timeout
                )
            
            # 保存连接
            self.connections[connection_id] = client
            logger.info(f"连接成功: {connection_id}")
            return client
            
        except paramiko.AuthenticationException:
            logger.error(f"认证失败: {connection_id}")
            raise Exception(f"SSH认证失败: 用户名或密码/密钥错误")
        except paramiko.SSHException as e:
            logger.error(f"SSH连接失败: {str(e)}")
            raise Exception(f"SSH连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"连接失败: {str(e)}")
            raise Exception(f"连接失败: {str(e)}")
    
    def execute_command(self, client: paramiko.SSHClient, command: str, 
                       timeout: int = 60) -> Dict[str, Any]:
        """执行SSH命令
        
        Args:
            client: SSH客户端对象
            command: 要执行的命令
            timeout: 命令执行超时时间（秒）
            
        Returns:
            包含执行结果的字典
        """
        try:
            logger.info(f"执行命令: {command}")
            start_time = time.time()
            
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            stdout_content = stdout.read().decode('utf-8')
            stderr_content = stderr.read().decode('utf-8')
            exit_status = stdout.channel.recv_exit_status()
            
            execution_time = time.time() - start_time
            logger.info(f"命令执行完成，用时: {execution_time:.2f}秒，退出状态: {exit_status}")
            
            return {
                'stdout': stdout_content,
                'stderr': stderr_content,
                'exit_status': exit_status,
                'execution_time': execution_time
            }
            
        except paramiko.SSHException as e:
            logger.error(f"命令执行失败: {str(e)}")
            raise Exception(f"命令执行失败: {str(e)}")
        except Exception as e:
            logger.error(f"执行命令时出错: {str(e)}")
            raise Exception(f"执行命令时出错: {str(e)}")
    
    def close_connection(self, host: str, port: int = 22, username: str = 'root'):
        """关闭SSH连接
        
        Args:
            host: 主机地址
            port: SSH端口
            username: 用户名
        """
        connection_id = self.get_connection_id(host, port, username)
        if connection_id in self.connections:
            try:
                client = self.connections[connection_id]
                client.close()
                del self.connections[connection_id]
                logger.info(f"连接已关闭: {connection_id}")
            except Exception as e:
                logger.error(f"关闭连接时出错: {str(e)}")
    
    def close_all_connections(self):
        """关闭所有SSH连接"""
        for connection_id, client in list(self.connections.items()):
            try:
                client.close()
                logger.info(f"连接已关闭: {connection_id}")
            except Exception as e:
                logger.error(f"关闭连接时出错: {str(e)}")
        self.connections.clear()

# 创建FastMCP实例
mcp = FastMCP("ssh_tool")

#============================
#@prompt 装饰器
#============================
@mcp.prompt(
    description="提供解决巡检交换机设备并且分析巡检结果然后查看交换机的端口流量的步骤"
)
def inspection_Huaweiswitch__and_read_logs_step():
    return f"""
    你是一个网络运维巡检助手。
    当需要获取数据时必须调用工具。
    不要自己生成数据。
    必须使用以下工具：
    get_all_switch_config
    read_inspection_logs
    get_switch_interface_traffic

    任务：
    巡检交换机设备并且分析巡检结果然后查看交换机的端口流量

    请完成以下步骤：

    1 执行 get_all_switch_config 等待结果返回
    2 get_all_switch_config返回结果使用read_inspection_logs查看文件
    3 分析日志文件
    4 执行 get_switch_interface_traffic 等待结果
    5 最终分析接口流量

    可用工具：

    get_all_switch_config
    read_inspection_logs
    get_switch_interface_traffic

    输出：
    1 巡检结果
    3 分析巡检结果
    4 分析交换机端口流量
    """

@mcp.prompt(
    description="提供服务器的服务出现异常的执行步骤"
)
def check_service_status_and_restart_the_service_step():
    return f"""
    你是一个网络运维巡检助手。
    当需要获取数据时必须调用工具。
    不要自己生成数据。

    必须按照以下思路进行:
    查看服务器的服务情况，然后分析日志并且重启服务

    必须使用以下工具:
    linux_ssh_execute_command
    ssh_read_file
    linux_ssh_execute_command
    
    使用 systemctl 命令要使用sudo 
    
    任务：
    巡检交换机设备并且分析巡检结果然后查看交换机的端口流量

    请完成以下步骤：

    1 使用 linux_ssh_execute_command 查看服务的运行情况
    2 使用 ssh_read_file 查看服务日志分析错误日志
    3 使用 linux_ssh_execute_command(command= "sudo systemctl restart vsftpd") 重启服务
    4 最终输出巡检报告

    可用工具：

    ssh_read_file
    linux_ssh_execute_command

    输出：
    1 分析步骤
    2 工具调用
    3 重启服务
    4 查看服务
    """

# 创建SSH管理器实例
ssh_manager = SSHManager()
#======================================
#交换机设备接口流量监控相关函数
#======================================

@mcp.tool(
    name="get_all_switch_config",
    description='完成对全部交换机路由器等网络设备的自动巡检配置情况,执行方法没有参数'
)
def audo_inspection():
    """完成对全部交换机路由器等网络设备的自动巡检配置情况"""
    result = batch_equipment_inspection()
    return result

async def batch_equipment_inspection():
    """
    完成对全部交换机路由器等网络设备的自动巡检
    """
    try:
        mcp_tool_logger.info("执行工具 get_all_switch_config")
        async with httpx.AsyncClient(timeout=45) as client:
            # 1. 登录
            payload = {"username": "admin", "password": "admin123"}
            r = await client.post(
                "http://10.0.147.101/api/login",
                json=payload
            )
            r.raise_for_status()

            # 2. 获取设备列表
            r = await client.get("http://10.0.147.101/api/devices")
            r.raise_for_status()

            devices = r.json()
            device_ids = [i["id"] for i in devices]

            if not device_ids:
                return {"msg": "未发现设备"}

            # 3. 批量巡检
            payload = {"device_ids": device_ids}
            r = await client.post(
                "http://10.0.147.101/api/devices/batch-inspect",
                json=payload
            )
            r.raise_for_status()
            mcp_tool_logger.info("成功批量巡检")
            return r.json()

    except Exception as e:
        mcp_tool_logger.info(f"工具 get_all_switch_config 执行失败:{e}")
        return {
            "error": str(e)
        }


@mcp.tool(
    name="get_switch_interface_traffic",
    description="获取交换机接口的流量监控数据;interface_index是一个列表,元素范围1到24，比如：['1','2','3'] 接口格式：Interface GigabitEthernet0/0/interface_index"
)
def get_switch_interface_traffic(interface_list: list = ['1'])->list[Any]:
    """通过API获取交换机接口的流量监控数据
    接口格式：Interface GigabitEthernet0/0/{interface_index}

    Args:
        interface_index:list 是列表元素为字符串数字，表示接口的最后一段编号，默认是'1'
        
    """
    try:
        result_list = []
        for interface_index in interface_list:
            result = (zabbix_api.main("SW1",interface_index))
            if result != None:
                mcp_tool_logger.info(f"获取接口G0/0/{interface_index}的流量成功")
                result_list.append(result)
            else:
                mcp_tool_logger.info(f"获取接口G0/0/{interface_index}的流量失败")
                result_list.append(f"获取接口G0/0/{interface_index}的流量失败")
        return result_list
    except Exception as e:
        mcp_tool_logger.info(f"获取接口G0/0/{interface_index}的流量失败\n({str(e)})")
        return {"error":e}
        

@mcp.tool(
    name="set_switch_interface_traffic",
    description="设置交换机接口G0/0/10的流量,Options (str):选择的流控配置选项有3个选项,'1':(bandwidth 1000000 );'2':(bandwidth 500000);'3':(bandwidth 100000)"
)
def set_switch_interface_traffice(Options:str='1')->Dict[str,Any]:
    """完成对交换机接口10的流量控制,有1到3个挡位,Options (str):选择的流控配置选项有3个选项,'1':(bandwidth 1000000 );'2':(bandwidth 500000);'3':(bandwidth 100000)
    
    Args:
        Options (str):选择的流控配置选项有3个选项,1(bandwidth 1000000 );2(bandwidth 500000);3(bandwidth 100000)
        host: 主机地址 = 10.0.147.254
        port: SSH端口 = 22
        username: 用户名 = admin    
        password: 密码（可选）= huawei@123
    Returns:
        执行结果
    """
    try:
        # 建立连接
        client = ssh_manager.connect(
            host='10.0.147.254',
            port='22',
            username='admin',
            password='huawei@123'
        )
        match Options:
            case '1':
                command = """
                    sys
                    interface  GigabitEthernet 0/0/10
                    bandwidth 1000000 
                    dis this
                """
                result = ssh_manager.execute_command(client, command, timeout=30)
                if result['exit_status'] == -1:
                    return {'stdout': result['stdout'],
                            'stderr': result['stderr']}
                mcp_tool_logger.info(f"设置接口G0/0/10的流量控制成功")
                return {'stdout': result['stdout'],
                        'stderr': result['stderr']}
            case '2':
                command = """
                    sys
                    interface  GigabitEthernet 0/0/10
                    bandwidth 500000
                    dis this 
                """
                result = ssh_manager.execute_command(client, command, timeout=30)
                if result['exit_status'] == -1:
                    return {'stdout': result['stdout'],
                            'stderr': result['stderr']}
                mcp_tool_logger.info(f"设置接口G0/0/10的流量控制成功")
                return {'stdout': result['stdout'],
                        'stderr': result['stderr']}
            case '3':
                command = """
                    sys
                    interface  GigabitEthernet 0/0/10
                    bandwidth 100000
                    dis this 
                """
                result = ssh_manager.execute_command(client, command, timeout=30)
                if result['exit_status'] == -1:
                    return {'stdout': result['stdout'],
                            'stderr': result['stderr']}
                mcp_tool_logger.info(f"设置接口G0/0/10的流量控制成功")
                return {'stdout': result['stdout'],
                        'stderr': result['stderr']}
        #关闭连接
        ssh_close_connection('host', '22', 'huawei')
        
    except Exception as e:
        mcp_tool_logger.error(f"执行命令时出错: {str(e)}")
        return {'success': False, 'error': str(e)}
#===========================    
#linux ssh
#========================
@mcp.tool(
    name="ssh_read_file",
    description = "读取服务器的文件"
)
def ssh_read_file(host: str, port: int = 22, username: str = 'root', 
                        password: Optional[str] = None,file_path: str = '', timeout: int = 60) -> Dict[str, Any]:
    """通过SSH读取远程服务器文件内容
    
    Args:
        host: 主机地址
        port: SSH端口
        username: 用户名
        password: 密码（可选）
        file_path: 文件路径
        
    Returns:
        包含文件内容的字典
    """
    try:
        mcp_tool_logger.info("执行工具 read_file")
        # 验证参数
        if not file_path:
            return {'success': False, 'error': '文件路径不能为空'}
        
        # 建立连接
        client = ssh_manager.connect(
            host=host,
            port=port,
            username=username,
            password=password
        )
        
        # 检查文件是否存在
        check_command = f"ls -la '{file_path}'"
        check_result = ssh_manager.execute_command(client, check_command)
        
        if check_result['exit_status'] != 0:
            return {
                'success': False,
                'error': f'文件不存在或无法访问: {file_path}'
            }
        
        # 读取文件内容
        read_command = f"tail -n 100 '{file_path}'"
        read_result = ssh_manager.execute_command(client, read_command)
        
        if read_result['exit_status'] != 0:
            return {
                'success': False,
                'error': f'读取文件失败: {read_result["stderr"]}'
            }
        
        mcp_tool_logger.info(f"文件读取成功: {file_path}")
        ssh_close_connection(host, port, username)
        return {
            'success': True,
            'file_path': file_path,
            'content': read_result['stdout']
        }
        
    except Exception as e:
        mcp_tool_logger.error(f"读取文件时出错: {str(e)}")
        return {'success': False, 'error': str(e)}
    
@mcp.tool(name = "ssh_create_OR_write_file")
def ssh_create_OR_write_file(host: str, port: int = 22, username: str = 'root', 
                   password: Optional[str] = None,file_path: str = '', content: str = '', permissions: str = '644') -> Dict[str, Any]:
    """通过SSH在远程服务器创建文件
    
    Args:
        host: 主机地址
        port: SSH端口
        username: 用户名
        password: 密码（可选）
        file_path: 文件路径
        content: 文件内容
        permissions: 文件权限（如 '644'）
        
    Returns:
        执行结果
    """
    try:
        mcp_tool_logger.info("执行工具： ssh_create_OR_write_file")
        # 验证参数
        if not file_path:
            return {'success': False, 'error': '文件路径不能为空'}
        
        # 建立连接
        client = ssh_manager.connect(
            host=host,
            port=port,
            username=username,
            password=password
        )
        
        # 创建文件或写入内容
        check_file_content = ssh_manager.execute_command(client, f"test -f '{file_path}' && echo 'File exists' || echo 'File does not exist'")
        file_exists = check_file_content['stdout'].strip() == 'File exists'
        if file_exists:
            # 文件已存在，写入内容
            if not content:
                return {'success': False, 'error': '文件内容不能为空'}
        command = f"cat > '{file_path}' << 'EOF'\n{content}\nEOF"
        result = ssh_manager.execute_command(client, command)
        
        if result['exit_status'] != 0:
            return {
                'success': False,
                'error': f'创建文件失败: {result["stderr"]}'
            }
        
        # 设置文件权限
        if permissions:
            chmod_command = f"chmod {permissions} '{file_path}'"
            chmod_result = ssh_manager.execute_command(client, chmod_command)
            if chmod_result['exit_status'] != 0:
                logger.warning(f"设置权限失败: {chmod_result['stderr']}")
        
        mcp_tool_logger.info(f"文件创建成功: {file_path}")
        ssh_close_connection(host, port, username)
        return {
            'success': True,
            'message': f'文件创建成功: {file_path}',
            'file_path': file_path,
            'permissions': permissions
        }
        
    except Exception as e:
        mcp_tool_logger.error(f"创建文件时出错: {str(e)}")
        return {'success': False, 'error': str(e)}
    

@mcp.tool()
def ssh_edit_file(host: str, port: int = 22, username: str = 'root', 
                   password: Optional[str] = None, key_file: Optional[str] = None,
                   file_path: str = '', content: str = ''):
    """通过SSH在远程服务器编辑文件

        Args:
        host: 主机地址
        port: SSH端口
        username: 用户名
        password: 密码（可选）
        key_file: 密钥文件路径（可选）
        file_path: 文件路径
        
    Returns:
        修改文件成功后的内容
    """
    try:
        # 验证参数
        if not file_path:
            return {'success': False, 'error': '文件路径不能为空'}
        if content is None:
            return {'success': False, 'error': '文件内容不能为空'}
        
        # 建立连接
        client = ssh_manager.connect(
            host=host,
            port=port,
            username=username,
            password=password,
            key_file=key_file
        )
        
        # 创建文件并写入内容
        command = f"cat > '{file_path}' << 'EOF'\n{content}\nEOF"

        backup_file = ssh_manager.execute_command(client, f"cp '{file_path}' '{file_path}.bak'")
        if backup_file['exit_status'] != 0:
            logger.warning(f"备份文件失败: {backup_file['stderr']}")
            return {
                'success': False,
                'error': f'备份文件失败: {backup_file["stderr"]}'
            }
        
        result = ssh_manager.execute_command(client, command)
        
        if result['exit_status'] != 0:
            return {
                'success': False,
                'error': f'编辑文件失败: {result["stderr"]}'
            }
        
        mcp_tool_logger.info(f"文件编辑成功: {file_path}")
        ssh_close_connection(host, port, username)
        return {
            'success': True,
            'message': f'文件编辑成功: {file_path}',
            'file_path': file_path,
            'content': content
        }
        
    except Exception as e:
        mcp_tool_logger.error(f"编辑文件时出错: {str(e)}")
        return {'success': False, 'error': str(e)}

@mcp.tool(
    name="linux_ssh_systemctl_restart",
    description="服务器可以使用命令 systemctl restart service "
)
def systemctl_restart(host: str, port: int = 22, username: str = 'root', 
                        password: Optional[str] = None, key_file: Optional[str] = None,
                        service: str = '', timeout: int = 60) -> Dict[str, Any]:
    """linux服务器可以使用命令 systemctl restart
    
    Args:
        host: 主机地址
        port: SSH端口
        username: 用户名
        password: 密码（可选）
        key_file: 密钥文件路径（可选）
        service: 服务名称
        timeout: 执行超时时间（秒）
        
    Returns:
        执行结果
    """
    try:
        command = f"sudo systemctl restart {service}"
        # 建立连接
        client = ssh_manager.connect(
            host=host,
            port=port,
            username=username,
            password=password,
            key_file=key_file
        )
        
        # 执行命令
        result = ssh_manager.execute_command(client, command, timeout=timeout)
        mcp_tool_logger.info(f"{service}服务重启成功: {command}")
        #关闭连接
        ssh_close_connection(host, port, username)
        return {
            'command': command,
            'stdout': result['stdout'],
            'stderr': result['stderr']
        }
        
    except Exception as e:
        mcp_tool_logger.error(f"服务重启失败: {str(e)}")
        return {'success': False, 'error': str(e)}

@mcp.tool(
    name="linux_ssh_execute_command",
    description="仅linux服务器可以使用SSH执行命令,禁止执行交互式命令(vim echo cat ,more,stop 等等)"
)
def ssh_execute_command(host: str, port: int = 22, username: str = 'root', 
                        password: Optional[str] = None,command: str = '', timeout: int = 60) -> Dict[str, Any]:
    """仅linux服务器通过SSH执行命令,禁止执行交互式命令(vim echo cat ,more 等等)
    
    Args:
        host: 主机地址
        port: SSH端口
        username: 用户名
        password: 密码（可选）
        command: 要执行的命令
        timeout: 执行超时时间（秒）
        
    Returns:
        执行结果
    """
    try:
        mcp_tool_logger.info("执行工具 linux_ssh_execute_command")
        # mcp_tool_logger.info(f"function_call:{host:{host},user:{username},password:{password},command:{command}}\n")
        from black_exec import dangerous_commands
        if not command:
            return {'success': False, 'error': '命令不能为空'}
        if any(interactive_cmd in command for interactive_cmd in dangerous_commands):
            return {'success': False, 'error': '禁止执行危险命令'}
        # 建立连接
        client = ssh_manager.connect(
            host=host,
            port=port,
            username=username,
            password=password,
        )
        
        # 执行命令
        if command in ("systemctl restart nginx" , "systemctl start nginx","sudo systemctl start nginx","sudo systemctl restart nginx"):
            command = "sudo systemctl restart nginx"
        
        result = ssh_manager.execute_command(client, command, timeout=timeout)
        mcp_tool_logger.info("执行工具 linux_ssh_execute_command")
        mcp_tool_logger.info(f"命令执行完成: {command}\n")
        mcp_tool_logger.info(f"'stdoutput': {result['stdout']},'stderr': {result['stderr']}\n\n")
        #关闭连接
        ssh_close_connection(host, port, username)
        return {
            'command': command,
            'stdout': result['stdout'],
            'stderr': result['stderr']
        }
        
    except Exception as e:
        mcp_tool_logger.error(f"执行{command}命令时出错: {str(e)}")
        return {'success': False, 'error': str(e)}


def ssh_close_connection(host: str, port: int = 22, username: str = 'root') -> Dict[str, Any]:
    """关闭SSH连接
    
    Args:
        host: 主机地址
        port: SSH端口
        username: 用户名
        
    Returns:
        操作结果
    """
    try:
        ssh_manager.close_connection(host, port, username)
        return {'success': True, 'message': '连接已关闭'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@mcp.tool(
        name = "get_remote_folder_all_filename",
        description = "获取远程主机的文件夹下有哪些文件"
)
def get_remote_folder_all_filename(host: str, port: int = 22, username: str = 'root', 
                  password: Optional[str] = None, key_file: Optional[str] = None,
                  file_path: str = '') -> Dict[str, Any]:
    """
    获取文件夹下有哪些文件

     Args:
        host: 主机地址
        port: SSH端口
        username: 用户名
        password: 密码（可选）
        key_file: 密钥文件路径（可选）
        file_path: 要读取的文件路径
    Returns:
        包含文件内容的字典
    """
    try:
        mcp_tool_logger.info("执行工具：get_folder_all_filename ")
        # 建立连接
        client = ssh_manager.connect(
            host=host,
            port=port,
            username=username,
            password=password,
            key_file=key_file
        )
        
        # 执行命令
        cmd = f'ls -a {file_path}'
        result = ssh_manager.execute_command(client,cmd)
        if result['exit_status'] != 0:
            return {
                'success': False,
                'error': f'查看文件夹失败: {result["stderr"]}'
            }
        mcp_tool_logger.info(f"查看文件夹: {file_path}")
        #关闭连接
        ssh_close_connection(host, port, username)
        return {
            'success': True,
            "current path": file_path,
            'stdout': result['stdout'],
            'stderr': result['stderr'],
        }
        
    except Exception as e:
        mcp_tool_logger.error(f"读取文件时出错: {str(e)}")
        return {'success': False, 'error': str(e)}



@mcp.tool()
def ssh_close_all_connections() -> Dict[str, Any]:
    """关闭所有SSH连接
    
    Returns:
        操作结果
    """
    try:
        ssh_manager.close_all_connections()
        return {'success': True, 'message': '所有连接已关闭'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# #=================
# #mcp服务器的管理
# #=================
# local_file_path = './file_tmp/'
# # 创建单个文件
# @mcp.tool()
# def create_file(a:str):
#     '''MCP服务器本机创建文件的需要带有后缀名'''
#     if os.path.exists(local_file_path+a):
#         return False
#     else:
#         open(local_file_path+a,"w").close()
#         return True 
    
# #创建多个文件
# @mcp.tool()
# def create_more_file(name:list):
#     '''MCP服务器本机创建多个文件,以python的列表形式存储文件名称为参数'''
#     for i in name:
#         if os.path.exists(local_file_path+i):
#             continue
#         else:
#             open(local_file_path+i,'w').close()  
#     return True

# #写入文件内容
# @mcp.tool()
# def write_file(filename, content=''):
#     """MCP服务器本机写入文件内容,filename参数是文件名称带后缀,content参数是写入内容"""
#     with open(local_file_path+filename, 'w') as f:
#         f.write(content)
#         return True

# #获取当前目录下的全部文件和文件夹    
@mcp.tool(name = "get_inspection_folder_logs",
          description="获取巡检目录下的全部文件名称,方法没有参数"
          )
def get_inspection_folder():
    '''MCP服务器本机获取当前目录下的全部文件和文件夹 
    
        Args:
            None
        Returns:
        list
    '''
    # 获取当前目录
    current_dir = Path('/var/log/huawei_xunjian/')
    # 获取所有文件和文件夹
    all_items = list(current_dir.iterdir())
    logger.info("查看目录下文件命令执行完成")
    return {"files_list":all_items}

#读取文件内容
@mcp.tool(
        name = "read_inspection_logs",
        description="查看巡检设备的日志，参数是文件路径,参数为文件的路径,结果返回文件的内容"
)
def read_inspection_file(filepath:str):
    '''MCP服务器本机读取设备巡检文件内容

    Args:
        filepath: 文件名及路径
    Returns:
        返回文件内容
    '''
    
    if os.path.exists(filepath):
        with open(filepath,'r') as f:
            content =  f.read()
            f.close()
        logger.info(f"读取文件内容命令执行完成")
        return {"file_content":content}
    return {'error':"文件不存在"}

# #下载文件
# @mcp.tool()
# def download_file(url:str,filename:str):
#     """MCP服务器本机下载文件,参数为url下载地址;文件名称带后缀"""
#     if filename == '':
#         filename = url.split('/')[-1]
#         result = subprocess.run(['curl','-o','./file_tmp/'+filename,url], capture_output=True, text=True)
#         return [True,result.stdout]
#     else:
#         result = subprocess.run(['curl','-o','./file_tmp/'+filename,url], capture_output=True, text=True)
#         return [True,result.stdout] 
        
# #centos 系统状况查看
# @mcp.tool()
# def check_servies_status(service_name:str):
#     '''MCP服务器本机查看系统服务运行状态

#         agre:
#         service_name : str 服务名称
#     '''
#     result = subprocess.run(['systemctl','status',service_name], capture_output=True, text=True)
#     return result

# #centos 查看服务运行日志
# @mcp.tool()
# def check_servies_log(path:str):
#     """MCP服务器本机查看系统服务的运行日志，日志目录已经在 /var/log/"""
#     result = subprocess.run(['cat',f"/var/log/{path}"], capture_output=True, text=True)
#     return result



if __name__ == "__main__":
    mcp_server =  mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=4204,
        path="/ssh",
        log_level="debug"
    )
    client = Client(
    mcp_server,
    log_handler=log_handler,
    )