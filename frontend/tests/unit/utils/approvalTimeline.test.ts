import { describe, expect, it } from 'vitest'
import { buildApprovalTimeline, type TimelineNode } from '@/utils/approvalTimeline'

describe('buildApprovalTimeline (T033)', () => {
  const history = [
    { operator: '张三', action: '提交申请', time: '2024-01-01 09:00', type: 'submit' },
    { operator: '李四', action: '初审通过', time: '2024-01-02 10:00' },
  ]
  const statusLogs = [
    { actor: '系统', action: '状态变更为审批中', time: '2024-01-01 09:01', type: 'status' },
    { user: '王五', action: '终审通过', time: '2024-01-03 14:00' },
  ]

  it('节点含操作人/动作/时间', () => {
    const nodes: TimelineNode[] = buildApprovalTimeline(history, statusLogs)
    expect(nodes.length).toBe(4)
    nodes.forEach((n) => {
      expect(n.operator).toBeTruthy()
      expect(n.action).toBeTruthy()
      expect(n.time).toBeTruthy()
    })
  })

  it('聚合两源并按时间倒序', () => {
    const nodes = buildApprovalTimeline(history, statusLogs)
    expect(nodes[0].time).toBe('2024-01-03 14:00')
    expect(nodes[nodes.length - 1].time).toBe('2024-01-01 09:00')
  })

  it('缺省字段回退为 - / 空串但不崩溃', () => {
    const nodes = buildApprovalTimeline([{}], [null as any])
    expect(nodes[0].operator).toBe('-')
  })

  it('空输入返回空数组', () => {
    expect(buildApprovalTimeline([], [])).toEqual([])
  })
})

/**
 * 单侧/双侧数据源缺失时的 `|| []` 兜底分支。
 * 后端详情接口在无审批历史或未开启状态日志时，对应字段会直接缺席（undefined）
 * 或为 null；调用方（如 approval/Detail.vue）不预先归一化就透传。
 */
describe('buildApprovalTimeline 数据源缺失兜底', () => {
  it('双源均为 null/undefined → 返回空数组，不抛 TypeError', () => {
    expect(buildApprovalTimeline(null as any, null as any)).toEqual([])
    expect(buildApprovalTimeline(undefined as any, undefined as any)).toEqual([])
  })

  it('仅 history 缺失 → 只保留状态日志节点（type 回退 status）', () => {
    const nodes = buildApprovalTimeline(null as any, [
      { actor: '系统', action: '状态变更为审批中', time: '2024-01-01 09:01' },
    ])
    expect(nodes).toHaveLength(1)
    expect(nodes[0]).toEqual({
      operator: '系统',
      action: '状态变更为审批中',
      time: '2024-01-01 09:01',
      type: 'status',
    })
  })

  it('仅 statusLogs 缺失 → 只保留审批历史节点（type 回退 history）', () => {
    const nodes = buildApprovalTimeline(
      [{ operator: '张三', action: '提交申请', time: '2024-01-01 09:00' }],
      undefined as any
    )
    expect(nodes).toHaveLength(1)
    expect(nodes[0].type).toBe('history')
    expect(nodes[0].operator).toBe('张三')
  })

  it('time 缺失时排序不抛（String(undefined) 参与 localeCompare）', () => {
    const nodes = buildApprovalTimeline(
      [{ operator: 'a', action: 'x' }, { operator: 'b', action: 'y', time: '2024-01-01' }],
      null as any
    )
    expect(nodes).toHaveLength(2)
    // 有时间的排前（倒序时空串最小）
    expect(nodes[0].time).toBe('2024-01-01')
    expect(nodes[1].time).toBe('')
  })
})

/**
 * 时间解析与排序（`toTimeValue`）。
 *
 * 背景：原实现用 `String(time).localeCompare` 排序，只在"同一格式且零填充"时正确 ——
 * ISO（2026-09-17T10:00:00Z）与空格格式（2026-09-17 10:00:00）混排错序、epoch 秒/毫秒
 * 完全乱序、localeCompare 还受运行环境语言影响。现改为解析为数值时间戳比较；
 * 无法解析的时间（null/NaN/空串/非时间字符串）一律沉底，同一时刻保持输入顺序。
 * 这些分支是排序正确性的核心，必须逐条覆盖。
 */
describe('buildApprovalTimeline 时间解析与排序', () => {
  const t = (v: unknown) => [{ operator: 'o', action: 'a', time: v }]

  it('ISO 与空格格式混排按真实时间倒序（不再依赖字符串字典序），且判据不随运行时时区漂移', () => {
    // 取值必须满足两条：① 字典序与时间戳序结论**相反**（否则无法判别旧实现）；
    // ② 对任意运行时时区结论**一致**（否则 CI 恒红、本地恒绿）。
    //
    // 反面教材（本用例 2026-10-02 修正前）：原取 `'2026-09-17 10:00:00'`
    // vs `'2026-09-17T10:00:00Z'`。朴素串无时区、由 JS 按**本地时区**解析，
    // 在 UTC runner（CI 的 ubuntu-latest）上二者是**同一时刻** → 落入稳定排序
    // 分支保持输入顺序 → 断言失败。而 UTC+8 本地恒绿 —— 并且该组合在新旧实现
    // 下"排第一"的都是 ISO，**从未真正判别过修复**（弱断言）。
    //
    // 现取同一天的最早/最晚时刻：lexicographically 仅第 10 位 ' '(0x20) vs 'T'(0x54)
    // 有别 → 空格串更小 → 旧实现（localeCompare 降序）把 ISO 排在前；
    // 而本地 23:59:59 折算 UTC 最坏情形为次日 11:59:59，恒晚于当日 00:00:00Z
    // （UTC-12…UTC+14 全覆盖验证）→ 新实现把空格串排在前。两者结论相反。
    const nodes = buildApprovalTimeline(
      [
        { operator: 'space', action: 'a', time: '2026-09-17 23:59:59' },
        { operator: 'iso', action: 'a', time: '2026-09-17T00:00:00Z' },
      ],
      null as any
    )
    expect(nodes[0].operator).toBe('space')
    expect(nodes[1].operator).toBe('iso')
  })

  it('epoch 秒（10 位）按 ×1000 解析为毫秒', () => {
    // 1700000000s ≈ 2023-11-14；与 2024-01-01 比较应排在后（更早）。
    const nodes = buildApprovalTimeline(
      [
        { operator: 'sec', action: 'a', time: 1700000000 },
        { operator: 'later', action: 'a', time: '2024-01-01 00:00:00' },
      ],
      null as any
    )
    expect(nodes[0].operator).toBe('later')
    expect(nodes[1].operator).toBe('sec')
  })

  it('epoch 毫秒（13 位）原样使用；数字串同样按 epoch 解析', () => {
    const nodes = buildApprovalTimeline(
      [
        { operator: 'ms', action: 'a', time: 1700000000000 },
        { operator: 'numstr', action: 'a', time: '1700000000000' },
        { operator: 'later', action: 'a', time: '2024-01-01 00:00:00' },
      ],
      null as any
    )
    // 前两条同一时刻，保持输入顺序；均早于 2024-01-01。
    expect(nodes.map((n) => n.operator)).toEqual(['later', 'ms', 'numstr'])
  })

  it('Date 实例参与解析', () => {
    const nodes = buildApprovalTimeline(
      [
        { operator: 'date', action: 'a', time: new Date('2025-06-01T00:00:00Z') },
        { operator: 'older', action: 'a', time: '2024-01-01 00:00:00' },
      ],
      null as any
    )
    expect(nodes[0].operator).toBe('date')
  })

  it('非法 Date（Invalid Date）解析为 null → 沉底', () => {
    const nodes = buildApprovalTimeline(
      [
        { operator: 'bad', action: 'a', time: new Date('not-a-date') },
        { operator: 'good', action: 'a', time: '2024-01-01 00:00:00' },
      ],
      null as any
    )
    expect(nodes[0].operator).toBe('good')
    expect(nodes[1].operator).toBe('bad')
  })

  it('非有限数字（NaN/Infinity）解析为 null → 沉底', () => {
    const nodes = buildApprovalTimeline(
      [
        { operator: 'nan', action: 'a', time: Number.NaN },
        { operator: 'inf', action: 'a', time: Number.POSITIVE_INFINITY },
        { operator: 'good', action: 'a', time: '2024-01-01 00:00:00' },
      ],
      null as any
    )
    expect(nodes[0].operator).toBe('good')
    // 两个 null 保持输入顺序。
    expect(nodes.slice(1).map((n) => n.operator)).toEqual(['nan', 'inf'])
  })

  it('无法解析的字符串（Date.parse 返回 NaN）沉底', () => {
    const nodes = buildApprovalTimeline(
      [
        { operator: 'junk', action: 'a', time: '不是一个时间' },
        { operator: 'good', action: 'a', time: '2024-01-01 00:00:00' },
      ],
      null as any
    )
    expect(nodes[0].operator).toBe('good')
    expect(nodes[1].operator).toBe('junk')
  })

  it('纯空白串 / null / undefined 一律沉底且互不抛错', () => {
    const nodes = buildApprovalTimeline(
      [
        { operator: 'blank', action: 'a', time: '   ' },
        { operator: 'null', action: 'a', time: null },
        { operator: 'undef', action: 'a', time: undefined },
        { operator: 'good', action: 'a', time: '2024-01-01 00:00:00' },
      ],
      null as any
    )
    expect(nodes[0].operator).toBe('good')
    expect(nodes.slice(1).every((n) => n.time !== '2024-01-01 00:00:00')).toBe(true)
  })

  it('全部无法解析时保持输入顺序（稳定排序）', () => {
    const nodes = buildApprovalTimeline(
      [
        { operator: 'first', action: 'a', time: null },
        { operator: 'second', action: 'a', time: 'junk' },
        { operator: 'third', action: 'a', time: '' },
      ],
      null as any
    )
    expect(nodes.map((n) => n.operator)).toEqual(['first', 'second', 'third'])
  })

  it('同一时刻跨两个来源按输入顺序稳定排列', () => {
    const nodes = buildApprovalTimeline(
      [{ operator: 'h', action: 'a', time: '2024-01-01 09:00:00' }],
      [{ operator: 's', action: 'b', time: '2024-01-01 09:00:00' }]
    )
    // history 先于 statusLogs 拼接，同一 ts 下顺序保持。
    expect(nodes.map((n) => n.operator)).toEqual(['h', 's'])
  })

  it('单个数字串（\`String(raw)\` 分支）也能解析', () => {
    const nodes = buildApprovalTimeline(
      [
        { operator: 'numstr', action: 'a', time: '1700000000' },
        { operator: 'later', action: 'a', time: '2024-01-01 00:00:00' },
      ],
      null as any
    )
    expect(nodes[0].operator).toBe('later')
    expect(nodes[1].operator).toBe('numstr')
  })

  it('t 辅助构造的时间在无解析能力时仍原样保留（不透传 undefined）', () => {
    const nodes = buildApprovalTimeline(t('2024-01-01 00:00:00'), null as any)
    expect(nodes[0].time).toBe('2024-01-01 00:00:00')
  })
})

/**
 * 逐分支覆盖：`toTimeValue` 的短路/三元与比较器分支。
 * 上面的用例已覆盖主要路径，这里补齐"同一条表达式两侧都取到"的场景 ——
 * v8 分支计数按**操作数**记录，`a || b` 只走左侧时右侧计 0，三元同理。
 */
describe('buildApprovalTimeline 逐分支补齐', () => {
  it('time 显式为 undefined（区别于 null）走第二个操作数', () => {
    // 22 行的 `raw === null || raw === undefined`：只用 null 时右侧恒 0。
    // 注意 norm() 会 `|| ''` 兜底，要让 `undefined` 真正到达 toTimeValue，
    // 需绕开 norm —— 这里通过 statusLogs 直传已归一化节点。
    const nodes = buildApprovalTimeline(
      [
        { operator: 'undef', action: 'a', time: undefined },
        { operator: 'good', action: 'a', time: '2024-01-01 00:00:00' },
      ],
      null as any
    )
    expect(nodes[0].operator).toBe('good')
    expect(nodes[1].operator).toBe('undef')
  })

  it('超长数字串导致 Number 为非有限值时回退 null（数字串分支的 !isFinite 真侧）', () => {
    // 40 行在"纯数字串"分支内：'1e999' 不匹配 /^\d+$/；用极长数字串让 Number 溢出为 Infinity。
    const huge = '9'.repeat(400)
    const nodes = buildApprovalTimeline(
      [
        { operator: 'huge', action: 'a', time: huge },
        { operator: 'good', action: 'a', time: '2024-01-01 00:00:00' },
      ],
      null as any
    )
    expect(nodes[0].operator).toBe('good')
    expect(nodes[1].operator).toBe('huge')
  })

  it('两侧时间均可解析且不等 → 取 ts 差值分支（60 行 y.ts !== x.ts）', () => {
    // 60 行 idx0 是 `y.ts !== x.ts` 的**真**侧：只要两侧都可解析且不相等即覆盖；
    // 用两个明确不同的时刻确保走该分支而非 61 行的稳定排序。
    const nodes = buildApprovalTimeline(
      [
        { operator: 'early', action: 'a', time: '2024-01-01 00:00:00' },
        { operator: 'late', action: 'a', time: '2024-06-01 00:00:00' },
      ],
      null as any
    )
    expect(nodes.map((n) => n.operator)).toEqual(['late', 'early'])
  })

  it('不可解析节点作为比较左侧（xInvalid）时排到可解析节点之后', () => {
    // 比较器的 `if (xInvalid) return 1` 需要**比较函数真的以 (无效, 有效) 顺序被调用**。
    // 2 元素数组下 V8 的比较顺序不保证命中，故用 3 元素：
    // 实测比较序列为 ["bad","v1",…]（x 无效、y 有效）→ 覆盖该分支。
    const nodes = buildApprovalTimeline(
      [
        { operator: 'v1', action: 'a', time: '2024-01-01 00:00:00' },
        { operator: 'bad', action: 'a', time: 'x' },
        { operator: 'v2', action: 'a', time: '2024-06-01 00:00:00' },
      ],
      null as any
    )
    expect(nodes.map((n) => n.operator)).toEqual(['v2', 'v1', 'bad'])
  })

  it('两侧均不可解析（xInvalid && yInvalid）保持输入顺序', () => {
    const nodes = buildApprovalTimeline(
      [
        { operator: 'b1', action: 'a', time: 'x' },
        { operator: 'b2', action: 'a', time: 'y' },
        { operator: 'b3', action: 'a', time: 'z' },
      ],
      null as any
    )
    expect(nodes.map((n) => n.operator)).toEqual(['b1', 'b2', 'b3'])
  })
})

