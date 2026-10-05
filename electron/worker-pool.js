/**
 * Electron Worker Thread Pool
 *
 * 将 CPU/IO 密集型任务从主进程转移到 Worker 线程，防止 UI 假死。
 *
 * 支持任务类型：
 *   - encrypt-file:   AES-256-GCM 文件加密
 *   - decrypt-file:   文件解密
 *   - hash-file:      SHA-256 文件哈希（用于完整性校验）
 *   - compress:       gzip 压缩大 JSON
 *   - decompress:     gzip 解压
 *
 * Usage:
 *   const { workerPool } = require('./worker-pool');
 *   const result = await workerPool.exec('encrypt-file', { inputPath, outputPath, key });
 */

const { Worker } = require('worker_threads');
const path = require('path');
const os = require('os');

const MAX_WORKERS = Math.max(2, os.cpus().length - 1);
const WORKER_SCRIPT = path.join(__dirname, 'worker-tasks.js');

class WorkerPool {
  constructor(maxWorkers = MAX_WORKERS) {
    this.maxWorkers = maxWorkers;
    this._workers = [];
    this._queue = [];
    this._active = 0;
    this._idCounter = 0;
  }

  /**
   * 执行任务
   * @param {string} task - 任务类型
   * @param {object} payload - 任务参数
   * @param {number} [timeout=120000] - 超时 (ms)
   * @returns {Promise<any>}
   */
  exec(task, payload, timeout = 120000) {
    return new Promise((resolve, reject) => {
      const job = {
        id: ++this._idCounter,
        task,
        payload,
        resolve,
        reject,
        timer: null,
        worker: null,
        done: false,
      };
      job.timer = setTimeout(() => {
        if (job.done) return;
        job.done = true;
        if (job.worker) {
          // 已在执行：必须强制终止，否则 hang 死的任务会永久占用并发槽位；
          // 同时回收计数（exit 回调因 done 标记不再重复处理）。
          this._active = Math.max(0, this._active - 1);
          job.worker.terminate();
          this._processNext();
        } else {
          this._cleanup(job.id);
        }
        reject(new Error(`Worker task "${task}" timed out after ${timeout}ms`));
      }, timeout);

      this._queue.push(job);
      this._processNext();
    });
  }

  _processNext() {
    if (this._queue.length === 0) return;
    if (this._active >= this.maxWorkers) return;

    const job = this._queue.shift();
    this._active++;

    const worker = new Worker(WORKER_SCRIPT, {
      workerData: { task: job.task, payload: job.payload },
    });
    job.worker = worker;

    // 终局收敛到单一路径：settle 只执行一次、_active 只扣减一次。
    // 此前 message 与 exit(code=1) 各扣一次（terminate 的 exit code 恒为 1），
    // _active 单调变负导致 maxWorkers 并发闸门永久失效。
    const finish = (ok, value) => {
      if (job.done) return;
      job.done = true;
      clearTimeout(job.timer);
      this._active = Math.max(0, this._active - 1);
      if (ok) job.resolve(value);
      else job.reject(value instanceof Error ? value : new Error(String(value)));
      // 幂等：对已退出的 worker 调用 terminate 是安全空操作
      worker.terminate();
      this._processNext();
    };

    worker.on('message', (result) => {
      if (result && result.error) finish(false, new Error(result.error));
      else finish(true, result ? result.data : undefined);
    });

    worker.on('error', (err) => finish(false, err));

    worker.on('exit', (code) => {
      if (code !== 0) {
        finish(false, new Error(`Worker exited with code ${code}`));
      }
    });
  }

  _cleanup(id) {
    this._queue = this._queue.filter((j) => j.id !== id);
  }

  get stats() {
    return { active: this._active, queued: this._queue.length, max: this.maxWorkers };
  }
}

// 单例
const workerPool = new WorkerPool();
module.exports = { WorkerPool, workerPool };
