/**
 * 批量粘贴解析（2026-10-25 / ③ 录入效率包）
 *
 * ## 为什么
 * 现场数据大多先在 Excel/WPS 里整理好，再逐条手敲进系统 —— 这是最费时的一步。
 * Excel 复制到剪贴板时就是 **制表符分隔、换行分行** 的纯文本，这里的任务是把那段
 * 文本稳定地解析成二维数组，供页面做"预览 + 确认后批量填入/批量新增"。
 *
 * ## 边界处理（这些是真实踩过的形态）
 * - Excel 单元格内含换行/制表符时会给字段加**双引号**，内部引号写成 `""` → 需要按 RFC4180 解引号；
 * - 从网页/Word 复制过来可能带 `\r\n`、行尾多余制表符；
 * - 末尾空行、整行空白必须丢弃（否则会多出一条空记录）；
 * - 必须有权重上限（行列数），避免一次粘贴把页面卡死（离线单机没有服务端兜底）。
 */

export interface PasteParseOptions {
  /** 最多接受多少行（超出即判定为超限，不静默截断）。 */
  maxRows?: number
  /** 最多接受多少列。 */
  maxCols?: number
}

export interface PasteParseResult {
  rows: string[][]
  /** 是否触发上限（此时 rows 为空，调用方应提示用户分批粘贴）。 */
  exceeded: boolean
  /** 触发的是哪个上限。 */
  exceededBy?: 'rows' | 'cols'
}

const DEFAULT_MAX_ROWS = 500
const DEFAULT_MAX_COLS = 50

/** 按制表符解析一行，支持双引号包裹的字段（内部可含制表符/换行，`""` 表示一个引号）。 */
export function splitPastedLine(line: string): string[] {
  const cells: string[] = []
  let current = ''
  let inQuotes = false

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i]
    if (inQuotes) {
      if (char === '"') {
        if (line[i + 1] === '"') {
          current += '"'
          i += 1
        } else {
          inQuotes = false
        }
      } else {
        current += char
      }
      continue
    }
    if (char === '"') {
      inQuotes = true
      continue
    }
    if (char === '\t') {
      cells.push(current)
      current = ''
      continue
    }
    current += char
  }
  cells.push(current)
  return cells
}

/**
 * 把剪贴板文本解析成二维数组。
 *
 * 注意：这里**不做**"去掉行尾空单元格"的裁剪以外的任何猜测 —— 列对应关系必须由页面
 * 显式给出（用户要能看到"第 3 列 → 帮扶村"的映射），否则静默错位比手工录入更危险。
 */
export function parsePastedTable(text: string, options: PasteParseOptions = {}): PasteParseResult {
  const maxRows = options.maxRows ?? DEFAULT_MAX_ROWS
  const maxCols = options.maxCols ?? DEFAULT_MAX_COLS

  const rawLines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n')
  const rows: string[][] = []

  for (const rawLine of rawLines) {
    if (rawLine.trim() === '') continue
    const cells = splitPastedLine(rawLine)
    // 行尾多余制表符（Excel 常见）→ 去掉末尾空单元格
    while (cells.length > 0 && cells[cells.length - 1] === '') cells.pop()
    // 注：这里不再判 `cells.length === 0` —— 纯空白/纯制表符行已在上面被
    // `rawLine.trim() === ''` 跳过，走到这里恒有 ≥1 个单元格；留着就是永不进入的死分支。
    if (cells.length > maxCols) {
      return { rows: [], exceeded: true, exceededBy: 'cols' }
    }
    rows.push(cells)
    if (rows.length > maxRows) {
      return { rows: [], exceeded: true, exceededBy: 'rows' }
    }
  }

  return { rows, exceeded: false }
}

/**
 * 校验粘贴结果与目标列数是否一致：返回首个列数不符的行号（1 基），全部一致返回 0。
 * 页面应在预览里把该行标红，而不是自动补空 —— 错位比缺行更难发现。
 */
export function findFirstMismatchedRow(rows: string[][], expectedCols: number): number {
  for (let i = 0; i < rows.length; i += 1) {
    if (rows[i].length !== expectedCols) return i + 1
  }
  return 0
}
