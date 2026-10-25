/**
 * 路径守卫单元测试（M50 回归）
 *
 * 运行: node electron/tests/path-guard.test.js
 *
 * 覆盖 R27-M50 的两个缺陷：
 *   1. 白名单根目录必须由调用方（主进程）注入，不再自行拼 LOCALAPPDATA/bumofu-assistance；
 *   2. hash-file 走的是同一份校验（不再存在"没调 validatePath"的分支）。
 */

const assert = require('assert');
const path = require('path');
const os = require('os');

const {
  isPathAllowed,
  assertPathAllowed,
  isSecretsPath,
  normalizeRoots,
} = require('../path-guard');

let passed = 0;
let failed = 0;

async function test(name, fn) {
  try {
    await fn();
    console.log(`  PASS: ${name}`);
    passed++;
  } catch (err) {
    console.error(`  FAIL: ${name} — ${err.message}`);
    failed++;
  }
}

async function run() {
  console.log('Path Guard Tests\n');

  const userData = path.join(os.tmpdir(), 'mrrms-guard-userdata');
  const appDir = path.join(os.tmpdir(), 'mrrms-guard-app');
  const roots = [userData, appDir, os.tmpdir()];

  await test('应用数据目录内的文件放行', async () => {
    assert.strictEqual(isPathAllowed(path.join(userData, 'database', 'x.db'), roots), true);
  });

  await test('根目录自身放行', async () => {
    assert.strictEqual(isPathAllowed(userData, roots), true);
  });

  await test('白名单之外拒绝（真实 userData 不再被误拒的前提：根由主进程注入）', async () => {
    const outside = process.platform === 'win32' ? 'C:\\Windows\\System32\\drivers\\etc\\hosts' : '/etc/hosts';
    assert.strictEqual(isPathAllowed(outside, roots), false);
  });

  await test('同前缀但不同目录不误放行（C:\\a 不得匹配 C:\\ab）', async () => {
    // 注意：不能把 os.tmpdir() 放进白名单 —— userData 与 sibling 都在其下，
    // 那样会因父目录命中而"看起来放行"，测不出前缀误判。
    const scopedRoots = [userData, appDir];
    const sibling = userData + '-evil';
    assert.strictEqual(isPathAllowed(path.join(sibling, 'x'), scopedRoots), false);
    assert.strictEqual(isPathAllowed(path.join(appDir + '-evil', 'x'), scopedRoots), false);
  });

  await test('密钥文件无论落在哪个根目录都拒绝', async () => {
    assert.strictEqual(isPathAllowed(path.join(userData, 'secrets.json'), roots), false);
    assert.strictEqual(isPathAllowed(path.join(userData, 'runtime_secrets.json'), roots), false);
    assert.strictEqual(isPathAllowed(path.join(userData, 'master.key'), roots), false);
  });

  await test('isSecretsPath 大小写不敏感', async () => {
    assert.strictEqual(isSecretsPath('C:\\X\\SECRETS.JSON'), true);
    assert.strictEqual(isSecretsPath('C:\\X\\normal.db'), false);
  });

  await test('assertPathAllowed 拒绝时抛 forbidden-path 且带 resolve 后路径', async () => {
    const outside = process.platform === 'win32' ? 'C:\\Windows\\win.ini' : '/etc/passwd';
    assert.throws(() => assertPathAllowed(outside, roots), /forbidden-path: /);
  });

  await test('assertPathAllowed 通过时返回 resolve 后路径', async () => {
    const target = path.join(userData, '..', 'mrrms-guard-userdata', 'a.txt');
    assert.strictEqual(assertPathAllowed(target, roots), path.resolve(target));
  });

  await test('normalizeRoots 过滤空值与非字符串', async () => {
    assert.deepStrictEqual(normalizeRoots([userData, '', null, undefined, 42]), [path.resolve(userData)]);
  });

  await test('根列表为空时一律拒绝（fail-closed）', async () => {
    assert.strictEqual(isPathAllowed(path.join(userData, 'a.txt'), []), false);
  });

  // Windows 大小写：同一目录的不同大小写写法应视为同一路径
  if (process.platform === 'win32') {
    await test('Windows 大小写不敏感比较（同一目录不同大小写仍放行）', async () => {
      const upper = userData.toUpperCase();
      assert.strictEqual(isPathAllowed(path.join(upper, 'a.txt'), roots), true);
    });
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  if (failed > 0) process.exit(1);
}

run().catch((err) => {
  console.error('Test runner error:', err);
  process.exit(1);
});
