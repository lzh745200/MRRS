/**
 * views/admin/OrgModulePolicy.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：组织列表加载（成功/静默失败/缺 items 兜底）、策略加载（未选组织早退、
 * data/裸响应/空响应三态、失败提示）、保存（未选组织早退、成功/失败、保存后回读）、
 * 字典函数、模板分支（提示条/表格、自定义 tag 两侧）与 v-model 真实 DOM/组件事件。
 *
 * 覆盖率合并不变量：本文件是该组件的唯一执行者（router-index.test.ts 已桩替换），
 * 不要再从其它测试文件 import/mount 本组件。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, mockGet, mockPut } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockGet: vi.fn(),
  mockPut: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/request', () => ({
  get: (...a: any[]) => mockGet(...a),
  put: (...a: any[]) => mockPut(...a),
}))

import OrgModulePolicy from '@/views/admin/OrgModulePolicy.vue'

const customRow = {
  key: 'industry',
  name: '产业帮扶',
  category: 'business',
  visibility: 'visible',
  edit_mode: 'full_edit',
  is_custom: true,
}

const defaultRow = {
  key: 'population',
  name: '人口数据',
  category: 'core',
  visibility: 'hidden',
  edit_mode: 'read_only',
  is_custom: false,
}

function makeStubs(row: Record<string, any>) {
  return {
    'el-button': {
      name: 'ElButton',
      props: ['disabled', 'loading'],
      template: '<button class="el-button-stub" :disabled="disabled"><slot /></button>',
    },
    'el-card': {
      name: 'ElCard',
      template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
    },
    'el-select': {
      name: 'ElSelect',
      props: ['modelValue'],
      emits: ['update:modelValue', 'change'],
      template: '<div class="el-select-stub"><slot /></div>',
    },
    'el-option': {
      name: 'ElOption',
      props: ['label', 'value'],
      template: '<span class="el-option-stub">{{ label }}</span>',
    },
    'el-alert': {
      name: 'ElAlert',
      props: ['title'],
      template: '<div class="el-alert-stub">{{ title }}</div>',
    },
    'el-table': { name: 'ElTable', template: '<table class="el-table-stub"><slot /></table>' },
    'el-table-column': {
      name: 'ElTableColumn',
      template: '<div class="el-table-column-stub"><slot :row="row" /></div>',
      data: () => ({ row }),
    },
    'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
    'el-switch': {
      name: 'ElSwitch',
      props: ['modelValue'],
      emits: ['update:modelValue'],
      template:
        '<span class="el-switch-stub" @click="$emit(\'update:modelValue\', \'hidden\')" />',
    },
    'el-radio-group': {
      name: 'ElRadioGroup',
      props: ['modelValue'],
      emits: ['update:modelValue'],
      template:
        '<span class="el-radio-group-stub" @click="$emit(\'update:modelValue\', \'disabled\')"><slot /></span>',
    },
    'el-radio-button': {
      name: 'ElRadioButton',
      props: ['value'],
      template: '<span class="el-radio-button-stub"><slot /></span>',
    },
  }
}

async function mountComp(row: Record<string, any> = customRow) {
  const wrapper = mount(OrgModulePolicy, {
    global: { renderStubDefaultSlot: true, stubs: makeStubs(row) },
  })
  await flushPromises()
  return wrapper
}

function findBtn(wrapper: any, text: string) {
  const btn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGet.mockImplementation((url: string) => {
    if (url === '/organizations') {
      return Promise.resolve({ data: { items: [{ id: 7, name: '某县人武部' }] } })
    }
    return Promise.resolve({ data: [customRow] })
  })
  mockPut.mockResolvedValue({})
})

describe('OrgModulePolicy.vue 组织与策略加载', () => {
  it('组织加载成功：映射 id/name 并渲染选项；未选组织显示提示条', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    expect(mockGet).toHaveBeenCalledWith('/organizations', { page_size: 100 })
    expect(vm.orgs).toEqual([{ id: 7, name: '某县人武部' }])
    expect(wrapper.find('.el-option-stub').text()).toContain('某县人武部')
    // v-if="!selectedOrgId" 真侧
    expect(wrapper.find('.el-alert-stub').exists()).toBe(true)
    expect(wrapper.find('.el-table-stub').exists()).toBe(false)
  })

  it('组织加载：items 裸字段与缺 items → [] 兜底；失败静默不提示', async () => {
    mockGet.mockResolvedValueOnce({ items: [{ id: 1, name: 'A' }] })
    const wrapper = await mountComp()
    expect((wrapper.vm as any).orgs).toEqual([{ id: 1, name: 'A' }])

    mockGet.mockResolvedValueOnce({})
    await (wrapper.vm as any).loadOrgs()
    expect((wrapper.vm as any).orgs).toEqual([])

    mockGet.mockRejectedValueOnce(new Error('net'))
    await (wrapper.vm as any).loadOrgs()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('未选组织：loadPolicies/handleSave 提前返回', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    mockGet.mockClear()
    await vm.loadPolicies()
    await vm.handleSave()
    expect(mockGet).not.toHaveBeenCalledWith('/org-policies/null')
    expect(mockPut).not.toHaveBeenCalled()
    expect(vm.loading).toBe(false)
    expect(vm.saving).toBe(false)
  })

  it('选定组织后加载策略：data / 裸响应 / 空响应三态与列表渲染', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.selectedOrgId = 7
    await nextTick()
    expect(wrapper.find('.el-table-stub').exists()).toBe(true)
    expect(wrapper.find('.el-alert-stub').exists()).toBe(false)

    await vm.loadPolicies()
    expect(mockGet).toHaveBeenCalledWith('/org-policies/7')
    expect(vm.policies).toEqual([customRow])
    // 自定义 tag 真侧
    expect(wrapper.text()).toContain('自定义')

    mockGet.mockResolvedValueOnce([defaultRow])
    await vm.loadPolicies()
    expect(vm.policies).toEqual([defaultRow])

    mockGet.mockResolvedValueOnce('')
    await vm.loadPolicies()
    expect(vm.policies).toEqual([])
  })

  it('策略加载失败：服务端 detail / message / 兜底', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.selectedOrgId = 7

    mockGet.mockRejectedValueOnce({ response: { data: { detail: '策略不存在' } } })
    await vm.loadPolicies()
    expect(ElMessage.error).toHaveBeenCalledWith('策略不存在')

    mockGet.mockRejectedValueOnce(new Error('网络错误'))
    await vm.loadPolicies()
    expect(ElMessage.error).toHaveBeenCalledWith('网络错误')

    mockGet.mockRejectedValueOnce({})
    await vm.loadPolicies()
    expect(ElMessage.error).toHaveBeenCalledWith('加载策略失败')
    expect(vm.loading).toBe(false)
  })

  it('默认 tag 假侧（is_custom=false）', async () => {
    const wrapper = await mountComp(defaultRow)
    const vm = wrapper.vm as any
    vm.selectedOrgId = 7
    await nextTick()
    expect(wrapper.text()).toContain('默认')
  })
})

describe('OrgModulePolicy.vue 保存', () => {
  it('保存成功：提交 key/visibility/edit_mode 并回读；saving 归位', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.selectedOrgId = 7
    await vm.loadPolicies()
    mockPut.mockResolvedValueOnce({})
    mockGet.mockClear()
    await vm.handleSave()
    expect(mockPut).toHaveBeenCalledWith('/org-policies/7', {
      policies: [{ module_key: 'industry', visibility: 'visible', edit_mode: 'full_edit' }],
    })
    expect(ElMessage.success).toHaveBeenCalledWith('模块策略已保存')
    expect(mockGet).toHaveBeenCalledWith('/org-policies/7')
    expect(vm.saving).toBe(false)
  })

  it('保存失败：服务端原因与兜底文案', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.selectedOrgId = 7

    mockPut.mockRejectedValueOnce(new Error('保存被拒绝'))
    await vm.handleSave()
    expect(ElMessage.error).toHaveBeenCalledWith('保存被拒绝')

    mockPut.mockRejectedValueOnce({})
    await vm.handleSave()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
    expect(vm.saving).toBe(false)
  })

  it('保存按钮点击（模板内联箭头）与禁用态', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    // 未选组织：:disabled="!selectedOrgId" 真侧
    expect(findBtn(wrapper, '保存策略').attributes('disabled')).toBeDefined()
    vm.selectedOrgId = 7
    await nextTick()
    expect(findBtn(wrapper, '保存策略').attributes('disabled')).toBeUndefined()
    await findBtn(wrapper, '保存策略').trigger('click')
    await flushPromises()
    expect(mockPut).toHaveBeenCalled()
  })

  it('选择组织：v-model 与 @change 事件', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    const select = wrapper.findComponent({ name: 'ElSelect' })
    select.vm.$emit('update:modelValue', 7)
    await nextTick()
    expect(vm.selectedOrgId).toBe(7)
    select.vm.$emit('change', 7)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/org-policies/7')
  })

  it('行内控件：switch/radio-group v-model 更新策略行', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.selectedOrgId = 7
    await vm.loadPolicies()
    await nextTick()
    await wrapper.find('.el-switch-stub').trigger('click')
    expect(vm.policies[0].visibility).toBe('hidden')
    await wrapper.find('.el-radio-group-stub').trigger('click')
    expect(vm.policies[0].edit_mode).toBe('disabled')
  })

  it('字典函数：全映射与未知透传', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    expect(vm.categoryLabel('core')).toBe('核心')
    expect(vm.categoryLabel('business')).toBe('业务')
    expect(vm.categoryLabel('analysis')).toBe('分析')
    expect(vm.categoryLabel('data')).toBe('数据')
    expect(vm.categoryLabel('system')).toBe('系统')
    expect(vm.categoryLabel('other')).toBe('other')
  })
})
