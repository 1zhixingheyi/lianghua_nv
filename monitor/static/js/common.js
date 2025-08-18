/**
 * 量化交易监控面板 - 通用JavaScript库
 * 
 * 提供通用的工具函数和基础功能：
 * - 数据格式化
 * - AJAX请求封装
 * - 消息提示
 * - 工具函数
 * - 事件处理
 */

// 全局变量
window.MonitorApp = {
    config: {
        apiBaseUrl: '/api',
        refreshInterval: 30000, // 30秒
        chartColors: [
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', 
            '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
        ],
        dateFormat: 'YYYY-MM-DD HH:mm:ss',
        numberFormat: {
            decimal: 2,
            thousand: ',',
            prefix: '¥'
        }
    },
    
    // 应用状态
    state: {
        isOnline: true,
        lastUpdateTime: null,
        activeFilters: {},
        currentPage: 1,
        itemsPerPage: 20
    },
    
    // 事件回调
    callbacks: {
        onDataUpdate: [],
        onError: [],
        onStatusChange: []
    }
};

/**
 * 数据格式化工具
 */
const DataFormatter = {
    /**
     * 格式化数字
     * @param {number} value - 数值
     * @param {number} decimals - 小数位数
     * @param {boolean} addComma - 是否添加千位分隔符
     * @returns {string} 格式化后的字符串
     */
    formatNumber: function(value, decimals = 2, addComma = true) {
        if (value === null || value === undefined || isNaN(value)) {
            return '0.00';
        }
        
        const num = parseFloat(value);
        const formatted = num.toFixed(decimals);
        
        if (addComma) {
            return formatted.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        }
        
        return formatted;
    },
    
    /**
     * 格式化货币
     * @param {number} value - 数值
     * @param {string} symbol - 货币符号
     * @param {number} decimals - 小数位数
     * @returns {string} 格式化后的货币字符串
     */
    formatCurrency: function(value, symbol = '¥', decimals = 2) {
        const formatted = this.formatNumber(value, decimals);
        return symbol + formatted;
    },
    
    /**
     * 格式化百分比
     * @param {number} value - 数值（0.1 表示 10%）
     * @param {number} decimals - 小数位数
     * @returns {string} 格式化后的百分比字符串
     */
    formatPercentage: function(value, decimals = 2) {
        if (value === null || value === undefined || isNaN(value)) {
            return '0.00%';
        }
        
        const percentage = parseFloat(value) * 100;
        return percentage.toFixed(decimals) + '%';
    },
    
    /**
     * 格式化时间
     * @param {string|Date} value - 时间值
     * @param {string} format - 格式字符串
     * @returns {string} 格式化后的时间字符串
     */
    formatTime: function(value, format = 'YYYY-MM-DD HH:mm:ss') {
        if (!value) return '-';
        
        const date = new Date(value);
        if (isNaN(date.getTime())) return '-';
        
        const now = new Date();
        const diff = now - date;
        
        // 相对时间显示
        if (diff < 60000) { // 1分钟内
            return '刚刚';
        } else if (diff < 3600000) { // 1小时内
            return Math.floor(diff / 60000) + '分钟前';
        } else if (diff < 86400000) { // 24小时内
            return Math.floor(diff / 3600000) + '小时前';
        } else if (diff < 604800000) { // 7天内
            return Math.floor(diff / 86400000) + '天前';
        }
        
        // 绝对时间显示
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
    },
    
    /**
     * 格式化文件大小
     * @param {number} bytes - 字节数
     * @returns {string} 格式化后的文件大小
     */
    formatFileSize: function(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
};

/**
 * AJAX请求封装
 */
const APIClient = {
    /**
     * 发起GET请求
     * @param {string} url - 请求URL
     * @param {Object} params - 查询参数
     * @param {Object} options - 选项
     * @returns {Promise} Promise对象
     */
    get: function(url, params = {}, options = {}) {
        const queryString = new URLSearchParams(params).toString();
        const fullUrl = queryString ? `${url}?${queryString}` : url;
        
        return this.request(fullUrl, {
            method: 'GET',
            ...options
        });
    },
    
    /**
     * 发起POST请求
     * @param {string} url - 请求URL
     * @param {Object} data - 请求数据
     * @param {Object} options - 选项
     * @returns {Promise} Promise对象
     */
    post: function(url, data = {}, options = {}) {
        return this.request(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: JSON.stringify(data),
            ...options
        });
    },
    
    /**
     * 发起PUT请求
     * @param {string} url - 请求URL
     * @param {Object} data - 请求数据
     * @param {Object} options - 选项
     * @returns {Promise} Promise对象
     */
    put: function(url, data = {}, options = {}) {
        return this.request(url, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: JSON.stringify(data),
            ...options
        });
    },
    
    /**
     * 发起DELETE请求
     * @param {string} url - 请求URL
     * @param {Object} options - 选项
     * @returns {Promise} Promise对象
     */
    delete: function(url, options = {}) {
        return this.request(url, {
            method: 'DELETE',
            ...options
        });
    },
    
    /**
     * 基础请求方法
     * @param {string} url - 请求URL
     * @param {Object} options - fetch选项
     * @returns {Promise} Promise对象
     */
    request: function(url, options = {}) {
        const defaultOptions = {
            timeout: 30000,
            credentials: 'same-origin'
        };
        
        const mergedOptions = { ...defaultOptions, ...options };
        
        // 超时处理
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('请求超时')), mergedOptions.timeout);
        });
        
        const fetchPromise = fetch(url, mergedOptions)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .catch(error => {
                console.error('API请求错误:', error);
                MonitorApp.state.isOnline = false;
                this.triggerCallback('onError', error);
                throw error;
            });
        
        return Promise.race([fetchPromise, timeoutPromise]);
    },
    
    /**
     * 触发回调
     * @param {string} event - 事件名称
     * @param {*} data - 数据
     */
    triggerCallback: function(event, data) {
        if (MonitorApp.callbacks[event]) {
            MonitorApp.callbacks[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error('回调执行错误:', error);
                }
            });
        }
    }
};

/**
 * 消息提示工具
 */
const MessageBox = {
    /**
     * 显示成功消息
     * @param {string} message - 消息内容
     * @param {number} duration - 显示时长（毫秒）
     */
    success: function(message, duration = 3000) {
        this.show(message, 'success', duration);
    },
    
    /**
     * 显示错误消息
     * @param {string} message - 消息内容
     * @param {number} duration - 显示时长（毫秒）
     */
    error: function(message, duration = 5000) {
        this.show(message, 'danger', duration);
    },
    
    /**
     * 显示警告消息
     * @param {string} message - 消息内容
     * @param {number} duration - 显示时长（毫秒）
     */
    warning: function(message, duration = 4000) {
        this.show(message, 'warning', duration);
    },
    
    /**
     * 显示信息消息
     * @param {string} message - 消息内容
     * @param {number} duration - 显示时长（毫秒）
     */
    info: function(message, duration = 3000) {
        this.show(message, 'info', duration);
    },
    
    /**
     * 显示消息
     * @param {string} message - 消息内容
     * @param {string} type - 消息类型
     * @param {number} duration - 显示时长（毫秒）
     */
    show: function(message, type = 'info', duration = 3000) {
        // 移除现有的消息
        $('.alert').remove();
        
        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show position-fixed" 
                 style="top: 80px; right: 20px; z-index: 9999; min-width: 300px;">
                <i class="fas ${this.getIcon(type)} me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        $('body').append(alertHtml);
        
        // 自动消失
        if (duration > 0) {
            setTimeout(() => {
                $('.alert').alert('close');
            }, duration);
        }
    },
    
    /**
     * 获取图标
     * @param {string} type - 消息类型
     * @returns {string} 图标类名
     */
    getIcon: function(type) {
        const icons = {
            'success': 'fa-check-circle',
            'danger': 'fa-times-circle',
            'warning': 'fa-exclamation-triangle',
            'info': 'fa-info-circle'
        };
        return icons[type] || 'fa-info-circle';
    },
    
    /**
     * 确认对话框
     * @param {string} message - 消息内容
     * @param {Function} callback - 确认回调
     * @param {string} title - 标题
     */
    confirm: function(message, callback, title = '确认操作') {
        if (confirm(title + '\n\n' + message)) {
            callback();
        }
    }
};

/**
 * 加载状态管理
 */
const LoadingManager = {
    loadingCount: 0,
    
    /**
     * 显示加载状态
     */
    show: function() {
        this.loadingCount++;
        $('#loadingOverlay').show();
    },
    
    /**
     * 隐藏加载状态
     */
    hide: function() {
        this.loadingCount = Math.max(0, this.loadingCount - 1);
        
        if (this.loadingCount === 0) {
            $('#loadingOverlay').hide();
        }
    },
    
    /**
     * 强制隐藏
     */
    forceHide: function() {
        this.loadingCount = 0;
        $('#loadingOverlay').hide();
    }
};

/**
 * 工具函数
 */
const Utils = {
    /**
     * 防抖函数
     * @param {Function} func - 要执行的函数
     * @param {number} wait - 等待时间
     * @returns {Function} 防抖后的函数
     */
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    /**
     * 节流函数
     * @param {Function} func - 要执行的函数
     * @param {number} limit - 时间限制
     * @returns {Function} 节流后的函数
     */
    throttle: function(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },
    
    /**
     * 深度克隆对象
     * @param {*} obj - 要克隆的对象
     * @returns {*} 克隆后的对象
     */
    deepClone: function(obj) {
        if (obj === null || typeof obj !== 'object') {
            return obj;
        }
        
        if (obj instanceof Date) {
            return new Date(obj.getTime());
        }
        
        if (obj instanceof Array) {
            return obj.map(item => this.deepClone(item));
        }
        
        const cloned = {};
        for (let key in obj) {
            if (obj.hasOwnProperty(key)) {
                cloned[key] = this.deepClone(obj[key]);
            }
        }
        
        return cloned;
    },
    
    /**
     * 生成唯一ID
     * @returns {string} 唯一ID
     */
    generateId: function() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    },
    
    /**
     * 检测设备类型
     * @returns {string} 设备类型
     */
    detectDevice: function() {
        const userAgent = navigator.userAgent;
        if (/tablet|ipad|playbook|silk/i.test(userAgent)) {
            return 'tablet';
        }
        if (/mobile|iphone|ipod|android|blackberry|opera|mini|windows\sce|palm|smartphone|iemobile/i.test(userAgent)) {
            return 'mobile';
        }
        return 'desktop';
    },
    
    /**
     * 获取URL参数
     * @param {string} name - 参数名
     * @returns {string|null} 参数值
     */
    getUrlParameter: function(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    },
    
    /**
     * 设置URL参数
     * @param {string} name - 参数名
     * @param {string} value - 参数值
     */
    setUrlParameter: function(name, value) {
        const url = new URL(window.location);
        url.searchParams.set(name, value);
        window.history.replaceState({}, '', url);
    }
};

/**
 * 本地存储管理
 */
const StorageManager = {
    /**
     * 设置本地存储
     * @param {string} key - 键名
     * @param {*} value - 值
     */
    set: function(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            console.error('本地存储设置失败:', error);
        }
    },
    
    /**
     * 获取本地存储
     * @param {string} key - 键名
     * @param {*} defaultValue - 默认值
     * @returns {*} 存储的值
     */
    get: function(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (error) {
            console.error('本地存储读取失败:', error);
            return defaultValue;
        }
    },
    
    /**
     * 移除本地存储
     * @param {string} key - 键名
     */
    remove: function(key) {
        try {
            localStorage.removeItem(key);
        } catch (error) {
            console.error('本地存储移除失败:', error);
        }
    },
    
    /**
     * 清空本地存储
     */
    clear: function() {
        try {
            localStorage.clear();
        } catch (error) {
            console.error('本地存储清空失败:', error);
        }
    }
};

/**
 * 事件管理器
 */
const EventManager = {
    events: {},
    
    /**
     * 注册事件监听器
     * @param {string} event - 事件名
     * @param {Function} callback - 回调函数
     */
    on: function(event, callback) {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(callback);
    },
    
    /**
     * 移除事件监听器
     * @param {string} event - 事件名
     * @param {Function} callback - 回调函数
     */
    off: function(event, callback) {
        if (this.events[event]) {
            this.events[event] = this.events[event].filter(cb => cb !== callback);
        }
    },
    
    /**
     * 触发事件
     * @param {string} event - 事件名
     * @param {*} data - 事件数据
     */
    emit: function(event, data) {
        if (this.events[event]) {
            this.events[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error('事件回调执行错误:', error);
                }
            });
        }
    }
};

// 全局函数别名
window.formatNumber = DataFormatter.formatNumber;
window.formatCurrency = DataFormatter.formatCurrency;
window.formatPercentage = DataFormatter.formatPercentage;
window.formatTime = DataFormatter.formatTime;
window.showSuccess = MessageBox.success;
window.showError = MessageBox.error;
window.showWarning = MessageBox.warning;
window.showInfo = MessageBox.info;
window.showLoading = LoadingManager.show;
window.hideLoading = LoadingManager.hide;

// 页面加载完成后的初始化
$(document).ready(function() {
    // 设置AJAX默认设置
    $.ajaxSetup({
        beforeSend: function() {
            LoadingManager.show();
        },
        complete: function() {
            LoadingManager.hide();
        },
        error: function(xhr, status, error) {
            console.error('AJAX错误:', status, error);
            if (xhr.status === 0) {
                MessageBox.error('网络连接失败，请检查网络状态');
            } else if (xhr.status === 404) {
                MessageBox.error('请求的资源不存在');
            } else if (xhr.status === 500) {
                MessageBox.error('服务器内部错误');
            } else {
                MessageBox.error('请求失败: ' + error);
            }
        }
    });
    
    // 启用工具提示
    $('[data-bs-toggle="tooltip"]').tooltip();
    
    // 启用弹出框
    $('[data-bs-toggle="popover"]').popover();
    
    // 添加全局键盘快捷键
    $(document).keydown(function(e) {
        // Ctrl+R 刷新页面
        if (e.ctrlKey && e.keyCode === 82) {
            e.preventDefault();
            location.reload();
        }
        
        // ESC 关闭模态框
        if (e.keyCode === 27) {
            $('.modal').modal('hide');
        }
    });
    
    console.log('监控面板通用库已初始化');
});