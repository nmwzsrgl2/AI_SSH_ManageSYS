#!/usr/bin/env python3
"""
纯Flask Web SSH客户端启动脚本
解决所有依赖和版本兼容性问题
"""
import subprocess
import sys
import os

def main():
    print("🚀 Flask Web SSH 客户端启动工具")
    
    try:
        # 启动Flask应用
        #使用venv环境
        # os.chdir('backend')
        cmd = "source /root/NetworkManageSYS/linux_venv/.venv/bin/activate && python /root/NetworkManageSYS/backend/app.py"
        subprocess.run(cmd, shell=True, check=True, executable="/bin/bash")
    except KeyboardInterrupt:
        print("\n🛑 正在停止服务...")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

if __name__ == '__main__':
    main() 
