import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

function localToday(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

vi.mock('@/api/request', () => ({ get: mocks.get, post: mocks.post,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))
vi.mock('element-plus', () => ({ ElMessage: mocks.message }))

import CheckinWorkbench from '@/views/ruralWorks/checkin/Index.vue'

function mountComp() {
  return mount(CheckinWorkbench, {
    global: {
      stubs: {
        'el-card': { name: 'ElCard', template: '<div class="card"><slot name="header" /><slot /></div>' },
        'el-button': { name: 'ElButton', template: '<button @click="$emit(\'click\')"><slot /></button>' },
        'el-form': { name: 'ElForm', template: '<div><slot /></div>' },
        'el-form-item': { name: 'ElFormItem', template: '<div><slot /></div>' },
        'el-input': { name: 'ElInput', template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
        'el-alert': { name: 'ElAlert', props: ['title'], template: '<div class="alert">{{ title }}</div>' },
        'el-row': { name: 'ElRow', template: '<div><slot /></div>' },
        'el-col': { name: 'ElCol', template: '<div><slot /></div>' },
        'el-descriptions': { name: 'ElDescriptions', template: '<div><slot /></div>' },
        'el-descriptions-item': { name: 'ElDescriptionsItem', template: '<span><slot /></span>' },
        'el-empty': { name: 'ElEmpty', props: ['description'], template: '<div>{{ description }}</div>' },
        'el-tag': { name: 'ElTag', template: '<span><slot /></span>' },
        'el-date-picker': { name: 'ElDatePicker', template: '<div />' },
      },
    },
  })
}

describe('CheckinWorkbench.vue（驻村工作台）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockImplementation((url: string) => {
      if (url === '/work-logs') {
        return Promise.resolve({
          items: [
            { log_date: localToday(), category: 'checkin', location: '甲村村委会' },
          ],
        })
      }
      if (url.includes('monthly-summary')) {
        return Promise.resolve({
          year: 2026,
          month: 8,
          total_logs: 5,
          checkin_days: 3,
          category_counts: { checkin: 3, daily: 2 },
          summary_text: '2026年8月驻村工作总结：共记录工作 5 项',
          items: [{ work_date: '2026-08-01', content: '走访', category: 'daily' }],
        })
      }
      return Promise.resolve({})
    })
    mocks.post.mockResolvedValue({})
  })

  it('挂载加载打卡状态与月度总结', async () => {
    const w = mountComp()
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledWith('/work-logs', expect.anything())
    expect(mocks.get).toHaveBeenCalledWith(expect.stringContaining('monthly-summary'))
    expect(w.text()).toContain('今日驻村打卡')
    expect(w.text()).toContain('甲村村委会')
    expect(w.text()).toContain('共记录工作 5 项')
    w.unmount()
  })

  it('已打卡时按钮禁用', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    expect(vm.checkedToday).toBe(true)
    w.unmount()
  })

  it('打卡成功：填写地点后提交并刷新总结', async () => {
    mocks.get.mockImplementation((url: string) => {
      if (url === '/work-logs') return Promise.resolve({ items: [] })
      if (url.includes('monthly-summary')) {
        return Promise.resolve({ total_logs: 0, checkin_days: 0, category_counts: {}, summary_text: '', items: [] })
      }
      return Promise.resolve({})
    })
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    vm.location = '乙村'
    vm.content = '开展走访'
    await vm.doCheckin()
    expect(mocks.post).toHaveBeenCalledWith('/work-logs', expect.objectContaining({ category: 'checkin', location: '乙村' }))
    expect(mocks.message.success).toHaveBeenCalledWith('打卡成功')
    expect(vm.checkedToday).toBe(true)
    w.unmount()
  })

  it('打卡缺地点提示', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    vm.location = ''
    await vm.doCheckin()
    expect(mocks.message.warning).toHaveBeenCalledWith('请填写打卡地点')
    expect(mocks.post).not.toHaveBeenCalled()
    w.unmount()
  })

  it('打卡重复时提示 info', async () => {
    mocks.post.mockRejectedValue({ detail: '今天已完成驻村打卡' })
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    vm.location = '丙村'
    await vm.doCheckin()
    expect(mocks.message.info).toHaveBeenCalledWith('今天已完成驻村打卡')
    expect(vm.checkedToday).toBe(true)
    w.unmount()
  })

  it('打卡其他错误提示 detail', async () => {
    mocks.post.mockRejectedValue({ detail: '服务器错误' })
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    vm.location = '丁村'
    await vm.doCheckin()
    expect(mocks.message.error).toHaveBeenCalledWith('服务器错误')
    w.unmount()
  })

  it('月度总结加载失败提示', async () => {
    mocks.get.mockImplementation((url: string) => {
      if (url === '/work-logs') return Promise.resolve({ items: [] })
      if (url.includes('monthly-summary')) return Promise.reject(new Error('net'))
      return Promise.resolve({})
    })
    const w = mountComp()
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('加载月度总结失败')
    w.unmount()
  })

  it('todayStr 计算属性格式', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    expect(vm.todayStr).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    w.unmount()
  })

  it('checkToday 请求失败时置为未打卡', async () => {
    mocks.get.mockImplementation((url: string) => {
      if (url === '/work-logs') return Promise.reject(new Error('net'))
      if (url.includes('monthly-summary')) {
        return Promise.resolve({ total_logs: 0, checkin_days: 0, category_counts: {}, summary_text: '', items: [] })
      }
      return Promise.resolve({})
    })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).checkedToday).toBe(false)
    w.unmount()
  })

  it('checkToday 响应无 items 字段时安全降级为空数组', async () => {
    mocks.get.mockImplementation((url: string) => {
      if (url === '/work-logs') return Promise.resolve({})
      if (url.includes('monthly-summary')) {
        return Promise.resolve({ total_logs: 0, checkin_days: 0, category_counts: {}, summary_text: '', items: [] })
      }
      return Promise.resolve({})
    })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).checkedToday).toBe(false)
    w.unmount()
  })

  it('log_type 为 checkin 时也识别为今日已打卡', async () => {
    mocks.get.mockImplementation((url: string) => {
      if (url === '/work-logs') {
        return Promise.resolve({ items: [{ log_date: localToday(), category: 'daily', log_type: 'checkin' }] })
      }
      if (url.includes('monthly-summary')) {
        return Promise.resolve({ total_logs: 0, checkin_days: 0, category_counts: {}, summary_text: '', items: [] })
      }
      return Promise.resolve({})
    })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).checkedToday).toBe(true)
    w.unmount()
  })

  it('今日已打卡且无地点时 alert 显示未记录位置', async () => {
    mocks.get.mockImplementation((url: string) => {
      if (url === '/work-logs') {
        return Promise.resolve({ items: [{ log_date: localToday(), category: 'checkin' }] })
      }
      if (url.includes('monthly-summary')) {
        return Promise.resolve({ total_logs: 0, checkin_days: 0, category_counts: {}, summary_text: '', items: [] })
      }
      return Promise.resolve({})
    })
    const w = mountComp()
    await flushPromises()
    expect(w.find('.alert').text()).toContain('未记录位置')
    w.unmount()
  })

  it('打卡失败且无 detail 时提示默认文案', async () => {
    mocks.post.mockRejectedValue({})
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    vm.location = '戊村'
    await vm.doCheckin()
    expect(mocks.message.error).toHaveBeenCalledWith('打卡失败')
    w.unmount()
  })

  it('打卡失败：axios 形态 e.response.data.detail（重复 → info；其他 → error）', async () => {
    mocks.post.mockRejectedValue({ response: { data: { detail: '今天已完成驻村打卡' } } })
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    vm.location = '己村'
    await vm.doCheckin()
    expect(mocks.message.info).toHaveBeenCalledWith('今天已完成驻村打卡')
    expect(vm.checkedToday).toBe(true)

    mocks.post.mockRejectedValue({ response: { data: { detail: '网络异常' } } })
    vm.checkedToday = false
    vm.location = '庚村'
    await vm.doCheckin()
    expect(mocks.message.error).toHaveBeenCalledWith('网络异常')
    w.unmount()
  })

  it('loadSummary 在月份为空时直接返回', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    vm.summaryMonth = ''
    mocks.get.mockClear()
    await vm.loadSummary()
    expect(mocks.get).not.toHaveBeenCalledWith(expect.stringContaining('monthly-summary'))
    w.unmount()
  })

  it('月度总结返回空时展示暂无数据', async () => {
    mocks.get.mockImplementation((url: string) => {
      if (url === '/work-logs') return Promise.resolve({ items: [] })
      if (url.includes('monthly-summary')) return Promise.resolve(null)
      return Promise.resolve({})
    })
    const w = mountComp()
    await flushPromises()
    expect(w.text()).toContain('暂无月度数据')
    w.unmount()
  })

  it('输入框 v-model 与月份选择 change 事件', async () => {
    const w = mountComp()
    await flushPromises()
    const inputs = w.findAll('input')
    await inputs[0].setValue('甲村村委会')
    await inputs[1].setValue('走访农户')
    const vm = w.vm as any
    expect(vm.location).toBe('甲村村委会')
    expect(vm.content).toBe('走访农户')

    const dp = w.findComponent({ name: 'ElDatePicker' })
    dp.vm.$emit('update:modelValue', '2026-07')
    dp.vm.$emit('change')
    await flushPromises()
    expect(vm.summaryMonth).toBe('2026-07')
    expect(mocks.get).toHaveBeenCalledWith(expect.stringContaining('year=2026'))
    w.unmount()
  })
})
