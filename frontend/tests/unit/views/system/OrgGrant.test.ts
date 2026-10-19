/**
 * views/system/OrgGrant.vue 测试（四指标 100%）
 *
 * 方案：mock 'element-plus'（只留 ElMessage）+ mock '@/api/orgGrants' +
 * mock '@/stores/menu'；el-* 组件 stub 成带插槽的真实标签（未解析的组件会丢弃插槽）。
 *
 * 覆盖：单位 ID 校验、加载成败、矩阵行构建（菜单与授权并集 + 去重）、
 * 保存（只提交非 none + 版本回填 + meta 为空的旁路）、导出成败、
 * 错误文案三级回退、签名标签两分支、单位编码缺省分支。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

const { mockGet, mockSet, mockExport, ElMessage, flatEntries } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockSet: vi.fn(),
  mockExport: vi.fn(),
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  flatEntries: [
    { key: 'dashboard', label: '工作台' },
    { key: 'projects', label: '项目管理' },
  ],
}))

vi.mock('element-plus', () => ({ ElMessage }))
vi.mock('@/api/orgGrants', () => ({
  getOrgGrants: mockGet,
  setOrgGrants: mockSet,
  exportGrantPackage: mockExport,
}))
vi.mock('@/stores/menu', () => ({
  useMenuStore: () => ({ flatEntries }),
}))

import OrgGrant from '@/views/system/OrgGrant.vue'

const STUBS = {
  'el-card': { template: '<div><slot name="header" /><slot /></div>' },
  'el-input': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
  'el-alert': { props: ['title'], template: '<div class="alert">{{ title }}</div>' },
  'el-descriptions': { template: '<div class="descriptions"><slot /></div>' },
  'el-descriptions-item': {
    props: ['label'],
    template: '<div class="desc-item">{{ label }}:<slot /></div>',
  },
  'el-tag': { template: '<span class="tag"><slot /></span>' },
  'el-select': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
  },
  'el-option': { props: ['label', 'value'], template: '<option :value="value">{{ label }}</option>' },
}

function factory() {
  return mount(OrgGrant, { global: { stubs: STUBS } })
}

const MATRIX = {
  organization_id: 7,
  org_code: 'C001',
  grant_version: 3,
  grant_source: 'import',
  grant_applied_at: null,
  signed: true,
  grants: { projects: 'view', legacy: 'edit' },
}

describe('views/system/OrgGrant', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('初始态：只有说明，无矩阵与错误', () => {
    const wrapper = factory()
    expect(wrapper.text()).toContain('单位授权配置')
    expect(wrapper.find('.descriptions').exists()).toBe(false)
    expect(wrapper.find('.matrix').exists()).toBe(false)
  })

  it('未填单位 ID 就加载：提示且不请求', async () => {
    const wrapper = factory()
    await wrapper.vm.load()
    expect(mockGet).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请先填写有效的单位 ID')
  })

  it('非法单位 ID（非正整数）按未填处理', async () => {
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('abc')
    await wrapper.vm.load()
    expect(mockGet).not.toHaveBeenCalled()
  })

  it('onOrgIdInput 容忍 null', () => {
    const wrapper = factory()
    wrapper.vm.onOrgIdInput(null)
    expect(wrapper.vm.buildRows({})).toEqual([
      { key: 'dashboard', label: '工作台', level: 'none' },
      { key: 'projects', label: '项目管理', level: 'none' },
    ])
  })

  it('加载成功：渲染元信息、签名标签与矩阵行（菜单 ∪ 授权）', async () => {
    mockGet.mockResolvedValue(MATRIX)
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    await wrapper.vm.$nextTick()

    expect(mockGet).toHaveBeenCalledWith(7)
    const text = wrapper.text()
    expect(text).toContain('C001')
    expect(text).toContain('已签名')
    expect(wrapper.findAll('select')).toHaveLength(3) // dashboard / projects / legacy
    expect(wrapper.findAll('option')).toHaveLength(9)
  })

  it('加载成功（未签名 + 无单位编码）：走 info 标签与缺省文案', async () => {
    mockGet.mockResolvedValue({ ...MATRIX, signed: false, org_code: null, grant_source: null })
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('未签名')
    expect(wrapper.text()).toContain('（未填写）')
    expect(wrapper.text()).toContain('未授权')
  })

  it('加载失败：清空矩阵并展示后端 detail', async () => {
    mockGet.mockRejectedValue({ response: { data: { detail: '单位不存在' } } })
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('单位不存在')
    expect(wrapper.find('.matrix').exists()).toBe(false)
  })

  it('加载失败：无 detail 时取 Error.message', async () => {
    mockGet.mockRejectedValue(new Error('Network Error'))
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    expect(wrapper.text()).toContain('Network Error')
  })

  it('加载失败：都取不到时用兜底文案', async () => {
    mockGet.mockRejectedValue({})
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    expect(wrapper.text()).toContain('操作失败')
  })

  it('buildRows 去重：菜单内重复 key 只保留一条', () => {
    const wrapper = factory()
    // 临时往 mock 的菜单里塞一个重复 key，覆盖去重分支
    flatEntries.push({ key: 'dashboard', label: '工作台副本' })
    try {
      const rows = wrapper.vm.buildRows({ dashboard: 'view' })
      expect(rows).toHaveLength(2)
      expect(rows[0]).toEqual({ key: 'dashboard', label: '工作台', level: 'view' })
    } finally {
      flatEntries.pop()
    }
  })

  it('加载成功但 grants 缺失：按空矩阵渲染（全部不开放）', async () => {
    mockGet.mockResolvedValue({ ...MATRIX, grants: undefined })
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('select')).toHaveLength(2)
  })

  it('保存：只提交非 none 的模块，并回填版本号', async () => {
    mockGet.mockResolvedValue(MATRIX)
    mockSet.mockResolvedValue({ organization_id: 7, grant_version: 4, modules: 2 })
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    await wrapper.vm.$nextTick()

    // 把 dashboard 从 none 改为 edit
    await wrapper.findAll('select')[0].setValue('edit')
    await wrapper.vm.save()

    expect(mockSet).toHaveBeenCalledWith(7, { legacy: 'edit', projects: 'view', dashboard: 'edit' })
    expect(ElMessage.success).toHaveBeenCalled()
    expect(wrapper.text()).toContain('4') // 版本号回填
  })

  it('保存：meta 为空时不回填版本号（旁路）', async () => {
    mockSet.mockResolvedValue({ organization_id: 7, grant_version: 9, modules: 0 })
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.save()
    expect(mockSet).toHaveBeenCalledWith(7, {})
    expect(wrapper.find('.descriptions').exists()).toBe(false)
  })

  it('保存失败：展示错误且不提示成功', async () => {
    mockGet.mockResolvedValue(MATRIX)
    mockSet.mockRejectedValue({ response: { data: { detail: '无权限' } } })
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    await wrapper.vm.save()
    expect(wrapper.text()).toContain('无权限')
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('保存未填 ID：提示且不请求', async () => {
    const wrapper = factory()
    await wrapper.vm.save()
    expect(mockSet).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请先填写有效的单位 ID')
  })

  it('导出成功：提示文件名', async () => {
    mockExport.mockResolvedValue('grant-C001-v4.json')
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.exportPkg()
    expect(mockExport).toHaveBeenCalledWith(7)
    expect(ElMessage.success).toHaveBeenCalledWith('已导出 grant-C001-v4.json')
  })

  it('导出失败：展示错误', async () => {
    mockExport.mockRejectedValue(new Error('download failed'))
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.exportPkg()
    expect(wrapper.text()).toContain('download failed')
  })

  it('导出未填 ID：提示且不请求', async () => {
    const wrapper = factory()
    await wrapper.vm.exportPkg()
    expect(mockExport).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请先填写有效的单位 ID')
  })
})
