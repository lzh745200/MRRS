import { describe, expect, it } from 'vitest'

import { findFirstMismatchedRow, parsePastedTable, splitPastedLine } from '@/utils/parsePastedTable'

describe('splitPastedLine', () => {
  it('按制表符切分普通行', () => {
    expect(splitPastedLine('贵阳\t遵义\t六盘水')).toEqual(['贵阳', '遵义', '六盘水'])
  })

  it('保留空单元格（中间列缺失不能被吞掉）', () => {
    expect(splitPastedLine('a\t\tc')).toEqual(['a', '', 'c'])
  })

  it('双引号字段内的制表符不切分（Excel 真实形态）', () => {
    expect(splitPastedLine('"含\t制表符"\tb')).toEqual(['含\t制表符', 'b'])
  })

  it('双引号内的 "" 还原为一个引号', () => {
    expect(splitPastedLine('"他说""好"""\tx')).toEqual(['他说"好"', 'x'])
  })

  it('未闭合引号按原样保留（不丢数据，交给列数校验报错）', () => {
    expect(splitPastedLine('"未闭合\ta')).toEqual(['未闭合\ta'])
  })
})

describe('parsePastedTable', () => {
  it('解析多行制表符文本', () => {
    const result = parsePastedTable('甲\t1\n乙\t2')
    expect(result.exceeded).toBe(false)
    expect(result.rows).toEqual([
      ['甲', '1'],
      ['乙', '2'],
    ])
  })

  it('兼容 \\r\\n 与裸 \\r', () => {
    expect(parsePastedTable('a\tb\r\nc\td\re\tf').rows).toEqual([
      ['a', 'b'],
      ['c', 'd'],
      ['e', 'f'],
    ])
  })

  it('丢弃空白行与行尾多余制表符（Excel 常见）', () => {
    expect(parsePastedTable('a\tb\t\n\n  \nc\td\t').rows).toEqual([
      ['a', 'b'],
      ['c', 'd'],
    ])
  })

  it('空文本 → 0 行且不超限', () => {
    const result = parsePastedTable('   \n\n')
    expect(result.rows).toEqual([])
    expect(result.exceeded).toBe(false)
  })

  it('超行数上限 → exceeded=rows 且不静默截断', () => {
    const result = parsePastedTable('a\nb\nc', { maxRows: 2 })
    expect(result.exceeded).toBe(true)
    expect(result.exceededBy).toBe('rows')
    expect(result.rows).toEqual([])
  })

  it('超列数上限 → exceeded=cols', () => {
    const result = parsePastedTable('a\tb\tc', { maxCols: 2 })
    expect(result.exceeded).toBe(true)
    expect(result.exceededBy).toBe('cols')
    expect(result.rows).toEqual([])
  })

  it('恰好等于上限时通过（边界含在内）', () => {
    const result = parsePastedTable('a\tb\nc\td', { maxRows: 2, maxCols: 2 })
    expect(result.exceeded).toBe(false)
    expect(result.rows.length).toBe(2)
  })

  it('整行只有制表符（Excel 空行残留）被丢弃，不产生空记录', () => {
    expect(parsePastedTable('\t\t\na\tb').rows).toEqual([['a', 'b']])
  })

  it('默认上限为 500 行 / 50 列', () => {
    const manyRows = Array.from({ length: 500 }, (_, i) => `r${i}`).join('\n')
    expect(parsePastedTable(manyRows).exceeded).toBe(false)
    expect(parsePastedTable(`${manyRows}\nr500`).exceeded).toBe(true)
  })
})

describe('findFirstMismatchedRow', () => {
  it('列数全部一致返回 0', () => {
    expect(
      findFirstMismatchedRow(
        [
          ['a', 'b'],
          ['c', 'd'],
        ],
        2
      )
    ).toBe(0)
  })

  it('返回首个不符行号（1 基），供预览标红', () => {
    expect(findFirstMismatchedRow([['a', 'b'], ['c'], ['d', 'e']], 2)).toBe(2)
  })

  it('空数组视为一致', () => {
    expect(findFirstMismatchedRow([], 3)).toBe(0)
  })
})
