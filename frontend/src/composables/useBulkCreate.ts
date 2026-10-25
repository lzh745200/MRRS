/**
 * 批量新增执行器（2026-10-25 / ③ 录入效率包）
 *
 * ## 为什么单独抽出来
 * `BulkPasteDialog` 只负责"拿到二维数组"，真正落地要靠各业务页调自己的 create 接口。
 * 如果每个页面各写一遍 for 循环，会重复出三类毛病：
 *   1. 不逐条 try/catch —— 第 5 条失败就整批中断，前 4 条已入库但用户以为全失败；
 *   2. 不给出失败明细 —— 用户不知道补哪几条，只能全量重来（而重来会重复入库）；
 *   3. 不限制并发 —— `Promise.all` 一次性打出去，离线 SQLite 会被写锁撞得满屏 500。
 *
 * 本模块把这三件事固化：**串行**执行（离线单机串行比并发安全）、逐条收集失败明细、
 * 返回可直接展示的结构；不吞错（失败信息原样保留 message）。
 */
import { ref } from 'vue'

export interface BulkCreateFailure {
  /** 原始行（便于用户对照 Excel 找出是哪一行） */
  row: unknown
  /** 行号（1 基，与预览表格的“#”一致） */
  index: number
  message: string
}

export interface BulkCreateResult {
  total: number
  success: number
  failures: BulkCreateFailure[]
}

/** 从任意异常里提取可读信息（后端 detail / message / Error.message 都兼容）。 */
export function extractErrorMessage(error: unknown, fallback = '新增失败'): string {
  if (typeof error === 'string' && error.trim()) return error
  if (error && typeof error === 'object') {
    const box = error as Record<string, unknown>
    for (const key of ['message', 'detail', 'msg']) {
      const value = box[key]
      if (typeof value === 'string' && value.trim()) return value
    }
  }
  return fallback
}

export function useBulkCreate<Row, Payload>(
  createOne: (payload: Payload) => Promise<unknown>,
  toPayload: (row: Row) => Payload
) {
  const running = ref(false)

  /**
   * 逐条创建。**串行**：离线单机下并发写 SQLite 只会互相等锁。
   * 单条失败不中断整批 —— 否则"前 4 条已入库、用户以为全失败"会导致重复录入。
   */
  async function run(rows: Row[]): Promise<BulkCreateResult> {
    running.value = true
    const failures: BulkCreateFailure[] = []
    let success = 0
    try {
      for (let i = 0; i < rows.length; i += 1) {
        const row = rows[i]
        try {
          await createOne(toPayload(row))
          success += 1
        } catch (error) {
          failures.push({ row, index: i + 1, message: extractErrorMessage(error) })
        }
      }
    } finally {
      running.value = false
    }
    return { total: rows.length, success, failures }
  }

  /** 结果摘要文案（页面直接 ElMessage 用，避免每处各写一套话术）。 */
  function summarize(result: BulkCreateResult): string {
    if (result.total === 0) return '没有需要新增的数据'
    if (result.failures.length === 0) return `已新增 ${result.success} 条`
    return `已新增 ${result.success} 条，失败 ${result.failures.length} 条（第 ${result.failures
      .map((f) => f.index)
      .join('、')} 行）`
  }

  return { running, run, summarize }
}
