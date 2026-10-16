'use strict';

/**
 * 路径安全守卫 —— 主进程 IPC 层与 worker 线程**共用同一实现**。
 *
 * M50（2026-10-14）：此前 worker-tasks.js 自带一份 validatePath()，白名单根目录
 * 用 `LOCALAPPDATA + bumofu-assistance` 自行推断，与真实
 * `app.getPath('userData')`（%APPDATA%\帮扶管理系统）不一致 → 加密/解密对真实
 * 数据一律 forbidden-path；且 hash-file 分支压根没调校验。规则重复实现必然漂移，
 * 故收口到本模块：根目录由**主进程**注入，worker 只消费。
 *
 * 约定：
 *   - 根目录一律 path.resolve 后比较；Windows（NTFS 大小写不敏感）下比较时
 *     统一转小写，避免 `C:\Users\X\AppData` 与 `c:\users\x\appdata` 这类
 *     同一目录因大小写不同被误判为越界（旧实现是精确比较，会漏判）。
 *   - 密钥文件（secrets.json / runtime_secrets.json / master.key）无论落在哪个
 *     根目录下都显式拒绝 —— 与主进程 open-path 的既有口径一致。
 */

const path = require('path');

/** 命中即拒绝的密钥文件名片段（小写比较） */
const SECRET_PATH_FRAGMENTS = [
  'runtime_secrets.json',
  'secrets.json',
  'master.key',
];

const IS_WINDOWS = process.platform === 'win32';

/** 该路径是否指向密钥/主密钥文件 */
function isSecretsPath(resolvedPath) {
  const lower = String(resolvedPath || '').toLowerCase();
  return SECRET_PATH_FRAGMENTS.some((fragment) => lower.includes(fragment));
}

/** 归一化根目录列表（去空、去非字符串、resolve） */
function normalizeRoots(roots) {
  return (Array.isArray(roots) ? roots : [])
    .filter((root) => typeof root === 'string' && root.length > 0)
    .map((root) => path.resolve(root));
}

function _comparable(p) {
  return IS_WINDOWS ? p.toLowerCase() : p;
}

/**
 * 路径是否在允许的根目录内且非密钥文件。
 * @param {string} filePath
 * @param {string[]} roots 允许的根目录（含自身与所有后代）
 * @returns {boolean}
 */
function isPathAllowed(filePath, roots) {
  const resolved = path.resolve(String(filePath || ''));
  if (isSecretsPath(resolved)) return false;
  const target = _comparable(resolved);
  return normalizeRoots(roots).some((root) => {
    const base = _comparable(root);
    return target === base || target.startsWith(base + path.sep);
  });
}

/**
 * 校验通过返回 resolve 后的路径，否则抛 `forbidden-path: <resolved>`。
 * @throws {Error}
 */
function assertPathAllowed(filePath, roots) {
  const resolved = path.resolve(String(filePath || ''));
  if (!isPathAllowed(resolved, roots)) {
    throw new Error(`forbidden-path: ${resolved}`);
  }
  return resolved;
}

module.exports = {
  SECRET_PATH_FRAGMENTS,
  isSecretsPath,
  normalizeRoots,
  isPathAllowed,
  assertPathAllowed,
};
