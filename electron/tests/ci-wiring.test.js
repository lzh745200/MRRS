/**
 * CI 接线守卫（元测试）：确保"该跑的东西真的被跑"。
 *
 * ## 为什么需要
 * `electron/tests/*.test.js` 三个用例文件长期是**孤儿**：文件存在、逐个跑 EXIT=0，
 * 但 `package.json` 没有 test 脚本、CI 也没有任何步骤执行它们 —— 等于一份永不执行的
 * 安全网。2026-10-25 把它们接进 `frontend-check`（Linux）与 `windows-smoke`（Windows）后，
 * 本文件负责**锁住这条接线**，防止后续重构 workflow 时又被悄悄摘掉。
 *
 * 同时校验发布前置门禁的等待预算：
 * `scripts/check_release_gate.py` 轮询 tag commit 的 PR Checks 结论，
 * 而本仓 PR Checks 实测 17.4~30.2 分钟。原 `build-arm64.yml` 写 30 分钟**正好压线**，
 * 「推 main → 立刻打 tag」的正常流程会让 arm64 构建超时变红。
 * 这里断言两个构建工作流的该值都 ≥ 60，低于阈值即测试失败并给出原因。
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const test = require('node:test');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const PR_CHECKS = path.join(REPO_ROOT, '.github', 'workflows', 'pr-checks.yml');
const BUILD_WINDOWS = path.join(REPO_ROOT, '.github', 'workflows', 'build-windows.yml');
const BUILD_ARM64 = path.join(REPO_ROOT, '.github', 'workflows', 'build-arm64.yml');
const PACKAGE_JSON = path.join(REPO_ROOT, 'package.json');

/** 门禁等待预算下限（分钟）：必须覆盖 PR Checks 实测最长 30.2 分钟 + 排队余量。 */
const MIN_GATE_TIMEOUT_MINUTES = 60;

function read(file) {
  return fs.readFileSync(file, 'utf8');
}

test('package.json 暴露 test:electron 脚本', () => {
  const pkg = JSON.parse(read(PACKAGE_JSON));
  assert.ok(pkg.scripts, 'package.json 缺少 scripts 段');
  assert.ok(
    typeof pkg.scripts['test:electron'] === 'string' && pkg.scripts['test:electron'].includes('--test'),
    'package.json 缺少 test:electron 脚本（Node 内置 test runner）'
  );
});

test('pr-checks 的 Linux 作业执行 electron 单测', () => {
  const yml = read(PR_CHECKS);
  assert.ok(
    yml.includes('npm run test:electron'),
    'pr-checks.yml 未执行 `npm run test:electron` —— electron 测试会重新退化成孤儿'
  );
});

test('pr-checks 的 windows-smoke 作业也执行 electron 单测', () => {
  const yml = read(PR_CHECKS);
  // 截取 windows-smoke 作业段落（到文件末尾或下一个顶层作业）
  const start = yml.indexOf('windows-smoke:');
  assert.ok(start > 0, 'pr-checks.yml 找不到 windows-smoke 作业');
  const section = yml.slice(start);
  assert.ok(
    section.includes('npm run test:electron'),
    'windows-smoke 未执行 electron 单测：path-guard 属路径语义敏感模块，Linux 绿不等于 Windows 正确'
  );
  assert.ok(
    section.includes('actions/setup-node'),
    'windows-smoke 未配置 actions/setup-node —— 上面的 electron 单测会因找不到 node 而失败'
  );
});

function parseGateTimeouts(ymlPath) {
  const yml = read(ymlPath);
  const matches = [...yml.matchAll(/check_release_gate\.py\s+--timeout-minutes\s+(\d+)/g)];
  return matches.map((m) => Number(m[1]));
}

test('两个构建工作流的发布门禁等待预算 ≥ 60 分钟', () => {
  for (const [label, file] of [
    ['build-windows.yml', BUILD_WINDOWS],
    ['build-arm64.yml', BUILD_ARM64],
  ]) {
    const values = parseGateTimeouts(file);
    assert.ok(values.length > 0, `${label} 未调用 check_release_gate.py（发布门禁缺失）`);
    for (const minutes of values) {
      assert.ok(
        minutes >= MIN_GATE_TIMEOUT_MINUTES,
        `${label} 的发布门禁等待 ${minutes} 分钟 < ${MIN_GATE_TIMEOUT_MINUTES} 分钟。` +
          '本仓 PR Checks 实测 17.4~30.2 分钟，30 分钟会与最慢一次压线导致 tag 构建超时；' +
          '正常发布流程（推 main 后立刻打 tag）必须留足余量。'
      );
    }
  }
});
