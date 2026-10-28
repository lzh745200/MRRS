/**
 * 构建临时目录接线的元测试（防止"能构建"这件事被悄悄退回去）。
 *
 * ## 为什么需要
 * 2026-10-28 实测：本机 %TEMP% 有「拒绝删除子项」ACL，esbuild 在
 * vite:esbuild-transpile 阶段删除临时文件时报 `Access is denied`，
 * `npm run build` 直接失败 —— 而这是发版流水线的第一步。
 * 把 TEMP/TMP/TMPDIR 指到仓库内 `.scratch/tmp` 后同一构建 rc=0。
 *
 * 修法（frontend/scripts/build-with-workspace-temp.mjs）容易被"顺手简化回
 * vite build"而无声复发，故在此锁死三件事：
 *   1. build / build:check / build:only 三个脚本都必须经包装脚本；
 *   2. 包装脚本必须真的改三个环境变量，且目录失败时不得抛错（只读介质兜底）；
 *   3. 目标目录必须被 .gitignore 忽略（不能把临时文件提交进仓库）。
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const test = require('node:test');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const FRONTEND_PKG = path.join(REPO_ROOT, 'frontend', 'package.json');
const WRAPPER = path.join(REPO_ROOT, 'frontend', 'scripts', 'build-with-workspace-temp.mjs');
const GITIGNORE = path.join(REPO_ROOT, '.gitignore');

function read(file) {
  return fs.readFileSync(file, 'utf8');
}

test('前端三个构建脚本都经工作区临时目录包装脚本', () => {
  const pkg = JSON.parse(read(FRONTEND_PKG));
  for (const name of ['build', 'build:check', 'build:only']) {
    assert.ok(
      pkg.scripts[name] && pkg.scripts[name].includes('build-with-workspace-temp.mjs'),
      `frontend/package.json 的 ${name} 必须走 scripts/build-with-workspace-temp.mjs（否则 Windows 上会因 %TEMP% ACL 构建失败）`,
    );
  }
  assert.ok(
    !pkg.scripts.build.includes('vite build'),
    'build 脚本不得绕过包装脚本直接 vite build',
  );
});

test('包装脚本改三个临时目录变量，并在目录不可用时静默兜底', () => {
  const source = read(WRAPPER);
  for (const key of ['TEMP', 'TMP', 'TMPDIR']) {
    assert.ok(source.includes(`env.${key} = `), `包装脚本必须设置 ${key}`);
  }
  assert.ok(source.includes(".scratch"), '包装脚本必须把临时目录指向仓库内 .scratch');
  assert.ok(source.includes('catch'), '目录创建失败必须兜底，不能抛错中断构建');
});

test('.scratch/ 已被 .gitignore 忽略（临时文件不得入库）', () => {
  const ignored = read(GITIGNORE)
    .split(/\r?\n/)
    .map((line) => line.trim());
  assert.ok(
    ignored.some((line) => line === '.scratch/' || line === '.scratch'),
    '.gitignore 必须忽略 .scratch/（构建临时目录就在这里）',
  );
});
