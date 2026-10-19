/**
 * W23 视觉回归基线：10 个关键页面的 DOM 结构快照（**不比较像素**）
 *
 * 验证方式：
 * 1. 文件化结构快照：`{ name, path, title, contentPresent, landmarksHit }` 与
 *    `__baselines__/visual-baseline.json` 逐字段比较（稳定字段，不随业务数据/并行 UI 改造漂移；
 *    用于发现路由失效、标题丢失、白屏、关键内容区域消失）；
 * 2. 结构断言：每个页面必须命中基线声明的「关键内容区域」且表格存在时表头非空；
 * 3. 稳定性断言：页面加载期间不得出现 console.error 或未捕获异常（失败必须可见）。
 *
 * 运行：`npx playwright test tests/e2e/visual --reporter=list`
 * 基线更新（确属 UI 结构调整时）：
 *   PowerShell: `$env:UPDATE_VISUAL_BASELINE='1'; npx playwright test tests/e2e/visual`
 *   bash:       `UPDATE_VISUAL_BASELINE=1 npx playwright test tests/e2e/visual`
 */
import { test, expect } from '@playwright/test'
import {
  VISUAL_BASELINES,
  buildSnapshotRecord,
  captureStructure,
  collectPageErrors,
  expectRequiredLandmarks,
  expectSnapshotMatches,
  expectTableHeadersIfPresent,
  loadVisualSnapshots,
  writeVisualSnapshots,
  type VisualSnapshotRecord,
} from './helpers'

const updateBaseline = process.env.UPDATE_VISUAL_BASELINE === '1'
const collectedRecords: VisualSnapshotRecord[] = []

test.describe('W23 视觉回归基线（DOM 结构快照）', () => {
  for (const baseline of VISUAL_BASELINES) {
    test(`${baseline.name} 页面结构稳定`, async ({ page }) => {
      const pageErrors = collectPageErrors(page)

      const structure = await captureStructure(page, baseline.path)

      // 1) 路由与内容：URL 命中、主内容非空、document.title 由 router meta 决定
      expect(structure.urlPath).toContain(baseline.pathPrefix)
      expect(structure.contentLength).toBeGreaterThan(0)
      expect(structure.title).toBe(baseline.title)

      // 2) 关键内容区域断言（表格/空态/统计卡/卡片/表单/Tabs/交互控件/大屏根）
      expectRequiredLandmarks(baseline, structure)
      expectTableHeadersIfPresent(baseline, structure)

      // 3) DOM 结构快照（稳定字段；不比较像素）
      const record = buildSnapshotRecord(baseline, structure)
      if (updateBaseline) {
        collectedRecords.push(record)
      } else {
        expectSnapshotMatches(record, loadVisualSnapshots())
      }

      // 4) 控制台不得有 error / 未捕获异常
      expect(pageErrors, `页面控制台错误：\n${pageErrors.join('\n')}`).toEqual([])
    })
  }

  test.afterAll(() => {
    if (updateBaseline) {
      writeVisualSnapshots(collectedRecords)
    }
  })
})
