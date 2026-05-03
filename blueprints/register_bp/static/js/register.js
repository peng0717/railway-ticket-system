/**
 * 注册流程控制脚本
 */

// ==================== 浮动通知条功能 ====================

function showNotification(message, type = 'info', duration = 3000) {
    const notification = document.getElementById('notification');
    const textEl = notification.querySelector('.notification-text');
    
    notification.className = `notification ${type}`;
    textEl.textContent = message;
    
    // 显示
    requestAnimationFrame(() => {
        notification.classList.add('show');
    });
    
    // 自动隐藏
    if (duration > 0) {
        clearTimeout(window._notificationTimer);
        window._notificationTimer = setTimeout(hideNotification, duration);
    }
}

function hideNotification() {
    const notification = document.getElementById('notification');
    notification.classList.remove('show');
}

// 注册数据存储
const registrationData = {
    real_name: '',
    id_card: '',
    email: '',
    email_verified: false,
    station_code: '',
    station_name: '',
    username: '',
    window_no: null,
    password: '',
    machine_code: ''
};

// 身份证校验码验证
function validateIdCard(idCard) {
    if (!idCard || idCard.length !== 18) return false;
    
    // 验证格式
    if (!/^\d{17}[\dXx]$/.test(idCard)) return false;
    
    // 加权因子
    const weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2];
    const checkCodes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2'];
    
    // 计算校验码
    let total = 0;
    for (let i = 0; i < 17; i++) {
        total += parseInt(idCard[i]) * weights[i];
    }
    const checkCode = checkCodes[total % 11];
    
    return idCard[17].toUpperCase() === checkCode;
}

// 邮箱验证
function validateEmail(email) {
    const pattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return pattern.test(email);
}

// 密码验证
function validatePassword(password) {
    if (password.length < 8 || password.length > 20) return false;
    if (!/[A-Za-z]/.test(password)) return false;
    if (!/[0-9]/.test(password)) return false;
    return true;
}

// 计算密码强度
function calculatePasswordStrength(password) {
    let strength = 0;
    if (password.length >= 8) strength++;
    if (password.length >= 12) strength++;
    if (/[A-Z]/.test(password) && /[a-z]/.test(password)) strength++;
    if (/[0-9]/.test(password)) strength++;
    if (/[^A-Za-z0-9]/.test(password)) strength++;
    return Math.min(strength, 4);
}

// 切换步骤
function showStep(stepNum) {
    document.querySelectorAll('.step-content').forEach(el => {
        el.classList.add('hidden');
    });
    document.getElementById(`step-${stepNum}`).classList.remove('hidden');
    
    // 更新步骤指示器
    document.querySelectorAll('.step').forEach(el => {
        const step = parseInt(el.dataset.step);
        if (step <= stepNum) {
            el.classList.add('active');
        } else {
            el.classList.remove('active');
        }
    });
}

// 步骤1: 实名认证
function initStep1() {
    const realNameInput = document.getElementById('real_name');
    const idCardInput = document.getElementById('id_card');
    const nameHint = document.getElementById('name_hint');
    const idCardHint = document.getElementById('id_card_hint');
    const nextBtn = document.getElementById('btn-step-1');
    
    function checkStep1() {
        let valid = true;
        
        // 验证姓名
        const nameRegex = /^[\u4e00-\u9fa5]{2,20}$/;
        if (!nameRegex.test(realNameInput.value)) {
            nameHint.textContent = '请输入2-20个汉字';
            nameHint.className = 'input-hint error';
            valid = false;
        } else {
            nameHint.textContent = '';
            nameHint.className = 'input-hint';
            registrationData.real_name = realNameInput.value;
        }
        
        // 验证身份证
        if (!validateIdCard(idCardInput.value)) {
            idCardHint.textContent = idCardInput.value.length === 18 ? '身份证校验码不正确' : '请输入18位身份证号';
            idCardHint.className = 'input-hint error';
            valid = false;
        } else {
            idCardHint.textContent = '身份证号格式正确';
            idCardHint.className = 'input-hint success';
            registrationData.id_card = idCardInput.value;
        }
        
        nextBtn.disabled = !valid;
    }
    
    realNameInput.addEventListener('input', checkStep1);
    idCardInput.addEventListener('input', checkStep1);
    
    document.getElementById('btn-step-1').addEventListener('click', async function() {
        // 检查身份证是否已注册
        const res = await fetch('/register/api/check-id-card', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id_card: registrationData.id_card})
        });
        const data = await res.json();
        
        if (data.status === 'error') {
            idCardHint.textContent = data.message;
            idCardHint.className = 'input-hint error';
            return;
        }
        
        showStep(2);
    });
}

// 步骤2: 邮箱验证
function initStep2() {
    const emailInput = document.getElementById('email');
    const emailHint = document.getElementById('email_hint');
    const verifyCodeGroup = document.getElementById('verify_code_group');
    const verifyCodeInput = document.getElementById('verify_code');
    const codeHint = document.getElementById('code_hint');
    const sendBtn = document.getElementById('btn-send-code');
    const verifyBtn = document.getElementById('btn-verify');
    const nextBtn = document.getElementById('btn-step-2');
    const devCodeDisplay = document.getElementById('dev_code_display');
    const devCodeValue = document.getElementById('dev_code_value');
    
    let devCode = null;
    
    function checkEmail() {
        if (!validateEmail(emailInput.value)) {
            emailHint.textContent = '请输入正确的邮箱地址';
            emailHint.className = 'input-hint error';
            return false;
        }
        emailHint.textContent = '';
        emailHint.className = 'input-hint';
        return true;
    }
    
    emailInput.addEventListener('blur', async function() {
        if (!checkEmail()) return;
        
        // 检查邮箱是否已注册
        const res = await fetch('/register/api/check-email', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: emailInput.value})
        });
        const data = await res.json();
        
        if (data.status === 'error') {
            emailHint.textContent = data.message;
            emailHint.className = 'input-hint error';
        }
    });
    
    sendBtn.addEventListener('click', async function() {
        if (!checkEmail()) return;
        
        sendBtn.disabled = true;
        sendBtn.textContent = '发送中...';
        
        const res = await fetch('/register/api/send-verification-code', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: emailInput.value})
        });
        const data = await res.json();
        
        sendBtn.disabled = false;
        sendBtn.textContent = '发送验证码';
        
        if (data.status === 'success') {
            verifyCodeGroup.style.display = 'block';
            
            if (data.dev_code) {
                // 开发模式显示验证码
                devCode = data.dev_code;
                devCodeDisplay.classList.remove('hidden');
                devCodeValue.textContent = devCode;
                // 开发模式：显示8秒，方便看到验证码
                showNotification(data.message, 'info', 8000);
            } else {
                // 邮件发送成功
                showNotification(data.message, 'success', 3000);
            }
        } else {
            showNotification(data.message, 'error');
        }
    });
    
    verifyBtn.addEventListener('click', async function() {
        const code = verifyCodeInput.value.trim();
        if (code.length !== 6) {
            codeHint.textContent = '请输入6位验证码';
            codeHint.className = 'input-hint error';
            return;
        }
        
        const res = await fetch('/register/api/verify-code', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: emailInput.value, code})
        });
        const data = await res.json();
        
        if (data.status === 'success') {
            codeHint.textContent = '验证成功';
            codeHint.className = 'input-hint success';
            registrationData.email = emailInput.value.toLowerCase();
            registrationData.email_verified = true;
            nextBtn.disabled = false;
        } else {
            codeHint.textContent = data.message;
            codeHint.className = 'input-hint error';
        }
    });
    
    nextBtn.addEventListener('click', function() {
        if (registrationData.email_verified) {
            showStep(3);
        }
    });
    
    document.getElementById('btn-back-2').addEventListener('click', function() {
        showStep(1);
    });
}

// 步骤3: 选择车站
function initStep3() {
    const searchInput = document.getElementById('station_search');
    const stationList = document.getElementById('station_list');
    const selectedStation = document.getElementById('selected_station');
    const selectedStationName = document.getElementById('selected_station_name');
    const selectedStationCode = document.getElementById('selected_station_code');
    const nextBtn = document.getElementById('btn-step-3');
    
    let debounceTimer = null;
    
    searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(searchStations, 300);
    });
    
    async function searchStations() {
        const keyword = searchInput.value.trim();
        if (keyword.length < 1) {
            stationList.innerHTML = '<div class="station-placeholder">请输入关键词搜索车站</div>';
            return;
        }
        
        const res = await fetch(`/register/api/search-stations?q=${encodeURIComponent(keyword)}`);
        const data = await res.json();
        
        if (data.status === 'success' && data.data.length > 0) {
            stationList.innerHTML = data.data.map(s => `
                <div class="station-item" data-code="${s.station_code}" data-name="${s.station_name}">
                    <span class="station-item-name">${s.station_name}</span>
                    <span class="station-item-code">${s.station_code}</span>
                </div>
            `).join('');
            
            // 绑定点击事件
            stationList.querySelectorAll('.station-item').forEach(item => {
                item.addEventListener('click', function() {
                    // 移除其他选中状态
                    stationList.querySelectorAll('.station-item').forEach(el => el.classList.remove('selected'));
                    this.classList.add('selected');
                    
                    // 显示选中信息
                    selectedStation.classList.remove('hidden');
                    selectedStationName.textContent = this.dataset.name;
                    selectedStationCode.textContent = this.dataset.code;
                    
                    registrationData.station_code = this.dataset.code;
                    registrationData.station_name = this.dataset.name;
                    nextBtn.disabled = false;
                });
            });
        } else {
            stationList.innerHTML = '<div class="station-placeholder">未找到匹配的车站</div>';
            nextBtn.disabled = true;
        }
    }
    
    nextBtn.addEventListener('click', function() {
        if (registrationData.station_code) {
            updateUsernamePreview();
            showStep(4);
        }
    });
    
    document.getElementById('btn-back-3').addEventListener('click', function() {
        showStep(2);
    });
}

// 更新工号预览
function updateUsernamePreview() {
    const previewText = document.getElementById('preview_text');
    const val = document.getElementById('username')?.value?.trim() || '';
    if (previewText) {
        previewText.textContent = val || '请输入工号';
    }
}

// 步骤4: 注册工号
function initStep4() {
    const usernameInput = document.getElementById('username');
    const usernameHint = document.getElementById('username_hint');
    const previewText = document.getElementById('preview_text');
    const checkBtn = document.getElementById('btn-check-username');
    const nextBtn = document.getElementById('btn-step-4');
    let usernameAvailable = false;
    
    // 实时预览
    usernameInput.addEventListener('input', function() {
        const val = this.value.trim();
        previewText.textContent = val || '请输入工号';
        usernameAvailable = false;
        nextBtn.disabled = true;
        
        // 实时格式校验
        if (val && !/^[a-zA-Z]/.test(val)) {
            usernameHint.textContent = '工号必须以字母开头';
            usernameHint.className = 'input-hint error';
        } else if (val && !/^[a-zA-Z][a-zA-Z0-9_-]{3,19}$/.test(val)) {
            usernameHint.textContent = '4-20位，字母开头，可含字母、数字、下划线、短横线';
            usernameHint.className = 'input-hint error';
        } else if (val) {
            usernameHint.textContent = '格式正确，请检查可用性';
            usernameHint.className = 'input-hint success';
        } else {
            usernameHint.textContent = '字母开头，可包含字母、数字、下划线、短横线';
            usernameHint.className = 'input-hint';
        }
    });
    
    // 检查可用性
    checkBtn.addEventListener('click', async function() {
        const val = usernameInput.value.trim();
        if (!val || !/^[a-zA-Z][a-zA-Z0-9_-]{3,19}$/.test(val)) {
            showNotification('请输入有效的工号格式', 'error');
            return;
        }
        
        // 检查保留词
        const reserved = ['admin', 'root', 'system', 'test', 'administrator'];
        if (reserved.includes(val.toLowerCase())) {
            usernameHint.textContent = '该工号为系统保留词，不可使用';
            usernameHint.className = 'input-hint error';
            showNotification('该工号为系统保留词', 'error');
            return;
        }
        
        checkBtn.disabled = true;
        checkBtn.textContent = '检查中...';
        
        const res = await fetch('/register/api/check-username', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: val})
        });
        const data = await res.json();
        
        checkBtn.disabled = false;
        checkBtn.textContent = '检查可用性';
        
        if (data.status === 'success') {
            usernameHint.textContent = '工号可用';
            usernameHint.className = 'input-hint success';
            usernameAvailable = true;
            nextBtn.disabled = false;
            registrationData.username = val;
            showNotification('工号可用！', 'success');
        } else {
            usernameHint.textContent = data.message;
            usernameHint.className = 'input-hint error';
            showNotification(data.message, 'error');
        }
    });
    
    // 下一步
    nextBtn.addEventListener('click', function() {
        if (usernameAvailable) {
            // 更新摘要中的车站信息
            document.getElementById('window_station').textContent = `${registrationData.station_name} (${registrationData.station_code})`;
            showStep(5);
        }
    });
    
    document.getElementById('btn-back-4').addEventListener('click', function() {
        showStep(3);
    });
}

// 步骤5: 选择窗口号
function initStep5() {
    const windowNoSelect = document.getElementById('window_no');
    const selectedWindow = document.getElementById('selected_window');
    const windowNoDisplay = document.getElementById('window_no_display');
    const windowHint = document.getElementById('window_hint');
    const nextBtn = document.getElementById('btn-step-5');
    
    windowNoSelect.addEventListener('change', async function() {
        const windowNo = parseInt(this.value);
        
        if (!windowNo) {
            selectedWindow.classList.add('hidden');
            nextBtn.disabled = true;
            return;
        }
        
        // 检查窗口是否可用
        const res = await fetch('/register/api/check-window', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                station_code: registrationData.station_code,
                window_no: windowNo
            })
        });
        const data = await res.json();
        
        if (data.status === 'success') {
            selectedWindow.classList.remove('hidden');
            windowNoDisplay.textContent = `${windowNo}号窗口`;
            windowHint.textContent = '';
            registrationData.window_no = windowNo;
            nextBtn.disabled = false;
        } else {
            selectedWindow.classList.add('hidden');
            windowHint.textContent = data.message;
            windowHint.className = 'input-hint error';
            nextBtn.disabled = true;
        }
    });
    
    nextBtn.addEventListener('click', function() {
        if (registrationData.window_no) {
            showStep(6);
        }
    });
    
    document.getElementById('btn-back-5').addEventListener('click', function() {
        showStep(4);
    });
}

// 步骤6: 设置密码
function initStep6() {
    const passwordInput = document.getElementById('password');
    const confirmInput = document.getElementById('confirm_password');
    const passwordHint = document.getElementById('password_hint');
    const confirmHint = document.getElementById('confirm_hint');
    const strengthBar = document.querySelector('.strength-bar');
    const nextBtn = document.getElementById('btn-step-6');
    
    const strengthColors = ['#dc3545', '#ffc107', '#17a2b8', '#28a745'];
    
    function checkPassword() {
        const password = passwordInput.value;
        const confirm = confirmInput.value;
        let valid = true;
        
        // 验证密码格式
        if (!validatePassword(password)) {
            if (password.length > 0) {
                passwordHint.textContent = '密码必须8-20位，包含字母和数字';
                passwordHint.className = 'input-hint error';
            } else {
                passwordHint.textContent = '';
                passwordHint.className = 'input-hint';
            }
            valid = false;
        } else {
            passwordHint.textContent = '密码格式正确';
            passwordHint.className = 'input-hint success';
        }
        
        // 更新强度条
        const strength = calculatePasswordStrength(password);
        const width = (strength / 4) * 100;
        const color = strengthColors[strength - 1] || '#dc3545';
        strengthBar.style.width = `${width}%`;
        strengthBar.style.backgroundColor = color;
        
        // 验证确认密码
        if (confirm && password !== confirm) {
            confirmHint.textContent = '两次输入的密码不一致';
            confirmHint.className = 'input-hint error';
            valid = false;
        } else if (confirm) {
            confirmHint.textContent = '';
            confirmHint.className = 'input-hint';
        }
        
        nextBtn.disabled = !(valid && validatePassword(password) && password === confirm && password.length > 0);
    }
    
    passwordInput.addEventListener('input', checkPassword);
    confirmInput.addEventListener('input', checkPassword);
    
    nextBtn.addEventListener('click', async function() {
        if (validatePassword(passwordInput.value) && passwordInput.value === confirmInput.value) {
            registrationData.password = passwordInput.value;
            
            // 采集机器码
            registrationData.machine_code = await getMachineCode();
            
            // 填充摘要
            document.getElementById('summary_name').textContent = registrationData.real_name;
            document.getElementById('summary_id_card').textContent = registrationData.id_card;
            document.getElementById('summary_email').textContent = registrationData.email;
            document.getElementById('summary_station').textContent = `${registrationData.station_name} (${registrationData.station_code})`;
            document.getElementById('summary_username').textContent = registrationData.username;
            document.getElementById('summary_window').textContent = `${registrationData.window_no}号窗口`;
            
            showStep(7);
        }
    });
    
    document.getElementById('btn-back-6').addEventListener('click', function() {
        showStep(5);
    });
}

// 步骤7: 提交注册
function initStep7() {
    const submitBtn = document.getElementById('btn-submit');
    const backBtn = document.getElementById('btn-back-7');
    
    submitBtn.addEventListener('click', async function() {
        submitBtn.disabled = true;
        submitBtn.textContent = '提交中...';
        
        try {
            const res = await fetch('/register/api/submit-registration', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(registrationData)
            });
            const data = await res.json();
            
            if (data.status === 'success') {
                document.getElementById('success_username').textContent = data.username;
                showStep('success');
            } else {
                showNotification(data.message, 'error');
            }
        } catch (e) {
            showNotification('提交失败，请重试', 'error');
        }
        
        submitBtn.disabled = false;
        submitBtn.textContent = '提交注册';
    });
    
    backBtn.addEventListener('click', function() {
        showStep(6);
    });
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initStep1();
    initStep2();
    initStep3();
    initStep4();
    initStep5();
    initStep6();
    initStep7();
});
