/**
 * 分块读取单元测试（M49 回归）
 *
 * 运行: node electron/tests/file-chunk.test.js
 *
 * 核心断言：分块接口**真的按游标读**——每次返回的字节数受 length 限制，
 * 与文件总大小无关（旧实现 chunks.join('') 会把整文件读进内存）。
 */

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const {
  readFileChunk,
  normalizeChunkOptions,
  DEFAULT_CHUNK_BYTES,
  MAX_CHUNK_BYTES,
} = require('../file-chunk');

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
  console.log('File Chunk Tests\n');

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'mrrms-chunk-'));
  const bigPath = path.join(tmpDir, 'big.bin');
  const payload = Buffer.alloc(700 * 1024);
  for (let i = 0; i < payload.length; i++) payload[i] = i % 251;
  fs.writeFileSync(bigPath, payload);

  const smallPath = path.join(tmpDir, 'small.txt');
  fs.writeFileSync(smallPath, 'hello-world', 'utf-8');

  await test('单块读取不超过请求长度（峰值内存与文件大小解耦）', async () => {
    const r = await readFileChunk(bigPath, { offset: 0, length: 1024 });
    assert.strictEqual(r.bytesRead, 1024);
    assert.strictEqual(Buffer.from(r.data, 'base64').length, 1024);
    assert.strictEqual(r.size, payload.length);
    assert.strictEqual(r.nextOffset, 1024);
    assert.strictEqual(r.eof, false);
  });

  await test('游标循环取块可无损还原整个文件', async () => {
    const parts = [];
    let cursor = 0;
    let guard = 0;
    for (;;) {
      const r = await readFileChunk(bigPath, { offset: cursor, length: 64 * 1024 });
      parts.push(Buffer.from(r.data, 'base64'));
      cursor = r.nextOffset;
      if (r.eof) break;
      if (++guard > 100) throw new Error('分块循环未收敛');
    }
    const merged = Buffer.concat(parts);
    assert.strictEqual(merged.length, payload.length);
    assert.ok(merged.equals(payload), '还原内容与原文件不一致');
  });

  await test('每块 data 长度受 length 约束（不再整文件驻留）', async () => {
    const r = await readFileChunk(bigPath, { offset: 0, length: 32 * 1024 });
    assert.ok(Buffer.from(r.data, 'base64').length <= 32 * 1024);
  });

  await test('length 超过硬上限时被裁剪到 MAX_CHUNK_BYTES', async () => {
    const r = await readFileChunk(bigPath, { offset: 0, length: 999 * 1024 * 1024 });
    assert.ok(Buffer.from(r.data, 'base64').length <= MAX_CHUNK_BYTES);
  });

  await test('小文件一次读完并标记 eof', async () => {
    const r = await readFileChunk(smallPath, { offset: 0, length: 4096 });
    assert.strictEqual(Buffer.from(r.data, 'base64').toString('utf-8'), 'hello-world');
    assert.strictEqual(r.eof, true);
    assert.strictEqual(r.nextOffset, 11);
  });

  await test('offset == size 时返回空块且 eof=true', async () => {
    const r = await readFileChunk(smallPath, { offset: 11, length: 16 });
    assert.strictEqual(r.data, '');
    assert.strictEqual(r.bytesRead, 0);
    assert.strictEqual(r.eof, true);
  });

  await test('offset 越界抛错（调用方转 offset-out-of-range）', async () => {
    await assert.rejects(() => readFileChunk(smallPath, { offset: 999, length: 16 }), /offset-out-of-range/);
  });

  await test('路径不存在抛错（调用方转 read-failed）', async () => {
    await assert.rejects(() => readFileChunk(path.join(tmpDir, 'nope.bin'), { offset: 0, length: 16 }));
  });

  await test('目录路径抛 not-a-file', async () => {
    await assert.rejects(() => readFileChunk(tmpDir, { offset: 0, length: 16 }), /not-a-file/);
  });

  await test('旧签名（第二参为数字）按"从 0 读一块"兼容', async () => {
    const r = await readFileChunk(bigPath, 2048);
    assert.strictEqual(r.bytesRead, 2048);
    assert.strictEqual(r.offset, 0);
  });

  await test('normalizeChunkOptions 处理非法/负数输入', async () => {
    assert.deepStrictEqual(normalizeChunkOptions(undefined), { offset: 0, length: DEFAULT_CHUNK_BYTES });
    assert.deepStrictEqual(normalizeChunkOptions({ offset: -5, length: -1 }), { offset: 0, length: DEFAULT_CHUNK_BYTES });
    assert.deepStrictEqual(normalizeChunkOptions({ offset: 3.7, length: 10.2 }), { offset: 3, length: 10 });
  });

  fs.rmSync(tmpDir, { recursive: true, force: true });

  console.log(`\n${passed} passed, ${failed} failed`);
  if (failed > 0) process.exit(1);
}

run().catch((err) => {
  console.error('Test runner error:', err);
  process.exit(1);
});
