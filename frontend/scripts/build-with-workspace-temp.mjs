/**
 * 以「工作区内临时目录」执行 `vite build`（Windows 打包链路的第一步）。
 *
 * ## 为什么需要它（2026-10-28 实测，不是猜测）
 *
 * 直接跑 `npm run build` 时构建**失败**：
 *
 *     [vite:esbuild-transpile] remove C:\Users\Administrator\AppData\Local\Temp\esbuild-...: Access is denied.
 *
 * 本机 %TEMP% 目录存在「拒绝删除子项」的 ACL，esbuild 在转译阶段删除自己的临时文件时被拒，
 * vite 直接把整次构建判失败。把 TEMP/TMP 指到仓库内 `.scratch/tmp` 后，**同一条构建 rc=0**。
 * 也就是说：这是环境缺陷，但必须由脚本兜住 —— 否则每台新机器、每次 CI 缓存态变化，
 * 都要有人肉去试一遍 `$env:TEMP=...` 才知道。
 *
 * ## 策略
 *
 * - 把 TEMP / TMP / TMPDIR 指到 `<repo>/.scratch/tmp`（已被 .gitignore 忽略）；
 * - 目录**创建失败**时静默沿用系统值：不能因为权限问题再制造一个新故障；
 * - 用 `node` 直接执行 vite 入口，避免 Windows 下 .cmd shell 包装带来的引号/退出码差异。
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const REPO_ROOT = path.resolve(FRONTEND, '..');
const WORKSPACE_TMP = path.join(REPO_ROOT, '.scratch', 'tmp');

try {
  fs.mkdirSync(WORKSPACE_TMP, { recursive: true });
} catch {
  // 只读介质 / ACL 限制：退回系统临时目录，不让构建因此再失败一次
}

const env = { ...process.env };
if (fs.existsSync(WORKSPACE_TMP)) {
  env.TEMP = WORKSPACE_TMP;
  env.TMP = WORKSPACE_TMP;
  env.TMPDIR = WORKSPACE_TMP;
}

const viteEntry = path.join(FRONTEND, 'node_modules', 'vite', 'bin', 'vite.js');
if (!fs.existsSync(viteEntry)) {
  console.error('[build] 找不到 vite 入口，请先在 frontend/ 执行 npm install：' + viteEntry);
  process.exit(1);
}

const child = spawn(process.execPath, [viteEntry, 'build', ...process.argv.slice(2)], {
  cwd: FRONTEND,
  env,
  stdio: 'inherit',
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
