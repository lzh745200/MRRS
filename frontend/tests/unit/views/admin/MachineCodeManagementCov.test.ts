/**
 * views/admin/MachineCodeManagement.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：isAdmin 三态（super_admin/admin/非管理员含 currentUser 缺失）、
 * fetchMachineCodeList 成功/无 data.data/异常 detail 与兜底、查询/重置、
 * 创建机器码（ref 为空早退、校验失败、成功、code!==200、response 为空、表单 ?? 兜底链）、
 * 撤销（confirm 通过/取消/失败、username 有无两侧）、状态映射字典与未知兜底、
 * 模板内联事件（录入/查询/重置/撤销/复制/取消/确定/我已复制）、
 * el-select/el-pagination/el-input v-model 与 change 事件、el-dialog close/v-model。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂提升求值，引用对象须先放入 vi.hoisted 初始化
const { userState, ElMessage, confirmMock, logError, apiMock, copyMock } = vi.hoisted(() => {
  return {
    userState: { currentUser: { role: 'admin' } as any },
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    confirmMock: vi.fn(),
    logError: vi.fn(),
    apiMock: {
      listMachineCodes: vi.fn(),
      createMachineCode: vi.fn(),
      revokeMachineCode: vi.fn(),
    },
    copyMock: vi.fn(),
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/stores/user', () => ({
  useUserStore: () => userState,
}))

vi.mock('@/api/machineCode', () => ({
  listMachineCodes: apiMock.listMachineCodes,
  createMachineCode: apiMock.createMachineCode,
  revokeMachineCode: apiMock.revokeMachineCode,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/utils', () => ({
  format: { formatDateTime: (d: any) => `FMT:${d}` },
}))

vi.mock('@/utils/clipboard', () => ({
  copyToClipboard: copyMock,
}))

import MachineCodeManagement from '@/views/admin/MachineCodeManagement.vue'

const recA = {
  id: 1,
  machine_code: 'A'.repeat(40),
  pass_code: '1234',
  status: 'pending',
  username: 'user1',
  description: '备注A',
  created_at: '2024-01-01',
}
const recB = {
  id: 2,
  machine_code: 'B'.repeat(40),
  pass_code: 'PASS-B',
  status: 'revoked',
  description: '备注B',
  created_at: '2024-02-02',
}

function mountComp() {
  // el-card/el-dialog/el-alert 需渲染具名插槽；el-table-column 注入两行样本
  // 覆盖 username v-if/v-else 与撤销按钮 v-if（pending）/v-else（revoked）两侧
  return mount(MachineCodeManagement, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        // 整合页内嵌 PassCodeManagement 子组件，测试中 stub 掉避免渲染其内部组件干扰计数
        PassCodeManagement: {
          name: 'PassCodeManagement',
          template: '<div class="pass-code-stub" />',
        },
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue', 'close'],
        },
        'el-alert': {
          name: 'ElAlert',
          template: '<div class="el-alert-stub"><slot name="title" /><slot /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return { rowA: { ...recA }, rowB: { ...recB } }
          },
        },
      },
    },
  })
}

const findBtn = (wrapper: any, text: string) => {
  const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes(text))
  expect(btn, text).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  userState.currentUser = { role: 'admin' }
  apiMock.listMachineCodes.mockResolvedValue({ data: { items: [recA, recB], total: 2 } })
  apiMock.createMachineCode.mockResolvedValue({ code: 200, pass_code: 'PC-9999', id: 3 })
  apiMock.revokeMachineCode.mockResolvedValue({})
  confirmMock.mockResolvedValue('confirm')
  copyMock.mockResolvedValue(true)
})

describe('权限与挂载', () => {
  it('super_admin / admin 均可访问；非管理员与 currentUser 缺失渲染 el-empty', async () => {
    userState.currentUser = { role: 'super_admin' }
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).isAdmin).toBe(true)
    expect(wrapper.find('.machine-code-management').exists()).toBe(true)
    wrapper.unmount()

    userState.currentUser = { role: 'admin' }
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).isAdmin).toBe(true)
    wrapper.unmount()

    userState.currentUser = { role: 'user' }
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).isAdmin).toBe(false)
    expect(wrapper.find('.machine-code-management').exists()).toBe(false)
    wrapper.unmount()

    userState.currentUser = null
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).isAdmin).toBe(false)
  })

  it('onMounted 拉取列表：成功填充 items/total，loading 复位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(apiMock.listMachineCodes).toHaveBeenCalledWith({
      status_filter: undefined,
      skip: 0,
      limit: 20,
    })
    expect(vm.machineCodeList).toHaveLength(2)
    expect(vm.pagination.total).toBe(2)
    expect(vm.loading).toBe(false)
  })

  it('响应无 data.data → 不更新列表', async () => {
    apiMock.listMachineCodes.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).machineCodeList).toEqual([])
  })

  it('拉取失败：detail 与兜底文案，记录日志', async () => {
    apiMock.listMachineCodes.mockRejectedValue({ response: { data: { detail: '权限不足' } } })
    let wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('权限不足')
    expect(logError).toHaveBeenCalled()
    expect((wrapper.vm as any).loading).toBe(false)
    wrapper.unmount()

    apiMock.listMachineCodes.mockRejectedValue(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('获取机器码列表失败')
  })
})

describe('查询与重置', () => {
  it('handleQuery：重置到第 1 页并按状态过滤', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pagination.page = 5
    vm.queryForm.status = 'active'
    apiMock.listMachineCodes.mockClear()
    vm.handleQuery()
    expect(vm.pagination.page).toBe(1)
    await flushPromises()
    expect(apiMock.listMachineCodes).toHaveBeenCalledWith({
      status_filter: 'active',
      skip: 0,
      limit: 20,
    })
  })

  it('handleReset：清空状态并重新查询', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.queryForm.status = 'pending'
    apiMock.listMachineCodes.mockClear()
    vm.handleReset()
    expect(vm.queryForm.status).toBe('')
    await flushPromises()
    expect(apiMock.listMachineCodes).toHaveBeenCalledWith({
      status_filter: undefined,
      skip: 0,
      limit: 20,
    })
  })
})

describe('创建机器码', () => {
  it('createFormRef 为空 → 早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createFormRef = undefined
    await vm.handleCreate()
    expect(apiMock.createMachineCode).not.toHaveBeenCalled()
  })

  it('校验失败 → detail 与兜底错误文案，submitting 复位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createFormRef = {
      validate: vi.fn().mockRejectedValue({ response: { data: { detail: '机器码已存在' } } }),
    }
    await vm.handleCreate()
    expect(ElMessage.error).toHaveBeenCalledWith('机器码已存在')
    expect(logError).toHaveBeenCalled()
    expect(vm.submitting).toBe(false)

    // 重渲染会把模板 ref 重同步为 stub，需重新赋 mock
    vm.createFormRef = { validate: vi.fn().mockRejectedValue(new Error('bad')) }
    await vm.handleCreate()
    expect(ElMessage.error).toHaveBeenCalledWith('录入机器码失败')
    expect(vm.submitting).toBe(false)
  })

  it('成功：表单 trim 与 || undefined 兜底，显示通行码并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createForm.machine_code = '  ' + 'C'.repeat(32) + '  '
    vm.createForm.description = ''
    vm.createForm.pass_code = ''
    vm.createDialogVisible = true
    apiMock.listMachineCodes.mockClear()
    vm.createFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleCreate()
    expect(apiMock.createMachineCode).toHaveBeenCalledWith({
      machine_code: 'C'.repeat(32),
      description: undefined,
      pass_code: undefined,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('机器码录入成功')
    expect(vm.generatedPassCode).toBe('PC-9999')
    expect(vm.passCodeDialogVisible).toBe(true)
    expect(vm.createDialogVisible).toBe(false)
    expect(vm.pagination.page).toBe(1)
    await flushPromises()
    expect(apiMock.listMachineCodes).toHaveBeenCalled()
    expect(vm.submitting).toBe(false)
  })

  it('成功：description/pass_code 有值时透传', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createForm.machine_code = 'D'.repeat(32)
    vm.createForm.description = '  测试备注  '
    vm.createForm.pass_code = '8888'
    vm.createFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleCreate()
    expect(apiMock.createMachineCode).toHaveBeenCalledWith({
      machine_code: 'D'.repeat(32),
      description: '测试备注',
      pass_code: '8888',
    })
  })

  it('code!==200 → 不提示成功；response 为空 → 可选链兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    apiMock.createMachineCode.mockResolvedValue({ code: 500 })
    vm.createFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleCreate()
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(vm.submitting).toBe(false)

    apiMock.createMachineCode.mockResolvedValue(undefined)
    vm.createFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleCreate()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })
})

describe('撤销机器码', () => {
  it('confirm 通过 → 撤销并刷新；username 有无两种提示文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    apiMock.listMachineCodes.mockClear()
    await vm.handleRevoke(recA as any)
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('用户 user1 将无法登录。'),
      '撤销确认',
      expect.any(Object)
    )
    expect(apiMock.revokeMachineCode).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('机器码已撤销')
    expect(vm.pagination.page).toBe(1)
    await flushPromises()
    expect(apiMock.listMachineCodes).toHaveBeenCalled()

    await vm.handleRevoke({ ...recA, username: undefined } as any)
    expect(confirmMock).toHaveBeenLastCalledWith(
      expect.not.stringContaining('将无法登录'),
      '撤销确认',
      expect.any(Object)
    )
  })

  it('confirm 取消（reject cancel）→ 静默不发请求', async () => {
    confirmMock.mockRejectedValue('cancel')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleRevoke(recA as any)
    expect(apiMock.revokeMachineCode).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('revoke 失败 → detail 与兜底文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    apiMock.revokeMachineCode.mockRejectedValue({ response: { data: { detail: '已绑定用户' } } })
    await vm.handleRevoke(recA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('已绑定用户')
    expect(logError).toHaveBeenCalled()

    apiMock.revokeMachineCode.mockRejectedValue(new Error('net'))
    await vm.handleRevoke(recA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('撤销机器码失败')
  })
})

describe('状态映射', () => {
  it('getStatusType / getStatusText 全映射与未知兜底', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.getStatusType('pending')).toBe('warning')
    expect(vm.getStatusType('active')).toBe('success')
    expect(vm.getStatusType('revoked')).toBe('info')
    expect(vm.getStatusType('other')).toBe('info')
    expect(vm.getStatusText('pending')).toBe('待使用')
    expect(vm.getStatusText('active')).toBe('已激活')
    expect(vm.getStatusText('revoked')).toBe('已撤销')
    expect(vm.getStatusText('other')).toBe('other')
  })
})

describe('resetCreateForm 与对话框 close', () => {
  it('ref 有 resetFields → 调用并清空表单；ref 为空 → 可选链安全', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createForm.machine_code = 'X'
    vm.createForm.description = 'Y'
    vm.createForm.pass_code = '1234'
    const resetFields = vi.fn()
    vm.createFormRef = { resetFields }
    vm.resetCreateForm()
    expect(resetFields).toHaveBeenCalled()
    expect(vm.createForm).toMatchObject({ machine_code: '', description: '', pass_code: '' })

    vm.createFormRef = undefined
    vm.resetCreateForm() // 不抛错
  })

  it('创建对话框 @close 触发 resetCreateForm', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createForm.machine_code = 'Z'
    const resetFields = vi.fn()
    vm.createFormRef = { resetFields }
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    dialogs[0].vm.$emit('close')
    expect(resetFields).toHaveBeenCalled()
    expect(vm.createForm.machine_code).toBe('')
  })
})

describe('模板交互（内联处理器与 v-model 覆盖）', () => {
  it('点击「录入机器码」打开对话框并清空 pass_code', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createForm.pass_code = '9999'
    await findBtn(wrapper, '录入机器码').trigger('click')
    expect(vm.createDialogVisible).toBe(true)
    expect(vm.createForm.pass_code).toBe('')
  })

  it('点击「查询」「重置」按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.queryForm.status = 'pending'
    apiMock.listMachineCodes.mockClear()
    await findBtn(wrapper, '查询').trigger('click')
    await flushPromises()
    expect(apiMock.listMachineCodes).toHaveBeenCalledWith(
      expect.objectContaining({ status_filter: 'pending' })
    )
    await findBtn(wrapper, '重置').trigger('click')
    expect(vm.queryForm.status).toBe('')
    await flushPromises()
    expect(apiMock.listMachineCodes).toHaveBeenCalledWith(
      expect.objectContaining({ status_filter: undefined })
    )
  })

  it('el-select：update:modelValue 与 change 均触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects.length).toBeGreaterThan(0)
    apiMock.listMachineCodes.mockClear()
    selects[0].vm.$emit('update:modelValue', 'revoked')
    expect(vm.queryForm.status).toBe('revoked')
    selects[0].vm.$emit('change', 'revoked')
    await flushPromises()
    expect(apiMock.listMachineCodes).toHaveBeenCalled()
  })

  it('el-pagination：size-change/current-change 与两个 v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const pager = wrapper.findAllComponents({ name: 'ElPagination' })
    expect(pager.length).toBeGreaterThan(0)
    apiMock.listMachineCodes.mockClear()
    pager[0].vm.$emit('size-change', 50)
    pager[0].vm.$emit('current-change', 3)
    await flushPromises()
    expect(apiMock.listMachineCodes).toHaveBeenCalled()
    pager[0].vm.$emit('update:current-page', 4)
    pager[0].vm.$emit('update:page-size', 100)
    expect(vm.pagination.page).toBe(4)
    expect(vm.pagination.pageSize).toBe(100)
  })

  it('表格样本行：点击「撤销」与复制按钮；revoked 行无撤销按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    // 撤销：仅 pending 行渲染
    const revokeBtns = wrapper
      .findAll('el-button-stub')
      .filter((b) => b.text().includes('撤销'))
    expect(revokeBtns.length).toBe(1)
    await revokeBtns[0].trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
    expect(apiMock.revokeMachineCode).toHaveBeenCalledWith(1)

    // 复制按钮（无文本，图标按钮）：按列渲染——机器码列两行，再通行码列两行
    const iconBtns = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '')
    expect(iconBtns.length).toBe(4)
    await iconBtns[0].trigger('click')
    expect(copyMock).toHaveBeenCalledWith('A'.repeat(40))
    await iconBtns[1].trigger('click')
    expect(copyMock).toHaveBeenCalledWith('B'.repeat(40))
    await iconBtns[2].trigger('click')
    expect(copyMock).toHaveBeenCalledWith('1234')
    await iconBtns[3].trigger('click')
    expect(copyMock).toHaveBeenCalledWith('PASS-B')
    // revoked 行显示占位符
    expect(wrapper.text()).toContain('未绑定')
  })

  it('创建对话框：el-input v-model 三项、取消与确定按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createDialogVisible = true
    await nextTick()

    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    expect(inputs.length).toBe(3)
    inputs[0].vm.$emit('update:modelValue', 'M'.repeat(32))
    inputs[1].vm.$emit('update:modelValue', '4321')
    inputs[2].vm.$emit('update:modelValue', '备注内容')
    expect(vm.createForm).toMatchObject({
      machine_code: 'M'.repeat(32),
      pass_code: '4321',
      description: '备注内容',
    })

    vm.createFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await findBtn(wrapper, '确定').trigger('click')
    await flushPromises()
    expect(apiMock.createMachineCode).toHaveBeenCalledWith({
      machine_code: 'M'.repeat(32),
      description: '备注内容',
      pass_code: '4321',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('机器码录入成功')

    vm.createDialogVisible = true
    await nextTick()
    await findBtn(wrapper, '取消').trigger('click')
    expect(vm.createDialogVisible).toBe(false)
  })

  it('通行码对话框：复制通行码与我已复制按钮、两个对话框 v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.generatedPassCode = 'PC-ABCD'
    vm.passCodeDialogVisible = true
    await nextTick()

    await findBtn(wrapper, '复制通行码').trigger('click')
    expect(copyMock).toHaveBeenCalledWith('PC-ABCD', '通行码')

    await findBtn(wrapper, '我已复制').trigger('click')
    expect(vm.passCodeDialogVisible).toBe(false)

    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    expect(dialogs.length).toBe(2)
    dialogs[0].vm.$emit('update:modelValue', true)
    expect(vm.createDialogVisible).toBe(true)
    dialogs[1].vm.$emit('update:modelValue', true)
    expect(vm.passCodeDialogVisible).toBe(true)
  })
})

describe('模板控件补充', () => {
  it('筛选 select v-model 触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    if (selects.length) {
      selects[0].vm.$emit('update:modelValue', 'pending')
    }
    wrapper.unmount()
  })
})
