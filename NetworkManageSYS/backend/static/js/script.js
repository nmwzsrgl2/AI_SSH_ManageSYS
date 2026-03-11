// 全局变量
let socket = null;
let terminal = null;
let connections = [];
let isConnected = false;
let currentConnectionId = null;
let sidebarVisible = true;
let AisidebarVisible = true;
let currentUser = null;
let isAuthenticated = false;

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    // 先检查认证状态，然后初始化其他组件
    checkAuthStatus().then(() => {
        if (isAuthenticated) {
            initializeSocket();
            initializeTerminal();
            loadConnections();
        } else {
            initializeSocket();
            initializeTerminal();
            // 显示登录提示
            terminal.write('请先登录以使用SSH连接功能...\r\n');
        }
    });

    // 绑定事件监听器
    document.getElementById('connectionForm').addEventListener('submit', saveConnection);

    // 点击模态框背景关闭
    document.getElementById('newConnectionModal').addEventListener('click', function(e) {
        if (e.target === this) {
            // hideNewConnectionModal();
        }
    });
});

// 初始化Socket连接
let sshOutputHistory = '';
let ssh_host_ip = "";
// 命令输出
let commandOutputHistory = '';
function initializeSocket() {
    socket = io();

    socket.on('connect', function() {
        console.log('Socket连接成功');
    });

    socket.on('ssh_connected', function(data) {
        isConnected = true;
        updateConnectionStatus('已连接', true);
        updateTerminalTitle(data.connection_name || data.host, data.username, data.host);
        document.getElementById('disconnectBtn').classList.remove('hidden');
        ssh_host_ip = data.host;
        terminal.write('\r\n✅ 连接成功! 主机: ' + data.host + '\r\n');

        // 更新连接状态指示器
        if (currentConnectionId) {
            updateConnectionIndicator(currentConnectionId, true);
        }

        // 隐藏新建连接模态框
        hideNewConnectionModal();
    });
    
    socket.on('ssh_output', function(data) {
    // ✅ 这里前端获取到了 SSH 输出内容
    terminal.write(data.data); 
    }); 

    socket.on('ssh_error', function(data) {
        isConnected = false;
        updateConnectionStatus('连接错误: ' + data.error, false);
        terminal.write('\r\n❌ 错误: ' + data.error + '\r\n');

        // 显示故障排除提示
        if (data.error.includes('认证失败') || data.error.includes('Authentication failed')) {
            terminal.write('\r\n💡 故障排除提示:\r\n');
            terminal.write('1. 检查用户名和密码是否正确\r\n');
            terminal.write('2. 确认服务器允许密码认证\r\n');
            terminal.write('3. 尝试使用普通用户而不是root用户\r\n');
            terminal.write('4. 检查服务器SSH配置(/etc/ssh/sshd_config)\r\n');
            terminal.write('5. 如果服务器只允许密钥认证，请使用私钥方式\r\n');
        }
    });

    socket.on('ssh_disconnected', function() {
        isConnected = false;
        updateConnectionStatus('未连接', false);
        updateTerminalTitle('SSH 终端');
        document.getElementById('disconnectBtn').classList.add('hidden');
        terminal.write('\r\n🔌 连接已断开\r\n');

        // 更新连接状态指示器
        if (currentConnectionId) {
            updateConnectionIndicator(currentConnectionId, false);
            currentConnectionId = null;
        }

        // 清除活跃状态
        document.querySelectorAll('.connection-item.active').forEach(item => {
            item.classList.remove('active');
        });
    });
}
// 重新计算terminal的 宽度和高度并且发送socket 后端修改
const fitAddon = new FitAddon.FitAddon();
const resizeTerminal = function resizeTerminal(){
    fitAddon.fit()
    const cols = terminal.cols
    const rows = terminal.rows
    // console.log("terminal resize:",cols,rows)
    terminal.resize(cols, rows)
    socket.emit("resize",{
        cols:cols,
        rows:rows
    })
}
// 初始化终端
function initializeTerminal() {
    terminal = new Terminal({
        cursorBlink:true,
        theme:{
            background:"#000000",
            foreground:"#ffffff"
        }
    });
    terminal.loadAddon(fitAddon);
    terminal.open(document.getElementById('terminal'));
    terminal.write('Web SSH 客户端已就绪，请建立连接...\r\n');
    // 自动计算大小
    resizeTerminal()
    // 监听键盘输入
    terminal.onData(function(data) {
        if (isConnected) {
            socket.emit('ssh_command', data );
        }
    });
}

// 加载已保存的连接
function loadConnections() {
    fetch('/api/connections')
        .then(response => response.json())
        .then(data => {
            connections = data;
            renderConnectionsList();
        })
        .catch(error => console.error('加载连接失败:', error));
}

// 渲染连接列表
function renderConnectionsList() {
    const listElement = document.getElementById('connectionsList');
    if (connections.length === 0) {
        listElement.innerHTML = `
            <div class="empty-connections">
                <div class="icon">📁</div>
                <p>暂无SSH连接</p>
                <p>点击"新建连接"创建第一个SSH连接</p>
            </div>
        `;
        return;
    }

    listElement.innerHTML = connections.map(conn => `
        <div class="connection-item" onclick="connectSaved(${conn.id})" oncontextmenu="showConnectionMenu(event, ${conn.id})">
            <div class="connection-info">
                <div class="connection-name">${conn.name}</div>
                <div class="connection-details">${conn.username}@${conn.host}:${conn.port}</div>
            </div>
            <div class="connection-status-indicator" id="indicator-${conn.id}"></div>
        </div>
    `).join('');
}

// 切换认证方式
function toggleAuthMethod() {
    const authMethod = document.querySelector('input[name="authMethod"]:checked').value;
    const passwordAuth = document.getElementById('passwordAuth');
    const keyAuth = document.getElementById('keyAuth');

    if (authMethod === 'password') {
        passwordAuth.classList.remove('hidden');
        keyAuth.classList.add('hidden');
    } else {
        passwordAuth.classList.add('hidden');
        keyAuth.classList.remove('hidden');
    }
}

// 调整端口号
function adjustPort(delta) {
    const portInput = document.getElementById('port');
    let currentPort = parseInt(portInput.value) || 22;
    let newPort = currentPort + delta;

    if (newPort < 1) newPort = 1;
    if (newPort > 65535) newPort = 65535;

    portInput.value = newPort;
}

// 切换密码可见性
function togglePasswordVisibility() {
    const passwordInput = document.getElementById('password');
    const eyeIcon = document.querySelector('.eye-icon');

    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        eyeIcon.textContent = '🙈';
    } else {
        passwordInput.type = 'password';
        eyeIcon.textContent = '👁';
    }
}

// 测试连接
function testConnection() {
    const authMethod = document.querySelector('input[name="authMethod"]:checked').value;
    const connectionData = {
        host: document.getElementById('host').value,
        port: parseInt(document.getElementById('port').value),
        username: document.getElementById('username').value,
        password: authMethod === 'password' ? document.getElementById('password').value : '',
        private_key: authMethod === 'key' ? document.getElementById('privateKey').value : ''
    };

    if (!connectionData.host || !connectionData.username) {
        showInputError('hostError', '请填写主机地址和用户名');
        return;
    }

    const testBtn = document.querySelector('.btn-test');
    const originalText = testBtn.textContent;
    testBtn.textContent = '测试中...';
    testBtn.disabled = true;

    // 调用后端测试连接API
    fetch('/api/connections/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(connectionData)
        })
        .then(response => response.json())
        .then(data => {
            testBtn.textContent = originalText;
            testBtn.disabled = false;

            if (data.success) {
                // 连接成功
                showTestResult(true, data.message, data.system_info, data.details);
            } else {
                // 连接失败
                showTestResult(false, data.error, null, null, data.suggestions);
            }
        })
        .catch(error => {
            testBtn.textContent = originalText;
            testBtn.disabled = false;
            console.error('测试连接失败:', error);
            showTestResult(false, '网络错误：无法连接到服务器', null, null, ['检查网络连接', '确认服务器运行正常']);
        });
}

// 显示测试结果
function showTestResult(success, message, systemInfo, details, suggestions) {
    // 创建结果弹窗
    const modal = document.createElement('div');
    modal.className = 'test-result-modal';
    modal.innerHTML = `
        <div class="test-result-content">
            <div class="test-result-header ${success ? 'success' : 'error'}">
                <span class="test-result-icon">${success ? '✅' : '❌'}</span>
                <h3>${success ? '连接测试成功' : '连接测试失败'}</h3>
                <button class="close-btn" onclick="closeTestResult()">&times;</button>
            </div>
            <div class="test-result-body">
                <p class="test-message">${message}</p>
                ${systemInfo ? `<div class="system-info"><strong>系统信息:</strong><br><code>${systemInfo}</code></div>` : ''}
                ${details ? `
                    <div class="connection-details">
                        <h4>连接详情:</h4>
                        <ul>
                            <li><strong>主机:</strong> ${details.host}</li>
                            <li><strong>端口:</strong> ${details.port}</li>
                            <li><strong>用户名:</strong> ${details.username}</li>
                            <li><strong>认证方式:</strong> ${details.auth_method}</li>
                        </ul>
                    </div>
                ` : ''}
                ${suggestions ? `
                    <div class="suggestions">
                        <h4>解决建议:</h4>
                        <ul>
                            ${suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
            <div class="test-result-footer">
                <button class="btn btn-secondary" onclick="closeTestResult()">关闭</button>
                ${success ? '<button class="btn btn-success" onclick="closeTestResult(); connectDirect(event);">立即连接</button>' : ''}
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // 添加样式
    if (!document.getElementById('test-result-styles')) {
        const styles = document.createElement('style');
        styles.id = 'test-result-styles';
        styles.textContent = `
            .test-result-modal {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 10000;
            }
            
            .test-result-content {
                background: white;
                border-radius: 8px;
                max-width: 500px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
            }
            
            .test-result-header {
                padding: 1rem;
                border-bottom: 1px solid #eee;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }
            
            .test-result-header.success {
                background: #d4edda;
                color: #155724;
            }
            
            .test-result-header.error {
                background: #f8d7da;
                color: #721c24;
            }
            
            .test-result-icon {
                font-size: 1.5rem;
            }
            
            .test-result-header h3 {
                margin: 0;
                flex: 1;
            }
            
            .close-btn {
                background: none;
                border: none;
                font-size: 1.5rem;
                cursor: pointer;
                color: inherit;
            }
            
            .test-result-body {
                padding: 1rem;
            }
            
            .test-message {
                font-size: 1.1rem;
                margin-bottom: 1rem;
            }
            
            .system-info {
                background: #f8f9fa;
                padding: 0.75rem;
                border-radius: 4px;
                margin: 1rem 0;
            }
            
            .system-info code {
                font-family: monospace;
                font-size: 0.9rem;
                color: #333;
            }
            
            .connection-details, .suggestions {
                margin: 1rem 0;
            }
            
            .connection-details ul, .suggestions ul {
                margin: 0.5rem 0;
                padding-left: 1.5rem;
            }
            
            .suggestions li {
                margin: 0.25rem 0;
            }
            
            .test-result-footer {
                padding: 1rem;
                border-top: 1px solid #eee;
                display: flex;
                justify-content: flex-end;
                gap: 0.5rem;
            }
        `;
        document.head.appendChild(styles);
    }
}

// 关闭测试结果弹窗
function closeTestResult() {
    const modal = document.querySelector('.test-result-modal');
    if (modal) {
        modal.remove();
    }
}

// 显示输入错误
function showInputError(errorId, message) {
    const errorElement = document.getElementById(errorId);
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
        setTimeout(() => {
            errorElement.style.display = 'none';
        }, 3000);
    }
}

// 保存连接
function saveConnection(event) {
    event.preventDefault();
    
    const authMethod = document.querySelector('input[name="authMethod"]:checked').value;
    const connectionData = {
        name: document.getElementById('connectionName').value,
        host: document.getElementById('host').value,
        port: parseInt(document.getElementById('port').value),
        username: document.getElementById('username').value,
        password: authMethod === 'password' ? document.getElementById('password').value : '',
        private_key: authMethod === 'key' ? document.getElementById('privateKey').value : ''
    };
    
    fetch('/api/connections', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(connectionData)
    })
    .then(response => response.json())
    .then(data => {
        alert('连接保存成功!');
        hideNewConnectionModal();
        loadConnections();
    })
    .catch(error => {
        console.error('保存连接失败:', error);
        alert('保存连接失败: ' + error.message);
    });
}

// 直接连接
function connectDirect(event) {
    const authMethod = document.querySelector('input[name="authMethod"]:checked').value;
    const connectionData = {
        host: document.getElementById('host').value,
        port: parseInt(document.getElementById('port').value),
        username: document.getElementById('username').value,
        password: authMethod === 'password' ? document.getElementById('password').value : '',
        private_key: authMethod === 'key' ? document.getElementById('privateKey').value : ''
    };
    
    if (!connectionData.host || !connectionData.username) {
        showInputError('hostError', '请填写主机地址和用户名');
        return;
    }
    
    // 断开当前连接
    if (isConnected) {
        disconnect();
    }
    
    currentConnectionId = null;
    
    // 清除活跃状态
    document.querySelectorAll('.connection-item.active').forEach(item => {
        item.classList.remove('active');
    });
    
    terminal.clear();
    terminal.write('🔄 正在连接 ' + connectionData.host + '...\r\n');
    updateConnectionStatus('连接中...', false);
    updateTerminalTitle('连接中...');
    
    socket.emit('ssh_connect', connectionData);
    saveConnection(event)
}

// 使用保存的连接
function connectSaved(connectionId) {
    // 如果已经连接到这个服务器，则不重复连接
    if (currentConnectionId === connectionId && isConnected) {
        return;
    }
    
    // 断开当前连接
    if (isConnected) {
        disconnect();
    }

    currentConnectionId = connectionId;
    
    // 更新UI状态
    document.querySelectorAll('.connection-item.active').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[onclick="connectSaved(${connectionId})"]`).classList.add('active');
    
    terminal.clear();
    terminal.write('🔄 正在连接...\r\n');
    updateConnectionStatus('连接中...', false);
    updateTerminalTitle('连接中...');
    socket.emit('ssh_connect_saved', {connection_id: connectionId});
    function cleanAnsiCodes(str) {
        return str.replace(
            /[\u001B\u009B][[\]()#;?]*(?:(?:(?:[a-zA-Z\d]*(?:;[-a-zA-Z\d\/#&.:=?%@~_]*)*)?\u0007)|(?:(?:\d{1,4}(?:;\d{0,4})*)?[\dA-PR-TZcf-ntqry=><~]))/g,
            ''
        );
    }
    // 获取终端鼠标选中的文字
    terminal.onSelectionChange(() => {
    const text = terminal.getSelection().trim()
    if (text) {
        commandOutputHistory = cleanAnsiCodes(text).replace(" ","");
    }
    })
}

// 断开连接
function disconnect() {
    socket.emit('ssh_disconnect');
    commandOutputHistory = "";
    ssh_host_ip = "";
}

// 删除连接
function deleteConnection(connectionId) {
    if (!confirm('确定要删除这个连接吗？')) return;
    
    fetch(`/api/connections/${connectionId}`, {method: 'DELETE'})
        .then(() => {
            alert('连接删除成功!');
            loadConnections();
        })
        .catch(error => {
            console.error('删除连接失败:', error);
            alert('删除连接失败');
        });
}

// 更新连接状态
function updateConnectionStatus(message, connected) {
    const statusElement = document.getElementById('connectionStatus');
    statusElement.className = 'connection-status ' + (connected ? 'status-connected' : 'status-disconnected');
    statusElement.textContent = message;
}

// 更新终端标题
function updateTerminalTitle(title, username = '', host = '') {
    const titleElement = document.getElementById('terminalTitle');
    if (username && host) {
        titleElement.textContent = `${title} - ${username}@${host}`;
    } else {
        titleElement.textContent = title;
    }
}

// 更新连接状态指示器
function updateConnectionIndicator(connectionId, connected) {
    const indicator = document.getElementById(`indicator-${connectionId}`);
    if (indicator) {
        if (connected) {
            indicator.classList.add('connected');
        } else {
            indicator.classList.remove('connected');
        }
    }
}

// 显示新建连接模态框
function showNewConnectionModal() {
    document.getElementById('newConnectionModal').classList.add('show');
    document.getElementById('connectionName').focus();
}

// 隐藏新建连接模态框
function hideNewConnectionModal() {
    document.getElementById('newConnectionModal').classList.remove('show');
    document.getElementById('connectionForm').reset();
    toggleAuthMethod(); // 重置认证方式显示
}

// 切换侧边栏显示/隐藏
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggleSidebarBtn');
    
    sidebarVisible = !sidebarVisible;
    
    if (sidebarVisible) {
        sidebar.classList.remove('collapsed');
        toggleBtn.textContent = '连接列表';
    } else {
        sidebar.classList.add('collapsed');
        toggleBtn.textContent = '显示列表';
    }
}

function AISidebar() {
    const sidebar =   document.getElementById('chat');
    const toggleBtn = document.getElementById('AISidebarBtn');
    
    AisidebarVisible = !AisidebarVisible;
    
    if (AisidebarVisible) {
        sidebar.classList.remove('collapsed');
        toggleBtn.textContent = '关闭智能助手';
    } else {
        sidebar.classList.add('collapsed');
        toggleBtn.textContent = '显示智能助手';
    }
}

// 显示连接右键菜单（删除功能）
function showConnectionMenu(event, connectionId) {
    event.preventDefault();
    event.stopPropagation();
    
    if (confirm('确定要删除这个连接吗？')) {
        deleteConnection(connectionId);
    }
}

// ========== 用户认证相关函数 ==========

// 检查用户认证状态
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
    
    // 重新加载连接列表
    if (typeof loadConnections === 'function') {
        loadConnections();
    }
}

// 显示认证界面（未登录）
function showAuthInterface() {
    document.getElementById('userActions').style.display = 'none';
    
    // 清空连接列表
    connections = [];
    renderConnectionsList();
}

// 处理用户登录
async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    
    if (!username || !password) {
        alert('请输入用户名和密码');
        return;
    }
    
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            isAuthenticated = true;
            currentUser = data.user;
            showUserInterface();
            hideLoginModal();
            alert('登录成功！');
            
            // 重新初始化
            loadConnections();
            terminal.clear();
            terminal.write('✅ 登录成功，欢迎使用 Web SSH 客户端！\r\n');
        } else {
            alert('登录失败: ' + data.error);
        }
    } catch (error) {
        console.error('登录请求失败:', error);
        alert('登录失败，请稍后重试');
    }
}

// 处理用户注册
async function handleRegister(event) {
    event.preventDefault();
    
    const username = document.getElementById('registerUsername').value.trim();
    const email = document.getElementById('registerEmail').value.trim();
    const password = document.getElementById('registerPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    // 客户端验证
    if (!username || !email || !password || !confirmPassword) {
        alert('请填写所有必填字段');
        return;
    }
    
    if (username.length < 3) {
        alert('用户名至少需要3个字符');
        return;
    }
    
    if (password.length < 6) {
        alert('密码至少需要6个字符');
        return;
    }
    
    if (password !== confirmPassword) {
        alert('两次输入的密码不一致');
        return;
    }
    
    // 简单的邮箱验证
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        alert('请输入有效的邮箱地址');
        return;
    }
    
    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            isAuthenticated = true;
            currentUser = data.user;
            showUserInterface();
            hideRegisterModal();
            alert('注册成功！欢迎使用 Web SSH 客户端！');
            
            // 重新初始化
            loadConnections();
            terminal.clear();
            terminal.write('✅ 注册成功，欢迎使用 Web SSH 客户端！\r\n');
        } else {
            alert('注册失败: ' + data.error);
        }
    } catch (error) {
        console.error('注册请求失败:', error);
        alert('注册失败，请稍后重试');
    }
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

// 显示登录模态框
function showLoginModal() {
    document.getElementById('loginModal').classList.add('show');
    document.getElementById('loginUsername').focus();
}

// 隐藏登录模态框
function hideLoginModal() {
    document.getElementById('loginModal').classList.remove('show');
    document.getElementById('loginForm').reset();
}

// 显示注册模态框
function showRegisterModal() {
    document.getElementById('registerModal').classList.add('show');
    document.getElementById('registerUsername').focus();
}

// 隐藏注册模态框
function hideRegisterModal() {
    document.getElementById('registerModal').classList.remove('show');
    document.getElementById('registerForm').reset();
}

// 在登录和注册模态框之间切换
function switchToRegister() {
    hideLoginModal();
    showRegisterModal();
}

function switchToLogin() {
    hideRegisterModal();
    showLoginModal();
}

// 切换密码可见性 - 登录界面
function toggleLoginPasswordVisibility() {
    const passwordInput = document.getElementById('loginPassword');
    const eyeIcon = passwordInput.parentElement.querySelector('.eye-icon');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        eyeIcon.textContent = '🙈';
    } else {
        passwordInput.type = 'password';
        eyeIcon.textContent = '👁';
    }
}

// 切换密码可见性 - 注册界面
function toggleRegisterPasswordVisibility() {
    const passwordInput = document.getElementById('registerPassword');
    const eyeIcon = passwordInput.parentElement.querySelector('.eye-icon');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        eyeIcon.textContent = '🙈';
    } else {
        passwordInput.type = 'password';
        eyeIcon.textContent = '👁';
    }
}

// 切换确认密码可见性
function toggleConfirmPasswordVisibility() {
    const passwordInput = document.getElementById('confirmPassword');
    const eyeIcon = passwordInput.parentElement.querySelector('.eye-icon');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        eyeIcon.textContent = '🙈';
    } else {
        passwordInput.type = 'password';
        eyeIcon.textContent = '👁';
    }
}

// 修改原有的 loadConnections 函数，添加认证检查
const originalLoadConnections = loadConnections;
loadConnections = function() {
    if (!isAuthenticated) {
        console.log('用户未登录，跳过加载连接');
        return;
    }
    
    fetch('/api/connections', {
        method: 'GET',
        credentials: 'same-origin'  // 确保发送session cookie
    })
    .then(response => {
        if (response.status === 401) {
            // 未授权，需要重新登录
            isAuthenticated = false;
            showAuthInterface();
            alert('登录已过期，请重新登录');
            return [];
        }
        return response.json();
    })
    .then(data => {
        connections = data;
        renderConnectionsList();
    })
    .catch(error => {
        console.error('加载连接失败:', error);
        // alert('加载连接失败: ' + error.message);
    });
};

// socket 持续连接
setInterval(function () {
    if (socket && socket.connected) {
        socket.emit("ping");
    }
}, 10000);


//  监听整个页面，终端防抖
let resizeTimer;
window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
        resizeTerminal();
    }, 100);
});
// 监听终端防抖
const box = document.querySelector(".terminal-container");
function debounce(fn, delay = 300) { let timer = null; return function (...args) { clearTimeout(timer); timer = setTimeout(() => { fn.apply(this, args); }, delay); }; }
const onResize = debounce(() => {
    if (terminal != null) {
        resizeTerminal();
    }
}, 500);

const observer = new ResizeObserver(entries => {
  for (const entry of entries) {
    onResize();
  }
});

observer.observe(box);