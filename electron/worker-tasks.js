/**
 * Worker Tasks — 在 worker_threads 中执行的 CPU 密集型任务
 *
 * 由 worker-pool.js 加载，通过 workerData 接收 task + payload。
 * 执行完毕后通过 parentPort.postMessage 返回结果。
 */

const { parentPort, workerData } = require('worker_threads');
const crypto = require('crypto');
const fs = require('fs');
const zlib = require('zlib');
const path = require('path');
const os = require('os');

// M50：规则收口到 electron/path-guard.js（主进程 IPC 层与 worker 共用同一实现）
const { assertPathAllowed } = require('./path-guard');

const { task, payload, allowedRoots: injectedRoots } = workerData;

/**
 * 路径安全校验 — 仅允许应用数据目录/安装目录/系统临时目录。
 *
 * M50（2026-10-14）：根目录**由主进程注入**（workerData.allowedRoots，取自
 * app.getPath('userData')/app.getAppPath()/os.tmpdir()）。旧实现在 worker 内自行
 * 拼 `LOCALAPPDATA/bumofu-assistance`，与真实 userData（%APPDATA%\帮扶管理系统）
 * 不一致 → 加密/解密对真实数据一律 forbidden-path。
 * 缺省回退仅在"未走主进程 IPC"的直连/测试场景生效，且保持同等强度。
 */
function resolveAllowedRoots() {
  if (Array.isArray(injectedRoots) && injectedRoots.length > 0) {
    return injectedRoots.map((p) => path.resolve(p));
  }
  const appData = process.env.LOCALAPPDATA || process.env.XDG_DATA_HOME || os.homedir();
  return [
    path.join(appData, 'bumofu-assistance'),
    path.resolve(__dirname, '..'),
    os.tmpdir(),
  ].map((p) => path.resolve(p));
}

function validatePath(filePath) {
  return assertPathAllowed(filePath, resolveAllowedRoots());
}

/**
 * 分块读取文件 → 处理 → 写入（避免大文件撑爆内存）
 */
function streamProcess(inputPath, outputPath, transform) {
  return new Promise((resolve, reject) => {
    const readStream = fs.createReadStream(inputPath, { highWaterMark: 64 * 1024 });
    const writeStream = fs.createWriteStream(outputPath);
    readStream.on('error', reject);
    writeStream.on('error', reject);
    writeStream.on('finish', () => resolve({ outputPath }));
    readStream.pipe(transform).pipe(writeStream);
  });
}

async function run() {
  try {
    let result;

    switch (task) {

      // ── AES-256-GCM 文件加密 ──
      case 'encrypt-file': {
        payload.inputPath = validatePath(payload.inputPath);
        payload.outputPath = validatePath(payload.outputPath);
        const key = crypto.scryptSync(payload.password, payload.salt || 'mrrms', 32);
        const iv = crypto.randomBytes(16);
        const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);

        // 写入 IV + 认证标签头
        const header = Buffer.concat([iv]);
        const tempPath = payload.outputPath + '.tmp';
        await streamProcess(payload.inputPath, tempPath, cipher);

        // 获取认证标签并写入最终文件
        const tag = cipher.getAuthTag();
        const fd = fs.openSync(payload.outputPath, 'w');
        fs.writeSync(fd, header);
        fs.writeSync(fd, tag);
        const encrypted = fs.readFileSync(tempPath);
        fs.writeSync(fd, encrypted);
        fs.closeSync(fd);
        fs.unlinkSync(tempPath);

        result = { outputPath: payload.outputPath, size: fs.statSync(payload.outputPath).size };
        break;
      }

      // ── AES-256-GCM 文件解密 ──
      case 'decrypt-file': {
        payload.inputPath = validatePath(payload.inputPath);
        payload.outputPath = validatePath(payload.outputPath);
        const key = crypto.scryptSync(payload.password, payload.salt || 'mrrms', 32);
        const fd = fs.openSync(payload.inputPath, 'r');
        const iv = Buffer.alloc(16);
        fs.readSync(fd, iv, 0, 16, 0);
        const tag = Buffer.alloc(16);
        const fileSize = fs.statSync(payload.inputPath).size;
        fs.readSync(fd, tag, 0, 16, fileSize - 16);
        const encryptedSize = fileSize - 32;
        const encrypted = Buffer.alloc(encryptedSize);
        fs.readSync(fd, encrypted, 0, encryptedSize, 16);
        fs.closeSync(fd);

        const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv);
        decipher.setAuthTag(tag);
        const decrypted = Buffer.concat([decipher.update(encrypted), decipher.final()]);
        fs.writeFileSync(payload.outputPath, decrypted);

        result = { outputPath: payload.outputPath, size: decrypted.length };
        break;
      }

      // ── SHA-256 文件哈希 ──
      case 'hash-file': {
        // M50：hash-file 原先完全跳过 validatePath —— 任意路径均可被渲染进程哈希
        payload.inputPath = validatePath(payload.inputPath);
        const hash = crypto.createHash('sha256');
        const stream = fs.createReadStream(payload.inputPath);
        await new Promise((resolve, reject) => {
          stream.on('data', (chunk) => hash.update(chunk));
          stream.on('end', resolve);
          stream.on('error', reject);
        });
        result = { hash: hash.digest('hex') };
        break;
      }

      // ── gzip 压缩 ──
      case 'compress': {
        const input = Buffer.from(payload.data, 'utf-8');
        const compressed = await new Promise((resolve, reject) => {
          zlib.gzip(input, (err, buf) => (err ? reject(err) : resolve(buf)));
        });
        result = { data: compressed.toString('base64'), originalSize: input.length, compressedSize: compressed.length };
        break;
      }

      // ── gzip 解压 ──
      case 'decompress': {
        const compressed = Buffer.from(payload.data, 'base64');
        const decompressed = await new Promise((resolve, reject) => {
          zlib.gunzip(compressed, (err, buf) => (err ? reject(err) : resolve(buf)));
        });
        result = { data: decompressed.toString('utf-8') };
        break;
      }

      default:
        throw new Error(`Unknown task: ${task}`);
    }

    parentPort.postMessage({ data: result });
  } catch (err) {
    parentPort.postMessage({ error: err.message });
  }
}

run();
