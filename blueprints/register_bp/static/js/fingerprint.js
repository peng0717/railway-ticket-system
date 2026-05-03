/**
 * 浏览器指纹（机器码）采集脚本
 * 使用纯JavaScript实现浏览器指纹采集，不依赖外部CDN
 * 生成SHA256哈希作为机器码
 * 
 * ============================================
 * 机器码识别原理说明
 * ============================================
 * 
 * 机器码是通过采集浏览器的多个硬件和软件特征，组合计算出的唯一标识。
 * 同一台电脑同一个浏览器，生成的机器码始终相同。
 * 换一台电脑或换一个浏览器，机器码就会不同。
 * 
 * 采集的特征包括：
 * 1. Canvas指纹 - 浏览器渲染图形的微小差异（GPU、驱动、抗锯齿算法不同）
 * 2. WebGL指纹 - 显卡型号、渲染器信息
 * 3. 屏幕分辨率 - 物理像素比、色深
 * 4. 时区信息 - 系统时区偏移
 * 5. 系统字体 - 安装的字体列表（通过测量字符宽度间接检测）
 * 6. UserAgent - 浏览器版本、操作系统
 * 7. 语言设置 - 浏览器首选语言
 * 8. 平台信息 - 操作系统类型
 * 
 * 这些特征组合在一起，通过SHA-256哈希算法生成64位十六进制字符串，
 * 作为该设备的唯一标识（机器码）。
 * 
 * 安全说明：
 * - 机器码不包含任何个人隐私信息
 * - 无法从机器码反推出具体硬件信息
 * - 仅用于检测"同一工号是否在不同设备上登录"
 * - 如果售票员换了电脑或浏览器，需要管理员重新解冻
 * 
 * ============================================
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
    components.push(`${touch.maxTouchPoints}|${touch.touchEvent}|${touch.touchPoints}`);
    
    // 硬件并发数
    components.push(getHardwareConcurrency().toString());
    
    // 组合所有组件
    const combined = components.join('###');
    
    // 计算SHA256哈希
    const hash = await sha256(combined);
    
    return hash;
}

// 缓存机器码
let cachedMachineCode = null;

// 获取机器码（带缓存）
async function getMachineCode() {
    if (cachedMachineCode) {
        return cachedMachineCode;
    }
    
    cachedMachineCode = await collectFingerprint();
    return cachedMachineCode;
}

// 页面加载时预采集机器码
document.addEventListener('DOMContentLoaded', function() {
    getMachineCode();
});
