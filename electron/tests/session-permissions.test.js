/**
 * 会话权限处理器回归测试（2026-11-01 安全审计项）
 *
 * ## 为什么需要
 * 未注册 setPermission*Handler 时，Electron 对会话权限采取"未处理即批准"：
 * 任意页面申请摄像头/麦克风/定位/屏幕共享都会被静默放行。main.js 无法直接
 * require（模块顶层会执行 app.whenReady、IPC 注册等主进程副作用），因此这里用
 * 两条互补的断言：
 *   1) 源码结构：main.js 必须注册 request/check 两个 handler，且在 whenReady
 *      回调内、任何窗口创建之前调用（否则首个窗口仍走默认批准策略）；
 *   2) VM 行为：把 main.js 的「会话权限」段落抽到 vm 沙箱，用假 session 执行，
 *      真正调用注册进去的两个回调，验证默认拒绝、白名单放行（notifications /
 *      clipboard-sanitized-write / fullscreen，后者供大屏页 HTML5 全屏使用）、
 *      check 与 request 同口径，以及拒绝告警含 permission 名与来源 URL。
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const test = require('node:test');

const MAIN_JS = path.resolve(__dirname, '..', 'main.js');
const source = fs.readFileSync(MAIN_JS, 'utf8');

const SECTION_START = '// ─── 会话权限';
const SECTION_END = '// ─── 应用生命周期';
const WHITELIST = ['clipboard-sanitized-write', 'fullscreen', 'notifications'];
/** 明确应被拒绝的敏感权限（含 Electron 的 PermissionType 取值）。 */
const DENIED_PERMISSIONS = [
  'camera',
  'microphone',
  'geolocation',
  'midi',
  'midiSysex',
  'display-capture',
  'clipboard-read',
  'serial',
  'hid',
  'usb',
  'bluetooth',
];

function readSection() {
  const start = source.indexOf(SECTION_START);
  assert.ok(start >= 0, `main.js 找不到会话权限段落标记「${SECTION_START}」`);
  const end = source.indexOf(SECTION_END, start + 1);
  assert.ok(end > start, `main.js 找不到会话权限段落结束标记「${SECTION_END}」`);
  return source.slice(start, end);
}

/** 在 vm 沙箱里执行「会话权限」段落，返回注册到假 session 的两个回调。 */
function loadHandlers() {
  const warnings = [];
  const registered = {};
  const fakeSession = {
    defaultSession: {
      setPermissionRequestHandler: (fn) => { registered.request = fn; },
      setPermissionCheckHandler: (fn) => { registered.check = fn; },
    },
  };
  const sandbox = {
    console: {
      log: () => {},
      warn: (...args) => warnings.push(args.join(' ')),
    },
    session: fakeSession,
  };

  vm.runInNewContext(
    `${readSection()}\n;globalThis.__setupPermissionHandlers = setupPermissionHandlers;`,
    sandbox,
  );
  assert.strictEqual(typeof sandbox.__setupPermissionHandlers, 'function', '未定义 setupPermissionHandlers');
  sandbox.__setupPermissionHandlers();

  assert.strictEqual(typeof registered.request, 'function', '未注册 setPermissionRequestHandler');
  assert.strictEqual(typeof registered.check, 'function', '未注册 setPermissionCheckHandler');
  return { request: registered.request, check: registered.check, warnings };
}

function makeWebContents(url = 'http://127.0.0.1:8000/system') {
  return { getURL: () => url };
}

/** 调一次 request handler，返回实际传给 callback 的值。 */
function requestPermission(handler, permission, webContents = makeWebContents()) {
  let result;
  handler(webContents, permission, (allowed) => { result = allowed; }, {});
  return result;
}

test('main.js 注册了 request 与 check 两个权限处理器', () => {
  loadHandlers();
  const section = readSection();
  assert.ok(
    section.includes('session.defaultSession'),
    '权限处理器必须注册在 session.defaultSession（会话级）上',
  );
  assert.ok(
    section.includes('setPermissionRequestHandler'),
    'main.js 必须注册 setPermissionRequestHandler（默认批准是本次审计的缺口）',
  );
  assert.ok(
    section.includes('setPermissionCheckHandler'),
    'main.js 必须注册 setPermissionCheckHandler，否则能力检查路径仍会把权限判为可用',
  );
});

test('main.js 在 whenReady 回调内、创建窗口之前调用 setupPermissionHandlers', () => {
  const readyStart = source.indexOf('app.whenReady().then');
  assert.ok(readyStart >= 0, 'main.js 未注册 app.whenReady');
  const readyEnd = source.indexOf('\n});', readyStart);
  assert.ok(readyEnd > readyStart, 'whenReady 回调边界解析失败');
  const readyBlock = source.slice(readyStart, readyEnd);

  const setupIdx = readyBlock.indexOf('setupPermissionHandlers();');
  assert.ok(setupIdx > 0, 'whenReady 内未调用 setupPermissionHandlers()，权限仍是默认批准');
  const windowIdx = readyBlock.indexOf('createMainWindow()');
  assert.ok(windowIdx > 0, 'whenReady 内找不到 createMainWindow()');
  assert.ok(
    setupIdx < windowIdx,
    'setupPermissionHandlers() 必须在 createMainWindow() 之前调用，否则首个窗口的权限请求仍走默认策略',
  );
});

test('白名单只含 notifications / clipboard-sanitized-write / fullscreen（多一个即权限面扩大）', () => {
  const section = readSection();
  const matched = section.match(/SESSION_PERMISSION_ALLOWLIST\s*=\s*new Set\(\[([\s\S]*?)\]\)/);
  assert.ok(matched, '找不到 SESSION_PERMISSION_ALLOWLIST 的 Set 字面量');
  const actual = [...matched[1].matchAll(/'([^']+)'/g)].map((m) => m[1]).sort();
  assert.deepStrictEqual(actual, WHITELIST, '白名单必须严格等于约定的三项权限');
});

test('fullscreen 必须放行（大屏页 BigScreen.vue 依赖 HTML5 全屏，属产品功能）', () => {
  const { request, check } = loadHandlers();
  assert.strictEqual(requestPermission(request, 'fullscreen'), true, 'fullscreen 被拒会让大屏页无法全屏');
  assert.strictEqual(check(makeWebContents(), 'fullscreen', 'http://127.0.0.1:8000'), true);
  assert.ok(
    readSection().includes('BigScreen.vue'),
    '白名单注释必须写明放行理由（大屏页 BigScreen.vue 依赖 HTML5 全屏），避免后续被当成多余项删除',
  );
});

test('request handler：敏感权限默认拒绝，且拒绝时 callback 收到 false（非 undefined）', () => {
  const { request, warnings } = loadHandlers();
  for (const permission of DENIED_PERMISSIONS) {
    const allowed = requestPermission(request, permission);
    assert.strictEqual(allowed, false, `${permission} 必须默认拒绝`);
    assert.ok(
      warnings.some((line) => line.includes(permission) && line.includes('http://127.0.0.1:8000/system')),
      `${permission} 的拒绝告警必须同时含 permission 名与来源 URL（现场排障依据）`,
    );
  }
});

test('request handler：白名单权限放行', () => {
  const { request } = loadHandlers();
  for (const permission of WHITELIST) {
    assert.strictEqual(requestPermission(request, permission), true, `${permission} 应在白名单内放行`);
  }
});

test('check handler：与 request 同口径返回布尔（避免只拦 request 的绕过）', () => {
  const { request, check } = loadHandlers();
  for (const permission of [...WHITELIST, ...DENIED_PERMISSIONS]) {
    const requestAllowed = requestPermission(request, permission);
    const checkAllowed = check(makeWebContents(), permission, 'http://127.0.0.1:8000');
    assert.strictEqual(typeof checkAllowed, 'boolean', `check handler 对 ${permission} 必须返回布尔值`);
    assert.strictEqual(checkAllowed, requestAllowed, `${permission} 在 request 与 check 两个 handler 上必须同口径`);
  }
});

test('未知权限 fail-closed 拒绝（新增的 PermissionType 不会默认放行）', () => {
  const { request, check } = loadHandlers();
  assert.strictEqual(requestPermission(request, 'brand-new-permission-type'), false);
  assert.strictEqual(check(makeWebContents(), 'brand-new-permission-type', 'http://127.0.0.1:8000'), false);
});

test('来源 URL 取不到时告警回退 unknown，不因 getURL 抛错中断拒绝', () => {
  const { request, warnings } = loadHandlers();
  const brokenWebContents = { getURL: () => { throw new Error('destroyed'); } };
  assert.strictEqual(requestPermission(request, 'camera', brokenWebContents), false);
  assert.ok(
    warnings.some((line) => line.includes('camera') && line.includes('unknown')),
    'getURL 抛错时应回退 unknown 并继续拒绝，不能把异常抛给 Electron',
  );
});
