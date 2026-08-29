'use strict';

const { contextBridge, ipcRenderer } = require('electron');

/**
 * 预加载脚本
 * 通过 contextBridge 安全地向渲染进程暴露 API
 */
contextBridge.exposeInMainWorld('electronAPI', {
  // ── 应用信息 ──
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getPlatform: () => ipcRenderer.invoke('get-platform'),
  getUserDataPath: () => ipcRenderer.invoke('get-user-data-path'),

  // ── 窗口控制 ──
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  /** 窗口最小化后恢复时强制重绘，防止白屏 */
  forceRedraw: () => ipcRenderer.send('window-force-redraw'),

  // ── 文件对话框 ──
  showSaveDialog: (options) => ipcRenderer.invoke('show-save-dialog', options),
  showOpenDialog: (options) => ipcRenderer.invoke('show-open-dialog', options),

  // ── 系统操作 ──
  openPath: (targetPath) => ipcRenderer.invoke('open-path', targetPath),

  // ── 桌面原生通知 ──
  showNotification: (title, body) => ipcRenderer.invoke('send-notification', title, body),

  // ── 托盘未读角标 ──
  /** 更新托盘未读消息数（0 清除角标） */
  updateTrayUnread: (count) => ipcRenderer.send('tray-unread', count),

  // ── 导航（托盘快捷菜单 → 前端路由）──
  navigateTo: (route) => ipcRenderer.send('app-navigate', route),
  /** 订阅主进程导航事件（托盘/快捷键跳转） */
  onNavigate: (callback) => {
    const listener = (_e, route) => { if (typeof callback === 'function') callback(route); };
    ipcRenderer.on('app-route', listener);
    return () => ipcRenderer.removeListener('app-route', listener);
  },

  // ── 开机自启（默认关闭）──
  getAutoStart: () => ipcRenderer.invoke('get-auto-start'),
  setAutoStart: (enabled) => ipcRenderer.invoke('set-auto-start', enabled),

  // ── Worker Thread 任务执行（避免主进程阻塞）──
  /** 在 Worker 线程执行 CPU 密集型任务 */
  workerExec: (task, payload, timeout) =>
    ipcRenderer.invoke('worker-exec', task, payload, timeout),
  /** 获取 Worker 线程池状态 */
  workerStats: () => ipcRenderer.invoke('worker-stats'),

  // ── 大数据流式传输 ──
  /** 分块读取大文件，避免序列化阻塞 IPC */
  readFileChunked: (filePath, chunkSize) =>
    ipcRenderer.invoke('read-file-chunked', filePath, chunkSize),
});
