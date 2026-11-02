/**
 * views/system/OrgGrant.vue 测试（四指标 100%）
 *
 * 覆盖：组织树加载/过滤/选中、四态矩阵（继承/可操作/只读/不开放）、
 * 显式 none 提交、有效值与来源展示、单包导出与子树批量导出、
 * 错误文案三级回退、手工 ID 兜底。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const {
  mockGet,
  mockSet,
  mockExport,
  mockExportBranch,
  mockTree,
  ElMessage,
  flatEntries,
} = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockSet: vi.fn(),
  mockExport: vi.fn(),
  mockExportBranch: vi.fn(),
  mockTree: vi.fn(),
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
  exportGrantBranch: mockExportBranch,
  getOrgGrantTree: mockTree,
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
  'el-option': {
    props: ['label', 'value'],
    template: '<option :value="value">{{ label }}</option>',
  },
  'el-tree': {
    props: ['data', 'nodeKey', 'props', 'defaultExpandedKeys', 'highlightCurrent'],
    emits: ['node-click'],
    template: '<div class="tree"><slot /></div>',
  },
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
  active: true,
  effective: { projects: 'view', legacy: 'edit', dashboard: 'edit' },
  sources: { dashboard: 'S01', projects: 'C001' },
}

const TREE = {
  root_id: 1,
  node: {
    id: 1,
    name: '省中心',
    code: 'S01',
    grant_version: 1,
    grant_source: 'local',
    signed: false,
    inherit_from_parent: true,
    grants: { dashboard: 'edit' },
    children: [
      {
        id: 7,
        name: '市分中心',
        code: 'C001',
        grant_version: 3,
        grant_source: 'import',
        signed: true,
        inherit_from_parent: true,
        grants: {},
        children: [],
      },
    ],
  },
}

describe('views/system/OrgGrant', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockTree.mockResolvedValue(TREE)
    mockGet.mockResolvedValue(MATRIX)
  })

  it('初始态：只有说明，无矩阵与错误', () => {
    const wrapper = factory()
    expect(wrapper.text()).toContain('单位授权配置')
    expect(wrapper.find('.descriptions').exists()).toBe(false)
    expect(wrapper.find('.matrix').exists()).toBe(false)
  })

  it('挂载即加载组织树，并展开根节点', async () => {
    const wrapper = factory()
    await flushPromises()
    expect(mockTree).toHaveBeenCalled()
    expect(wrapper.vm.treeLoadFailed).toBe(false)
    expect(wrapper.vm.treeData[0].label).toBe('省中心（S01）')
    expect(wrapper.vm.treeData[0].children[0].label).toBe('市分中心（C001）')
  })

  it('组织树加载失败：提示可改用手工 ID，手工输入仍可用', async () => {
    mockTree.mockRejectedValue(new Error('boom'))
    const wrapper = factory()
    await flushPromises()
    expect(wrapper.vm.treeLoadFailed).toBe(true)
    expect(wrapper.text()).toContain('未能加载组织树')

    wrapper.vm.toggleManual()
    await wrapper.vm.$nextTick()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    expect(mockGet).toHaveBeenCalledWith(7)
  })

  it('组织树返回空节点：按加载失败处理', async () => {
    mockTree.mockResolvedValue({ root_id: 0, node: null })
    const wrapper = factory()
    await flushPromises()
    expect(wrapper.vm.treeData).toEqual([])
    expect(wrapper.vm.treeLoadFailed).toBe(true)
  })

  it('选中树节点：写入 ID、清空旧矩阵并立即加载', async () => {
    const wrapper = factory()
    await flushPromises()
    wrapper.vm.onTreeSelect({ id: 7 })
    await flushPromises()
    expect(wrapper.vm.orgIdText).toBe('7')
    expect(mockGet).toHaveBeenCalledWith(7)
  })

  it('按名称/编码过滤组织树：命中子节点保留父节点，无命中为空', async () => {
    const wrapper = factory()
    await flushPromises()
    wrapper.vm.onSearch('C001')
    expect(wrapper.vm.visibleTree[0].children).toHaveLength(1)
    wrapper.vm.onSearch('不存在')
    expect(wrapper.vm.visibleTree).toEqual([])
    wrapper.vm.onSearch('')
    expect(wrapper.vm.visibleTree).toHaveLength(1)
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
    expect(wrapper.vm.orgIdText).toBe('')
  })

  it('加载成功：渲染元信息、四态矩阵与有效值来源', async () => {
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    await wrapper.vm.$nextTick()

    expect(mockGet).toHaveBeenCalledWith(7)
    const text = wrapper.text()
    expect(text).toContain('C001')
    expect(text).toContain('已签名')
    // 3 行 × 4 级别选项
    expect(wrapper.findAll('option')).toHaveLength(12)
    expect(text).toContain('继承：可操作（来自 S01）')
  })

  it('加载成功（未签名 + 无编码/来源）：走 info 标签与缺省文案', async () => {
    mockGet.mockResolvedValue({
      ...MATRIX,
      signed: false,
      org_code: null,
      grant_source: null,
      effective: {},
      sources: {},
    })
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('未签名')
    expect(wrapper.text()).toContain('（未填写）')
    expect(wrapper.text()).toContain('未授权')
    expect(wrapper.text()).toContain('继承：不开放')
  })

  it('加载失败：清空矩阵并展示后端 detail', async () => {
    mockGet.mockRejectedValue({ response: { data: { detail: '单位不存在' } } })
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    expect(wrapper.text()).toContain('单位不存在')
    expect(wrapper.find('.matrix').exists()).toBe(false)
  })

  it('加载失败：无 detail 时取 Error.message，再回退兜底文案', async () => {
    mockGet.mockRejectedValue(new Error('Network Error'))
    const wrapperA = factory()
    wrapperA.vm.onOrgIdInput('7')
    await wrapperA.vm.load()
    expect(wrapperA.text()).toContain('Network Error')

    mockGet.mockRejectedValue({})
    const wrapperB = factory()
    wrapperB.vm.onOrgIdInput('7')
    await wrapperB.vm.load()
    expect(wrapperB.text()).toContain('操作失败')
  })

  it('buildRows：菜单 ∪ 授权并去重，显式值覆盖为对应状态', () => {
    const wrapper = factory()
    const rows = wrapper.vm.buildRows({
      grants: { dashboard: 'none', projects: 'view' },
      effective: { dashboard: 'edit', projects: 'view' },
      sources: { dashboard: 'S01' },
    })
    expect(rows).toHaveLength(2)
    expect(rows[0]).toMatchObject({ key: 'dashboard', state: 'none', effectiveLabel: '' })
    expect(rows[1]).toMatchObject({ key: 'projects', state: 'view' })
  })

  it('buildRows：菜单内重复 key 只保留一条，未显式配置为继承', () => {
    flatEntries.push({ key: 'dashboard', label: '工作台副本' })
    try {
      const wrapper = factory()
      const rows = wrapper.vm.buildRows({ grants: {}, effective: {}, sources: {} })
      expect(rows).toHaveLength(2)
      expect(rows[0]).toMatchObject({ key: 'dashboard', state: 'inherit', effectiveLabel: '继承：不开放' })
    } finally {
      flatEntries.pop()
    }
  })

  it('levelLabel：三种级别与未知值兜底', () => {
    const wrapper = factory()
    expect(wrapper.vm.levelLabel('edit')).toBe('可操作')
    expect(wrapper.vm.levelLabel('view')).toBe('只读')
    expect(wrapper.vm.levelLabel('none')).toBe('不开放')
    expect(wrapper.vm.levelLabel('weird')).toBe('不开放')
  })

  it('保存：提交显式覆盖（含显式 none），回填版本并重新加载有效值', async () => {
    mockSet.mockResolvedValue({ organization_id: 7, grant_version: 4, modules: 3 })
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.load()
    await wrapper.vm.$nextTick()

    // 第一行 dashboard 设为「不开放」——必须显式提交，才能压住继承
    wrapper.vm.rows[0].state = 'none'
    wrapper.vm.rows[1].state = 'edit'
    await wrapper.vm.save()

    expect(mockSet).toHaveBeenCalledWith(7, {
      dashboard: 'none',
      projects: 'edit',
      legacy: 'edit',
    })
    expect(ElMessage.success).toHaveBeenCalled()
    // 保存后重新拉取，服务端版本已回填
    expect(mockGet).toHaveBeenCalledTimes(2)
  })

  it('保存：meta 为空时不重新加载（旁路）', async () => {
    mockSet.mockResolvedValue({ organization_id: 7, grant_version: 9, modules: 0 })
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.save()
    expect(mockSet).toHaveBeenCalledWith(7, {})
    expect(wrapper.find('.descriptions').exists()).toBe(false)
  })

  it('保存失败：展示错误且不提示成功', async () => {
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

  it('导出单包：成功提示文件名，失败展示错误，未填 ID 不请求', async () => {
    mockExport.mockResolvedValue('grant-C001-v4.json')
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.exportPkg()
    expect(mockExport).toHaveBeenCalledWith(7)
    expect(ElMessage.success).toHaveBeenCalledWith('已导出 grant-C001-v4.json')

    mockExport.mockRejectedValue(new Error('download failed'))
    await wrapper.vm.exportPkg()
    expect(wrapper.text()).toContain('download failed')

    const blank = factory()
    await blank.vm.exportPkg()
    expect(mockExport).toHaveBeenCalledTimes(2)
    expect(blank.text()).toContain('请先填写有效的单位 ID')
  })

  it('导出子树：成功提示 zip 文件名，失败展示错误，未填 ID 不请求', async () => {
    mockExportBranch.mockResolvedValue('grants-S01.zip')
    const wrapper = factory()
    wrapper.vm.onOrgIdInput('7')
    await wrapper.vm.exportBranch()
    expect(mockExportBranch).toHaveBeenCalledWith(7)
    expect(ElMessage.success).toHaveBeenCalledWith('已导出发子树授权包 grants-S01.zip')

    mockExportBranch.mockRejectedValue(new Error('zip failed'))
    await wrapper.vm.exportBranch()
    expect(wrapper.text()).toContain('zip failed')

    const blank = factory()
    await blank.vm.exportBranch()
    expect(mockExportBranch).toHaveBeenCalledTimes(2)
    expect(blank.text()).toContain('请先填写有效的单位 ID')
  })

  it('切换手工模式：非法值清空、合法值保留，可切回组织树', async () => {
    const wrapper = factory()
    await flushPromises()
    expect(wrapper.vm.manualMode).toBe(false)

    wrapper.vm.onOrgIdInput('abc')
    wrapper.vm.toggleManual()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('input.org-input').exists()).toBe(true)
    expect(wrapper.vm.orgIdText).toBe('')

    wrapper.vm.onOrgIdInput('7')
    wrapper.vm.toggleManual()
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.manualMode).toBe(false)
    expect(wrapper.vm.orgIdText).toBe('7')
  })
})
