#!/usr/bin/env node
/*
 * postinstall 补丁：根治 vitest 覆盖率分片读回 ENOENT 竞态（vitest-dev/vitest#9758，已 closed not_planned）。
 *
 * 缺陷：v8/istanbul 共用的 BaseCoverageProvider 把每个 suite 的覆盖率写入
 *   coverage/.tmp/coverage-N.json（writeFile 的 promise 已 resolve、写盘成功），
 *   但 generateCoverage 阶段 readCoverageFiles 再读回时，部分分片已从磁盘消失 →
 *   readFile 抛 ENOENT → 覆盖率报告中断、门禁变红。官方确认与 provider / pool /
 *   worker 数 / fileParallelism 均无关（singleFork、fileParallelism=false、maxWorkers:1
 *   同样复现），无法用配置规避，4.x 仍在。本仓库 ~299 个测试文件的大型集恒触发。
 *
 * 根治（采用 upstream reporter 的内存镜像方案）：
 *   1) onAfterSuiteRun 写盘的同时，把同一份分片 JSON 存入 provider 实例上的内存镜像 Map；
 *   2) readCoverageFiles 读盘命中 ENOENT 时回退内存镜像，读到后按 filename 释放该镜像项。
 *   使报告/阈值阶段不再依赖分片在磁盘上存活，跨平台（Windows 本地 + Linux CI）一致生效。
 *
 * 设计约束：
 *   - 纯 fs、零依赖、CommonJS（package.json "type":"module"，故用 .cjs 后缀）。
 *   - 幂等：已打过补丁（出现 __memShards 标记）则跳过，可重复执行。
 *   - fail-loud：目标文件缺失、锚点非唯一、写后校验失败均以非 0 退出并打印明确原因，
 *     使 CI 的 npm ci 立即失败而非静默放行未打补丁的 vitest（届时门禁会再次变红）。
 *   - 目标 chunk 文件名含内容哈希（vitest@3.2.7 锁定为 coverage.DfSpMS-b.js）：优先用
 *     精确名，缺失时回退到 chunks 目录下唯一的 coverage.*.js 匹配，兼顾确定性与抗升级。
 */
'use strict'

const fs = require('fs')
const path = require('path')

const MARKER = '__memShards'

// 站点 1：onAfterSuiteRun 写分片处 —— 写盘同时存入内存镜像。
const SITE1_ANCHOR =
  'const promise = promises$1.writeFile(filename, JSON.stringify(coverage), "utf-8");'
const SITE1_PATCHED =
  'const __serialized = JSON.stringify(coverage); if (!this.__memShards) this.__memShards = new Map(); this.__memShards.set(filename, __serialized); const promise = promises$1.writeFile(filename, __serialized, "utf-8");'

// 站点 3（2026-09-05 扩展）：写侧竞态防护 —— clean() 的 rm(.tmp) 与本回调并发时，
// writeFile 落在"目录已删、mkdir 未建"的窗口内抛 ENOENT，成为 Unhandled Rejection
// 崩掉报告阶段（读侧镜像已存在但写侧 promise 未被 await 任何一个 catch）。
// 防护：捕获写失败 → mkdir 重建目录重试一次 → 仍失败则静默放弃磁盘分片
//（内存镜像仍是权威数据源，读侧已能回退），并返回已消化的 promise。
const SITE3_PATCHED =
  'const __serialized = JSON.stringify(coverage); if (!this.__memShards) this.__memShards = new Map(); this.__memShards.set(filename, __serialized); const promise = promises$1.writeFile(filename, __serialized, "utf-8").catch(async (__werr) => { if (__werr && __werr.code === "ENOENT") { try { await promises$1.mkdir(this.coverageFilesDirectory, { recursive: true }); await promises$1.writeFile(filename, __serialized, "utf-8"); return; } catch (__retryErr) { /* 磁盘分片放弃；内存镜像兜底（读侧 SITE2 回退） */ } } throw __werr; });'

// 站点 2：readCoverageFiles 读分片处 —— 读盘 ENOENT 时回退内存镜像，随后释放镜像项。
const SITE2_ANCHOR = 'const contents = await promises$1.readFile(filename, "utf-8");'
const SITE2_PATCHED =
  'let contents; try { contents = await promises$1.readFile(filename, "utf-8"); } catch (__e) { const __m = this.__memShards && this.__memShards.get(filename); if (__e && __e.code === "ENOENT" && __m !== undefined) { contents = __m; } else { throw __e; } } if (this.__memShards) this.__memShards.delete(filename);'

function fail(msg) {
  console.error('[patch-vitest-coverage] FAIL: ' + msg)
  process.exit(1)
}

function resolveTargetFile() {
  const chunksDir = path.join(__dirname, '..', 'node_modules', 'vitest', 'dist', 'chunks')
  if (!fs.existsSync(chunksDir)) {
    fail(
      'vitest chunks 目录不存在: ' +
        chunksDir +
        '（vitest 未安装或目录结构变更；请确认 npm 安装已完成）'
    )
  }
  const pinned = path.join(chunksDir, 'coverage.DfSpMS-b.js')
  if (fs.existsSync(pinned)) return pinned

  // 回退：哈希随 vitest 补丁版本变化时，匹配唯一的 coverage.*.js。
  const matches = fs.readdirSync(chunksDir).filter((f) => /^coverage\..*\.js$/.test(f))
  if (matches.length === 0) {
    fail('chunks 目录下未找到 coverage.*.js（vitest 内部结构已变更，需人工核对本补丁）')
  }
  if (matches.length > 1) {
    fail(
      'chunks 目录下存在多个 coverage.*.js（' +
        matches.join(', ') +
        '），无法确定目标，需人工核对本补丁'
    )
  }
  return path.join(chunksDir, matches[0])
}

function countOccurrences(haystack, needle) {
  return haystack.split(needle).length - 1
}

function main() {
  const target = resolveTargetFile()
  let src = fs.readFileSync(target, 'utf-8')

  // 幂等：已是最新补丁（SITE3 写侧防护已生效）则跳过。
  // 注意不能仅用 MARKER 短路——旧版补丁（仅读侧）也含 MARKER，
  // 需继续走下方分支升级到 SITE3。
  if (src.includes(SITE3_PATCHED)) {
    console.log(
      '[patch-vitest-coverage] 已打最新补丁（含写侧防护），跳过（' +
        path.relative(process.cwd(), target) +
        '）'
    )
    return
  }

  const c1 = countOccurrences(src, SITE1_ANCHOR)
  const c2 = countOccurrences(src, SITE2_ANCHOR)
  const c3 = countOccurrences(src, SITE3_PATCHED)
  if (c1 > 1 || c2 > 1 || c3 > 1) {
    fail(
      '锚点匹配数异常（期望各 ≤1）：site1=' +
        c1 +
        ', site2=' +
        c2 +
        ', site3=' +
        c3 +
        '。vitest 版本或内部实现与补丁假设不符，已拒绝修改（目标: ' +
        target +
        '）'
    )
  }

  const before = Buffer.byteLength(src, 'utf-8')
  if (c1 === 1 && c2 === 1) {
    // 全新安装：SITE1 → SITE3（写侧防护），SITE2 → 读侧防护。
    src = src.replace(SITE1_ANCHOR, SITE3_PATCHED).replace(SITE2_ANCHOR, SITE2_PATCHED)
  } else if (c3 === 1) {
    // 已是最新补丁（SITE3 生效），无需动作。
    console.log(
      '[patch-vitest-coverage] 已是最新补丁（含写侧防护），跳过（' +
        path.relative(process.cwd(), target) +
        '）'
    )
    return
  } else if (src.includes(SITE1_PATCHED)) {
    // 旧版补丁（仅 SITE1 写镜像 + 可能已有 SITE2 读防护）→ 升级：SITE1 替换为 SITE3。
    // SITE2 若未打则不在此路径处理（新装路径已覆盖），已打则保持原样。
    src = src.replace(SITE1_PATCHED, SITE3_PATCHED)
  } else {
    fail(
      '无法识别目标文件状态（site1=' +
        c1 +
        ', site2=' +
        c2 +
        ', site3=' +
        c3 +
        '，含旧 SITE1=' +
        src.includes(SITE1_PATCHED) +
        '），需人工核对本补丁'
    )
  }
  fs.writeFileSync(target, src, 'utf-8')

  // 写后校验：SITE3 已生效、原锚点已消失、字节数增长。
  const after = fs.readFileSync(target, 'utf-8')
  const markerCount = countOccurrences(after, MARKER)
  const afterBytes = Buffer.byteLength(after, 'utf-8')
  if (
    countOccurrences(after, SITE3_PATCHED) !== 1 ||
    !after.includes(MARKER) ||
    markerCount < 4 ||
    after.includes(SITE1_ANCHOR) ||
    after.includes(SITE2_ANCHOR) ||
    afterBytes <= before
  ) {
    fail(
      '写后校验未通过（marker=' +
        markerCount +
        ', before=' +
        before +
        'B, after=' +
        afterBytes +
        'B），已打补丁的文件可能损坏，请删除 node_modules/vitest 后重装'
    )
  }

  console.log(
    '[patch-vitest-coverage] 已应用 #9758 内存镜像补丁（含写侧竞态防护）（' +
      path.relative(process.cwd(), target) +
      '，' +
      before +
      'B → ' +
      afterBytes +
      'B）'
  )
}

module.exports = {
  MARKER,
  SITE1_ANCHOR,
  SITE1_PATCHED,
  SITE2_ANCHOR,
  SITE2_PATCHED,
}

if (require.main === module) main()
