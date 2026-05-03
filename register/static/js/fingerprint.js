/**
 * FingerprintJS - 纯JavaScript实现的机器码采集
 * 不依赖任何外部CDN
 * 
 * 采集以下特征并组合生成32位机器码：
 * - Canvas指纹
 * - WebGL渲染器信息
 * - 屏幕分辨率 + 色深
 * - 时区
 * - 语言
 * - User Agent关键信息
 * - 已安装的字体探测
 */

(function(window) {
    'use strict';

    // SHA256哈希函数
    async function sha256(message) {
        const msgBuffer = new TextEncoder().encode(message);
        const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        return hashHex;
    }

    // 获取Canvas指纹
    function getCanvasFingerprint() {
        try {
            const canvas = document.createElement('canvas');
            canvas.width = 200;
            canvas.height = 50;
            canvas.style.display = 'inline';
            
            const ctx = canvas.getContext('2d');
            
            // 绘制文字
            ctx.textBaseline = 'top';
            ctx.font = '14px Arial';
            ctx.fillStyle = '#f60';
            ctx.fillRect(125, 1, 62, 20);
            
            ctx.fillStyle = '#069';
            ctx.fillText('Fingerprint', 2, 15);
            
            ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
            ctx.fillText('Fingerprint', 4, 17);
            
            // 添加一些图形
            ctx.beginPath();
            ctx.arc(50, 25, 20, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(255, 0, 115, 0.5)';
            ctx.fill();
            
            return canvas.toDataURL();
        } catch (e) {
            return 'canvas-error';
        }
    }

    // 获取WebGL信息
    function getWebGLInfo() {
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
                return vendor + '|' + renderer;
            }
            
            return 'webgl-no-debug-info';
        } catch (e) {
            return 'webgl-error';
        }
    }

    // 获取屏幕信息
    function getScreenInfo() {
        return [
            screen.width,
            screen.height,
            screen.colorDepth,
            screen.pixelDepth
        ].join('x');
    }

    // 获取时区信息
    function getTimezoneInfo() {
        const offset = new Date().getTimezoneOffset();
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        return offset + '|' + tz;
    }

    // 获取语言信息
    function getLanguageInfo() {
        return navigator.language + '|' + navigator.languages.join(',');
    }

    // 获取User Agent关键信息
    function getUserAgentInfo() {
        const ua = navigator.userAgent;
        // 提取关键信息而非完整UA
        const parts = [];
        
        // 浏览器
        if (ua.includes('Chrome')) {
            parts.push('Chrome');
        } else if (ua.includes('Firefox')) {
            parts.push('Firefox');
        } else if (ua.includes('Safari')) {
            parts.push('Safari');
        } else if (ua.includes('Edge')) {
            parts.push('Edge');
        }
        
        // 操作系统
        if (ua.includes('Windows')) {
            parts.push('Windows');
        } else if (ua.includes('Mac')) {
            parts.push('Mac');
        } else if (ua.includes('Linux')) {
            parts.push('Linux');
        } else if (ua.includes('Android')) {
            parts.push('Android');
        } else if (ua.includes('iOS')) {
            parts.push('iOS');
        }
        
        // 平台
        parts.push(navigator.platform);
        
        return parts.join('|');
    }

    // 探测已安装字体
    function getFontFingerprint() {
        const baseFonts = ['monospace', 'sans-serif', 'serif'];
        
        const testFonts = [
            'Arial', 'Arial Black', 'Arial Narrow', 'Calibri', 'Cambria',
            'Comic Sans MS', 'Consolas', 'Courier', 'Courier New',
            'Georgia', 'Helvetica', 'Impact', 'Lucida Console',
            'Lucida Sans Unicode', 'Microsoft Sans Serif', 'Palatino Linotype',
            'Tahoma', 'Times', 'Times New Roman', 'Trebuchet MS',
            'Verdana', 'Wingdings', 'Webdings', 'Symbol',
            'SimSun', 'SimHei', 'Microsoft YaHei', 'FangSong',
            'KaiTi', 'STKaiti', 'STSong', 'STZhongsong',
            'MingLiU', 'PMingLiU', 'DFKai-SB'
        ];
        
        const testString = 'mmmmmmmmmmlli';
        const testSize = '72px';
        
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        function getWidth(font) {
            ctx.font = testSize + ' ' + font;
            return ctx.measureText(testString).width;
        }
        
        const baseWidths = {};
        baseFonts.forEach(function(font) {
            baseWidths[font] = getWidth(font);
        });
        
        const detected = [];
        testFonts.forEach(function(font) {
            let isDetected = false;
            for (const baseFont of baseFonts) {
                const width = getWidth("'" + font + "', " + baseFont);
                if (width !== baseWidths[baseFont]) {
                    isDetected = true;
                    break;
                }
            }
            if (isDetected) {
                detected.push(font);
            }
        });
        
        return detected.slice(0, 15).join(',');
    }

    // 获取触控支持
    function getTouchInfo() {
        const touches = [];
        touches.push(navigator.maxTouchPoints || 0);
        touches.push(navigator.msMaxTouchPoints || 0);
        touches.push('ontouchstart' in window);
        return touches.join('|');
    }

    // 获取硬件并发数
    function getHardwareInfo() {
        const info = [];
        info.push(navigator.hardwareConcurrency || 'unknown');
        info.push(navigator.deviceMemory || 'unknown');
        return info.join('|');
    }

    // 获取插件信息
    function getPluginInfo() {
        const plugins = [];
        if (navigator.plugins) {
            for (let i = 0; i < Math.min(navigator.plugins.length, 5); i++) {
                plugins.push(navigator.plugins[i].name);
            }
        }
        return plugins.join(',');
    }

    // 主函数：生成机器码
    async function getFingerprint() {
        const components = [];
        
        components.push(getCanvasFingerprint());
        components.push(getWebGLInfo());
        components.push(getScreenInfo());
        components.push(getTimezoneInfo());
        components.push(getLanguageInfo());
        components.push(getUserAgentInfo());
        components.push(getFontFingerprint());
        components.push(getTouchInfo());
        components.push(getHardwareInfo());
        components.push(getPluginInfo());
        
        // 添加随机噪声防止完全相同的指纹
        components.push(Math.random().toString());
        components.push(Date.now().toString());
        
        const combined = components.join('###');
        
        const hash = await sha256(combined);
        
        return {
            hash: hash,
            components: {
                canvas: getCanvasFingerprint(),
                webgl: getWebGLInfo(),
                screen: getScreenInfo(),
                timezone: getTimezoneInfo(),
                language: getLanguageInfo(),
                userAgent: getUserAgentInfo(),
                fonts: getFontFingerprint(),
                touch: getTouchInfo(),
                hardware: getHardwareInfo()
            }
        };
    }

    // 回调式接口（兼容旧代码）
    function get(callback) {
        getFingerprint().then(function(result) {
            callback(null, result);
        }).catch(function(error) {
            callback(error, null);
        });
    }

    // 导出到全局
    window.FingerprintJS = {
        get: get,
        getPromise: getFingerprint,
        sha256: sha256
    };

    // 同时支持旧写法
    window.Fingerprint = {
        get: get
    };

})(window);
