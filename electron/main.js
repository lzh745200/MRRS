'use strict';

const { app, BrowserWindow, dialog, Menu, Tray, shell, ipcMain, safeStorage } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const crypto = require('crypto');
const http = require('http');
const fs = require('fs');

// ─── 全局变量 ───
let mainWindow = null;
let backendProcess = null;
let tray = null;
let isQuitting = false;
let backendRestartCount = 0;
const MAX_BACKEND_RESTARTS = 3;
const INTERNAL_BACKUP_KEY = crypto.randomBytes(16).toString('hex');
const INTERNAL_SHUTDOWN_KEY = crypto.randomBytes(16).toString('hex');

const DEFAULT_BACKEND_PORT = 8000;
const MAX_PORT_ATTEMPTS = 11;
let backendPort = DEFAULT_BACKEND_PORT;
const APP_TITLE = '帮扶管理系统';
const BACKEND_READY_TIMEOUT = 300000; // 5分钟——PyInstaller打包exe首次启动需提取文件+杀软扫描+初始化数据库（实测可超3分钟）
const MAX_URL_LOAD_RETRIES = 5;     // 页面加载失败最大重试次数
const URL_LOAD_RETRY_DELAY = 3000;  // 页面加载重试间隔（毫秒，健康检查等待将覆盖此延时）
const AUTO_BACKUP_INTERVAL = 24 * 60 * 60 * 1000;
const WINDOW_STATE_FILE = path.join(getUserDataPath(), 'window-state.json');
const SECRETS_FILE = path.join(getUserDataPath(), 'secrets.json');
const CRASH_LOG_FILE = path.join(getUserDataPath(), 'crash.log');

const appVersion = (() => {
  try {
    const pkgPath = app.isPackaged
      ? path.join(process.resourcesPath, '..', 'package.json')
      : path.join(__dirname, '..', 'package.json');
    return JSON.parse(fs.readFileSync(pkgPath, 'utf-8')).version || '1.7.2';
  } catch (_) {
    return '1.7.2';
  }
})();

// ─── 路径解析 ───
function getUserDataPath() {
  if (process.env.ELECTRON_USER_DATA_PATH) return process.env.ELECTRON_USER_DATA_PATH;
  if (!app.isPackaged) return path.join(__dirname, '..', 'data');
  return app.getPath('userData');
}

function getResourcePath(...segments) {
  if (app.isPackaged) return path.join(process.resourcesPath, ...segments);
  return path.join(__dirname, '..', ...segments);
}

function getBackendExePath() {
  const isWin = process.platform === 'win32';
  const exeName = isWin ? 'assistance-backend.exe' : 'assistance-backend';
  if (app.isPackaged) {
    const backendDir = path.join(process.resourcesPath, 'backend');
    const primaryPath = path.join(backendDir, exeName);
    // On Linux, the binary may be packaged as .exe due to cross-platform extraResources
    if (!isWin && !fs.existsSync(primaryPath)) {
      const fallbackPath = path.join(backendDir, 'assistance-backend.exe');
      if (fs.existsSync(fallbackPath)) return fallbackPath;
    }
    return primaryPath;
  }
  return path.join(__dirname, '..', 'backend', 'dist', exeName);
}

function getFrontendPath() {
  if (app.isPackaged) return path.join(process.resourcesPath, 'frontend');
  return path.join(__dirname, '..', 'frontend', 'dist');
}

function getIconPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'icon.png');
  }
  return path.join(__dirname, '..', 'resources', 'icons', 'app-circle-256.png');
}

// ─── 密钥持久化 ───
function getOrCreateSecrets() {
  const canEncrypt = safeStorage.isEncryptionAvailable();
  try {
    if (fs.existsSync(SECRETS_FILE)) {
      const raw = fs.readFileSync(SECRETS_FILE);
      let data;
      if (canEncrypt) {
        try {
          const decrypted = safeStorage.decryptString(raw);
          data = JSON.parse(decrypted);
        } catch (_) {
          try {
            data = JSON.parse(raw.toString('utf-8'));
            _writeSecrets(data, true);
          } catch (__) { data = {}; }
        }
      } else {
        data = JSON.parse(raw.toString('utf-8'));
      }
      if (data.SECRET_KEY && data.CSRF_SECRET_KEY) {
        // 确保旧版本密钥文件也有 ENCRYPTION_KEY
        if (!data.ENCRYPTION_KEY) {
          data.ENCRYPTION_KEY = crypto.randomBytes(32).toString('base64');
          _writeSecrets(data, canEncrypt);
        }
        return data;
      }
    }
  } catch (e) { console.warn('[Secrets] 读取失败:', e.message); }
  const secrets = {
    SECRET_KEY: crypto.randomBytes(32).toString('hex'),
    CSRF_SECRET_KEY: crypto.randomBytes(32).toString('hex'),
    ENCRYPTION_KEY: crypto.randomBytes(32).toString('base64'),
  };
  _writeSecrets(secrets, canEncrypt);
  return secrets;
}

function _writeSecrets(secrets, encrypt) {
  try {
    if (encrypt) {
      const encrypted = safeStorage.encryptString(JSON.stringify(secrets));
      fs.writeFileSync(SECRETS_FILE, encrypted);
    } else {
      fs.writeFileSync(SECRETS_FILE, JSON.stringify(secrets), 'utf-8');
    }
  } catch (e) { console.error('[Secrets] 写入失败:', e.message); }
}

function getDatabasePath() {
  let dbDir;
  if (process.platform === 'linux') {
    const homeDir = process.env.HOME || '/root';
    dbDir = path.join(homeDir, '.bumofu', 'data');
  } else {
    dbDir = path.join(getUserDataPath(), 'database');
  }
  if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });
  const dbPath = path.join(dbDir, 'rural_revitalization.db');
  if (!fs.existsSync(dbPath)) {
    const sourceDb = getResourcePath('database', 'rural_revitalization.db');
    if (fs.existsSync(sourceDb)) fs.copyFileSync(sourceDb, dbPath);
  }
  return dbPath;
}

// ─── 日志写入 ───
function writeDiagnosticLog(message) {
  try {
    const timestamp = new Date().toISOString();
    fs.appendFileSync(CRASH_LOG_FILE, `[${timestamp}] ${message}\n`);
  } catch (_) {}
}

// ─── 端口检测 ───
function checkPortInUse(port) {
  return new Promise((resolve) => {
    const net = require('net');
    const server = net.createServer();
    server.once('error', (err) => { resolve(err.code === 'EADDRINUSE'); });
    server.once('listening', () => { server.close(); resolve(false); });
    server.listen(port, '127.0.0.1');
  });
}

async function findAvailablePort(startPort, maxAttempts) {
  // 不再强杀端口占用进程（可能误杀同机第三方服务），直接顺移探测备用端口
  for (let i = 0; i < maxAttempts; i++) {
    const port = startPort + i;
    const inUse = await checkPortInUse(port);
    if (!inUse) return port;
    if (i === 0) {
      console.warn(`[Port] 默认端口 ${port} 被占用，尝试备用端口...`);
      writeDiagnosticLog(`默认端口 ${port} 被占用，尝试备用端口`);
    }
  }
  return null;
}

function analyzeStartupError(stderrCapture) {
  const logs = stderrCapture.join('\n').toLowerCase();
  if (logs.includes('vcruntime') || logs.includes('msvcp')) return '缺少 VC++ 运行时库。';
  if (logs.includes('address already in use') || logs.includes('eaddrinuse')) return '端口被占用。';
  if (logs.includes('database') || logs.includes('sqlite')) return '数据库错误。';
  if (logs.includes('permission denied') || logs.includes('eacces')) return '权限不足。';
  if (logs.includes('importerror') || logs.includes('modulenotfounderror')) return 'Python 依赖缺失。';
  if (logs.includes('timeout') || stderrCapture.length === 0) return '启动超时。';
  return '未知错误，请查看日志。';
}

// ─── 后端启动 ───
// isFirstStart: 首次启动时探测端口；后续重启复用已确定的端口，
// 避免端口变化导致前端页面（已加载在旧端口）API 请求失败。
async function startBackend(stderrCapture = null, isFirstStart = false) {
  // 防止重复启动：如果已有后端进程在运行，先终止
  if (backendProcess && !backendProcess.killed) {
    console.log('[Backend] 后端进程已在运行，跳过重复启动');
    return backendProcess;
  }
  const exePath = getBackendExePath();
  console.log('[Backend] 启动路径:', exePath);
  writeDiagnosticLog(`后端路径: ${exePath}`);

  if (!fs.existsSync(exePath)) {
    const msg = `后端程序不存在:\n${exePath}`;
    console.error('[Backend]', msg);
    writeDiagnosticLog(msg);
    dialog.showErrorBox('启动失败', msg);
    app.quit();
    return null;
  }

  try {
    fs.accessSync(exePath, fs.constants.X_OK);
  } catch (_) {
    try { fs.chmodSync(exePath, 0o755); } catch (e) {}
  }

  // 首次启动时探测可用端口；重启时复用已确定的端口（前端页面已加载在该端口）
  if (isFirstStart || !backendPort) {
    const availablePort = await findAvailablePort(DEFAULT_BACKEND_PORT, MAX_PORT_ATTEMPTS);
    if (availablePort === null) {
      const msg = `端口 ${DEFAULT_BACKEND_PORT}-${DEFAULT_BACKEND_PORT + MAX_PORT_ATTEMPTS - 1} 均被占用。`;
      writeDiagnosticLog(msg);
      dialog.showErrorBox('端口冲突', msg);
      app.quit();
      return null;
    }
    backendPort = availablePort;
    if (backendPort !== DEFAULT_BACKEND_PORT) {
      console.log(`[Backend] 使用备用端口 ${backendPort}`);
      writeDiagnosticLog(`备用端口: ${backendPort}`);
    }
  } else {
    console.log(`[Backend] 重启复用端口 ${backendPort}`);
    writeDiagnosticLog(`重启复用端口: ${backendPort}`);
    // 检查复用端口是否仍被占用（旧进程可能未完全释放）
    const stillInUse = await checkPortInUse(backendPort);
    if (stillInUse) {
      // 端口仍被占用（可能是旧进程尚未退出），等待 2 秒后重试
      await new Promise(r => setTimeout(r, 2000));
    }
  }

  const dbPath = getDatabasePath();
  const logsDir = path.join(getUserDataPath(), 'logs');
  const uploadsDir = path.join(getUserDataPath(), 'uploads');
  const cacheDir = path.join(getUserDataPath(), 'cache');
  const exportsDir = path.join(getUserDataPath(), 'exports');
  [logsDir, uploadsDir, cacheDir, exportsDir].forEach(dir => {
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  });

  const env = {
    ...process.env,
    DATABASE_URL: `sqlite:///${dbPath}`,
    HOST: '127.0.0.1',
    PORT: String(backendPort),
    LOG_FILE: path.join(logsDir, 'app.log'),
    UPLOAD_DIR: uploadsDir,
    CACHE_DIR: cacheDir,
    EXPORT_DIR: exportsDir,
    FRONTEND_DIST_PATH: getFrontendPath(),
    ENVIRONMENT: 'production',
    PROJECT_VERSION: appVersion,
    INTERNAL_BACKUP_KEY,
    INTERNAL_SHUTDOWN_KEY,
    ...getOrCreateSecrets(),
  };

  if (process.platform === 'linux') {
    const libDir = path.join(path.dirname(exePath), '..', 'lib');
    if (fs.existsSync(libDir)) {
      const existing = env.LD_LIBRARY_PATH || '';
      env.LD_LIBRARY_PATH = libDir + (existing ? ':' + existing : '');
    }
  }

  const proc = spawn(exePath, [], {
    cwd: path.dirname(exePath),
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: process.platform === 'win32',
  });

  proc.stdout.on('data', (data) => {
    console.log('[Backend stdout]', data.toString().trim());
  });

  proc.stderr.on('data', (data) => {
    const text = data.toString().trim();
    if (!text) return;
    console.error('[Backend stderr]', text);
    try {
      fs.appendFileSync(CRASH_LOG_FILE, `[${new Date().toISOString()}] ${text}\n`);
    } catch (_) {}
    if (stderrCapture) {
      stderrCapture.push(text);
      if (stderrCapture.length > 100) stderrCapture.shift();
    }
  });

  proc.on('error', (err) => {
    console.error('[Backend] 启动错误:', err);
    writeDiagnosticLog(`启动错误: ${err.message}`);
    let userMsg = err.message;
    if (err.code === 'ENOENT') userMsg = '后端程序不存在。';
    else if (err.code === 'EACCES') userMsg = '权限不足，请以管理员身份运行。';
    dialog.showErrorBox('后端启动失败', userMsg);
  });

  proc.on('exit', (code) => {
    console.log('[Backend] 退出, code:', code);
    writeDiagnosticLog(`后端退出, code: ${code}`);
    backendProcess = null;
    if (!isQuitting && code !== 0) {
      if (backendRestartCount < MAX_BACKEND_RESTARTS) {
        backendRestartCount++;
        console.log(`[Backend] 自动重启 (${backendRestartCount}/${MAX_BACKEND_RESTARTS})...`);
        writeDiagnosticLog(`自动重启 ${backendRestartCount}/${MAX_BACKEND_RESTARTS}`);
        setTimeout(async () => {
          const restartStderr = [];
          // 重启时复用已确定的端口（isFirstStart=false），避免前端连接失效
          backendProcess = await startBackend(restartStderr, false);
          // 等待重启的后端就绪后重新加载页面
          try {
            await waitForBackend(restartStderr);
            // 重启成功后重置重启计数：恢复运行后偶发崩溃不应消耗历史配额
            backendRestartCount = 0;
            console.log('[Backend] 重启后端已就绪，重新加载页面');
            writeDiagnosticLog('重启后端已就绪，重新加载页面');
            if (mainWindow && !mainWindow.isDestroyed()) {
              mainWindow.loadURL(`http://127.0.0.1:${backendPort}`).catch((err) => {
                console.error('[Window] 重启后重新加载失败:', err?.message || err);
                writeDiagnosticLog(`重启后重新加载失败: ${err?.message || err}`);
              });
            }
          } catch (restartErr) {
            console.error('[Backend] 重启后端等待就绪失败:', restartErr.message);
            writeDiagnosticLog(`重启后端等待就绪失败: ${restartErr.message}`);
          }
        }, 2000);
      } else {
        const logPath = path.join(getUserDataPath(), 'logs', 'app.log');
        // 提示可能原因：安全软件（杀软）可能拦截/终止了后端进程，
        // 请将安装目录加入白名单；不要将应用安装在系统临时目录。
        dialog.showErrorBox('后端异常退出',
          `后端已重启 ${MAX_BACKEND_RESTARTS} 次仍失败。\n\n` +
          `可能原因：\n` +
          `1. 安全软件（杀毒/Defender）拦截了后端进程——请将程序安装目录加入白名单\n` +
          `2. 安装目录位于临时目录（%TEMP%），文件可能被系统清理——请安装到正式目录\n` +
          `3. 数据库文件损坏或磁盘空间不足\n\n` +
          `诊断日志: ${CRASH_LOG_FILE}\n应用日志: ${logPath}`);
      }
    }
  });

  return proc;
}

function stopBackend() {
  return new Promise((resolve) => {
    if (!backendProcess) { resolve(); return; }
    console.log('[Backend] 停止...');
    const pid = backendProcess.pid;
    let resolved = false;
    const done = () => { if (!resolved) { resolved = true; resolve(); } };
    const forceKill = () => {
      try {
        if (process.platform === 'win32') {
          spawn('taskkill', ['/pid', String(pid), '/f', '/t'], { windowsHide: true });
        } else {
          process.kill(pid, 'SIGKILL');
        }
      } catch (_) {}
    };
    const proc = backendProcess;
    proc.once('exit', () => { backendProcess = null; done(); });
    const req = http.request({
      hostname: '127.0.0.1',
      port: backendPort,
      path: '/api/v1/shutdown',
      method: 'POST',
      timeout: 3000,
      headers: { 'X-Internal-Shutdown': INTERNAL_SHUTDOWN_KEY },
    }, () => { setTimeout(forceKill, 3000); });
    req.on('error', forceKill);
    req.on('timeout', () => { req.destroy(); forceKill(); });
    req.end();
    setTimeout(() => { backendProcess = null; done(); }, 5000);
  });
}

function waitForBackend(stderrCapture = []) {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    let checkCount = 0;
    let lastLogTime = 0;
    let done = false;  // 防止 resolve 后继续检查
    function check() {
      if (done) return;  // 已完成，不再检查
      const elapsed = Date.now() - startTime;
      checkCount++;
      // 每5秒打印一次进度日志
      if (elapsed - lastLogTime > 5000) {
        console.log(`[Backend] 等待就绪... ${(elapsed / 1000).toFixed(1)}s`);
        lastLogTime = elapsed;
      }
      if (elapsed > BACKEND_READY_TIMEOUT) {
        done = true;
        const recent = stderrCapture.slice(-10).join('\n');
        reject(new Error(`后端启动超时 (${(elapsed / 1000).toFixed(0)}秒)\n日志:\n${recent || '无日志'}`));
        return;
      }
      const req = http.get(`http://127.0.0.1:${backendPort}/health`, (res) => {
        if (done) return;  // 防止重复处理
        if (res.statusCode === 200) {
          done = true;  // 标记完成，阻止后续 check
          console.log(`[Backend] 就绪，耗时 ${(elapsed / 1000).toFixed(1)}s`);
          writeDiagnosticLog(`后端就绪，耗时 ${(elapsed / 1000).toFixed(1)}s`);
          resolve();
        } else if (!done) setTimeout(check, 500);
      });
      req.on('error', () => {
        if (done) return;  // 已完成，忽略错误
        // 前3次和10秒后打印错误日志
        if (checkCount <= 3 || elapsed > 10000) {
          console.log(`[Backend] 健康检查失败 (${(elapsed / 1000).toFixed(1)}s)`);
        }
        setTimeout(check, 500);
      });
      req.setTimeout(3000, () => {
        if (done) return;  // 已完成，不重启检查
        req.destroy();
        setTimeout(check, 500);
      });
    }
    // 首次检查延迟500ms（比原来1s更快开始探测）
    setTimeout(check, 500);
  });
}

// ─── 页面加载（带重试） ───
// 后端冷启动（PyInstaller 解包 + 杀软扫描）可能长达数分钟，页面重试前
// 先做 /health 健康检查，后端就绪后再加载，避免盲目重试耗尽次数。
function waitForBackendReady(timeoutMs) {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    let done = false;  // 防止 resolve 后继续检查
    function probe() {
      if (done) return;
      if (Date.now() - startTime > timeoutMs) {
        done = true;
        reject(new Error('backend not ready'));
        return;
      }
      const req = http.get(`http://127.0.0.1:${backendPort}/health`, (res) => {
        if (done) return;
        if (res.statusCode === 200) {
          done = true;
          resolve();
        } else setTimeout(probe, 1000);
      });
      req.on('error', () => { if (!done) setTimeout(probe, 1000); });
      req.setTimeout(3000, () => { if (!done) { req.destroy(); setTimeout(probe, 1000); } });
    }
    probe();
  });
}

function loadURLWithRetry(win, url, retryCount) {
  if (retryCount >= MAX_URL_LOAD_RETRIES) {
    const msg = `加载页面失败（已重试 ${MAX_URL_LOAD_RETRIES} 次）: ${url}`;
    console.error('[Window]', msg);
    writeDiagnosticLog(msg);
    dialog.showErrorBox('页面加载失败', `${msg}\n\n请检查后端服务是否正常运行，或重启应用。`);
    return;
  }
  if (retryCount > 0) {
    console.log(`[Window] 页面加载重试 ${retryCount}/${MAX_URL_LOAD_RETRIES}: ${url}`);
    writeDiagnosticLog(`页面加载重试 ${retryCount}/${MAX_URL_LOAD_RETRIES}`);
  }
  win.loadURL(url).then(() => {
    console.log('[Window] 页面加载成功');
  }).catch((err) => {
    const errMsg = err?.message || String(err);
    console.error(`[Window] 加载失败 (重试 ${retryCount + 1}/${MAX_URL_LOAD_RETRIES}):`, errMsg);
    writeDiagnosticLog(`页面加载失败 (${retryCount + 1}/${MAX_URL_LOAD_RETRIES}): ${errMsg}`);
    // 后端可能仍在冷启动：先等待健康检查通过（每轮最长 60 秒），就绪后再重试加载
    waitForBackendReady(60000).then(() => {
      if (win && !win.isDestroyed()) {
        console.log(`[Window] 后端已就绪，重新加载页面 (${retryCount + 1}/${MAX_URL_LOAD_RETRIES})`);
        loadURLWithRetry(win, url, retryCount + 1);
      }
    }).catch(() => {
      if (win && !win.isDestroyed()) {
        setTimeout(() => loadURLWithRetry(win, url, retryCount + 1), URL_LOAD_RETRY_DELAY);
      }
    });
  });
}

// ─── 窗口状态 ───
function loadWindowState() {
  try {
    if (fs.existsSync(WINDOW_STATE_FILE)) {
      return JSON.parse(fs.readFileSync(WINDOW_STATE_FILE, 'utf-8'));
    }
  } catch (e) {}
  return null;
}

function saveWindowState() {
  if (!mainWindow) return;
  try {
    const bounds = mainWindow.getBounds();
    const isMaximized = mainWindow.isMaximized();
    fs.writeFileSync(WINDOW_STATE_FILE, JSON.stringify({ bounds, isMaximized }), 'utf-8');
  } catch (e) {}
}

// ─── 窗口管理 ───
function createMainWindow() {
  const iconPath = getIconPath();
  const saved = loadWindowState();
  const winOptions = {
    width: saved?.bounds?.width || 1400,
    height: saved?.bounds?.height || 900,
    x: saved?.bounds?.x,
    y: saved?.bounds?.y,
    minWidth: 1024,
    minHeight: 768,
    title: APP_TITLE,
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
      sandbox: true,
    },
    show: false,
    autoHideMenuBar: true,
  };
  mainWindow = new BrowserWindow(winOptions);
  if (saved?.isMaximized) mainWindow.maximize();

  // ─── 导航安全限制 ───
  const ALLOWED_EXTERNAL_PROTOCOLS = ['https:', 'http:', 'mailto:'];
  mainWindow.webContents.on('will-navigate', (event, url) => {
    const appOrigin = 'http://127.0.0.1';
    const appOrigin2 = 'http://localhost';
    if (!url.startsWith(appOrigin) && !url.startsWith(appOrigin2) && !url.startsWith('file://')) {
      event.preventDefault();
      try {
        const proto = new URL(url).protocol;
        if (ALLOWED_EXTERNAL_PROTOCOLS.includes(proto)) {
          shell.openExternal(url);
        } else {
          console.warn('[Security] 拒绝非白名单协议导航:', url);
        }
      } catch (_) { /* malformed URL, ignore */ }
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://127.0.0.1') || url.startsWith('http://localhost')) {
      return { action: 'allow' };
    }
    try {
      const proto = new URL(url).protocol;
      if (ALLOWED_EXTERNAL_PROTOCOLS.includes(proto)) {
        shell.openExternal(url);
      } else {
        console.warn('[Security] 拒绝非白名单协议窗口:', url);
      }
    } catch (_) { /* malformed URL, ignore */ }
    return { action: 'deny' };
  });

  const url = `http://127.0.0.1:${backendPort}`;
  loadURLWithRetry(mainWindow, url, 0);
  mainWindow.once('ready-to-show', () => { mainWindow.show(); mainWindow.focus(); });
  let timer = null;
  mainWindow.on('resize', () => { clearTimeout(timer); timer = setTimeout(saveWindowState, 500); });
  mainWindow.on('move', () => { clearTimeout(timer); timer = setTimeout(saveWindowState, 500); });
  mainWindow.on('close', (e) => {
    saveWindowState();
    if (!isQuitting) {
      const remembered = closeBehaviorStore.get();
      if (remembered === 'quit') { isQuitting = true; return; }
      if (remembered === 'hide') { e.preventDefault(); mainWindow.hide(); return; }
      e.preventDefault();
      // 首次关闭：询问用户（结果经 confirm-close-behavior IPC 处理，此处仅隐藏等待回答）
      mainWindow.hide();
      handleCloseBehaviorPrompt(mainWindow);
    }
  });
  mainWindow.on('closed', () => { mainWindow = null; });
  mainWindow.webContents.on('render-process-gone', (event, details) => {
    console.error('[Renderer] 崩溃:', details.reason);
    dialog.showErrorBox('页面异常', `渲染进程崩溃 (${details.reason})，请重启程序。`);
  });
}

async function restartBackend() {
  await stopBackend();
  const stderr = [];
  // 手动重启也复用端口
  backendProcess = await startBackend(stderr, false);
}

// ─── 系统托盘 ───
let trayUnreadCount = 0;

function updateTrayUnread(count) {
  trayUnreadCount = Math.max(0, Number(count) || 0);
  if (!tray) return;
  tray.setToolTip(trayUnreadCount > 0 ? `${APP_TITLE}（${trayUnreadCount} 条未读消息）` : APP_TITLE);
}

function createTray() {
  const iconPath = getIconPath();
  if (!fs.existsSync(iconPath)) return;
  tray = new Tray(iconPath);
  const menu = Menu.buildFromTemplate([
    { label: '显示主窗口', click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } } },
    { type: 'separator' },
    { label: '我的待办', click: () => navigateToRoute('/todos') },
    { label: '打开成效大屏', click: () => navigateToRoute('/bigscreen') },
    { type: 'separator' },
    { label: '立即备份', click: () => { performAutoBackup(); showTrayNotification('备份任务', '执行中...'); } },
    { label: '重启后端', click: () => { restartBackend(); } },
    { type: 'separator' },
    { label: '退出', click: () => { isQuitting = true; app.quit(); } },
  ]);
  tray.setToolTip(APP_TITLE);
  tray.setContextMenu(menu);
  tray.on('double-click', () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } });
}

/** 托盘/快捷键 → 打开窗口并跳转前端路由 */
function navigateToRoute(route) {
  if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
  if (mainWindow) { mainWindow.webContents.send('app-route', route); }
}

// ─── 关闭行为记忆 ───
const CLOSE_BEHAVIOR_KEY = 'close-behavior';
function closeBehaviorStore() {
  return {
    get() {
      try { return require('fs').readFileSync(require('path').join(app.getPath('userData'), CLOSE_BEHAVIOR_KEY), 'utf8'); }
      catch (_) { return null; }
    },
    set(v) {
      try { require('fs').writeFileSync(require('path').join(app.getPath('userData'), CLOSE_BEHAVIOR_KEY), v); } catch (_) {}
    },
  };
}
function handleCloseBehaviorPrompt(win) {
  const remembered = closeBehaviorStore().get();
  if (remembered === 'quit') { isQuitting = true; app.quit(); return; }
  if (remembered === 'hide') { return; } // 已隐藏
  dialog.showMessageBox(win, {
    type: 'question',
    title: '关闭窗口',
    message: '关闭窗口后程序将最小化到系统托盘继续运行（自动备份、消息提醒仍生效）。',
    buttons: ['最小化到托盘', '完全退出'],
    defaultId: 0,
    cancelId: 1,
    checkboxLabel: '记住我的选择，下次不再询问',
    checkboxChecked: false,
  }).then(({ response, checkboxChecked }) => {
    if (checkboxChecked) { closeBehaviorStore().set(response === 0 ? 'hide' : 'quit'); }
    if (response === 0) { win.show(); win.hide(); } // 保持最小化到托盘
    else { isQuitting = true; app.quit(); }
  }).catch(() => {});
}

// ─── 全局快捷键 ───
function registerGlobalShortcuts() {
  const { globalShortcut } = require('electron');
  const shortcuts = [
    { accelerator: 'CommandOrControl+Alt+N', route: '/approval/pending', name: '新建审批' },
    { accelerator: 'CommandOrControl+Alt+T', route: '/todos', name: '我的待办' },
    { accelerator: 'CommandOrControl+Alt+B', route: null, name: '立即备份' },
    { accelerator: 'CommandOrControl+Alt+D', route: '/bigscreen', name: '成效大屏' },
  ];
  for (const s of shortcuts) {
    let ok = false;
    try { ok = globalShortcut.register(s.accelerator, () => {
      if (s.route) { navigateToRoute(s.route); }
      else { performAutoBackup(); showTrayNotification('备份任务', '执行中...'); }
    }); } catch (_) { ok = false; }
    if (ok) { console.log(`[Shortcut] 已注册 ${s.accelerator} (${s.name})`); }
    else { console.warn(`[Shortcut] 注册失败 ${s.accelerator} (${s.name})，可能被其他程序占用`); }
  }
  app.on('will-quit', () => { try { globalShortcut.unregisterAll(); } catch (_) {} });
}

function showTrayNotification(title, body) {
  try {
    const { Notification } = require('electron');
    if (Notification.isSupported()) {
      new Notification({ title: `${APP_TITLE} - ${title}`, body }).show();
    }
  } catch (_) {}
}

// ─── 自动备份 ───
function startAutoBackup() {
  setTimeout(() => {
    performAutoBackup();
    setInterval(performAutoBackup, AUTO_BACKUP_INTERVAL);
  }, 5 * 60 * 1000);
  console.log('[AutoBackup] 已调度');
}

function performAutoBackup() {
  const req = http.request({
    hostname: '127.0.0.1',
    port: backendPort,
    path: '/api/v1/system/backup',
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Internal-Backup': INTERNAL_BACKUP_KEY },
    timeout: 30000,
  }, (res) => {
    let body = '';
    res.on('data', (chunk) => { body += chunk; });
    res.on('end', () => {
      if (res.statusCode === 200 || res.statusCode === 201) {
        console.log('[AutoBackup] 成功');
        showTrayNotification('备份完成', '自动备份成功');
        cleanupOldBackups();
      } else console.warn(`[AutoBackup] 状态码 ${res.statusCode}`);
    });
  });
  req.on('error', (err) => { console.warn('[AutoBackup] 请求失败:', err.message); });
  req.write(JSON.stringify({ description: '自动定时备份' }));
  req.end();
}

function cleanupOldBackups() {
  const req = http.get(`http://127.0.0.1:${backendPort}/api/v1/system/backup`, (res) => {
    let body = '';
    res.on('data', (chunk) => { body += chunk; });
    res.on('end', () => {
      try {
        const parsed = JSON.parse(body);
        // API 返回 envelope 格式: {code:200, data:{items:[...], total:N}}
        const backups = (parsed && parsed.data && parsed.data.items) ? parsed.data.items : [];
        const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
        for (const backup of backups) {
          const createdAt = new Date(backup.created_at).getTime();
          if (createdAt < sevenDaysAgo && backup.file_name && backup.file_name.startsWith('backup_')) {
            const delReq = http.request({
              hostname: '127.0.0.1',
              port: backendPort,
              path: `/api/v1/system/backup/${encodeURIComponent(backup.file_name)}`,
              method: 'DELETE',
              timeout: 10000,
            }, (res) => { if (res.statusCode >= 400) console.warn(`删除 ${backup.file_name} 失败`); });
            delReq.on('error', (err) => { console.warn(`删除 ${backup.file_name} 错误:`, err.message); });
            delReq.end();
            console.log(`[AutoBackup] 删除旧备份: ${backup.file_name}`);
          }
        }
      } catch (e) { console.warn('[AutoBackup] 清理失败:', e.message); }
    });
  });
  req.on('error', (err) => { console.warn('[AutoBackup] 获取列表失败:', err.message); });
}

// ─── VC++ 检查（Windows，但保留定义） ───
function checkVCRuntime() { return true; }
async function tryInstallVCRuntime() { return false; }

// ─── IPC 处理器 ───
function setupIpcHandlers() {
  ipcMain.handle('get-app-version', () => appVersion);
  ipcMain.handle('get-platform', () => process.platform);
  ipcMain.handle('get-user-data-path', () => getUserDataPath());
  ipcMain.on('window-minimize', () => { if (mainWindow) mainWindow.minimize(); });
  ipcMain.on('window-maximize', () => { if (mainWindow) { mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize(); } });
  ipcMain.on('window-close', () => { if (mainWindow) mainWindow.close(); });
  ipcMain.handle('show-save-dialog', async (_, opts) => {
    if (!mainWindow) return { canceled: true };
    return dialog.showSaveDialog(mainWindow, opts || { title: '保存文件', filters: [{ name: '所有文件', extensions: ['*'] }] });
  });
  ipcMain.handle('show-open-dialog', async (_, opts) => {
    if (!mainWindow) return { canceled: true };
    return dialog.showOpenDialog(mainWindow, opts || { title: '选择文件', properties: ['openFile'] });
  });
  ipcMain.handle('send-notification', (_, title, body) => { showTrayNotification(title, body); });
  // 托盘未读角标
  ipcMain.on('tray-unread', (_, count) => {
    updateTrayUnread(Number(count) || 0);
  });
  // 前端路由导航（托盘/快捷键 → 打开窗口并跳转）
  ipcMain.on('app-navigate', (_, route) => {
    if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
    const target = typeof route === 'string' ? route : '';
    if (target && mainWindow) {
      mainWindow.webContents.send('app-route', target);
    }
  });
  // 开机自启（默认关闭，单机共用电脑场景谨慎开启）
  ipcMain.handle('get-auto-start', () => {
    try { return app.getLoginItemSettings().openAtLogin; } catch (_) { return false; }
  });
  ipcMain.handle('set-auto-start', (_, enabled) => {
    try {
      app.setLoginItemSettings({ openAtLogin: !!enabled });
      return { success: true, enabled: !!enabled };
    } catch (e) {
      return { success: false, error: String(e) };
    }
  });
  ipcMain.handle('open-path', async (_, p) => {
    const os = require('os');
    const resolved = path.resolve(String(p || ''));
    const allowedRoots = [app.getPath('userData'), app.getAppPath(), os.tmpdir()]
      .map((r) => path.resolve(r));
    const inScope = allowedRoots.some(
      (root) => resolved === root || resolved.startsWith(root + path.sep)
    );
    const lower = resolved.toLowerCase();
    const isSecrets = lower.includes('runtime_secrets.json') || lower.includes('secrets.json') || lower.includes('master.key');
    if (!inScope || isSecrets) {
      console.warn(`[IPC] open-path 拒绝越界路径: ${resolved}`);
      return { error: 'forbidden-path' };
    }
    return shell.openPath(resolved);
  });
  // worker-pool 如果不存在，可忽略或提供占位
  try {
    const { workerPool } = require('./worker-pool');
    ipcMain.handle('worker-exec', async (_, task, payload, timeout) => {
      try { const result = await workerPool.exec(task, payload, timeout); return { success: true, data: result }; }
      catch (err) { return { success: false, error: err.message }; }
    });
    ipcMain.handle('worker-stats', () => workerPool.stats);
  } catch (_) {}
  ipcMain.handle('read-file-chunked', async (_, filePath, chunkSize) => {
    // 路径白名单：仅允许应用数据目录/安装目录/系统临时目录，
    // 并显式拒绝密钥文件，防止被注入的渲染进程读取任意文件（如 SECRET_KEY）
    const os = require('os');
    const resolved = path.resolve(String(filePath || ''));
    const allowedRoots = [app.getPath('userData'), app.getAppPath(), os.tmpdir()]
      .map((p) => path.resolve(p));
    const inScope = allowedRoots.some(
      (root) => resolved === root || resolved.startsWith(root + path.sep)
    );
    const lower = resolved.toLowerCase();
    const isSecrets = lower.includes('runtime_secrets.json') || lower.includes('secrets.json');
    if (!inScope || isSecrets) {
      console.warn(`[IPC] read-file-chunked 拒绝越界路径: ${resolved}`);
      return { error: 'forbidden-path' };
    }
    return new Promise((resolve) => {
      const chunks = [];
      const stream = fs.createReadStream(resolved, { highWaterMark: chunkSize || 256 * 1024, encoding: 'base64' });
      stream.on('data', (chunk) => chunks.push(chunk));
      stream.on('end', () => resolve({ data: chunks.join('') }));
      stream.on('error', () => resolve({ error: 'read-failed' }));
    });
  });
  ipcMain.on('window-force-redraw', () => {
    if (mainWindow) { mainWindow.webContents.invalidate(); mainWindow.focus(); mainWindow.webContents.focus(); }
  });
  console.log('[IPC] 注册完成');
}

// ─── 应用生命周期 ───
// 单实例锁必须在 whenReady 注册之前获取：否则第二个实例（如重复双击、安装后
// 自动启动+手动启动）会绕过锁检查执行 whenReady 回调，同时拉起两个后端进程，
// 争抢端口与 SQLite 数据库导致闪退/崩溃（生产 crash.log 中 1 秒内两条"后端路径"）。
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) { if (mainWindow.isMinimized()) mainWindow.restore(); mainWindow.show(); mainWindow.focus(); }
  });
}

app.whenReady().then(async () => {
  // 防御：即使 app.quit() 与 ready 事件存在竞态，未获锁的实例也不启动后端
  if (!gotLock) { app.exit(0); return; }
  console.log('[App] 启动...');
  setupIpcHandlers();
  registerGlobalShortcuts();

  const stderrCapture = [];
  // 首次启动时探测可用端口
  backendProcess = await startBackend(stderrCapture, true);

  let splash = null;
  try {
    const splashPath = path.join(__dirname, 'splash.html');
    if (fs.existsSync(splashPath)) {
      splash = new BrowserWindow({ width: 400, height: 300, frame: false, transparent: true, alwaysOnTop: true, resizable: false, icon: getIconPath(), webPreferences: { nodeIntegration: false, contextIsolation: true } });
      splash.loadFile(splashPath);
      splash.center();
    }
  } catch (e) {}

  try {
    console.log('[App] 等待后端就绪...');
    await waitForBackend(stderrCapture);
    console.log('[App] 后端已就绪');
    backendRestartCount = 0;
  } catch (err) {
    console.error('[App] 后端启动失败:', err.message);
    writeDiagnosticLog(`后端启动失败: ${err.message}`);
    const analysis = analyzeStartupError(stderrCapture);
    const logPath = path.join(getUserDataPath(), 'logs', 'app.log');
    const choice = dialog.showMessageBoxSync({
      type: 'error',
      title: '后端启动失败',
      message: `后端启动失败。\n${analysis}\n诊断日志: ${CRASH_LOG_FILE}\n应用日志: ${logPath}`,
      buttons: ['退出', '查看日志', '重试等待', '继续启动'],
      defaultId: 2,
    });
    if (choice === 0) { isQuitting = true; stopBackend(); app.quit(); return; }
    if (choice === 1) {
      const logs = stderrCapture.join('\n') || '无日志';
      dialog.showMessageBoxSync({ type: 'info', title: '后端日志', message: '后端输出：', detail: logs.substring(0, 2000) });
      isQuitting = true; stopBackend(); app.quit(); return;
    }
    if (choice === 2) {
      // 重试等待后端就绪
      try {
        console.log('[App] 重试等待后端就绪...');
        writeDiagnosticLog('重试等待后端就绪');
        await waitForBackend(stderrCapture);
        console.log('[App] 重试后端已就绪');
        backendRestartCount = 0;
      } catch (retryErr) {
        console.error('[App] 重试后端启动仍然失败:', retryErr.message);
        writeDiagnosticLog(`重试后端启动仍然失败: ${retryErr.message}`);
        // 仍然继续启动，loadURLWithRetry 会处理重试
      }
    }
    // choice === 3: 继续启动，loadURLWithRetry 会自动重试页面加载
  }

  createMainWindow();
  if (splash && !splash.isDestroyed()) { splash.close(); splash = null; }
  createTray();
  startAutoBackup();
});

app.on('before-quit', () => { isQuitting = true; stopBackend(); });
app.on('activate', () => { if (!mainWindow) createMainWindow(); else mainWindow.show(); });

app.disableHardwareAcceleration();
if (process.platform === 'win32') {
  app.commandLine.appendSwitch('disable-features', 'CacheControl');
  const gpuCache = path.join(getUserDataPath(), 'gpu-cache');
  if (!fs.existsSync(gpuCache)) fs.mkdirSync(gpuCache, { recursive: true });
  app.commandLine.appendSwitch('gpu-disk-cache-dir', gpuCache);
  app.commandLine.appendSwitch('disable-background-timer-throttling');
}
if (process.platform === 'linux' && typeof process.getuid === 'function' && process.getuid() === 0) {
  console.warn('[Main] root 用户，启用 --no-sandbox');
  app.commandLine.appendSwitch('no-sandbox');
}

process.on('uncaughtException', (err) => {
  console.error('[Main] 未捕获异常:', err);
  writeDiagnosticLog(`未捕获异常: ${err.message}\n${err.stack || ''}`);
});
process.on('unhandledRejection', (reason) => {
  console.error('[Main] 未处理的拒绝:', reason);
  writeDiagnosticLog(`未处理的拒绝: ${String(reason)}`);
});

console.log('[Main] 主进程加载完成');
