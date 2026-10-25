/**
 * CI 治理策略守卫（2026-10-25，⑦⑧）。
 *
 * 锁住三条"看起来配置了、其实没生效"的治理项：
 *
 * 1. **main 分支不取消运行**：`concurrency.cancel-in-progress` 若对 main 也生效，
 *    连续快速推送会互相打断 —— 实测当天 main 上连续 5 次运行**全部 cancelled**，
 *    那段时间"推送成功"但**零完整验证**。故只允许对 PR 生效。
 * 2. **发布前必须查 CI 结论**：`scripts/check_main_ci.py` 必须在仓库里，且发布流程文档
 *    真的让它出场（否则又是一个没人调用的脚本）。
 * 3. **覆盖率缺口必须可见**：`scripts/coverage_gaps.py` + 后端/前端两个作业都要有
 *    生成清单的步骤（`if: always()`，红了也能看到缺哪几行）。
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const test = require('node:test');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const PR_CHECKS = path.join(REPO_ROOT, '.github', 'workflows', 'pr-checks.yml');
const CLAUDE_MD = path.join(REPO_ROOT, 'CLAUDE.md');
const CHECK_MAIN_CI = path.join(REPO_ROOT, 'scripts', 'check_main_ci.py');
const COVERAGE_GAPS = path.join(REPO_ROOT, 'scripts', 'coverage_gaps.py');

function read(file) {
  return fs.readFileSync(file, 'utf8');
}

test('main 分支不再取消并发运行（只有 PR 取消）', () => {
  const yml = read(PR_CHECKS);
  const idx = yml.indexOf('concurrency:');
  assert.ok(idx >= 0, 'pr-checks.yml 缺少 concurrency 配置');
  const block = yml.slice(idx, idx + 400);
  assert.ok(
    block.includes("github.event_name == 'pull_request'"),
    'cancel-in-progress 必须对 PR 才为 true。若写死 true，连续推送会把前一次的 main 验证取消掉 —— ' +
      '2026-10-25 实测连续 5 次 main 运行全部 cancelled。'
  );
  assert.ok(
    !/cancel-in-progress:\s*true\s*$/m.test(block),
    'cancel-in-progress 不得再写死 true'
  );
});

test('存在打 tag 前的 CI 结论检查脚本，且发布流程引用它', () => {
  assert.ok(fs.existsSync(CHECK_MAIN_CI), '缺少 scripts/check_main_ci.py');
  const claude = read(CLAUDE_MD);
  assert.ok(
    claude.includes('check_main_ci.py'),
    'CLAUDE.md 的发布流程必须写明用 scripts/check_main_ci.py 确认 CI 已绿（不能靠眼睛看）'
  );
});

test('覆盖率缺口脚本支持双格式且带自测', () => {
  assert.ok(fs.existsSync(COVERAGE_GAPS), '缺少 scripts/coverage_gaps.py');
  const src = read(COVERAGE_GAPS);
  assert.ok(src.includes('--coveragepy'), '需支持 coverage.py JSON');
  assert.ok(src.includes('--istanbul'), '需支持 istanbul coverage-final.json');
  assert.ok(src.includes('--selftest'), '需内置 --selftest（脚本自身可验证）');
});

test('后端与前端作业都生成覆盖率缺口清单（且 always 生效）', () => {
  const yml = read(PR_CHECKS);
  assert.ok(
    /name: Coverage gaps \(backend\)[\s\S]{0,120}if: always\(\)/.test(yml),
    'backend 作业缺少 Coverage gaps (backend) 且必须 if: always()'
  );
  assert.ok(
    /name: Coverage gaps \(frontend\)[\s\S]{0,120}if: always\(\)/.test(yml),
    'frontend 作业缺少 Coverage gaps (frontend) 且必须 if: always()'
  );
  assert.ok(
    yml.includes('--coveragepy') && yml.includes('--istanbul'),
    '两个作业应分别调用 --coveragepy / --istanbul'
  );
});
