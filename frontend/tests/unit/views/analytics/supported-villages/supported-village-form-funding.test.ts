/**
 * SupportedVillageForm.vue — H2「经费加载失败不用空数据覆盖」回归测试
 *
 * 缺陷背景：loadTransitionFunding 旧实现用 `catch {}` 静默吞异常，transitionFundingRows 停在 []；
 * handleSubmit 编辑模式无条件调用 saveTransitionFunding(id, { items: [] })，
 * 打开编辑弹窗时若 GET /transition-funding 瞬时失败（网络抖动/500/404），
 * 用户只改村基本信息点保存，就会用空 items 把已保存经费总额覆盖为 0（真实数据丢失）。
 *
 * 修复：加载失败置 fundingLoadFailed 标志；handleSubmit 检测到该标志时跳过 saveTransitionFunding，
 * 仅提交村基本信息（保留原总额），并提示用户重新打开编辑。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  getTransitionFunding: vi.fn(),
  saveTransitionFunding: vi.fn(),
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

vi.mock('@/api/supportedVillage', () => ({
  getTransitionFunding: (...a: any[]) => mocks.getTransitionFunding(...a),
  saveTransitionFunding: (...a: any[]) => mocks.saveTransitionFunding(...a),
}))

vi.mock('@/utils/logger', () => ({ logger: mocks.logger }))

// 重量级/地图相关子组件用轻量桩替换，避免引入 leaflet 等依赖
vi.mock('@/components/MapPicker.vue', () => ({
  default: { name: 'MapPicker', props: ['latitude', 'longitude', 'disabled'], template: '<div class="map-picker-stub" />' },
}))
vi.mock('@/components/common/GuizhouRegionSelector.vue', () => ({
  default: { name: 'GuizhouRegionSelector', props: ['modelValue', 'disabled', 'showTownship'], template: '<div class="region-stub" />' },
}))
vi.mock('@/components/business/EmptyState/EmptyState.vue', () => ({
  default: { name: 'EmptyState', props: ['text', 'size'], template: '<div class="empty-stub" />' },
}))

import SupportedVillageForm from '@/views/analytics/supported-villages/components/SupportedVillageForm.vue'

// 含必填字段的村记录，确保 el-form 校验通过
const baseVillage = {
  id: 42,
  sequenceNo: 1,
  department: '某部门',
  supportUnit: '某单位',
  villageName: '示范村',
  transitionFundMilitaryTotal: 100,
  transitionFundLocalTotal: 50,
}

function mountForm(village: any = baseVillage, mode: 'create' | 'edit' | 'view' = 'edit') {
  return mount(SupportedVillageForm as any, {
    props: { village, mode },
    global: {
      plugins: [ElementPlus],
      stubs: { 'el-icon': { template: '<i class="icon-stub"><slot /></i>' } },
    },
  })
}

function st(wrapper: ReturnType<typeof mountForm>) {
  return (wrapper.vm as any).$.setupState
}

// 用桩替换 el-form 校验，隔离 H2 逻辑与表单校验机制（必填项已填充，此处仅保证确定性）
function stubValidate(wrapper: ReturnType<typeof mountForm>) {
  const vm = st(wrapper)
  vm.formRef = { validate: vi.fn().mockResolvedValue(true) }
  return vm
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.saveTransitionFunding.mockResolvedValue({})
})

describe('SupportedVillageForm.vue H2 经费加载失败保护', () => {
  it('加载失败：置 fundingLoadFailed 标志、rows 为空，并渲染告警条', async () => {
    mocks.getTransitionFunding.mockRejectedValueOnce(new Error('500'))
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    expect(vm.fundingLoadFailed).toBe(true)
    expect(vm.transitionFundingRows).toEqual([])
    expect(wrapper.text()).toContain('经费数据加载失败')
  })

  it('加载失败后提交：跳过 saveTransitionFunding（不用空 items 覆盖），仅提交基本信息并告警', async () => {
    mocks.getTransitionFunding.mockRejectedValueOnce(new Error('网络抖动'))
    const warningSpy = vi.spyOn(ElMessage, 'warning').mockImplementation(() => true as any)
    const wrapper = mountForm()
    await flushPromises()
    const vm = stubValidate(wrapper)
    expect(vm.fundingLoadFailed).toBe(true)

    await vm.handleSubmit()
    await flushPromises()

    // 关键断言：绝不以空 items 覆盖已保存经费
    expect(mocks.saveTransitionFunding).not.toHaveBeenCalled()
    // 仍然提交村基本信息（保留 watch 填入的原总额，不被重算为 0）
    const emitted = wrapper.emitted('submit')
    expect(emitted).toBeTruthy()
    const payload: any = emitted![0][0]
    expect(payload.villageName).toBe('示范村')
    expect(payload.transitionFundMilitaryTotal).toBe(100)
    expect(payload.transitionFundLocalTotal).toBe(50)
    expect(warningSpy).toHaveBeenCalled()
  })

  it('加载成功：正常提交年度经费（saveTransitionFunding 携带 items）', async () => {
    mocks.getTransitionFunding.mockResolvedValueOnce([
      { year: 2024, militaryInvestment: 10, localInvestment: 5 },
    ])
    const wrapper = mountForm()
    await flushPromises()
    const vm = stubValidate(wrapper)
    expect(vm.fundingLoadFailed).toBe(false)
    expect(vm.transitionFundingRows).toHaveLength(1)

    await vm.handleSubmit()
    await flushPromises()

    expect(mocks.saveTransitionFunding).toHaveBeenCalledTimes(1)
    const [vid, body] = mocks.saveTransitionFunding.mock.calls[0]
    expect(vid).toBe(42)
    expect(body.items).toEqual([
      { year: 2024, militaryInvestment: 10, localInvestment: 5, totalInvestment: 15 },
    ])
  })

  it('确实无数据（空数组，非错误）：不置失败标志，正常以空 items 提交（用户主动清空）', async () => {
    mocks.getTransitionFunding.mockResolvedValueOnce([])
    const wrapper = mountForm()
    await flushPromises()
    const vm = stubValidate(wrapper)
    // 空数据 ≠ 加载失败：标志保持 false，允许提交（后端另有空 items 兜底）
    expect(vm.fundingLoadFailed).toBe(false)

    await vm.handleSubmit()
    await flushPromises()
    expect(mocks.saveTransitionFunding).toHaveBeenCalledTimes(1)
  })
})
