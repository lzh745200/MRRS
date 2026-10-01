import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useBackupSchedule, type ScheduleConfig } from '@/composables/useBackupSchedule'

vi.mock('@/api/request', () => ({
  get: vi.fn(),
  put: vi.fn(),
}))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn() },
}))

import { get, put } from '@/api/request'
import { ElMessage } from 'element-plus'

describe('useBackupSchedule (T044 唯一真相源)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loadScheduleConfig 从后端读取真实配置（cron 解析为友好模型）', async () => {
    ;(get as any).mockResolvedValue({
      data: { data: { enabled: true, keepCount: 7, schedule: '0 2 * * *' } },
    })
    const { scheduleConfig, loadScheduleConfig } = useBackupSchedule()
    await loadScheduleConfig()
    expect(get).toHaveBeenCalledWith('/system/backup/schedule')
    expect(scheduleConfig.value.enabled).toBe(true)
    expect(scheduleConfig.value.retentionCount).toBe(7)
    // cron "0 2 * * *" 解析 → 每日 02:00
    expect(scheduleConfig.value.frequency).toBe('daily')
    expect(scheduleConfig.value.backupTime).toBe('02:00')
  })

  it('weekly cron 表达式解析为 weekly 频率', async () => {
    ;(get as any).mockResolvedValue({
      data: { data: { enabled: false, keepCount: 3, schedule: '30 3 * * 1' } },
    })
    const { scheduleConfig, loadScheduleConfig } = useBackupSchedule()
    await loadScheduleConfig()
    expect(scheduleConfig.value.frequency).toBe('weekly')
    expect(scheduleConfig.value.backupTime).toBe('03:30')
  })

  it('schedule 缺失时回退默认 daily 02:00', async () => {
    ;(get as any).mockResolvedValue({ data: { data: { enabled: false } } })
    const { scheduleConfig, loadScheduleConfig } = useBackupSchedule()
    await loadScheduleConfig()
    expect(scheduleConfig.value.frequency).toBe('daily')
    expect(scheduleConfig.value.backupTime).toBe('02:00')
  })

  it('端点不可用（GET 拒绝）时静默保留默认配置且不抛出', async () => {
    // catch 空块：cron 配置端点 404/500/网络断开时不能因加载失败而白屏或中断初始化
    const defaultSnapshot = useBackupSchedule().scheduleConfig.value
    ;(get as any).mockRejectedValue(new Error('Network Error'))
    const { scheduleConfig, loadScheduleConfig } = useBackupSchedule()
    await expect(loadScheduleConfig()).resolves.toBeUndefined()
    // 默认值原样保留（未被失败响应污染）
    expect(scheduleConfig.value.enabled).toBe(defaultSnapshot.enabled)
    expect(scheduleConfig.value.frequency).toBe(defaultSnapshot.frequency)
    expect(scheduleConfig.value.backupTime).toBe(defaultSnapshot.backupTime)
    expect(scheduleConfig.value.retentionCount).toBe(defaultSnapshot.retentionCount)
  })

  it('响应体为空（data 为 null）时同样保留默认配置', async () => {
    ;(get as any).mockResolvedValue({ data: null })
    const { scheduleConfig, loadScheduleConfig } = useBackupSchedule()
    await loadScheduleConfig()
    // data 为假值 → if (data) 不进入，配置保持默认
    expect(scheduleConfig.value.frequency).toBe('daily')
    expect(scheduleConfig.value.backupTime).toBe('02:00')
  })

  it('saveSchedule 写入 cron + keep_count，并回读保持一致', async () => {
    ;(put as any).mockResolvedValue({ data: { success: true } })
    ;(get as any).mockResolvedValue({
      data: { data: { enabled: false, keepCount: 3, schedule: '0 2 * * *' } },
    })
    const { scheduleConfig, saveSchedule } = useBackupSchedule()
    scheduleConfig.value.enabled = false
    scheduleConfig.value.retentionCount = 3

    await saveSchedule()

    // PUT 携带后端契约字段：cron 字符串 + snake_case keep_count
    expect(put).toHaveBeenCalledWith('/system/backup/schedule', {
      enabled: false,
      keep_count: 3,
      schedule: '00 02 * * *',
    })
    // 保存后必须回读 GET，保证前端与后端一致
    expect(get).toHaveBeenCalled()
    expect(scheduleConfig.value.enabled).toBe(false)
    expect(scheduleConfig.value.retentionCount).toBe(3)
    expect(ElMessage.success).toHaveBeenCalled()
  })
})

/**
 * parseCron 的剩余分支。
 * 新增用例统一用【裸 body】形式 mock get（AGENTS.md：helper 已解包信封），
 * 同时顺带覆盖 loadScheduleConfig 里 `res.data?.data ?? res.data ?? res` 的 `?? res` 兜底侧。
 */
describe('useBackupSchedule parseCron 分支', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /** 直接走 loadScheduleConfig 观察解析结果 */
  async function parse(schedule: unknown) {
    ;(get as any).mockResolvedValue({ enabled: true, keepCount: 5, schedule })
    const { scheduleConfig, loadScheduleConfig } = useBackupSchedule()
    await loadScheduleConfig()
    return { ...scheduleConfig.value }
  }

  it('monthly：dom 固定且 dow 为 * → 0 2 1 * *', async () => {
    const cfg = await parse('0 2 1 * *')
    expect(cfg.frequency).toBe('monthly')
    expect(cfg.backupTime).toBe('02:00')
  })

  it('monthly 分支：仅 3 段 cron（dow 缺席）时 `!dow` 为真仍判 monthly', async () => {
    // parts = ['0','2','1'] → 解构后 dow === undefined，命中 `!dow` 真侧
    const cfg = await parse('0 2 1')
    expect(cfg.frequency).toBe('monthly')
  })

  it('dom 缺席（仅 2 段）时 `dom &&` 短路，回退 daily', async () => {
    // parts.length === 2 不小于 2，不会被 fallback 提前拦下；
    // dom/dow 均为 undefined → 两个 if 都短路 → frequency 保持 'daily'
    const cfg = await parse('30 3')
    expect(cfg.frequency).toBe('daily')
    expect(cfg.backupTime).toBe('03:30')
  })

  it('parts.length < 2（单段/空串/多余空白）→ 回退 daily 02:00', async () => {
    // 命中 `if (parts.length < 2) return fallback`
    expect((await parse('0')).frequency).toBe('daily')
    expect((await parse('0')).backupTime).toBe('02:00')
    expect((await parse('')).frequency).toBe('daily')
    // 全空白串 split(/\s+/) 得 ['']，长度 1 同样走 fallback
    expect((await parse('   ')).frequency).toBe('daily')
  })

  it('非字符串 schedule（脏数据）→ typeof 守卫回退默认', async () => {
    expect((await parse(12345)).frequency).toBe('daily')
    expect((await parse(null)).frequency).toBe('daily')
    expect((await parse({ cron: '0 2 * * *' })).frequency).toBe('daily')
  })

  it('dom 与 dow 同时指定（非法 cron）→ 两分支均不成立，保守回退 daily', async () => {
    // '0 2 1 * 1'：dom='1' 但 dow='1' → `(!dow || dow==='*')` 为假；
    // else-if 里 `(!dom || dom==='*')` 也为假 → 不误判为 weekly
    const cfg = await parse('0 2 1 * 1')
    expect(cfg.frequency).toBe('daily')
  })

  it('单位数时/分被 padStart 补零；多余空白被 trim 归一', async () => {
    expect((await parse('5 3 * * *')).backupTime).toBe('03:05')
    expect((await parse('  0   2  *  *  *  ')).backupTime).toBe('02:00')
  })
})

describe('useBackupSchedule toCron 分支（经 saveSchedule 间接驱动）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(put as any).mockResolvedValue({ success: true })
    ;(get as any).mockResolvedValue({ enabled: false, keepCount: 7, schedule: '0 2 * * *' })
  })

  /** 设定 backupTime/frequency 后保存，回传 PUT 携带的 cron 字符串 */
  async function cronFor(backupTime: string, frequency: 'daily' | 'weekly' | 'monthly') {
    const { scheduleConfig, saveSchedule } = useBackupSchedule()
    scheduleConfig.value.backupTime = backupTime
    scheduleConfig.value.frequency = frequency
    await saveSchedule()
    // 取【最后一次】调用：同一用例内多次 cronFor 时 calls[0] 会指向首次调用
    const calls = (put as any).mock.calls
    return calls[calls.length - 1][1].schedule as string
  }

  it("backupTime 为空串 → `|| '02:00'` 兜底", async () => {
    expect(await cronFor('', 'daily')).toBe('00 02 * * *')
  })

  it("backupTime 无冒号 → 解构默认值 m = '0' 生效", async () => {
    // '3'.split(':') === ['3'] → h='3'、m 缺席取默认 '0' → 03:00
    expect(await cronFor('3', 'daily')).toBe('00 03 * * *')
  })

  it('weekly → 末位固定为 1；monthly → dom 固定为 1', async () => {
    expect(await cronFor('23:45', 'weekly')).toBe('45 23 * * 1')
    expect(await cronFor('23:45', 'monthly')).toBe('45 23 1 * *')
    // 未知频率保守回退 daily 表达式
    expect(await cronFor('23:45', 'daily')).toBe('45 23 * * *')
  })
})

/**
 * 2026-09-30 深审修复：cron 解析/回写的静默失真
 * - 步长表达式（每 5 分钟）原先拼成 backupTime "02:05/5"（假时间）
 * - `0 2 * * 3` / `0 2 15 * *` 经界面一保存即被改写成 周一 / 1 号
 * - backupTime 非法（25:99 / abc:xyz / 02:99）原先直接拼进 cron 下发
 */
describe('useBackupSchedule cron 保真与时刻校验', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(put as any).mockResolvedValue({ success: true })
  })

  /** 用给定后端 cron 载入配置（可选改动）后保存，返回 PUT 下发的 schedule */
  async function loadThenSave(schedule: string, mutate?: (c: ScheduleConfig) => void) {
    ;(get as any).mockResolvedValue({ enabled: true, keepCount: 5, schedule })
    const api = useBackupSchedule()
    await api.loadScheduleConfig()
    mutate?.(api.scheduleConfig.value)
    await api.saveSchedule()
    const calls = (put as any).mock.calls
    return calls[calls.length - 1][1].schedule as string
  }

  it('分钟字段非纯数字（*/5）→ 用户未改动时原样回写，不再编造 02:*/5', async () => {
    expect(await loadThenSave('*/5 2 * * *')).toBe('*/5 2 * * *')
    // 展示侧仍回落到默认 02:00（不显示假时间）
    ;(get as any).mockResolvedValue({ enabled: true, keepCount: 5, schedule: '*/5 2 * * *' })
    const api = useBackupSchedule()
    await api.loadScheduleConfig()
    expect(api.scheduleConfig.value.backupTime).toBe('02:00')
  })

  it('不可表达的 cron + 用户改了时间 → 按用户输入下发新表达式', async () => {
    expect(
      await loadThenSave('*/5 2 * * *', (c) => {
        c.backupTime = '03:30'
      })
    ).toBe('30 03 * * *')
  })

  it('weekly 保留原星期字段（0 2 * * 3 不再被静默改写成周一）', async () => {
    expect(await loadThenSave('0 2 * * 3')).toBe('00 02 * * 3')
  })

  it('monthly 保留原"日"字段（0 2 15 * * 不再被静默改写成 1 号）', async () => {
    expect(await loadThenSave('0 2 15 * *')).toBe('00 02 15 * *')
  })

  it('weekly/monthly 且原字段为 * → 回落默认 周一 / 1 号', async () => {
    expect(await loadThenSave('0 2 * * 1')).toBe('00 02 * * 1')
    expect(await loadThenSave('0 2 1 * *')).toBe('00 02 1 * *')
  })

  it('backupTime 非法 → fail-closed：提示且不下发任何请求', async () => {
    for (const bad of ['25:99', 'abc:xyz', '02:99', '99:00', ':']) {
      vi.clearAllMocks()
      ;(put as any).mockResolvedValue({ success: true })
      const { scheduleConfig, saveSchedule, savingSchedule } = useBackupSchedule()
      scheduleConfig.value.backupTime = bad
      await saveSchedule()
      expect(put).not.toHaveBeenCalled()
      expect(ElMessage.error).toHaveBeenCalledWith(expect.stringContaining('备份时间格式不正确'))
      expect(ElMessage.success).not.toHaveBeenCalled()
      expect(savingSchedule.value).toBe(false)
    }
  })
})

describe('useBackupSchedule saveSchedule 失败分支', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(get as any).mockResolvedValue({ enabled: false, keepCount: 7, schedule: '0 2 * * *' })
  })

  it('后端 detail 优先作为错误文案', async () => {
    ;(put as any).mockRejectedValue({
      response: { data: { detail: '保留份数不能小于 1', message: '忽略我' } },
    })
    const { saveSchedule, savingSchedule } = useBackupSchedule()
    await saveSchedule()
    expect(ElMessage.error).toHaveBeenCalledWith('保留份数不能小于 1')
    expect(ElMessage.success).not.toHaveBeenCalled()
    // finally 必须释放 saving 标志，否则按钮永久禁用
    expect(savingSchedule.value).toBe(false)
  })

  it('无 detail 时回退 message', async () => {
    ;(put as any).mockRejectedValue({ response: { data: { message: '计划写入失败' } } })
    const { saveSchedule } = useBackupSchedule()
    await saveSchedule()
    expect(ElMessage.error).toHaveBeenCalledWith('计划写入失败')
  })

  it('response 链缺失（网络层错误）→ 通用兜底文案', async () => {
    ;(put as any).mockRejectedValue(new Error('Network Error'))
    const { saveSchedule, savingSchedule } = useBackupSchedule()
    await saveSchedule()
    expect(ElMessage.error).toHaveBeenCalledWith('保存备份计划失败')
    expect(savingSchedule.value).toBe(false)
  })

  it('reject 值为 null/undefined 时可选链短路，不抛 TypeError', async () => {
    ;(put as any).mockRejectedValue(undefined)
    const { saveSchedule } = useBackupSchedule()
    await expect(saveSchedule()).resolves.toBeUndefined()
    expect(ElMessage.error).toHaveBeenCalledWith('保存备份计划失败')
  })

  it('保存失败时不执行回读 GET（put 已抛，后续 await 被跳过）', async () => {
    ;(put as any).mockRejectedValue({ response: { data: { detail: 'x' } } })
    const { saveSchedule } = useBackupSchedule()
    await saveSchedule()
    expect(get).not.toHaveBeenCalled()
  })
})
