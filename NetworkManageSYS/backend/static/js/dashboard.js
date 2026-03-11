let cpuChart = echarts.init(document.getElementById("cpuChart"));
let memChart = echarts.init(document.getElementById("memChart"));
let diskChart = echarts.init(document.getElementById("diskChart"));

function gaugeOption(title, value) {
    return {
        series: [{
            type: 'gauge',
            min: 0,
            max: 100,
            progress: { show: true },
            detail: {
                valueAnimation: true,
                formatter: '{value}%',
                color: '#38bdf8'
            },
            axisLine: {
                lineStyle: {
                    width: 10,
                    color: [[0.7, '#22c55e'], [0.9, '#facc15'], [1, '#ef4444']]
                }
            },
            data: [{ value: value, name: title }]
        }]
    }
}

function renderCharts(data) {
    cpuChart.setOption(gaugeOption('CPU', data.cpu));
    memChart.setOption(gaugeOption('内存', data.memory));
    diskChart.setOption(gaugeOption('磁盘', data.disk));
}

/* === 本机监控 === */
async function loadLocalStatus() {
    const res = await fetch("/api/monitor/local");
    const data = await res.json();
    renderCharts(data);
}

/* === Zabbix === */
async function loadZabbix() {
    const res = await fetch("/api/zabbix/hosts");
    const data = await res.json();

    let html = `
        <h2>Zabbix 主机状态</h2>
        <table class="table">
            <tr>
                <th>主机名</th>
                <th>IP</th>
                <th>CPU</th>
                <th>内存</th>
                <th>状态</th>
            </tr>
    `;

    data.forEach(h => {
        html += `
            <tr>
                <td>${h.name}</td>
                <td>${h.ip}</td>
                <td>${h.cpu}%</td>
                <td>${h.memory}%</td>
                <td>${h.status}</td>
            </tr>
        `;
    });

    html += "</table>";
    document.getElementById("tableArea").innerHTML = html;
}

/* === 页面管理 === */
function showPage(type) {
    // 1️⃣ 所有页面隐藏
    document.querySelectorAll('.page').forEach(p => {
        p.style.display = 'none';
    });

    // 2️⃣ 左侧菜单状态
    document.querySelectorAll('.sidebar ul li').forEach(li => {
        li.classList.remove('active');
    });

    // 3️⃣ 根据类型显示
    if (type === 'local') {
        document.getElementById('log_info_page').style.display = 'flex';
        document.querySelectorAll('.sidebar ul li')[0].classList.add('active');
    }

    if (type === 'zabbix') {
        document.getElementById('zabbixPage').style.display = 'flex';
        document.querySelectorAll('.sidebar ul li')[1].classList.add('active');
        loadZabbix(); // 可选
    }

    if (type === 'user') {
        document.getElementById('userPage').style.display = 'block';
        document.querySelectorAll('.sidebar ul li')[2].classList.add('active');
        loadUsers(); // 可选
    }
}
let currentUser = ''
async function checkAuthStatus() {
    try {
        const response = await fetch('/api/auth/check');
        const data = await response.json();
        
        if (data.authenticated) {
            isAuthenticated = true;
            currentUser = data.user;
            showUserInterface();
        } else {
            isAuthenticated = false;
            currentUser = null;
            showAuthInterface();
        }
    } catch (error) {
        console.error('检查认证状态失败:', error);
        isAuthenticated = false;
        showAuthInterface();
    }
}
// 显示用户界面（登录后）
function showUserInterface() {
    document.getElementById('userActions').style.display = 'flex';
    document.getElementById('currentUsername').textContent = currentUser.username;
    
}

/* === 用户管理 === */
async function loadUsers() {
    const res = await fetch("/api/getusers");
    const users = await res.json();
    let html = ""

    users.forEach(u => {

        html += `
            <tr>
                <td><input type="checkbox" name="id[]" value="${u.id}"></td>
                <td>${u.username}</td>
                <td>${u.email}</td>
                <td>${u.role ==1 ? "管理员": "普通用户"}</td>
                <td>${u.create_time}</td>
                
                <td>
                <a href="#editEmployeeModal" class="edit" data-toggle="modal">
                <button onclick="editUser('${u.id}')" class="btn btn-sm btn-primary">编辑</button>
                </a>
                    <a href="#deleteEmployeeModal" class="delete" data-toggle="modal">
                    <button onclick="deleteUser('${u.id}')" class="btn btn-sm btn-danger">删除</button>
                    </a>
                </td>
            </tr>
        `;
    });

    html += "</table>";
    document.getElementById("userTable").innerHTML = html;
}

// 用户登出
async function logout() {
    if (!confirm('确定要退出登录吗？')) {
        return;
    }
    
    try {
        // 先断开SSH连接
        if (isConnected) {
            disconnect();
        }
        
        const response = await fetch('/api/logout', {
            method: 'POST'
        });
        
        if (response.ok) {
            isAuthenticated = false;
            currentUser = null;
            // showAuthInterface();
            // 确定是否退出登录
            window.location.href = '/login';
            
        } else {
            alert('退出登录失败');
        }
    } catch (error) {
        // console.error('退出登录失败:', error);
        alert('退出登录失败，请稍后重试');
    }
}

// 用户界面样式
$(document).ready(function(){
	// Activate tooltip
	$('[data-toggle="tooltip"]').tooltip();
	
	// Select/Deselect checkboxes
	var checkbox = $('table tbody input[type="checkbox"]');
	$("#selectAll").click(function(){
		if(this.checked){
			checkbox.each(function(){
				this.checked = true;                        
			});
		} else{
			checkbox.each(function(){
				this.checked = false;                        
			});
		} 
	});
	checkbox.click(function(){
		if(!this.checked){
			$("#selectAll").prop("checked", false);
		}
	});
});


function editUser(id) {
    // 获取用户信息并填充到表单中
    fetch(`/api/users/${id}`)
        .then(res => res.json())
        .then(user => {
            document.getElementById('editUserId').value = user.id;
            document.getElementById('editUsername').value = user.username;
            document.getElementById('editEmail').value = user.email;
            document.getElementById('editRole').value = user.role;
        });
}

function deleteUser(id) {
    fetch(`/api/users/${id}`, { method: "DELETE" })
        .then(() => loadUsers());
}

let socket;
let allLogs = [];
let filteredLogs = [];
let isPaused = false;
let currentFilter = 'all';
let currentSearch = '';

// 连接状态
let isConnected = false;

// 初始化WebSocket连接
function initWebSocket() {
    // 获取当前主机和端口
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const port = window.location.port || (protocol === 'wss:' ? 443 : 80);
    const wsUrl = `${protocol}//${host}:${port}`;
    
    console.log('连接WebSocket:', wsUrl);
    
    // 连接Socket.IO
    socket = io(wsUrl, {
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000
    });
    
    // 连接成功
    socket.on('connect', function() {
        console.log('WebSocket连接成功');
    });
    
    // 接收新日志
    socket.on('new_log', function(log) {
        if (!isPaused) {
            addLog(log);
        }
    });
    
    // 连接断开
    socket.on('disconnect', function() {
        console.log('WebSocket连接断开');
    });
    
    // 连接错误
    socket.on('connect_error', function(error) {
        console.error('连接错误:', error);

    });
}


// 添加日志到列表
function addLog(log) {
    // 添加到所有日志数组
    allLogs.unshift(log); // 新日志添加到开头
    // 隐藏空状态
    document.getElementById('empty-state').style.display = 'none';
    renderLogs();
}

// 渲染日志列表
function renderLogs() {
    const logList = document.getElementById('log-list');
    
    // 移除现有条目（除了空状态）
    const existingEntries = logList.querySelectorAll('.log-entry');
    existingEntries.forEach(entry => entry.remove());
    
    // 添加新条目
    allLogs.forEach(log => {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        
        // 设置级别对应的CSS类
        const levelClass = `level-${log.level.toLowerCase()}`;
        
        entry.innerHTML = `
            <div class="timestamp">${log.timestamp}</div>
            <div class="log-level ${levelClass}">${log.level}</div>
            <div class="log-message">${escapeHtml(log.message)}</div>
            <div class="logger-name">${log.logger || 'N/A'}</div>
            <div class="line-info">${log.filename}:${log.lineno || 'N/A'}</div>
        `;
        
        logList.appendChild(entry);
    });
    
    // 如果没有日志，显示空状态
    // if (allLogs.length > 0) {
    //     const emptyState = document.getElementById('empty-state');
    //     emptyState.innerHTML = `
    //         <i class="fas fa-search"></i>
    //         <h3>无匹配的日志</h3>
    //     `;
    //     emptyState.style.display = 'block';
    // }
}
 

$(document).ready(function(){
	// Activate tooltip
	$('[data-toggle="tooltip"]').tooltip();
	
	// Select/Deselect checkboxes
	var checkbox = $('table tbody input[type="checkbox"]');
	$("#selectAll").click(function(){
		if(this.checked){
			checkbox.each(function(){
				this.checked = true;                        
			});
		} else{
			checkbox.each(function(){
				this.checked = false;                        
			});
		} 
	});
	checkbox.click(function(){
		if(!this.checked){
			$("#selectAll").prop("checked", false);
		}
	});
});

function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

/* 定时刷新本机状态 */
document.addEventListener('DOMContentLoaded', function() {
            initWebSocket();
            updateHostList();
            // 初始显示空状态
            document.getElementById('empty-state').style.display = 'block';
            setInterval(loadLocalStatus, 5000);
            loadLocalStatus();
            checkAuthStatus();
            showPage('local');
        });

// zabbix 主机列表动态生成

async function updateHostList() {
            const hosts =  await generateHostData();
            const hostListEl = document.getElementById('hostList');
            hostListEl.innerHTML = '';
            
            hosts.forEach(host => {
                const hostEl = document.createElement('div');
                hostEl.className = `host-item ${host.status === 'problem' ? 'problem' : ''}`;
                
                hostEl.innerHTML = `
                    <div>
                        <div><strong>${host.name}</strong></div>
                        <div style="font-size: 0.9rem; color: #a0b9e0;">云数据中心 | 最后检查: ${host.lastCheck}</div>
                    </div>
                    <div>
                        <div class="host-status ${host.status === 'normal' ? 'status-normal' : 'status-problem'}">
                            ${host.status === 'normal' ? '正常' : '异常'}
                        </div>
                        <div style="font-size: 0.9rem; color: #a0b9e0; text-align: right;">运行: ${host.uptime}</div>
                    </div>
                `;
                
                hostListEl.appendChild(hostEl);
            });
        }

async function generateHostData() {
        try{
            const response = await fetch('/api/zabbix/hosts');
            const data = await response.json();
            const hosts = data.map((host, index) => ({
                id: index + 1,
                name: host.name,
                status: host.status,
                lastCheck: new Date().toLocaleTimeString(),
                uptime: host.runing ? `${host.runing}天` : '0天'
            }));
            return hosts;
        }catch(e){
            console.log(e)
        }
    }