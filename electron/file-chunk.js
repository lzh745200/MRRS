'use strict';

/**
 * 大文件分块读取（真实游标接口）—— M49（2026-10-14）。
 *
 * 旧实现在 IPC 处理器里 `createReadStream(...).on('data', c => chunks.push(c))`
 * 后 `chunks.join('')`：名为分块，实为把**整个文件**（base64 再放大 1.33×）
 * 驻留主进程内存 → 大文件必然 OOM，且 IPC 一次性序列化巨型字符串还会卡 UI。
 *
 * 本模块只负责"读一段"：调用方拿 nextOffset 循环取块，主进程峰值内存 =
 * 单块大小（默认 256KB，硬上限 4MB），与文件总大小无关。
 * 抽成独立模块是为了可被 node 直接测试（不依赖 electron 运行时）。
 */

const fs = require('fs');

const DEFAULT_CHUNK_BYTES = 256 * 1024;
/** 单次读取硬上限：防止渲染进程传入超大 length 又把内存打回去 */
const MAX_CHUNK_BYTES = 4 * 1024 * 1024;

/**
 * 归一化读取参数。
 * 兼容旧签名 readFileChunked(path, chunkSize: number) —— 视为"从 0 读一块"。
 */
function normalizeChunkOptions(options) {
  const opts = typeof options === 'number' ? { length: options } : (options || {});
  const rawOffset = Number(opts.offset);
  const rawLength = Number(opts.length);
  const offset = Number.isFinite(rawOffset) && rawOffset > 0 ? Math.floor(rawOffset) : 0;
  const requested = Number.isFinite(rawLength) && rawLength > 0
    ? Math.floor(rawLength)
    : DEFAULT_CHUNK_BYTES;
  return { offset, length: Math.min(requested, MAX_CHUNK_BYTES) };
}

/**
 * 读取 [offset, offset+length) 区间，返回 base64 数据与游标信息。
 *
 * @param {string} filePath 已通过白名单校验的路径（本模块不做安全校验）
 * @param {number|{offset?: number, length?: number}} [options]
 * @returns {Promise<{data: string, offset: number, bytesRead: number, size: number, nextOffset: number, eof: boolean}>}
 * @throws {Error} 路径不存在/非普通文件/offset 越界（调用方转成 IPC 错误码）
 */
async function readFileChunk(filePath, options) {
  const { offset, length } = normalizeChunkOptions(options);
  const fd = await fs.promises.open(filePath, 'r');
  try {
    const stat = await fd.stat();
    if (!stat.isFile()) {
      throw new Error('not-a-file');
    }
    const size = stat.size;
    if (offset > size) {
      throw new Error('offset-out-of-range');
    }
    const toRead = Math.min(length, size - offset);
    if (toRead <= 0) {
      return { data: '', offset, bytesRead: 0, size, nextOffset: size, eof: true };
    }
    const buffer = Buffer.allocUnsafe(toRead);
    const { bytesRead } = await fd.read(buffer, 0, toRead, offset);
    const nextOffset = offset + bytesRead;
    return {
      data: buffer.subarray(0, bytesRead).toString('base64'),
      offset,
      bytesRead,
      size,
      nextOffset,
      eof: nextOffset >= size,
    };
  } finally {
    try { await fd.close(); } catch (_) { /* 关闭失败不影响结果 */ }
  }
}

module.exports = {
  DEFAULT_CHUNK_BYTES,
  MAX_CHUNK_BYTES,
  normalizeChunkOptions,
  readFileChunk,
};
