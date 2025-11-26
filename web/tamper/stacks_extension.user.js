// ==UserScript==
// @name         Stacks - Anna's Archive Downloader
// @namespace    http://tampermonkey.net/
// @version      1.1.0
// @description  Add download buttons to Anna's Archive that queue downloads to Stacks server
// @author       Zelest Carlyone
// @match        https://annas-archive.org/*
// @icon         https://annas-archive.org/favicon.ico
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        GM_addStyle
// @connect      localhost
// @connect      127.0.0.1
// @connect      *
// ==/UserScript==

(function () {
    'use strict';

    // ============================================================
    // CONFIGURATION
    // ============================================================

    const DEFAULT_SERVER_URL = 'http://localhost:7788';
    const SCRIPT_VERSION = GM_info.script.version;

    const CONFIG = {
        serverUrl: DEFAULT_SERVER_URL,
        apiKey: '',
        showNotifications: true,
    };

    function reloadConfig() {
        CONFIG.serverUrl = GM_getValue('stacksServerUrl', DEFAULT_SERVER_URL);
        CONFIG.apiKey = GM_getValue('stacksApiKey', '');
        CONFIG.showNotifications = GM_getValue('stacksShowNotifications', true);
    }

    reloadConfig();

    // ============================================================
    // STYLES (Dracula theme + toast notifications)
    // ============================================================

    GM_addStyle(`
        /* Settings overlay + dialog */
        #stacks-settings-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.7);
            z-index: 10000;
        }

        #stacks-settings-dialog {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #282a36 !important;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            z-index: 10001;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 500px;
            width: 90%;
            border: 4px solid #bd93f9 !important;
        }

        #stacks-settings-dialog h2 {
            margin: 0 0 20px 0;
            color: #f8f8f2 !important;
            font-size: 20px;
        }

        #stacks-settings-dialog label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #8be9fd !important;
        }

        #stacks-settings-dialog input[type="text"],
        #stacks-settings-dialog input[type="password"] {
            width: 100%;
            padding: 10px;
            border: 2px solid #44475a !important;
            border-radius: 4px;
            font-size: 14px;
            font-family: monospace;
            background: #181a26 !important;
            color: #f8f8f2 !important;
        }

        #stacks-settings-dialog input[type="text"]:focus,
        #stacks-settings-dialog input[type="password"]:focus {
            outline: none;
            border-color: #bd93f9 !important;
        }

        #stacks-settings-dialog .stacks-settings-footer {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 10px;
        }

        #stacks-settings-dialog button {
            padding: 10px 20px;
            border-radius: 4px;
            border: none;
            cursor: pointer;
            font-size: 14px;
            transition: opacity 0.2s;
        }

        #stacks-settings-dialog button:hover {
            opacity: 0.8;
        }

        #stacks-settings-dialog button#cancelSettings {
            background: #6272a4 !important;
            color: #f8f8f2 !important;
        }

        #stacks-settings-dialog button#saveSettings {
            background: #50fa7b !important;
            color: #282a36 !important;
        }

        #stacks-settings-dialog button#testConnection {
            padding: 6px 12px;
            font-size: 13px;
            background: #8be9fd !important;
            color: #282a36 !important;
        }

        /* Connection info box */
        #stacks-settings-dialog .stacks-connection-box {
            margin-bottom: 20px;
            padding: 15px;
            background: #181a26 !important;
            border-left: 4px solid #8be9fd !important;
            border-radius: 4px;
            font-size: 13px;
            color: #6272a4 !important;
        }

        #stacks-settings-dialog .stacks-settings-examples {
            margin-top: 8px;
            font-size: 12px;
            color: #6272a4 !important;
        }

        #stacks-settings-dialog .stacks-settings-examples code {
            background: #181a26 !important;
            padding: 2px 6px;
            border-radius: 3px;
            color: #50fa7b !important;
        }

        /* Toast notifications (matching main site) */
        #stacks-toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            gap: 10px;
            pointer-events: none;
        }

        .stacks-toast {
            display: flex;
            align-items: center;
            gap: 12px;
            min-width: 320px;
            max-width: 420px;
            padding: 16px;
            background: #282a36 !important;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            pointer-events: all;
            transform: translateX(400px);
            opacity: 0;
            transition: transform 0.3s ease-in-out, opacity 0.3s ease-in-out;
            position: relative;
            border: 1px solid #44475a !important;
        }

        .stacks-toast.show {
            transform: translateY(0);
            opacity: 1;
        }

        .stacks-toast.hide {
            transform: translateX(400px);
            opacity: 0;
        }

        .stacks-toast-success {
            border-left: 7px solid #50fa7b !important;
        }

        .stacks-toast-success .stacks-toast-progress {
            background: #50fa7b !important;
        }

        .stacks-toast-error {
            border-left: 7px solid #ff5555 !important;
        }

        .stacks-toast-error .stacks-toast-progress {
            background: #ff5555 !important;
        }

        .stacks-toast-warning {
            border-left: 7px solid #ffb86c !important;
        }

        .stacks-toast-warning .stacks-toast-progress {
            background: #ffb86c !important;
        }

        .stacks-toast-info {
            border-left: 7px solid #8be9fd !important;
        }

        .stacks-toast-info .stacks-toast-progress {
            background: #8be9fd !important;
        }

        .stacks-toast-icon {
            flex-shrink: 0;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            color: #f8f8f2 !important;
        }

        .stacks-toast-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .stacks-toast-title {
            font-weight: 600;
            font-size: 14px;
            color: #f8f8f2 !important;
            line-height: 1.4;
        }

        .stacks-toast-message {
            font-size: 13px;
            color: #f8f8f2 !important;
            line-height: 1.4;
        }

        .stacks-toast-message a {
            color: inherit !important;
        }

        .stacks-toast-close {
            flex-shrink: 0;
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: none;
            border: none;
            cursor: pointer;
            color: #6272a4 !important;
            font-size: 18px;
            line-height: 1;
            padding: 0;
            transition: color 0.2s;
        }

        .stacks-toast-close:hover {
            color: #f8f8f2 !important;
        }

        .stacks-toast-progress {
            position: absolute;
            bottom: 0;
            left: 0;
            height: 3px;
            width: 100%;
            border-radius: 0 8px 0 8px;
        }

        /* Update banner (using Dracula purple gradient) */
        #stacks-update-banner {
            border-left: 7px solid #bd93f9 !important;
        }

        #stacks-update-banner .stacks-toast-progress {
            background: #bd93f9 !important;
        }

        #stacks-update-banner .stacks-update-link {
            display: inline-block;
            background: #bd93f9 !important;
            color: #282a36 !important;
            padding: 6px 14px;
            border-radius: 4px;
            text-decoration: none !important;
            font-size: 13px;
            font-weight: 600;
            transition: opacity 0.2s;
            margin-top: 8px;
        }

        #stacks-update-banner .stacks-update-link:hover {
            opacity: 0.8 !important;
        }

        /* Button micro-animations */
        .stacks-btn {
            transition: opacity 0.2s, transform 0.1s;
        }
        .stacks-btn:hover {
            opacity: 0.8;
            transform: scale(1.05);
        }
        .stacks-btn:active {
            transform: scale(0.95);
        }
    `);

    // ============================================================
    // UTILITIES
    // ============================================================

    const MD5_REGEX = /\/md5\/([A-Fa-f0-9]{32})(?=$|[/?#])/;

    function extractMD5(url) {
        const match = MD5_REGEX.exec(url);
        return match ? match[1].toLowerCase() : null;
    }

    function compareVersions(v1, v2) {
        // Returns: 1 if v1 > v2, -1 if v1 < v2, 0 if equal
        const parts1 = v1.split('.').map(Number);
        const parts2 = v2.split('.').map(Number);

        for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
            const p1 = parts1[i] || 0;
            const p2 = parts2[i] || 0;
            if (p1 > p2) return 1;
            if (p1 < p2) return -1;
        }
        return 0;
    }

    // ============================================================
    // TOAST NOTIFICATION SYSTEM (matching main site)
    // ============================================================

    function getToastContainer() {
        let container = document.getElementById('stacks-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'stacks-toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    function showToast({ title = '', message = '', type = 'info', timeout = 4000 }) {
        if (!CONFIG.showNotifications) return;

        const container = getToastContainer();

        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ',
        };

        const toast = document.createElement('div');
        toast.className = `stacks-toast stacks-toast-${type}`;
        toast.innerHTML = `
            <div class="stacks-toast-icon">${icons[type] || icons.info}</div>
            <div class="stacks-toast-content">
                ${title ? `<div class="stacks-toast-title">${title}</div>` : ''}
                <div class="stacks-toast-message">${message}</div>
            </div>
            <button class="stacks-toast-close">×</button>
            <div class="stacks-toast-progress"></div>
        `;

        container.appendChild(toast);

        // Close button
        toast.querySelector('.stacks-toast-close').addEventListener('click', () => {
            removeToast(toast);
        });

        // Animate in
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                toast.classList.add('show');
                const progress = toast.querySelector('.stacks-toast-progress');
                progress.style.transition = `width ${timeout}ms linear`;
                progress.style.width = '0%';
            });
        });

        // Auto-remove
        setTimeout(() => removeToast(toast), timeout);
    }

    function removeToast(toast) {
        toast.classList.remove('show');
        toast.classList.add('hide');
        const handler = (e) => {
            if (e.target === toast) {
                toast.remove();
                toast.removeEventListener('transitionend', handler);
            }
        };
        toast.addEventListener('transitionend', handler);
    }

    // ============================================================
    // VERSION CHECK
    // ============================================================

    async function checkForUpdates() {
        console.log('%c🔍 Stacks: Checking for updates...', 'color: #bd93f9;');
        console.log(`   Current version: ${SCRIPT_VERSION}`);

        // Don't check if already dismissed this version
        const dismissedVersion = localStorage.getItem('stacks-dismissed-version');
        if (dismissedVersion === SCRIPT_VERSION) {
            console.log(`   ⏭️ Update dismissed for version ${SCRIPT_VERSION}`);
            return;
        }

        try {
            const result = await apiRequest({
                method: 'GET',
                path: '/api/version',
                timeout: 5000,
            });

            console.log('   API Response:', result);

            if (result.status === 200 && result.data && result.data.tamper_version) {
                const serverVersion = result.data.tamper_version;
                console.log(`   Server version: ${serverVersion}`);

                const comparison = compareVersions(serverVersion, SCRIPT_VERSION);
                console.log(`   Version comparison result: ${comparison} (1=newer, 0=same, -1=older)`);

                if (comparison > 0) {
                    console.log(`   ✅ Update available! Showing banner...`);
                    showUpdateBanner(serverVersion);
                } else {
                    console.log('   ✅ Script is up to date');
                }
            } else {
                console.log('   ⚠️ Invalid response or missing tamper_version');
            }
        } catch (err) {
            console.log('%c⚠️ Stacks: Version check failed:', 'color: #ff5555;', err.message);
        }
    }

    function showUpdateBanner(newVersion) {
        // Don't show if already exists
        if (document.getElementById('stacks-update-banner')) {
            return;
        }

        const container = getToastContainer();

        const banner = document.createElement('div');
        banner.id = 'stacks-update-banner';
        banner.className = 'stacks-toast stacks-toast-info';
        banner.innerHTML = `
            <div class="stacks-toast-icon">🔔</div>
            <div class="stacks-toast-content">
                <div class="stacks-toast-title">Stacks Update Available!</div>
                <div class="stacks-toast-message">
                    Version ${newVersion} is available. You're running ${SCRIPT_VERSION}.
                    <a href="${CONFIG.serverUrl}" target="_blank" class="stacks-update-link">Update Now</a>
                </div>
            </div>
            <button class="stacks-toast-close">×</button>
            <div class="stacks-toast-progress"></div>
        `;

        container.appendChild(banner);

        // Close button
        banner.querySelector('.stacks-toast-close').addEventListener('click', () => {
            removeToast(banner);
            localStorage.setItem('stacks-dismissed-version', SCRIPT_VERSION);
        });

        // Animate in
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                banner.classList.add('show');
                const progress = banner.querySelector('.stacks-toast-progress');
                progress.style.transition = 'width 30000ms linear';
                progress.style.width = '0%';
            });
        });

        // Auto-dismiss after 30 seconds
        setTimeout(() => removeToast(banner), 30000);
    }

    // ============================================================
    // API REQUEST HELPER
    // ============================================================

    function apiRequest({ method = 'GET', path = '/', body = null, baseUrl, apiKey, timeout = 15000 }) {
        const urlBase = baseUrl || CONFIG.serverUrl;
        const key = apiKey || CONFIG.apiKey;

        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method,
                url: urlBase.replace(/\/+$/, '') + path,
                headers: {
                    'X-API-Key': key,
                    'Content-Type': 'application/json',
                },
                data: body ? JSON.stringify(body) : undefined,
                timeout,
                onload: (response) => {
                    let data = null;
                    try {
                        if (response.responseText) {
                            data = JSON.parse(response.responseText);
                        }
                    } catch (e) {
                        // ignore
                    }
                    resolve({
                        status: response.status,
                        statusText: response.statusText,
                        data,
                        raw: response,
                    });
                },
                onerror: () => {
                    reject(new Error('Failed to connect to Stacks server'));
                },
                ontimeout: () => {
                    reject(new Error('Request timed out'));
                },
            });
        });
    }

    // ============================================================
    // SETTINGS DIALOG & MENU COMMANDS
    // ============================================================

    GM_registerMenuCommand('⚙️ Stacks Settings', showSettingsDialog);
    GM_registerMenuCommand('🔄 Reset to Default Server', resetToDefault);

    function showSettingsDialog() {
        const currentUrl = GM_getValue('stacksServerUrl', DEFAULT_SERVER_URL);
        const currentApiKey = GM_getValue('stacksApiKey', '');
        const currentNotifications = GM_getValue('stacksShowNotifications', true);

        // Overlay
        const overlay = document.createElement('div');
        overlay.id = 'stacks-settings-overlay';

        // Dialog
        const dialog = document.createElement('div');
        dialog.id = 'stacks-settings-dialog';

        dialog.innerHTML = `
            <h2 style="margin:0 0 20px 0;color:#f8f8f2 !important;font-size:20px;">⚙️ Stacks Settings</h2>

            <div style="margin-bottom: 20px;">
                <label for="stacksServerUrl" style="display:block;margin-bottom:8px;font-weight:600;color:#8be9fd !important;">Server URL:</label>
                <input type="text"
                       id="stacksServerUrl"
                       value="${currentUrl}"
                       placeholder="http://your-server:7788"
                       style="width:100%;padding:10px;border:2px solid #44475a !important;border-radius:4px;font-size:14px;font-family:monospace;background:#181a26 !important;color:#f8f8f2 !important;">
                <div style="margin-top:8px;font-size:12px;color:#6272a4 !important;">
                    Examples:<br>
                    • Local: <code style="background:#181a26 !important;padding:2px 6px;border-radius:3px;color:#50fa7b !important;">http://localhost:7788</code><br>
                    • Network: <code style="background:#181a26 !important;padding:2px 6px;border-radius:3px;color:#50fa7b !important;">http://192.168.1.100:7788</code><br>
                    • Remote: <code style="background:#181a26 !important;padding:2px 6px;border-radius:3px;color:#50fa7b !important;">http://yourdomain.com:7788</code>
                </div>
            </div>

            <div style="margin-bottom: 20px;">
                <label for="stacksApiKey" style="display:block;margin-bottom:8px;font-weight:600;color:#8be9fd !important;">API Key:</label>
                <input type="password"
                       id="stacksApiKey"
                       value="${currentApiKey}"
                       placeholder="Your 32-character API key"
                       style="width:100%;padding:10px;border:2px solid #44475a !important;border-radius:4px;font-size:14px;font-family:monospace;background:#181a26 !important;color:#f8f8f2 !important;">
                <div style="margin-top:8px;font-size:12px;color:#6272a4 !important;">
                    <strong>📍 Find your API key:</strong>
                    Open Stacks web interface → Settings tab → API Key section (click Copy).
                </div>
            </div>

            <div style="margin-bottom: 25px;">
                <label style="display:flex;align-items:center;cursor:pointer;">
                    <input type="checkbox"
                           id="stacksShowNotifications"
                           ${currentNotifications ? 'checked' : ''}
                           style="margin-right:8px;width:18px;height:18px;cursor:pointer;">
                    <span style="color:#f8f8f2 !important;font-weight:600;">Show notifications</span>
                </label>
            </div>

            <div style="margin-bottom:20px;padding:15px;background:#181a26 !important;border-left:4px solid #8be9fd !important;border-radius:4px;font-size:13px;color:#6272a4 !important;">
                <div style="font-weight:600;color:#8be9fd !important;margin-bottom:5px;">💡 Connection Test</div>
                <div id="connectionStatus" style="color:#6272a4 !important;">
                    Click "Test Connection" to verify
                </div>
                <button id="testConnection" style="margin-top:10px;padding:6px 12px;font-size:13px;background:#8be9fd !important;color:#282a36 !important;border:none;border-radius:4px;cursor:pointer;">Test Connection</button>
            </div>

            <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:10px;">
                <button id="cancelSettings" style="padding:10px 20px;border-radius:4px;border:none;cursor:pointer;font-size:14px;background:#6272a4 !important;color:#f8f8f2 !important;">Cancel</button>
                <button id="saveSettings" style="padding:10px 20px;border-radius:4px;border:none;cursor:pointer;font-size:14px;background:#50fa7b !important;color:#282a36 !important;">Save Settings</button>
            </div>
        `;

        document.body.appendChild(overlay);
        document.body.appendChild(dialog);

        const serverInput = dialog.querySelector('#stacksServerUrl');
        const apiKeyInput = dialog.querySelector('#stacksApiKey');
        const notificationsInput = dialog.querySelector('#stacksShowNotifications');
        const statusDiv = dialog.querySelector('#connectionStatus');
        const testBtn = dialog.querySelector('#testConnection');

        // Add focus handlers for inputs
        [serverInput, apiKeyInput].forEach(input => {
            input.addEventListener('focus', () => {
                input.style.borderColor = '#bd93f9';
                input.style.outline = 'none';
            });
            input.addEventListener('blur', () => {
                input.style.borderColor = '#44475a';
            });
        });

        // Add hover handlers for buttons
        [testBtn, dialog.querySelector('#cancelSettings'), dialog.querySelector('#saveSettings')].forEach(btn => {
            btn.addEventListener('mouseenter', () => {
                btn.style.opacity = '0.8';
            });
            btn.addEventListener('mouseleave', () => {
                btn.style.opacity = '1';
            });
        });

        function closeDialog() {
            overlay.remove();
            dialog.remove();
            document.removeEventListener('keydown', onKeyDown);
        }

        function onKeyDown(e) {
            if (e.key === 'Escape') {
                closeDialog();
            }
        }

        overlay.addEventListener('click', closeDialog);
        dialog.querySelector('#cancelSettings').addEventListener('click', closeDialog);
        document.addEventListener('keydown', onKeyDown);

        // Test connection
        testBtn.addEventListener('click', async () => {
            const testUrl = serverInput.value.trim();
            const testApiKey = apiKeyInput.value.trim();

            if (!testApiKey) {
                statusDiv.innerHTML = `❌ <strong>API key required</strong><br>Get it from Stacks web interface → Settings`;
                statusDiv.style.color = '#ff5555';
                return;
            }

            testBtn.disabled = true;
            testBtn.textContent = 'Testing...';
            statusDiv.textContent = 'Connecting...';
            statusDiv.style.color = '#6272a4';

            try {
                const result = await apiRequest({
                    method: 'GET',
                    path: '/api/status',
                    baseUrl: testUrl,
                    apiKey: testApiKey,
                    timeout: 7788,
                });

                if (result.status === 401 || result.status === 403) {
                    statusDiv.innerHTML = `❌ <strong>Invalid API key</strong><br>Check your API key in Stacks → Settings`;
                    statusDiv.style.color = '#ff5555';
                } else if (result.status === 200 && result.data) {
                    const { queue_size, recent_history } = result.data;
                    const historyCount = Array.isArray(recent_history) ? recent_history.length : 0;
                    statusDiv.innerHTML = `✅ <strong>Connected!</strong><br>Queue: ${queue_size}, History: ${historyCount} items`;
                    statusDiv.style.color = '#50fa7b';
                } else {
                    statusDiv.innerHTML = `❌ <strong>Error ${result.status}</strong><br>${result.statusText || 'Unknown error'}`;
                    statusDiv.style.color = '#ff5555';
                }
            } catch (err) {
                statusDiv.innerHTML = `❌ <strong>Connection failed</strong><br>${err.message}`;
                statusDiv.style.color = '#ff5555';
            } finally {
                testBtn.disabled = false;
                testBtn.textContent = 'Test Connection';
            }
        });

        // Save
        dialog.querySelector('#saveSettings').addEventListener('click', () => {
            const newUrl = serverInput.value.trim();
            const newApiKey = apiKeyInput.value.trim();
            const newNotifications = notificationsInput.checked;

            if (!newUrl) {
                alert('Please enter a server URL');
                return;
            }

            if (!newApiKey) {
                alert(
                    'Please enter an API key\n\n' +
                    'Get it from: Stacks web interface → Settings tab → API Key section'
                );
                return;
            }

            GM_setValue('stacksServerUrl', newUrl);
            GM_setValue('stacksApiKey', newApiKey);
            GM_setValue('stacksShowNotifications', newNotifications);

            reloadConfig();

            closeDialog();
            showToast({
                title: 'Settings Saved',
                message: 'Refresh the page to apply changes.',
                type: 'success',
            });
        });
    }

    function resetToDefault() {
        if (confirm(`Reset server URL to:\n${DEFAULT_SERVER_URL}\n\nYou'll need to re-enter your API key.`)) {
            GM_setValue('stacksServerUrl', DEFAULT_SERVER_URL);
            GM_setValue('stacksApiKey', '');
            GM_setValue('stacksShowNotifications', true);
            reloadConfig();
            alert('Settings reset! Please configure your API key in settings.');
        }
    }

    // ============================================================
    // API: Add to queue
    // ============================================================

    async function addToQueue(md5, source = 'browser') {
        if (!CONFIG.apiKey) {
            throw new Error(
                '⚠️ API key not configured.\n\n' +
                'Get your API key from:\n' +
                'Stacks web interface → Settings tab → API Key section\n\n' +
                'Then configure it here:\n' +
                'Tampermonkey icon → Stacks Settings'
            );
        }

        const result = await apiRequest({
            method: 'POST',
            path: '/api/queue/add',
            body: { md5, source },
        });

        if (result.status === 401 || result.status === 403) {
            throw new Error('Invalid API key. Get a new key from Stacks web interface → Settings.');
        }

        if (result.status !== 200 || !result.data) {
            throw new Error(`Failed with status ${result.status}: ${result.statusText || 'Unknown error'}`);
        }

        return result.data;
    }

    // ============================================================
    // BUTTON CREATION
    // ============================================================

    function createDownloadButton(md5) {
        const btn = document.createElement('a');
        btn.href = '#';
        btn.className = 'custom-a text-[#2563eb] inline-block outline-offset-[-2px] outline-2 rounded-[3px] focus:outline font-semibold text-sm leading-none hover:opacity-80 relative stacks-btn';
        btn.innerHTML = '<span class="text-[15px] align-text-bottom inline-block icon-[typcn--download] mr-[1px]"></span>Download';
        btn.title = 'Add to Stacks queue';

        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();

            const originalText = btn.innerHTML;
            btn.innerHTML = '<span class="text-[15px] align-text-bottom inline-block icon-[svg-spinners--ring-resize] mr-[1px]"></span>Adding...';
            btn.style.pointerEvents = 'none';

            try {
                const result = await addToQueue(md5, 'search-page');

                if (result && result.success) {
                    showToast({
                        title: 'Success',
                        message: 'Added to queue',
                        type: 'success',
                    });
                    btn.innerHTML = '<span class="text-[15px] align-text-bottom inline-block icon-[mdi--check] mr-[1px]"></span>Queued';
                    setTimeout(() => {
                        btn.innerHTML = originalText;
                        btn.style.pointerEvents = 'auto';
                    }, 2000);
                } else {
                    showToast({
                        title: 'Info',
                        message: 'Already in queue',
                        type: 'info',
                    });
                    btn.innerHTML = originalText;
                    btn.style.pointerEvents = 'auto';
                }
            } catch (error) {
                showToast({
                    title: 'Error',
                    message: error.message,
                    type: 'error',
                    timeout: 6000,
                });
                btn.innerHTML = originalText;
                btn.style.pointerEvents = 'auto';
            }
        });

        return btn;
    }

    function findSaveButton(root = document) {
        return Array.from(root.querySelectorAll('a[href="#"]')).find((a) => {
            return a.innerHTML.includes('bookmark') && a.textContent.includes('Save');
        });
    }

    // ============================================================
    // INJECTION: SEARCH RESULTS
    // ============================================================

    function addButtonsToSearchResults() {
        const items = document.querySelectorAll('.flex.pt-3.pb-3.border-b');
        if (!items.length) return;

        items.forEach((item) => {
            const mainLink = item.querySelector('a.js-vim-focus.custom-a');
            if (!mainLink) return;

            const md5 = extractMD5(mainLink.href);
            if (!md5) return;

            const saveButton = findSaveButton(item);
            if (!saveButton) return;

            if (saveButton.dataset.stacksHasDownload === '1') return;
            saveButton.dataset.stacksHasDownload = '1';

            const downloadBtn = createDownloadButton(md5);

            const separator = document.createTextNode(' · ');
            const parent = saveButton.parentNode;
            if (!parent) return;

            parent.insertBefore(separator, saveButton.nextSibling);
            parent.insertBefore(downloadBtn, separator.nextSibling);
        });
    }

    // ============================================================
    // INJECTION: DETAIL PAGE
    // ============================================================

    function addButtonToDetailPage() {
        const md5 = extractMD5(window.location.href);
        if (!md5) return;

        const saveButton = findSaveButton(document);
        if (!saveButton) return;

        if (saveButton.dataset.stacksHasDownload === '1') return;
        saveButton.dataset.stacksHasDownload = '1';

        const downloadBtn = createDownloadButton(md5);

        const separator = document.createTextNode(' · ');
        const parent = saveButton.parentNode;
        if (!parent) return;

        parent.insertBefore(separator, saveButton.nextSibling);
        parent.insertBefore(downloadBtn, separator.nextSibling);
    }

    // ============================================================
    // INIT
    // ============================================================

    function init() {
        const currentPath = window.location.pathname;

        console.log('%c📚 Stacks Extension Loaded', 'font-size: 14px; font-weight: bold; color: #50fa7b;');
        console.log('%cServer: ' + CONFIG.serverUrl, 'color: #8be9fd;');

        if (CONFIG.apiKey) {
            console.log('%cAPI Key: Configured', 'color: #50fa7b;');
        } else {
            console.log('%cAPI Key: NOT CONFIGURED', 'color: #ff5555; font-weight: bold;');
            console.log('%cGet key from: Stacks web interface → Settings tab', 'color: #ffb86c;');
            console.log('%cConfigure it here: Tampermonkey icon → Stacks Settings', 'color: #ffb86c;');
        }

        console.log(
            '%cNotifications: ' + (CONFIG.showNotifications ? 'Enabled' : 'Disabled'),
            'color: #6272a4;'
        );

        if (!CONFIG.serverUrl.includes('localhost') && !CONFIG.serverUrl.includes('127.0.0.1')) {
            console.log('%c🌐 Remote server connection', 'font-size: 12px; color: #ffb86c;');
        }

        // Check for updates (always check, no session cache)
        if (CONFIG.serverUrl) {
            checkForUpdates();
        }

        // If no API key, don't inject buttons yet
        if (!CONFIG.apiKey) {
            return;
        }

        if (currentPath.startsWith('/search')) {
            addButtonsToSearchResults();

            // Debounced observer for infinite scroll
            let scheduled = false;
            const observer = new MutationObserver(() => {
                if (scheduled) return;
                scheduled = true;
                requestAnimationFrame(() => {
                    scheduled = false;
                    addButtonsToSearchResults();
                });
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true,
            });
        } else if (currentPath.startsWith('/md5/')) {
            addButtonToDetailPage();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
