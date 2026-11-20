#!/usr/bin/env node
/**
 * 构建来源门禁：拒绝把「脏工作区」或「版本与 tag 不一致」的代码打成安装包。
 *
 * 背景（2026-11-20 实测）：
 *   `dist/electron/` 曾出现 v1.18.52/v1.18.53 的本地包，版本号与 tag 相同，但
 *   PyInstaller 把工作区里一个未提交的 `account_package_attempts_001.py` 收进了
 *   `_internal/alembic/versions`。同版本包在干净机器上迁移头不同，升级/排障都会
 *   被误导，且这类“同版本不同代码”的产物无法用 SHA256 之外的方式识别。
 *
 * 规则：
 *   1. 工作区有未提交的源码/配置/测试/迁移（dist/backend/dist/frontend/dist 除外）→ 失败；
 *   2. HEAD 正好有 tag 时，tag 必须是 `v<package.json version>`；
 *   3. GitHub tag 构建时，`GITHUB_REF_NAME` 必须等于 `v<version>`；
 *   4. package.json / frontend/package.json / backend/version.json / version.txt 版本必须一致；
 *   5. 版本/来源门禁可被 `ALLOW_DIRTY_BUILD=1` 显式绕过（仅本地调试），但会打印醒目警告。
 *
 * 用法：
 *   node scripts/check_build_provenance.js
 *   ALLOW_DIRTY_BUILD=1 npm run build:win   # 仅本地调试，禁止用于交付
 */

'use strict';

const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(process.env.PROVENANCE_ROOT || path.join(__dirname, '..'));
const ALLOW_DIRTY = process.env.ALLOW_DIRTY_BUILD === '1';
const RELEASE_CONTEXT =
  process.env.GITHUB_REF_TYPE === 'tag' ||
  String(process.env.GITHUB_REF || '').startsWith('refs/tags/');

function git(args) {
  return execFileSync('git', args, {
    cwd: ROOT,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim();
}

function readJson(rel) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, rel), 'utf8'));
}

function fail(message, details) {
  console.error(`\n[provenance] ✗ ${message}`);
  if (details) console.error(details);
  console.error(
    '\n[provenance] 交付构建必须来自干净提交。请先提交/还原改动；' +
      '仅本地调试可显式设置 ALLOW_DIRTY_BUILD=1（产物不可用于发布）。\n'
  );
  process.exit(2);
}

function main() {
  const pkg = readJson('package.json');
  const version = String(pkg.version || '').trim();
  if (!version) fail('package.json 缺少 version');

  let head = '';
  let headFull = '';
  let gitAvailable = true;
  try {
    headFull = git(['rev-parse', 'HEAD']);
    head = headFull.slice(0, 8);
  } catch (_) {
    gitAvailable = false;
  }

  if (gitAvailable) {
    const status = git(['status', '--porcelain=v1', '--untracked-files=all']);
    const ignoredPrefixes = [
      'dist/',
      'backend/dist/',
      'frontend/dist/',
      'node_modules/',
      '.scratch/',
      'coverage/',
    ];
    const dirty = status
      .split(/\r?\n/)
      .filter(Boolean)
      .map((line) => line.replace(/^.. /, '').replace(/^"|"$/g, ''))
      .filter((file) => !ignoredPrefixes.some((prefix) => file.startsWith(prefix)));

    if (dirty.length && !ALLOW_DIRTY) {
      fail(
        `工作区有 ${dirty.length} 个未提交文件，拒绝构建“同版本不同代码”的安装包`,
        dirty.slice(0, 20).map((file) => `  - ${file}`).join('\n') +
          (dirty.length > 20 ? `\n  ... 另有 ${dirty.length - 20} 个` : '')
      );
    }
    if (dirty.length && ALLOW_DIRTY) {
      console.warn(
        `[provenance] ⚠️ ALLOW_DIRTY_BUILD=1：忽略 ${dirty.length} 个未提交文件；` +
          '该产物不可用于 Release。'
      );
    }

    let exactTag = '';
    try {
      exactTag = git(['describe', '--tags', '--exact-match', 'HEAD']);
    } catch (_) {
      // HEAD 不在 tag 上是正常本地开发状态
    }
    const expectedTag = `v${version}`;
    if (exactTag && exactTag !== expectedTag && !ALLOW_DIRTY) {
      fail(`HEAD tag=${exactTag} 与 package.json version=${version}（期望 ${expectedTag}）不一致`);
    }
    // 版本复用门禁：v<version> 已存在但指向另一提交时，禁止从当前 HEAD 再打同版本包。
    // 否则 main 在发布后新增修复、版本号未 bump 时，会生成“同版本不同代码”的本地包。
    let releasedCommit = '';
    try {
      releasedCommit = git(['rev-parse', `refs/tags/${expectedTag}^{commit}`]);
    } catch (_) {
      // 该版本还没有 tag：正常的新版本开发
    }
    if (releasedCommit && headFull && releasedCommit !== headFull && !ALLOW_DIRTY) {
      fail(
        `版本 ${version} 已由 tag ${expectedTag} 发布在 ${releasedCommit.slice(0, 8)}，` +
          `当前 HEAD=${head} 不允许复用同版本出包；请先 bump 版本号`
      );
    }
    if (RELEASE_CONTEXT && !ALLOW_DIRTY) {
      const refTag = process.env.GITHUB_REF_NAME || '';
      if (refTag && refTag !== expectedTag) {
        fail(`CI tag=${refTag} 与 package.json version=${version}（期望 ${expectedTag}）不一致`);
      }
    }
    console.log(`[provenance] commit=${head} version=${version} tag=${exactTag || '(none)'}`);
  } else {
    if (RELEASE_CONTEXT) fail('构建目录不是 Git 工作树，无法校验发布来源');
    console.warn('[provenance] ⚠️ 未检测到 Git，跳过工作区/tag 校验（非发布构建）');
  }

  const expected = [
    ['frontend/package.json', readJson('frontend/package.json').version],
    ['backend/version.json', readJson('backend/version.json').version],
  ];
  try {
    expected.push(['version.txt', fs.readFileSync(path.join(ROOT, 'version.txt'), 'utf8').trim()]);
  } catch (_) {
    // version.txt 可选
  }
  const mismatches = expected.filter(([, value]) => String(value).trim() !== version);
  if (mismatches.length) {
    fail(
      '版本号不一致',
      mismatches.map(([file, value]) => `  - ${file}: ${value}（package.json=${version}）`).join('\n')
    );
  }

  console.log('[provenance] OK：版本 / tag / 工作区一致性通过');
}

main();
