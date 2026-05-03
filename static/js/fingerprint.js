/**
 * 机器码采集脚本
 * 使用纯JavaScript实现浏览器指纹采集，不依赖外部CDN
 * 生成SHA256哈希作为机器码
 */

// 将字符串转换为UTF-8编码的ArrayBuffer
function stringToBuffer(str) {
    return new TextEncoder().encode(str).buffer;
}

// 使用Web Crypto API计算SHA256哈希
async function sha256(message) {
    const msgBuffer = stringToBuffer(message);
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

// 获取Canvas指纹
function getCanvasFingerprint() {
    try {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 200;
        canvas.height = 50;
        
        // 绘制文字
        ctx.textBaseline = 'top';
        ctx.font = '14px Arial';
        ctx.fillStyle = '#f60';
        ctx.fillRect(125, 1, 62, 20);
        ctx.fillStyle = '#069';
        ctx.fillText('Railway TRS', 2, 15);
        ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
        ctx.fillText('Fingerprint', 4, 17);
        
        // 获取数据URL
        const dataUrl = canvas.toDataURL();
        return dataUrl;
    } catch (e) {
        return 'canvas-error';
    }
}

// 获取WebGL渲染器信息
function getWebGLFingerprint() {
    try {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        
        if (!gl) {
            return 'webgl-not-supported';
        }
        
        const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
        if (debugInfo) {
            const vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
            const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
            return `${vendor}~${renderer}`;
        }
        
        return gl.getParameter(gl.VENDOR) + '~' + gl.getParameter(gl.RENDERER);
    } catch (e) {
        return 'webgl-error';
    }
}

// 获取屏幕信息
function getScreenFingerprint() {
    return `${screen.width}x${screen.height}x${screen.colorDepth}`;
}

// 获取时区
function getTimezone() {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

// 获取语言
function getLanguage() {
    return navigator.language || navigator.userLanguage || 'unknown';
}

// 获取平台
function getPlatform() {
    return navigator.platform || 'unknown';
}

// 获取User Agent关键信息
function getUserAgent() {
    const ua = navigator.userAgent;
    // 提取关键部分，不使用完整UA
    const parts = [];
    
    // 浏览器
    if (ua.includes('Chrome')) parts.push('Chrome');
    else if (ua.includes('Firefox')) parts.push('Firefox');
    else if (ua.includes('Safari')) parts.push('Safari');
    else if (ua.includes('Edge')) parts.push('Edge');
    
    // 操作系统
    if (ua.includes('Windows')) parts.push('Win');
    else if (ua.includes('Mac')) parts.push('Mac');
    else if (ua.includes('Linux')) parts.push('Linux');
    else if (ua.includes('Android')) parts.push('Android');
    else if (ua.includes('iOS')) parts.push('iOS');
    
    return parts.join('|');
}

// 获取已安装插件（简化版）
function getPlugins() {
    try {
        const plugins = [];
        for (let i = 0; i < navigator.plugins.length; i++) {
            plugins.push(navigator.plugins[i].name);
        }
        return plugins.slice(0, 10).join(',');
    } catch (e) {
        return 'plugins-error';
    }
}

// 获取字体列表
function getFonts() {
    const testFonts = [
        'Arial', 'Verdana', 'Times New Roman', 'Courier New', 'Georgia',
        'Comic Sans MS', 'Impact', 'Lucida Console', 'Tahoma', 'Trebuchet MS'
    ];
    const testString = 'mmmmmmmmmmlli';
    const testSize = '72px';
    const baseFonts = ['monospace', 'sans-serif', 'serif'];
    
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    function getWidth(font) {
        ctx.font = `${testSize} ${font}`;
        return ctx.measureText(testString).width;
    }
    
    const baseWidths = baseFonts.map(f => getWidth(f));
    const detected = [];
    
    for (const font of testFonts) {
        let match = false;
        for (let i = 0; i < baseFonts.length; i++) {
            if (getWidth(`'${font}', ${baseFonts[i]}`) !== baseWidths[i]) {
                match = true;
                break;
            }
        }
        if (match) detected.push(font);
    }
    
    return detected.join('|');
}

// 获取Touch支持
function getTouchSupport() {
    return {
        maxTouchPoints: navigator.maxTouchPoints || 0,
        touchEvent: 'ontouchstart' in window,
        touchPoints: navigator.msMaxTouchPoints || 0
    };
}

// 获取硬件并发数
function getHardwareConcurrency() {
    return navigator.hardwareConcurrency || 'unknown';
}

// 综合采集所有指纹信息
async function collectFingerprint() {
    const components = [];
    
    // Canvas指纹
    components.push(getCanvasFingerprint());
    
    // WebGL指纹
    components.push(getWebGLFingerprint());
    
    // 屏幕信息
    components.push(getScreenFingerprint());
    
    // 时区
    components.push(getTimezone());
    
    // 语言
    components.push(getLanguage());
    
    // 平台
    components.push(getPlatform());
    
    // User Agent关键信息
    components.push(getUserAgent());
    
    // 字体
    components.push(getFonts());
    
    // Touch支持
    const touch = getTouchSupport();
    components.push(`${touch.maxTouchPoints}~${touch.touchEvent}~${touch.touchPoints}`);
    
    // 硬件并发
    components.push(String(getHardwareConcurrency()));
    
    // 组合所有信息
    const combined = components.join('||');
    
    // 计算SHA256哈希
    const hash = await sha256(combined);
    
    return hash;
}

// 导出函数
window.Fingerprint = {
    collect: collectFingerprint,
    sha256: sha256
};
