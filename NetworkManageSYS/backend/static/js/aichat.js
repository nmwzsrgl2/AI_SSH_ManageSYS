const messages = document.getElementById("chatMessages");
const sendButton = document.getElementById("sendButton");
const stopButton = document.getElementById("stopButton");
const messageInput = document.getElementById("messageInput");
const clearButton = document.getElementById("clearChat");


sendButton.disabled = true;
stopButton.disabled = true;
let isGenerating = false; // 当前是否在生成

function inputisNull(){
    if(messageInput.value.trim() == ""){
        return true;
    }
    return false;
}


// 发送按钮点击事件
sendButton.addEventListener("click", () => {
    if (!isGenerating) {
        send();
    }
});

// 输入框回车事件
messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!isGenerating) {
            send();
        }
    }
});

// 停止按钮事件
stopButton.addEventListener("click", stopGeneration);
clearButton.addEventListener('click', () => clearConversation());
sshcommedButton.addEventListener('click', () => sshcommed());

let sshcommed_is_on = true;
function sshcommed(){
    sshcommed_is_on ? false : true;
    if(sshcommed_is_on){
        sshcommedButton.className="btn-stop";
        sshcommedButton.innerText = "SSH上下文 OFF";
        sshcommed_is_on = false;
        return
    }
    sshcommedButton.className="btn-ssh";
    sshcommedButton.innerText = "SSH上下文 ON";
    sshcommed_is_on = true;
    
    
}
async function clearConversation() {
        if (confirm('确定要清空对话历史吗？')) {
            messages.innerHTML = '';
            Usermessage = [];
            chatHistory = [];
            isgethistory = false
            try{
                const res = await fetchWithTimeout('/api/clear/history',{
                    method:'GET'
                })
                const data = await res.json();
                if(data.result == "success"){
                    alert("清除成功")
                }
            }catch(e){
                alert("清除失败，可能是网络问题")
            }
        }
    }


let ishiding = [];

function Thinking() {
    ishiding = [];

    const buttons = document.querySelectorAll(".ThinkingButton");

    buttons.forEach(function (item) {
        const target = item.nextElementSibling;

        // 初始化为“显示状态”
        ishiding.push({ dom: target, hidden: true });

        // 防止重复绑定
        item.onclick = function () {
            hideThink(target);
        };
        // 鼠标移入显示提示
        target.addEventListener('mouseenter', function () {
            item.title = '点击隐藏/显示 AI 回复';
        });
    });
}

function hideThink(dom) {
    for (const item of ishiding) {
        if (item.dom === dom) {
            item.hidden = !item.hidden;
            item.dom.style.display = item.hidden ? "none" : "block";
            break;
        }
    }
}

function addMessage(thinking,content, sender) {   
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const time = new Date().toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        messageDiv.innerHTML = `
             ${sender ==='ai' ? 
                `<div class="Thinking">
                    <a href="javascript:void(0)" alt="显示" class="ThinkingButton">Thinking...</a>
                    <p id="AiThinking">${thinking}</p>
                </div>`:''}

            <div class="message ${sender ==='ai' ?'ai flex-row':'user'}">
                <div class="avatar">
                    ${sender === 'user' ? '<i style="font-size:14px"></i>' : '<i class="fas fa-robot"></i>'}
                </div>
                <div class="message-content" >
                    ${sender === 'user' ? '<div class="content-text">' + this.formatMessage(content) + '</div>' : '<div id="Aimessages" class="content-text spinner">' + this.formatMessage(content) + '</div>'}
                    ${sender === 'ai' ? '<span id="over_time" class="message-time"></span>':''}
                    <span class="message-time">${time}</span>
                </div>
            </div>
           
        `;
        
        this.chatMessages.appendChild(messageDiv);
        // this.scrollToBottom();
        
        return messageDiv.querySelector('.content-text');
    }

// 格式化消息内容
function formatMessage(content) {
    if (!content) return "";

    // 1. 先处理代码块（必须最优先）
    content = content.replace(/```(\w+)?\n([\s\S]*?)```/g, (m, lang, code) => {
        return `<pre><code class="language-${lang || ""}">${escapeHtml(code)}</code></pre>`;
    });

    content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
    content = content.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    content = content.replace(/\*(.+?)\*/g, '<em>$1</em>');
    content = content.replace(/\-\-\-\#\#\#/g, '<br>');

    return content;
}

function escapeHtml(str) {
    return str.replace(/[&<>"']/g, s => ({
        '&':'&amp;',
        '<':'&lt;',
        '>':'&gt;',
        '"':'&quot;',
        "'":'&#039;'
    }[s]));
}

const md = window.markdownit({
  html: false,      // 禁止原始 HTML（防 XSS）
  linkify: true,
  breaks: true
});


let controller = null;     // 用于中断 fetch
let StopGenerating = false;
let aiDivcount = null;
let ai_response = null;
let firseChat = true;
let Usermessage = []; // 存储用户输入的消息
let conversation_id = ''; // 会话 ID，需要基于之前的聊天记录继续对
let task_id = ''; // 任务 ID ,用于停止对话

// 修改 fetchWithTimeout 函数，使其更通用
async function fetchWithTimeout(url, options = {}) {
    // 从 options 中提取 timeout 参数，设置默认值
    const { timeout = 700000, ...fetchOptions } = options; // 默认 70 秒超时
    
    const controller = new AbortController();
    const { signal } = controller;
    
    // 设置超时定时器
    const timeoutId = setTimeout(() => {
        controller.abort();
    }, timeout);
    
    try {
        // 合并 options，传入 signal
        const response = await fetch(url, {
            ...fetchOptions,
            signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}`);
        }
        
        return response; // 返回完整的 response 对象，让调用者决定如何处理
    } catch (error) {
        clearTimeout(timeoutId);
        
        if (error.name === 'AbortError') {
            throw new Error(`请求超时 (${timeout}ms)`);
        } else if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
            throw new Error('网络错误，请检查网络连接');
        } else {
            throw error;
        }
    }
}

// 监听鼠标滚轮事件，打断默认消息滚动
let = stopScroll = false;
let = lastScrollTop = 0;
messages.addEventListener('wheel', (e) => {
    // e.preventDefault();
    // console.log(e.deltaY);
    if(isGenerating){
        stopScroll = true;
        scrollToBottom();
    }
    // }else{
    //     if(lastScrollTop > window.screen){ }
    //     if(lastScrollTop < 0){}
    //     else{
    //     lastScrollTop += e.deltaY;
    //     messages.scroll(0,lastScrollTop);}
    // }
    
});
// 默认消息滚动

function scrollToBottom() {
    if(stopScroll){
        return;
    }
    else{
        messages.scrollTop = messages.scrollHeight;
    }
}



async function send(event) {
    const question = document.querySelector("#messageInput").value;
    Usermessage[0] = {"role": "system", "content": ""};
    // 验证输入
    if (!question.trim()) {
        return;
    }
    if(commandOutputHistory !=""&& ssh_host_ip != "" && sshcommed_is_on == true){
        Usermessage.push({"role": "user", "content": "<请使用中文回答，并且最准确、完整、有逻辑,数据尽可能不要使用表格输出"+"SSH终端输出:"+commandOutputHistory+",来自服务器:"+ ssh_host_ip+">"+question});
    }else if(ssh_host_ip != "" && commandOutputHistory ==""){
        Usermessage.push({"role": "user", "content": "<请使用中文回答，并且最准确、完整、有逻辑,数据尽可能不要使用表格输出,来自服务器:"+ ssh_host_ip+">"+question});
    }
    else{
        Usermessage.push({"role": "user", "content": "<请使用中文回答，并且最准确、完整、有逻辑,数据尽可能不要使用表格输出>"+question});
    }
    // 记录正在AI生成
    
    isGenerating = true;
    // 清空输入框
    messageInput.value = "";
    
    // 如果是中止事件，处理中止逻辑
    if (event && event.type === 'abort') {
        if (controller) {
            controller.abort();
        }
        return;
    }
    
    // 如果是第一次聊天，清理界面
    if (firseChat === true) {
        try {
            document.querySelector(".message").remove();
        } catch (e) {
            console.log("清理消息时出错:", e);
        }
        firseChat = false;
    }
    
    // 添加用户消息和AI消息占位符
    addMessage("",question, "user"); 
    addMessage("","", "ai"); 
    
    // 获取当前AI消息元素

    const aiResponses = document.querySelectorAll("#Aimessages");
    const aiThinkings = document.querySelectorAll("#AiThinking");

    const currentAiResponse = aiResponses[aiResponses.length - 1];
    const currentAiThinking = aiThinkings[aiThinkings.length - 1];
    
    // 滚动到最新消息
    scrollToBottom();
    
    let rawBuffer = ""; 
    let thinkingBuffer = "";
    
    try {
        // 使用统一的 AbortController
        controller = new AbortController();
        // 更新按钮状态
        stopButton.disabled = false;
        sendButton.disabled = true;
        // 计时
        const start = performance.now();
        // 调用 fetchWithTimeout，传入 timeout 和 signal
        const res = await fetchWithTimeout("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                'message': Usermessage,
                'stream': true, 
                'conversation_id':""  
            }),
            signal: controller.signal, // 使用统一的 controller
            timeout: 300000 // 设置 300000 秒超时
        });
        
        // 处理流式响应
        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        
        let buffer = "";
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            // SSE 事件以 \n\n 分隔
            const events = buffer.split("\n\n");
            buffer = events.pop(); // 留下不完整部分
            
            for (const event of events) {
                if (!event.startsWith("data:")) continue;
                
                const data = event.replace("data:", "").trim();
                
                // 处理流结束
                if (data === "[DONE]") {
                    const end = performance.now();
                    stopButton.disabled = true;
                    sendButton.disabled = false;
                    isGenerating = false;
                    Usermessage.length = 0;
                    // 统一markdown渲染
                    if (currentAiResponse) {
                        currentAiResponse.innerHTML = this.formatMessage(rawBuffer);
                    }
                    let over_time_length = document.querySelectorAll("#over_time").length
                    document.querySelectorAll("#over_time")[over_time_length-1].innerHTML ="完成时间：" + ((end - start) / 1000).toFixed(1) +'s';
                    rawBuffer = "";
                    thinkingBuffer = "";
                    commandOutputHistory = "";
                    break;
                }
                
                // 解析 JSON 数据
                try {
                    const obj = JSON.parse(data);
                    // 上下文 ID
                    if(obj.conversation_id){
                        conversation_id = obj.conversation_id;
                    }
                    // 每一次会话 ID
                    if(obj.task_id){
                        task_id = obj.task_id
                    }
                    // 处理数
                    if (obj.data) {
                        rawBuffer += obj.data;
                        if (currentAiResponse) {
                            currentAiResponse.textContent = rawBuffer;
                            currentAiResponse.className = "content-text";
                            currentAiThinking.style.display = "none";
                        }
                    }
                    
                    // 处理思考过程
                    if (obj.thinking) {
                        thinkingBuffer += obj.thinking;
                        if (currentAiThinking) {
                            currentAiThinking.textContent = thinkingBuffer;
                        }
                    }
                    
                } catch (parseError) {
                    console.error("解析JSON出错:", parseError, "原始数据:", data);
                }
                
                // 检查是否用户请求停止
                if (StopGenerating) {
                    if (currentAiResponse) {
                        currentAiResponse.className = "content-text";
                        currentAiResponse.textContent = rawBuffer + "[已中断]";
                    }
                    sendButton.disabled = false;
                    break;
                }
                
                // 滚动到最新消息
                messages.scrollTop = messages.scrollHeight;
            }
            
            // 更新token计数
            updateTokenCount();
            
            // 如果用户请求停止，跳出循环
            if (StopGenerating) {
                isGenerating = false;
                StopGenerating = false;
                break;
            }
        }
        
        // 处理思考过程显示
        Thinking();
        stopScroll = false;
        
    } catch (error) {
        console.error("发送请求时出错:", error);
        
        // 显示错误信息
        if (currentAiResponse) {
            if (error.message.includes("超时")) {
                currentAiResponse.textContent = rawBuffer + "\n\n[请求超时，请重试]";
            } else if (error.name === "AbortError" || error.message.includes("已中断")) {
                currentAiResponse.textContent = rawBuffer + "[已中断]";
            } else if (error.message.includes("网络错误")) {
                currentAiResponse.textContent = rawBuffer + "\n\n[网络错误，请检查连接]";
            } else {
                currentAiResponse.textContent = rawBuffer + `\n\n[错误: ${error.message}]`;
            }
            currentAiResponse.className = "content-text error";
        }
        
    } finally {
        // 重置状态
        isGenerating = false;
        StopGenerating = false;
        stopButton.disabled = true;
        sendButton.disabled = false;
        controller = null;
        
        // 滚动到最新消息
        messages.scrollTop = messages.scrollHeight;
    }
}


async function stopGeneration() {
    if (isGenerating && controller) {
        try{
            if(task_id == ""){
                console.log("没有task_id无法暂停")
            }else{
            // 更新按钮状态
            stopButton.disabled = true;
            sendButton.disabled = false;
            const res = await fetchWithTimeout("/api/stop",{
                method:"POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    "user": "admin",
                    "task_id":task_id 
                }),
                signal: controller.signal, // 使用统一的 controller
                timeout: 5000 
            })
            const data = await res.json()
            if(data.result =='success'){
                StopGenerating = true;
                controller.abort();
            }}
        }catch (error) {
            console.log(error);
            
        } 
    }
}

function updateTokenCount() {
    // 确保 ai_response 存在且有元素
    const aiResponses = document.querySelectorAll("#Aimessages");
    
    if (aiResponses.length > 0) {
        const latestAiResponse = aiResponses[aiResponses.length - 1];
        const textCount = latestAiResponse.innerText.length;
        document.querySelector('#tokenCount').textContent = `字符数: ${textCount}`;
    } else {
        // 如果没有AI消息，显示0
        document.querySelector('#tokenCount').textContent = `字符数: 0`;
    }
}

let chatHistory = [];
let isgethistory = false;
async function GetChatHistory(){
    try{
        // 如果是第一次聊天，清理界面
        if (firseChat === true) {
            try {
                document.querySelector(".message").remove();
            } catch (e) {
                console.log("清理消息时出错:", e);
            }
            firseChat = false;
        }
        //是否已经获取过历史记录
        if(isgethistory == true){
            return
        }
        if(chatHistory.length > 0){
            for(let i=0;i<chatHistory.length;i++){
                let match = (chatHistory[i].user_message).match(/<([^<>]*)>/);
                const result = match ? match[0] : '';
                user_message = chatHistory[i].user_message.replace(result,"").replace("<请使用中文回答，并且最准确、完整、有逻辑,数据尽可能不要使用表格输出>",'');
                addMessage(
                    "",
                    (user_message),
                    "user"
                )
                addMessage(
                    chatHistory[i].ai_thinking,
                    chatHistory[i].ai_message,
                    "ai"
                )
                const aiResponses = document.querySelectorAll("#Aimessages");
                aiResponses[aiResponses.length - 1].className = "content-text";
                const aiThinkings = document.querySelectorAll("#AiThinking");
                const currentAiThinking = aiThinkings[aiThinkings.length - 1];
                aiThinkings[aiThinkings.length - 1].style.display = "none";
            }
            Thinking();
            // 滚动到最新消息
            messages.scrollTop = messages.scrollHeight;
            isgethistory = true;
        }else{
            const  res  = await fetchWithTimeout("/api/chat/history",{
                method: "GET",
                headers: { "Content-Type": "application/json" },

            });
            const data = await res.json();
            data.forEach(item => {
                chatHistory.push({
                    "user_message": item.user_message,
                    "ai_message": item.ai_message,
                    "ai_thinking": item.ai_thinking
                })
            });
            if (chatHistory.length != 0){
                GetChatHistory();
            }
            
        }
    }catch(e){
        console.log(e)
    }
}

function addinfoMessage(content,status) {
        const errorDiv = document.createElement('div');
        if(status == "error"){
            errorDiv.className = 'message ai error';
        }else{
            errorDiv.className = 'message ai success';
        }
        const time = new Date().toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        errorDiv.innerHTML = `
            <div class="message-content">
                <div class="content-text">${content}</div>
                <div class="message-time">${time}</div>
            </div>
        `;
        this.chatMessages.appendChild(errorDiv);
    }

async function testAIConnection() {
        try {
            const response = await fetchWithTimeout(`/api/tags`);
            const data = await response;
            if (data.length === 0) {
                return false;
            }
            return true;
        } catch (error) {
            console.error('连接测试失败:', error);
            return false;
        }
    }

document.addEventListener('DOMContentLoaded', async () => {
    // 测试连接
    const isConnected = await testAIConnection();
    if (!isConnected) {
        addinfoMessage('无法连接到 Ollama 服务，请确保：<br>1. Ollama 已安装并运行<br>2. 服务运行在 http://localhost:11434<br>3. 已通过命令行安装模型：<code>ollama pull qwen3:4b</code>','error');
    }else{
        addinfoMessage('已成功连接到服务，您可以开始对话。','success');
        sendButton.disabled = false;
        GetChatHistory();
    }
});
