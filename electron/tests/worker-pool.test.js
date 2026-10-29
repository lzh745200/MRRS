/**
 * Worker Pool 单元测试
 *
 * 运行: node electron/tests/worker-pool.test.js
 */

const { WorkerPool } = require('../worker-pool');
const assert = require('assert');
const path = require('path');
const os = require('os');

async function runTests() {
  let passed = 0;
  let failed = 0;

  function test(name, fn) {
    return fn().then(() => {
      console.log(`  PASS: ${name}`);
      passed++;
    }).catch((err) => {
      console.error(`  FAIL: ${name} — ${err.message}`);
      failed++;
    });
  }

  console.log('Worker Pool Tests\n');

  // ── 初始化 ──
  await test('WorkerPool 实例化', async () => {
    const pool = new WorkerPool(2);
    assert.ok(pool instanceof WorkerPool);
    assert.strictEqual(pool.maxWorkers, 2);
    assert.deepStrictEqual(pool.stats, { active: 0, queued: 0, max: 2 });
  });

  await test('stats 反映空闲状态', async () => {
    const pool = new WorkerPool(2);
    const s = pool.stats;
    assert.strictEqual(s.active, 0);
    assert.strictEqual(s.queued, 0);
    assert.strictEqual(s.max, 2);
  });

  // ── 默认 maxWorkers ──
  await test('默认 maxWorkers 基于 CPU 核数', async () => {
    const os = require('os');
    const pool = new WorkerPool();
    assert.ok(pool.maxWorkers >= 2);
    assert.ok(pool.maxWorkers <= os.cpus().length);
  });

  // ── Worker 任务执行（需要 worker-tasks.js 存在） ──
  await test('worker-tasks.js 脚本存在', async () => {
    const fs = require('fs');
    const path = require('path');
    const scriptPath = path.join(__dirname, '..', 'worker-tasks.js');
    assert.ok(fs.existsSync(scriptPath), `worker-tasks.js not found at ${scriptPath}`);
  });

  // ── hash-file 端到端测试 ──
  await test('hash-file 任务（创建临时文件并计算 SHA-256）', async () => {
    const fs = require('fs');
    const path = require('path');
    const os = require('os');
    const crypto = require('crypto');

    const tmpFile = path.join(os.tmpdir(), `mrrms-test-${Date.now()}.tmp`);
    const content = Buffer.from('test-data-' + Date.now());
    fs.writeFileSync(tmpFile, content);

    const expectedHash = crypto.createHash('sha256').update(content).digest('hex');

    const pool = new WorkerPool(2);
    const result = await pool.exec('hash-file', { inputPath: tmpFile }, 5000);

    assert.strictEqual(result.hash, expectedHash, 'hash mismatch');
    fs.unlinkSync(tmpFile);
  });

  // ── AES-256-GCM 加解密往返（布局 IV+TAG+密文）──
  // 旧实现加密写 IV+TAG+CT，解密却把文件末尾 16 字节当 TAG，
  // 因此连自己刚生成的文件都解不开（本用例在旧实现上必失败）。
  await test('encrypt-file → decrypt-file 往返一致（IV+TAG+密文）', async () => {
    const fs = require('fs');
    const path = require('path');
    const os = require('os');
    const crypto = require('crypto');

    const source = path.join(os.tmpdir(), `mrrms-plain-${Date.now()}.bin`);
    const encrypted = path.join(os.tmpdir(), `mrrms-enc-${Date.now()}.enc`);
    const decrypted = path.join(os.tmpdir(), `mrrms-dec-${Date.now()}.bin`);
    const content = crypto.randomBytes(512 * 1024);
    fs.writeFileSync(source, content);

    const pool = new WorkerPool(1);
    try {
      await pool.exec(
        'encrypt-file',
        { inputPath: source, outputPath: encrypted, password: 'test-pass-123' },
        20000,
        { allowedRoots: [os.tmpdir()] }
      );
      assert.strictEqual(fs.statSync(encrypted).size, content.length + 32, '密文应为 IV+TAG+明文长度');

      await pool.exec(
        'decrypt-file',
        { inputPath: encrypted, outputPath: decrypted, password: 'test-pass-123' },
        20000,
        { allowedRoots: [os.tmpdir()] }
      );
      assert.ok(fs.readFileSync(decrypted).equals(content), '解密结果必须与原文一致');
    } finally {
      for (const f of [source, encrypted, decrypted]) {
        try {
          fs.unlinkSync(f);
        } catch {
          /* 忽略清理失败 */
        }
      }
    }
  });

  await test('解密被篡改的密文必须认证失败且不产出明文', async () => {
    const fs = require('fs');
    const path = require('path');
    const os = require('os');

    const source = path.join(os.tmpdir(), `mrrms-tamper-src-${Date.now()}.bin`);
    const encrypted = path.join(os.tmpdir(), `mrrms-tamper-${Date.now()}.enc`);
    const output = path.join(os.tmpdir(), `mrrms-tamper-out-${Date.now()}.bin`);
    fs.writeFileSync(source, Buffer.from('tamper-check-content'));

    const pool = new WorkerPool(1);
    try {
      await pool.exec(
        'encrypt-file',
        { inputPath: source, outputPath: encrypted, password: 'test-pass-123' },
        20000,
        { allowedRoots: [os.tmpdir()] }
      );
      const bytes = fs.readFileSync(encrypted);
      bytes[bytes.length - 1] ^= 0xff;
      fs.writeFileSync(encrypted, bytes);

      await assert.rejects(
        () =>
          pool.exec(
            'decrypt-file',
            { inputPath: encrypted, outputPath: output, password: 'test-pass-123' },
            20000,
            { allowedRoots: [os.tmpdir()] }
          ),
        /authenticate|Unsupported state/i
      );
      assert.ok(!fs.existsSync(output), '认证失败不得留下半成品明文');
    } finally {
      for (const f of [source, encrypted, output]) {
        try {
          fs.unlinkSync(f);
        } catch {
          /* 忽略清理失败 */
        }
      }
    }
  });

  await test('过短的加密文件被拒绝（不足 IV+TAG）', async () => {
    const fs = require('fs');
    const path = require('path');
    const os = require('os');
    const shortFile = path.join(os.tmpdir(), `mrrms-short-${Date.now()}.enc`);
    fs.writeFileSync(shortFile, Buffer.alloc(31));
    const pool = new WorkerPool(1);
    try {
      await assert.rejects(
        () =>
          pool.exec(
            'decrypt-file',
            { inputPath: shortFile, outputPath: shortFile + '.out', password: 'x' },
            5000,
            { allowedRoots: [os.tmpdir()] }
          ),
        /长度非法/
      );
    } finally {
      try {
        fs.unlinkSync(shortFile);
      } catch {
        /* 忽略清理失败 */
      }
    }
  });

  // ── 超时测试 ──
  // 2026-10-14（M50 收口）：旧断言用 '/nonexistent/file' 期望 ENOENT，但该路径
  // 本就在白名单之外 —— hash-file 现在与其它文件任务走同一份 validatePath，
  // 返回的是 forbidden-path。为了让本用例真正测"超时"语义，改用**白名单内**
  // 且确实不存在的路径（临时目录），此时才会走到读文件的 ENOENT 分支。
  await test('exec 超时应抛错（白名单内不存在路径 → ENOENT/超时）', async () => {
    const pool = new WorkerPool(1);
    const missing = path.join(os.tmpdir(), `mrrms-missing-${Date.now()}.tmp`);
    try {
      await pool.exec('hash-file', { inputPath: missing }, 100);
      throw new Error('should have timed out');
    } catch (err) {
      assert.ok(err.message.includes('timed out') || err.message.includes('ENOENT'),
        `unexpected error: ${err.message}`);
    }
  });

  // ── M50 回归：白名单外路径必须被拒（worker 层防线）──
  await test('hash-file 拒绝白名单外路径（M50）', async () => {
    const pool = new WorkerPool(1);
    const outside = process.platform === 'win32' ? 'C:\\Windows\\win.ini' : '/etc/hostname';
    try {
      await pool.exec('hash-file', { inputPath: outside }, 5000);
      throw new Error('should have been rejected');
    } catch (err) {
      assert.ok(err.message.includes('forbidden-path'), `unexpected error: ${err.message}`);
    }
  });

  // ── M50 回归：主进程注入的根目录被采纳（真实 userData 不再误拒）──
  await test('allowedRoots 由主进程注入时被采纳（M50）', async () => {
    const fs = require('fs');
    const os = require('os');
    const path = require('path');
    const crypto = require('crypto');
    const tmpFile = path.join(os.tmpdir(), `mrrms-inject-${Date.now()}.tmp`);
    const content = Buffer.from('injected-roots-' + Date.now());
    fs.writeFileSync(tmpFile, content);
    const expected = crypto.createHash('sha256').update(content).digest('hex');
    const pool = new WorkerPool(1);
    const result = await pool.exec('hash-file', { inputPath: tmpFile }, 5000, { allowedRoots: [os.tmpdir()] });
    assert.strictEqual(result.hash, expected);
    fs.unlinkSync(tmpFile);
  });

  // ── 结果 ──
  console.log(`\n${passed} passed, ${failed} failed`);
  if (failed > 0) process.exit(1);
}

runTests().catch((err) => {
  console.error('Test runner error:', err);
  process.exit(1);
});
