#!/usr/bin/env node
/**
 * electron/*.js 语法检查（mojibake / 非法字符守卫，回归 10c56cd0）。
 *
 * 取代原先 `bash -c 'for f in electron/*.js; do node --check ...'` 的钩子：
 * Windows 上 `bash` 常解析到 C:\Windows\System32\bash.exe —— 那是**没装发行版的
 * WSL 启动器**，钩子必然失败；而 Electron 侧的真实运行时是 node，跨平台一致。
 *
 * 用法：node scripts/check_electron_syntax.js
 * 退出码：0 全部通过；1 至少一个文件语法错误。
 */
'use strict';

const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const electronDir = path.join(__dirname, '..', 'electron');
const files = fs
  .readdirSync(electronDir)
  .filter((name) => name.endsWith('.js'))
  .sort();

if (files.length === 0) {
  console.error('ERROR: electron/ 下没有 .js 文件，守卫失效');
  process.exit(1);
}

let failed = 0;
for (const name of files) {
  const full = path.join(electronDir, name);
  try {
    execFileSync(process.execPath, ['--check', full], { stdio: 'pipe' });
  } catch (err) {
    failed += 1;
    console.error(`ERROR: node --check 失败: electron/${name}`);
    const detail = String((err.stderr || err.stdout || '')).trim();
    if (detail) {
      console.error(detail.split('\n').slice(0, 10).join('\n'));
    }
  }
}

if (failed > 0) {
  console.error(`electron 语法检查失败：${failed}/${files.length}`);
  process.exit(1);
}

console.log(`electron syntax OK (${files.length} files)`);
