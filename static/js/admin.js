/**
 * 铁路客票系统 - 管理端 JavaScript
 */

// ==================== Toast 提示 ====================

/**
 * 显示 Toast 提示
 * @param {string} message - 提示消息
 * @param {string} type - 类型: success, error, warning, info
 * @param {number} duration - 显示时长(毫秒), 0表示不自动关闭
 */
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-times-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    const toast = document.createElement('div');
    toast.className = `toast-item ${type}`;
    toast.innerHTML = `
        <i class="fas ${icons[type]}"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    if (duration > 0) {
        setTimeout(() => {
            toast.style.animation = 'toastIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
}

// ==================== 网络状态检测 ====================

document.addEventListener('DOMContentLoaded', function() {
    const networkStatus = document.getElementById('networkStatus');
    const networkMessage = document.getElementById('networkMessage');
    
    // 离线时显示提示
    window.addEventListener('offline', function() {
        if (networkStatus) {
            networkStatus.classList.remove('hidden');
            if (networkMessage) {
                networkMessage.textContent = '网络连接已断开，请检查网络';
            }
        }
        showToast('网络连接已断开，请检查网络', 'error', 0);
    });
    
    // 在线时显示恢复提示并刷新
    window.addEventListener('online', function() {
        if (networkStatus) {
            networkStatus.classList.add('hidden');
        }
        showToast('网络已恢复，正在重新加载...', 'success');
        setTimeout(() => location.reload(), 1500);
    });
});

// ==================== 快捷键支持 ====================

document.addEventListener('keydown', function(e) {
    // 只在主内容区响应快捷键
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
        return;
    }
    
    // F5: 刷新页面
    if (e.key === 'F5') {
        e.preventDefault();
        location.reload();
    }
    
    // Esc: 返回上一页
    if (e.key === 'Escape') {
        if (window.history.length > 1) {
            window.history.back();
        }
    }
});

// ==================== 确认对话框 ====================

/**
 * 显示确认对话框
 * @param {string} message - 确认消息
 * @param {function} onConfirm - 确认回调
 * @param {function} onCancel - 取消回调
 */
function confirmDialog(message, onConfirm, onCancel) {
    if (confirm(message)) {
        if (typeof onConfirm === 'function') {
            onConfirm();
        }
    } else {
        if (typeof onCancel === 'function') {
            onCancel();
        }
    }
}

// ==================== 表单验证 ====================

/**
 * 简单的表单验证
 * @param {HTMLFormElement} form - 表单元素
 * @param {Object} rules - 验证规则
 * @returns {boolean} 是否通过验证
 */
function validateForm(form, rules) {
    for (const fieldName in rules) {
        const field = form.querySelector(`[name="${fieldName}"]`);
        if (!field) continue;
        
        const rule = rules[fieldName];
        const value = field.value.trim();
        
        // 必填验证
        if (rule.required && !value) {
            showToast(rule.message || `${fieldName}不能为空`, 'warning');
            field.focus();
            return false;
        }
        
        // 最小长度验证
        if (rule.minLength && value.length < rule.minLength) {
            showToast(rule.message || `${fieldName}长度不能少于${rule.minLength}个字符`, 'warning');
            field.focus();
            return false;
        }
        
        // 最大长度验证
        if (rule.maxLength && value.length > rule.maxLength) {
            showToast(rule.message || `${fieldName}长度不能超过${rule.maxLength}个字符`, 'warning');
            field.focus();
            return false;
        }
        
        // 正则验证
        if (rule.pattern && !rule.pattern.test(value)) {
            showToast(rule.message || `${fieldName}格式不正确`, 'warning');
            field.focus();
            return false;
        }
    }
    return true;
}

// ==================== 数据格式化 ====================

/**
 * 格式化金额
 * @param {number} amount - 金额
 * @param {string} symbol - 货币符号
 * @returns {string} 格式化后的金额
 */
function formatMoney(amount, symbol = '¥') {
    return symbol + parseFloat(amount || 0).toFixed(2);
}

/**
 * 格式化日期时间
 * @param {string} datetime - ISO格式日期时间
 * @param {string} format - 输出格式
 * @returns {string} 格式化后的日期时间
 */
function formatDateTime(datetime, format = 'YYYY-MM-DD HH:mm:ss') {
    if (!datetime) return '-';
    
    const date = new Date(datetime);
    if (isNaN(date.getTime())) return datetime;
    
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    
    return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hours)
        .replace('mm', minutes)
        .replace('ss', seconds);
}

/**
 * 相对时间（多久以前）
 * @param {string} datetime - ISO格式日期时间
 * @returns {string} 相对时间字符串
 */
function timeAgo(datetime) {
    if (!datetime) return '-';
    
    const date = new Date(datetime);
    if (isNaN(date.getTime())) return datetime;
    
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}天前`;
    
    return formatDateTime(datetime, 'MM-DD HH:mm');
}

// ==================== API 请求 ====================

/**
 * 发送 API 请求
 * @param {string} url - 请求URL
 * @param {Object} options - 请求选项
 * @returns {Promise} 请求Promise
 */
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    try {
        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (!response.ok) {
            throw new Error(`请求失败: ${response.status} ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API请求错误:', error);
        throw error;
    }
}

/**
 * GET 请求
 * @param {string} url - 请求URL
 * @returns {Promise}
 */
async function get(url) {
    return apiRequest(url, { method: 'GET' });
}

/**
 * POST 请求
 * @param {string} url - 请求URL
 * @param {Object} data - 请求数据
 * @returns {Promise}
 */
async function post(url, data = {}) {
    return apiRequest(url, {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

// ==================== 数字动画 ====================

/**
 * 数字滚动动画
 * @param {HTMLElement} element - 目标元素
 * @param {number} endValue - 结束值
 * @param {number} duration - 动画时长(毫秒)
 */
function animateNumber(element, endValue, duration = 1000) {
    const startValue = parseFloat(element.textContent) || 0;
    const startTime = performance.now();
    const diff = endValue - startValue;
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // 缓动函数
        const easeProgress = 1 - Math.pow(1 - progress, 3);
        const currentValue = startValue + diff * easeProgress;
        
        element.textContent = Math.round(currentValue);
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

// ==================== 表格排序 ====================

/**
 * 为表格添加排序功能
 * @param {string} tableId - 表格ID
 */
function initTableSort(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    const headers = table.querySelectorAll('th[data-sortable]');
    
    headers.forEach((header, index) => {
        header.style.cursor = 'pointer';
        header.innerHTML += ' <i class="fas fa-sort" style="opacity: 0.3;"></i>';
        
        header.addEventListener('click', () => {
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const isAsc = header.dataset.sortDir !== 'asc';
            
            // 重置其他列的排序状态
            headers.forEach(h => {
                if (h !== header) {
                    h.dataset.sortDir = '';
                    const icon = h.querySelector('i');
                    if (icon) {
                        icon.className = 'fas fa-sort';
                        icon.style.opacity = '0.3';
                    }
                }
            });
            
            // 设置当前列的排序状态
            header.dataset.sortDir = isAsc ? 'asc' : 'desc';
            const icon = header.querySelector('i');
            if (icon) {
                icon.className = isAsc ? 'fas fa-sort-up' : 'fas fa-sort-down';
                icon.style.opacity = '1';
            }
            
            // 排序行
            rows.sort((a, b) => {
                const aVal = a.cells[index].textContent.trim();
                const bVal = b.cells[index].textContent.trim();
                
                // 尝试按数字排序
                const aNum = parseFloat(aVal.replace(/[^\d.-]/g, ''));
                const bNum = parseFloat(bVal.replace(/[^\d.-]/g, ''));
                
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    return isAsc ? aNum - bNum : bNum - aNum;
                }
                
                // 按字符串排序
                return isAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
            });
            
            rows.forEach(row => tbody.appendChild(row));
        });
    });
}

// ==================== 防抖和节流 ====================

/**
 * 防抖函数
 * @param {Function} func - 要执行的函数
 * @param {number} wait - 等待时间
 * @returns {Function}
 */
function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 节流函数
 * @param {Function} func - 要执行的函数
 * @param {number} limit - 时间限制
 * @returns {Function}
 */
function throttle(func, limit = 300) {
    let inThrottle;
    return function executedFunction(...args) {
        if (!inThrottle) {
            func(...args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// ==================== 本地存储 ====================

const Storage = {
    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) {
            console.error('存储失败:', e);
            return false;
        }
    },
    
    get(key, defaultValue = null) {
        try {
            const value = localStorage.getItem(key);
            return value ? JSON.parse(value) : defaultValue;
        } catch (e) {
            console.error('读取失败:', e);
            return defaultValue;
        }
    },
    
    remove(key) {
        try {
            localStorage.removeItem(key);
            return true;
        } catch (e) {
            console.error('删除失败:', e);
            return false;
        }
    }
};

// ==================== 导出功能 ====================

/**
 * 下载文件
 * @param {string} content - 文件内容
 * @param {string} filename - 文件名
 * @param {string} contentType - 文件类型
 */
function downloadFile(content, filename, contentType = 'text/plain') {
    const blob = new Blob([content], { type: contentType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

/**
 * 导出表格为 CSV
 * @param {HTMLTableElement} table - 表格元素
 * @param {string} filename - 文件名
 */
function exportTableToCSV(table, filename) {
    const rows = table.querySelectorAll('tr');
    const csvContent = [];
    
    rows.forEach(row => {
        const cells = row.querySelectorAll('th, td');
        const rowData = [];
        cells.forEach(cell => {
            let text = cell.textContent.trim().replace(/"/g, '""');
            rowData.push(`"${text}"`);
        });
        csvContent.push(rowData.join(','));
    });
    
    downloadFile(csvContent.join('\n'), `${filename}.csv`, 'text/csv;charset=utf-8');
}

// 导出为 Excel (CSV 格式)
function exportToExcel(tableId, filename) {
    const table = document.getElementById(tableId);
    if (table) {
        exportTableToCSV(table, filename);
    }
}
