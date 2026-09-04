/**
 * SupportedVillageForm.vue 覆盖率攻坚（经费年度增删改 / regionValue 双向绑定 / handleSubmit 分支）
 *
 * 与同目录 supported-village-form-funding.test.ts 互补：后者聚焦 H2「经费加载失败不用空数据覆盖」
 * 的回归保护，本文件补齐其余未覆盖的脚本级函数与分支：
 *   hasFundingYear / onFundingYearChange / validateFundingYear / upsertFundingRow /
 *   advanceToNextYear / addOrUpdateFunding / removeFundingByYear / editFundingYear /
 *   regionValue.get / regionValue.set / handleCancel
 * 以及 branch@409,412,495,500,504,505,561,562,577,597,598,599,606,617,619。
 *
 * 说明：全局 config.global.stubs 已把 el-* 组件桩为 true 桩（不渲染插槽），
 * 模板内联产物在本文件的 istanbul 映射中不单独计数，故统一通过 setupState 驱动脚本逻辑；
 * el-form 校验用桩对象替换（与 H2 回归测试同一手法），隔离表单校验机制。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  getTransitionFunding: vi.fn(),
  saveTransitionFunding: vi.fn(),
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

vi.mock('@/api/supportedVillage', () => ({
  getTransitionFunding: (...a: any[]) => mocks.getTransitionFunding(...a),
  saveTransitionFunding: (...a: any[]) => mocks.saveTransitionFunding(...a),
}))

vi.mock('element-plus', () => ({ ElMessage: mocks.ElMessage }))

vi.mock('@/utils/logger', () => ({ logger: mocks.logger }))

// 重量级/地图相关子组件用可 emit 的轻量桩替换：
// GuizhouRegionSelector 的 update:modelValue 是覆盖 regionValue.set 的唯一入口
vi.mock('@/components/MapPicker.vue', () => ({
  default: {
    name: 'MapPicker',
    props: ['latitude', 'longitude', 'disabled'],
    emits: ['update:latitude', 'update:longitude'],
    template:
      '<div class="map-picker-stub">' +
      '<button type="button" class="mp-lat" @click="$emit(\'update:latitude\', 26.5)">lat</button>' +
      '<button type="button" class="mp-lng" @click="$emit(\'update:longitude\', 106.7)">lng</button>' +
      '</div>',
  },
}))
vi.mock('@/components/common/GuizhouRegionSelector.vue', () => ({
  default: {
    name: 'GuizhouRegionSelector',
    props: ['modelValue', 'disabled', 'showTownship'],
    emits: ['update:modelValue'],
    template:
      '<div class="region-stub">' +
      '<button type="button" class="rg-set" @click="$emit(\'update:modelValue\', { city: \'贵阳市\', county: \'修文县\', township: \'六屯镇\' })">set</button>' +
      '<button type="button" class="rg-empty" @click="$emit(\'update:modelValue\', {})">empty</button>' +
      '</div>',
  },
}))
vi.mock('@/components/business/EmptyState/EmptyState.vue', () => ({
  default: {
    name: 'EmptyState',
    props: ['text', 'size', 'title', 'description'],
    template: '<div class="empty-stub">{{ title }}{{ text }}</div>',
  },
}))

import SupportedVillageForm from '@/views/analytics/supported-villages/components/SupportedVillageForm.vue'

const baseVillage: any = {
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
      stubs: {
        'el-icon': { template: '<i class="icon-stub"><slot /></i>' },
        // el-alert 未在全局 stubs 中登记，且本文件不注册 ElementPlus 插件，
        // 若不显式桩掉则「经费数据加载失败」告警不会渲染任何内容。
        'el-alert': {
          props: ['title', 'description', 'type', 'showIcon', 'closable'],
          template: '<div class="alert-stub">{{ title }}{{ description }}</div>',
        },
      },
    },
  })
}

function st(wrapper: any) {
  return (wrapper.vm as any).$.setupState
}

/** 用桩替换 el-form 校验，隔离表单校验机制（必填项已在 baseVillage 中填充） */
function stubValidate(wrapper: any, impl: () => Promise<any> = () => Promise.resolve(true)) {
  const vm = st(wrapper)
  vm.formRef = { validate: vi.fn().mockImplementation(impl) }
  return vm
}

const CUR_YEAR = new Date().getFullYear()

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getTransitionFunding.mockResolvedValue([])
  mocks.saveTransitionFunding.mockResolvedValue({})
})

describe('经费年度：查询与回填', () => {
  it('hasFundingYear 命中/未命中', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.transitionFundingRows = [{ year: 2024, militaryInvestment: 10, localInvestment: 5 }]
    expect(vm.hasFundingYear(2024)).toBe(true)
    expect(vm.hasFundingYear(2025)).toBe(false)
    expect(vm.hasFundingYear(2024)).toBe(true)
  })

  it('onFundingYearChange：命中已有年度 → 回填；未命中 → 归零', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.transitionFundingRows = [{ year: 2024, militaryInvestment: 12.5, localInvestment: 3.25 }]
    vm.currentMilitaryInput = 999
    vm.currentLocalInput = 888

    vm.onFundingYearChange(2024)
    expect(vm.currentMilitaryInput).toBe(12.5)
    expect(vm.currentLocalInput).toBe(3.25)

    vm.onFundingYearChange(2030)
    expect(vm.currentMilitaryInput).toBe(0)
    expect(vm.currentLocalInput).toBe(0)
  })

  it('editFundingYear：切换选中年度并回填该年度金额', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.transitionFundingRows = [
      { year: 2023, militaryInvestment: 1, localInvestment: 2 },
      { year: 2024, militaryInvestment: 3, localInvestment: 4 },
    ]
    vm.selectedFundingYear = 2024
    vm.editFundingYear(2023)
    expect(vm.selectedFundingYear).toBe(2023)
    expect(vm.currentMilitaryInput).toBe(1)
    expect(vm.currentLocalInput).toBe(2)
  })
})

describe('经费年度：校验', () => {
  it('validateFundingYear：非数字 / 非整数 / 早于 2000 → 警告并返回 null', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)

    vm.selectedFundingYear = 'abc' as any
    expect(vm.validateFundingYear()).toBeNull()
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('请输入有效年度（如 2024）')

    vm.selectedFundingYear = 2024.5 as any
    expect(vm.validateFundingYear()).toBeNull()

    vm.selectedFundingYear = 1999
    expect(vm.validateFundingYear()).toBeNull()
    expect(mocks.ElMessage.warning).toHaveBeenCalledTimes(3)
  })

  it('validateFundingYear：合法年度 → 返回数值', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.selectedFundingYear = 2024
    expect(vm.validateFundingYear()).toBe(2024)
    expect(mocks.ElMessage.warning).not.toHaveBeenCalled()
    // 字符串数字亦可（allow-create 的 el-select 可能给出字符串）
    vm.selectedFundingYear = '2025' as any
    expect(vm.validateFundingYear()).toBe(2025)
  })
})

describe('经费年度：upsert 与年度推进', () => {
  it('upsertFundingRow：已有年度 → 原地更新，不新增行', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.transitionFundingRows = [{ year: 2024, militaryInvestment: 1, localInvestment: 1 }]
    vm.currentMilitaryInput = 20
    vm.currentLocalInput = 30
    vm.upsertFundingRow(2024)
    expect(vm.transitionFundingRows).toEqual([
      { year: 2024, militaryInvestment: 20, localInvestment: 30 },
    ])
  })

  it('upsertFundingRow：新年度 → 追加并按年度升序排序', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.transitionFundingRows = [{ year: 2024, militaryInvestment: 1, localInvestment: 1 }]
    vm.currentMilitaryInput = 7
    vm.currentLocalInput = 8
    vm.upsertFundingRow(2022)
    expect(vm.transitionFundingRows.map((r: any) => r.year)).toEqual([2022, 2024])
    vm.upsertFundingRow(2026)
    expect(vm.transitionFundingRows.map((r: any) => r.year)).toEqual([2022, 2024, 2026])
    expect(vm.transitionFundingRows[2]).toEqual({
      year: 2026,
      militaryInvestment: 7,
      localInvestment: 8,
    })
  })

  it('advanceToNextYear：下一年在可选范围 → 前移；超出范围 → 保持当前年度', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.transitionFundingRows = [{ year: 2025, militaryInvestment: 4, localInvestment: 6 }]

    vm.selectedFundingYear = 2022
    vm.advanceToNextYear(2022)
    expect(vm.selectedFundingYear).toBe(2023)
    // 2023 无记录 → 输入归零
    expect(vm.currentMilitaryInput).toBe(0)
    expect(vm.currentLocalInput).toBe(0)

    // 滚动窗口上界（当前年+10）：下一年不在可选项内 → 选中年度不变，但仍回填
    const upper = CUR_YEAR + 10
    expect(vm.availableFundingYears).toContain(upper)
    expect(vm.availableFundingYears).not.toContain(upper + 1)
    vm.selectedFundingYear = upper
    vm.advanceToNextYear(upper)
    expect(vm.selectedFundingYear).toBe(upper)
  })

  it('addOrUpdateFunding：年度非法 → 直接返回不落行；合法 → upsert + 推进年度', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.transitionFundingRows = []
    vm.selectedFundingYear = 'bad' as any
    vm.currentMilitaryInput = 5
    vm.addOrUpdateFunding()
    expect(vm.transitionFundingRows).toEqual([])

    vm.selectedFundingYear = 2024
    vm.currentMilitaryInput = 5
    vm.currentLocalInput = 6
    vm.addOrUpdateFunding()
    expect(vm.transitionFundingRows).toEqual([
      { year: 2024, militaryInvestment: 5, localInvestment: 6 },
    ])
    expect(vm.selectedFundingYear).toBe(2025)
    expect(vm.currentMilitaryInput).toBe(0)
    expect(vm.currentLocalInput).toBe(0)
  })
})

describe('经费年度：删除', () => {
  it('removeFundingByYear：删除当前选中年度 → 移除行并重置输入', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.transitionFundingRows = [
      { year: 2023, militaryInvestment: 1, localInvestment: 2 },
      { year: 2024, militaryInvestment: 3, localInvestment: 4 },
    ]
    vm.selectedFundingYear = 2024
    vm.currentMilitaryInput = 3
    vm.currentLocalInput = 4
    vm.removeFundingByYear(2024)
    expect(vm.transitionFundingRows.map((r: any) => r.year)).toEqual([2023])
    expect(vm.currentMilitaryInput).toBe(0)
    expect(vm.currentLocalInput).toBe(0)
  })

  it('removeFundingByYear：删除非选中年度 → 移除行但保留当前输入', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.transitionFundingRows = [
      { year: 2023, militaryInvestment: 1, localInvestment: 2 },
      { year: 2024, militaryInvestment: 3, localInvestment: 4 },
    ]
    vm.selectedFundingYear = 2024
    vm.currentMilitaryInput = 77
    vm.currentLocalInput = 88
    vm.removeFundingByYear(2023)
    expect(vm.transitionFundingRows.map((r: any) => r.year)).toEqual([2024])
    expect(vm.currentMilitaryInput).toBe(77)
    expect(vm.currentLocalInput).toBe(88)
  })

  it('removeFundingByYear：年度不存在 → idx < 0 不修改行；选中态仍重置输入', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.transitionFundingRows = [{ year: 2024, militaryInvestment: 3, localInvestment: 4 }]
    vm.selectedFundingYear = 2099
    vm.currentMilitaryInput = 11
    vm.currentLocalInput = 22
    vm.removeFundingByYear(2099)
    expect(vm.transitionFundingRows).toHaveLength(1)
    // isSelected 为真但行不存在：只重置输入，不动数据
    expect(vm.currentMilitaryInput).toBe(0)
    expect(vm.currentLocalInput).toBe(0)

    // 年度不存在且非选中 → 两者都不变
    vm.currentMilitaryInput = 33
    vm.removeFundingByYear(2100)
    expect(vm.currentMilitaryInput).toBe(33)
    expect(vm.transitionFundingRows).toHaveLength(1)
  })
})

// 说明：GuizhouRegionSelector / MapPicker 在模板中分别位于 el-form-item / el-col 内，
// 二者都是全局 true 桩（不渲染插槽），因此子组件桩不会出现在 DOM 中。
// 这里直接通过 setupState 读写 computed（regionValue）来覆盖其 get@518 / set@523，
// 模板内联的 v-model 回写产物由 supported-village-form-funding.test.ts（注册真实 ElementPlus）覆盖。
describe('regionValue 双向绑定（flat formData ↔ RegionValue）', () => {
  it('set：有值写入 formData；空对象 → 回落为空串', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)

    vm.regionValue = { city: '贵阳市', county: '修文县', township: '六屯镇' }
    expect(vm.formData.city).toBe('贵阳市')
    expect(vm.formData.county).toBe('修文县')
    expect(vm.formData.township).toBe('六屯镇')

    vm.regionValue = {}
    expect(vm.formData.city).toBe('')
    expect(vm.formData.county).toBe('')
    expect(vm.formData.township).toBe('')
  })

  it('set：部分字段缺省 → || \'\' 逐字段兜底', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.regionValue = { city: '毕节市' }
    expect(vm.formData.city).toBe('毕节市')
    expect(vm.formData.county).toBe('')
    expect(vm.formData.township).toBe('')
  })

  it('get：空串映射为 undefined，有值原样返回', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.formData.city = ''
    vm.formData.county = ''
    vm.formData.township = ''
    expect(vm.regionValue).toEqual({
      city: undefined,
      county: undefined,
      township: undefined,
    })

    vm.formData.city = '遵义市'
    vm.formData.county = '湄潭县'
    vm.formData.township = '兴隆镇'
    expect(vm.regionValue).toEqual({
      city: '遵义市',
      county: '湄潭县',
      township: '兴隆镇',
    })
  })

})

describe('loadTransitionFunding 响应形态', () => {
  it('village 为空 → 直接返回，不发请求（branch@495）', async () => {
    const wrapper = mountForm(null, 'create')
    await flushPromises()
    const vm = st(wrapper)
    mocks.getTransitionFunding.mockClear()
    await vm.loadTransitionFunding()
    expect(mocks.getTransitionFunding).not.toHaveBeenCalled()
    expect(vm.fundingLoadFailed).toBe(false)
  })

  it('village 存在但无 id → watch 不触发加载', async () => {
    const wrapper = mountForm({ villageName: '无ID村' }, 'create')
    await flushPromises()
    expect(mocks.getTransitionFunding).not.toHaveBeenCalled()
    expect(st(wrapper).transitionFundingRows).toEqual([])
  })

  it('resp 为 {data:[...]} 信封 → 取 data 并按年度升序', async () => {
    mocks.getTransitionFunding.mockResolvedValueOnce({
      data: [
        { year: 2025, militaryInvestment: 2, localInvestment: 3 },
        { year: 2023, militaryInvestment: 1, localInvestment: 1 },
      ],
    })
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    expect(vm.transitionFundingRows.map((r: any) => r.year)).toEqual([2023, 2025])
    expect(vm.fundingLoadFailed).toBe(false)
  })

  it('resp 为裸数组 → 直接使用；resp 为 null → || 链兜底为空数组（branch@500）', async () => {
    mocks.getTransitionFunding.mockResolvedValueOnce([
      { year: 2024, militaryInvestment: 9, localInvestment: 9 },
    ])
    const wrapper = mountForm()
    await flushPromises()
    expect(st(wrapper).transitionFundingRows).toEqual([
      { year: 2024, militaryInvestment: 9, localInvestment: 9 },
    ])

    mocks.getTransitionFunding.mockResolvedValueOnce(null)
    await st(wrapper).loadTransitionFunding()
    expect(st(wrapper).transitionFundingRows).toEqual([])
  })

  it('行内金额缺省 → Number(x || 0) 归零（branch@504/505）', async () => {
    mocks.getTransitionFunding.mockResolvedValueOnce([
      { year: 2024 },
      { year: 2025, militaryInvestment: null, localInvestment: undefined },
    ])
    const wrapper = mountForm()
    await flushPromises()
    expect(st(wrapper).transitionFundingRows).toEqual([
      { year: 2024, militaryInvestment: 0, localInvestment: 0 },
      { year: 2025, militaryInvestment: 0, localInvestment: 0 },
    ])
  })

  it('加载失败 → 置失败标志 + 清空行 + 记日志', async () => {
    mocks.getTransitionFunding.mockRejectedValueOnce(new Error('500'))
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    expect(vm.fundingLoadFailed).toBe(true)
    expect(vm.transitionFundingRows).toEqual([])
    expect(mocks.logger.error).toHaveBeenCalled()
    // 再次加载前重置失败标志
    mocks.getTransitionFunding.mockResolvedValueOnce([])
    await vm.loadTransitionFunding()
    expect(vm.fundingLoadFailed).toBe(false)
  })
})

describe('watch 填充与合计口径', () => {
  it('village 无总额字段 → || 0 兜底（branch@561/562）', async () => {
    const wrapper = mountForm({ id: 7, department: 'D', supportUnit: 'U', villageName: 'V' })
    await flushPromises()
    const vm = st(wrapper)
    expect(vm.formData.transitionFundMilitaryTotal).toBe(0)
    expect(vm.formData.transitionFundLocalTotal).toBe(0)
    expect(vm.formData.province).toBeTruthy() // DEFAULT_PROVINCE 兜底
    expect(vm.formData.latitude).toBeNull()
    expect(vm.formData.longitude).toBeNull()
  })

  it('village 携带总额与坐标 → 原样填入；props 变化后重新加载经费', async () => {
    const wrapper = mountForm({ ...baseVillage, latitude: 26.1, longitude: 106.2, county: 'C' })
    await flushPromises()
    const vm = st(wrapper)
    expect(vm.formData.transitionFundMilitaryTotal).toBe(100)
    expect(vm.formData.transitionFundLocalTotal).toBe(50)
    expect(vm.formData.latitude).toBe(26.1)
    expect(vm.formData.longitude).toBe(106.2)
    expect(vm.formData.isThreeRegions).toBe(false)

    mocks.getTransitionFunding.mockClear()
    await wrapper.setProps({ village: { ...baseVillage, id: 43, villageName: '另一村' } })
    await flushPromises()
    expect(mocks.getTransitionFunding).toHaveBeenCalledWith(43)
    expect(vm.formData.villageName).toBe('另一村')
  })

  it('合计 computed：行内金额缺省 → || 0（branch@409/412）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.transitionFundingRows = [
      { year: 2023 },
      { year: 2024, militaryInvestment: 10, localInvestment: 5 },
      { year: 2025, militaryInvestment: null, localInvestment: null },
    ]
    expect(vm.transitionMilitaryTotal).toBe(10)
    expect(vm.transitionLocalTotal).toBe(5)
    // 可选年度为 2021 ~ 当前年+10 的升序滚动窗口
    expect(vm.availableFundingYears[0]).toBe(2021)
    expect(vm.availableFundingYears.at(-1)).toBe(CUR_YEAR + 10)
  })
})

describe('handleSubmit 分支', () => {
  it('formRef 为空 → 直接返回，不提交（branch@577）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = st(wrapper)
    vm.formRef = null
    await vm.handleSubmit()
    expect(wrapper.emitted('submit')).toBeFalsy()
    expect(mocks.saveTransitionFunding).not.toHaveBeenCalled()
  })

  it('表单校验失败 → 记日志且不提交（branch@619 / stmts@620-621）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = stubValidate(wrapper, () => Promise.reject(new Error('validate fail')))
    await vm.handleSubmit()
    expect(mocks.logger.error).toHaveBeenCalled()
    expect(wrapper.emitted('submit')).toBeFalsy()
    expect(mocks.saveTransitionFunding).not.toHaveBeenCalled()
  })

  it('编辑模式：先保存年度经费再提交；金额缺省行走 || 0（branch@597/598/599）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const vm = stubValidate(wrapper)
    vm.transitionFundingRows = [
      { year: 2024 },
      { year: 2025, militaryInvestment: 10, localInvestment: 5 },
    ]
    await vm.handleSubmit()
    await flushPromises()

    expect(mocks.saveTransitionFunding).toHaveBeenCalledTimes(1)
    const [vid, body] = mocks.saveTransitionFunding.mock.calls[0]
    expect(vid).toBe(42)
    expect(body.items).toEqual([
      { year: 2024, militaryInvestment: 0, localInvestment: 0, totalInvestment: 0 },
      { year: 2025, militaryInvestment: 10, localInvestment: 5, totalInvestment: 15 },
    ])
    const payload: any = wrapper.emitted('submit')![0][0]
    // 编辑模式不附带 _transitionFundingItems（branch@617 假侧）
    expect(payload).not.toHaveProperty('_transitionFundingItems')
    expect(payload.transitionFundMilitaryTotal).toBe(10)
    expect(payload.transitionFundLocalTotal).toBe(5)
  })

  it('创建模式：payload 附带 _transitionFundingItems 且不调用保存接口（branch@617 真侧）', async () => {
    const wrapper = mountForm(null, 'create')
    await flushPromises()
    const vm = stubValidate(wrapper)
    vm.formData.department = 'D'
    vm.formData.supportUnit = 'U'
    vm.formData.villageName = '新村'
    vm.transitionFundingRows = [{ year: 2026, militaryInvestment: 1, localInvestment: 2 }]
    await vm.handleSubmit()
    await flushPromises()

    expect(mocks.saveTransitionFunding).not.toHaveBeenCalled()
    const payload: any = wrapper.emitted('submit')![0][0]
    expect(payload._transitionFundingItems).toEqual([
      { year: 2026, militaryInvestment: 1, localInvestment: 2, totalInvestment: 3 },
    ])
    expect(payload.villageName).toBe('新村')
  })

  it('年度经费保存失败：带 detail → 展示 detail 并阻止提交（branch@606 / stmts@607-610）', async () => {
    mocks.saveTransitionFunding.mockRejectedValueOnce({
      response: { data: { detail: '经费年度冲突' } },
    })
    const wrapper = mountForm()
    await flushPromises()
    const vm = stubValidate(wrapper)
    vm.transitionFundingRows = [{ year: 2024, militaryInvestment: 1, localInvestment: 1 }]
    await vm.handleSubmit()
    await flushPromises()
    expect(mocks.logger.error).toHaveBeenCalled()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('经费年度冲突')
    expect(wrapper.emitted('submit')).toBeFalsy()
  })

  it('年度经费保存失败：无 detail → 默认文案', async () => {
    mocks.saveTransitionFunding.mockRejectedValueOnce(new Error('down'))
    const wrapper = mountForm()
    await flushPromises()
    const vm = stubValidate(wrapper)
    await vm.handleSubmit()
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('过渡资金保存失败，请重试')
    expect(wrapper.emitted('submit')).toBeFalsy()
  })

  it('加载失败保护仍生效：跳过经费保存并告警（与 H2 回归互补）', async () => {
    mocks.getTransitionFunding.mockRejectedValueOnce(new Error('500'))
    const wrapper = mountForm()
    await flushPromises()
    const vm = stubValidate(wrapper)
    expect(vm.fundingLoadFailed).toBe(true)
    await vm.handleSubmit()
    await flushPromises()
    expect(mocks.saveTransitionFunding).not.toHaveBeenCalled()
    expect(mocks.ElMessage.warning).toHaveBeenCalled()
    const payload: any = wrapper.emitted('submit')![0][0]
    expect(payload.transitionFundMilitaryTotal).toBe(100)
  })
})

describe('handleCancel 与模式差异', () => {
  it('handleCancel → emit cancel（编辑/查看模式各一次）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    st(wrapper).handleCancel()
    expect(wrapper.emitted('cancel')).toHaveLength(1)

    const viewWrapper = mountForm(baseVillage, 'view')
    await flushPromises()
    st(viewWrapper).handleCancel()
    expect(viewWrapper.emitted('cancel')).toHaveLength(1)
  })

  it('view 模式：经费区加禁用样式且仍渲染加载失败告警', async () => {
    mocks.getTransitionFunding.mockRejectedValueOnce(new Error('500'))
    const wrapper = mountForm(baseVillage, 'view')
    await flushPromises()
    expect(wrapper.find('.funding-section--disabled').exists()).toBe(true)
    expect(wrapper.find('.alert-stub').exists()).toBe(true)
    expect(wrapper.text()).toContain('经费数据加载失败')
    expect(st(wrapper).fundingLoadFailed).toBe(true)
  })

  it('非 view 模式：经费区无禁用样式，空数据显示 EmptyState', async () => {
    const wrapper = mountForm(null, 'create')
    await flushPromises()
    expect(wrapper.find('.funding-section--disabled').exists()).toBe(false)
    expect(wrapper.find('.empty-stub').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无帮扶经费数据，请选择年度添加')
  })
})
