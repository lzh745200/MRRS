'use strict';

const { contextBridge, ipcRenderer } = require('electron');

/**
 * 预加载脚本 —— 通过 contextBridge 向渲染进程暴露**最小必要** API。
 *
 * M52（2026-10-14）：此处曾暴露约 20 个 IPC（含 workerExec 直达 worker 池、
 * showOpenDialog/showSaveDialog、openPath、getUserDataPath 等），而渲染进程
 * 实际只消费 2 个 —— 攻击面远大于需要。收紧原则：**只保留有真实调用方的接口**。
 *
 * 收敛依据（全仓 grep 取证，2026-10-14）：
 *   - 前端（frontend/src）：仅 `onNavigate`（router/index.ts:896）与
 *     `updateTrayUnread`（layouts/DefaultLayoutSafe.vue:514）被消费；
 *     `navigateTo` 是主进程经 'app-route' 推路由的镜像方向，前端从不主动调用，
 *     一并移除（托盘/快捷键导航由主进程 navigateToRoute 直发 'app-route'）。
 *   - 修复引导页（electron/recovery.html）由主进程 loadFile 加载，同样使用本
 *     preload：它消费 `recovery-get-info` / `recovery-restart-backend` /
 *     `recovery-open-log` 三个通道，故保留。
 *
 * 主进程侧的 ipcMain 处理器保留原样（主进程内部仍使用同一批能力，如
 * read-file-chunked / worker-exec / open-path），仅关闭"渲染进程直达"通道。
 * 重新暴露任何通道前，必须先有真实调用方与威胁评估。
 */
contextBridge.exposeInMainWorld('electronAPI', {
  // ── 托盘未读角标 ──
  /** 更新托盘未读消息数（0 清除角标） */
  updateTrayUnread: (count) => ipcRenderer.send('tray-unread', count),

  // ── 导航（主进程托盘快捷菜单 → 前端路由）──
  /** 订阅主进程导航事件（托盘/快捷键跳转） */
  onNavigate: (callback) => {
    const listener = (_e, route) => { if (typeof callback === 'function') callback(route); };
    ipcRenderer.on('app-route', listener);
    return () => ipcRenderer.removeListener('app-route', listener);
  },

  // ── 修复引导页（A3/C2：后端不可用时的自助恢复，仅 recovery.html 消费）──
  /** 获取引导页信息（触发原因 + 日志路径） */
  getRecoveryInfo: () => ipcRenderer.invoke('recovery-get-info'),
  /** 一键修复：重启后端并等待就绪，成功后主进程自动返回系统页面 */
  recoveryRestartBackend: () => ipcRenderer.invoke('recovery-restart-backend'),
  /** 打开日志（'crash' 诊断日志 / 'app' 应用日志） */
  recoveryOpenLog: (which) => ipcRenderer.invoke('recovery-open-log', which),
});
