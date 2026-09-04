/**
 * views/funds/TransferVoucher.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 列表加载、状态筛选、分页、新建凭证（校验/成功/失败）、
 * 确认（取消/成功/失败）、删除（取消/成功/失败）、模板分支与 v-model。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, confirmMock, lifecycleApi, pushSafeMock, routeBox, formValidateMock, logError } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  formValidateMock: vi.fn(() => Promise.resolve(true)),
  logError: vi.fn(),
  lifecycleApi: {
    listTransferVouchers: vi.fn(),
    createTransferVoucher: vi.fn(),
    confirmTransferVoucher: vi.fn(),
    deleteTransferVoucher: vi.fn(),
    uploadVoucherAttachment: vi.fn(),
  },
  pushSafeMock: vi.fn(),
  routeBox: { query: {} as Record<string, any> },
}))

vi.mock('vue-router', () => ({ useRoute: () => routeBox }))

vi.mock('element-plus', () => ({ ElMessage, ElMessageBox: { confirm: confirmMock } }))

vi.mock('@/api/fundLifecycle', () => ({ fundLifecycleApi: lifecycleApi }))

// handleVoucherUpload 的 catch 分支使用 logger.error，隔离真实 logger 的 console 副作用
vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
  safeRouteParam: (v: any) => Number(v) || v,
}))

import TransferVoucher from '@/views/funds/TransferVoucher.vue'

const voucherDraft = {
  id: 1,
  voucher_no: 'VZ-001',
  direction_label: '专项→地方',
  amount: 50,
  payer_account: 'PA',
  payee_account: 'PB',
  transfer_date: '2024-01-01',
  status: 'draft',
  status_label: '草稿',
}

const voucherSubmitted = {
  id: 2,
  voucher_no: 'VZ-002',
  status: 'submitted',
  status_label: '已提交',
}

const voucherConfirmed = {
  id: 3,
  voucher_no: 'VZ-003',
  status: 'confirmed',
  status_label: '已确认',
}

const voucherRejected = {
  id: 4,
  voucher_no: 'VZ-004',
  status: 'rejected',
  status_label: '已拒绝',
}

function mountComp() {
  return mount(TransferVoucher, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-page-header': {
          name: 'ElPageHeader',
          template: '<div class="el-page-header-stub"><slot name="content" /><slot /></div>',
          emits: ['back'],
        },
        'el-card': { template: '<div class="el-card-stub"><slot /></div>' },
        'el-table': {
          template:
            '<div class="el-table-stub"><slot name="empty" /><slot name="default" /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /></div>',
          data() {
            return {
              rowA: { ...voucherDraft },
              rowB: { ...voucherSubmitted },
              rowC: { ...voucherConfirmed },
              rowD: { ...voucherRejected },
            }
          },
        },
        'el-form': {
          name: 'ElForm',
          template: '<div class="el-form-stub"><slot /></div>',
          methods: { validate: formValidateMock },
        },
        'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
        'el-input': {
          template:
            '<div class="el-input-stub" @click="$emit(\'update:modelValue\', \'V\')" />',
        },
        'el-input-number': {
          template:
            '<div class="el-input-number-stub" @click="$emit(\'update:modelValue\', 5)" />',
        },
        'el-select': {
          template:
            '<div class="el-select-stub" @click="$emit(\'update:modelValue\', \'draft\'); $emit(\'change\', \'draft\')"><slot /></div>',
        },
        'el-option': { template: '<div class="el-option-stub" />' },
        'el-radio-group': {
          template:
            '<div class="el-radio-group-stub" @click="$emit(\'update:modelValue\', \'local_to_military\')"><slot /></div>',
        },
        'el-radio': { template: '<div class="el-radio-stub" />' },
        'el-date-picker': {
          template:
            '<div class="el-date-picker-stub" @click="$emit(\'update:modelValue\', \'2024-01-01\')" />',
        },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-pagination': {
          template:
            '<div class="el-pagination-stub" @click="$emit(\'current-change\'); $emit(\'update:currentPage\', 2)" />',
        },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        // 全局 el-upload: true 的默认 stub 不会回调 http-request，导致模板内的
        // (opt) => handleVoucherUpload(row.id, opt.file) 箭头函数永不执行；
        // 此处提供可主动触发 httpRequest 的 stub。
        'el-upload': {
          name: 'ElUpload',
          props: ['httpRequest', 'showFileList', 'accept'],
          template:
            '<div class="el-upload-stub">' +
            '<button type="button" class="fire-upload" @click="httpRequest({ file: fakeFile })">up</button>' +
            '<slot /></div>',
          data() {
            return { fakeFile: new File(['pdf-bytes'], 'voucher.pdf', { type: 'application/pdf' }) }
          },
        },
        'el-dialog': {
          template:
            '<div class="el-dialog-stub" @click="$emit(\'update:modelValue\', false)"><slot /><slot name="footer" /></div>',
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  formValidateMock.mockResolvedValue(true)
  routeBox.query = {}
  lifecycleApi.listTransferVouchers.mockResolvedValue({
    items: [voucherDraft, voucherSubmitted, voucherConfirmed, voucherRejected],
    total: 4,
  })
  lifecycleApi.createTransferVoucher.mockResolvedValue({})
  lifecycleApi.confirmTransferVoucher.mockResolvedValue({})
  lifecycleApi.deleteTransferVoucher.mockResolvedValue({})
  lifecycleApi.uploadVoucherAttachment.mockResolvedValue({})
  confirmMock.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与列表', () => {
  it('onMounted 加载列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(lifecycleApi.listTransferVouchers).toHaveBeenCalledWith({
      project_id: undefined,
      status: undefined,
      page: 1,
      page_size: 20,
    })
    expect(vm.vouchers).toHaveLength(4)
    expect(vm.total).toBe(4)
  })

  it('带 project_id 查询参数', async () => {
    routeBox.query = { project_id: '7' }
    const wrapper = mountComp()
    await flushPromises()
    expect(lifecycleApi.listTransferVouchers).toHaveBeenCalledWith(
      expect.objectContaining({ project_id: 7 })
    )
  })

  it('loadData 失败 → 错误提示', async () => {
    lifecycleApi.listTransferVouchers.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载失败')
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('loadData 缺 items/total → || 兜底', async () => {
    lifecycleApi.listTransferVouchers.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).vouchers).toEqual([])
    expect((wrapper.vm as any).total).toBe(0)
  })

  it('状态筛选 change + 分页', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    lifecycleApi.listTransferVouchers.mockClear()
    await wrapper.find('.el-select-stub').trigger('click')
    await flushPromises()
    expect(lifecycleApi.listTransferVouchers).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'draft' })
    )

    vm.page = 3
    lifecycleApi.listTransferVouchers.mockClear()
    await wrapper.find('.el-pagination-stub').trigger('click')
    await flushPromises()
    expect(lifecycleApi.listTransferVouchers).toHaveBeenCalledWith(
      expect.objectContaining({ page: 3 })
    )
    expect(vm.page).toBe(2)
  })

  it('页头返回 → pushSafe /funds', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.findComponent({ name: 'ElPageHeader' }).vm.$emit('back')
    expect(pushSafeMock).toHaveBeenCalledWith('/funds')
  })
})

describe('新建凭证', () => {
  it('校验失败 → 不提交', async () => {
    const wrapper = mountComp()
    await flushPromises()
    formValidateMock.mockRejectedValueOnce(new Error('invalid'))
    const vm = wrapper.vm as any
    vm.form.voucher_no = ''
    await vm.handleCreate()
    expect(lifecycleApi.createTransferVoucher).not.toHaveBeenCalled()
  })

  it('创建成功 → 提示 + 关弹窗 + 刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.form.voucher_no = 'VZ-X'
    vm.form.amount = 10
    vm.page = 5
    lifecycleApi.listTransferVouchers.mockClear()
    await vm.handleCreate()
    expect(lifecycleApi.createTransferVoucher).toHaveBeenCalledWith(vm.form)
    expect(ElMessage.success).toHaveBeenCalledWith('创建成功')
    expect(vm.showCreateDialog).toBe(false)
    expect(vm.page).toBe(1)
    expect(lifecycleApi.listTransferVouchers).toHaveBeenCalled()
  })

  it('创建失败 → detail 与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.form.voucher_no = 'VZ-X'
    vm.form.amount = 10
    lifecycleApi.createTransferVoucher.mockRejectedValueOnce({
      response: { data: { detail: '编号重复' } },
    })
    await vm.handleCreate()
    expect(ElMessage.error).toHaveBeenCalledWith('编号重复')

    lifecycleApi.createTransferVoucher.mockRejectedValueOnce(new Error('net'))
    await vm.handleCreate()
    expect(ElMessage.error).toHaveBeenCalledWith('创建失败')
  })

  it('新建按钮 → 打开弹窗', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('新建凭证'))
    await btn!.trigger('click')
    expect((wrapper.vm as any).showCreateDialog).toBe(true)
  })

  it('openCreateDialog：formRef 存在但无 clearValidate → 防御不抛错', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formRef = {} // 空对象（测试环境/未挂载形态）
    await vm.openCreateDialog()
    expect(vm.showCreateDialog).toBe(true)
    expect(vm.form.voucher_no).toBe('')
  })

  it('openCreateDialog：formRef 有 clearValidate → 调用清除校验', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const clearValidate = vi.fn()
    vm.formRef = { clearValidate }
    await vm.openCreateDialog()
    expect(clearValidate).toHaveBeenCalled()
  })
})

describe('确认凭证', () => {
  it('确认成功 → 提示 + 刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    lifecycleApi.listTransferVouchers.mockClear()
    await vm.handleConfirm(1)
    expect(confirmMock).toHaveBeenCalledWith('确认该凭证？', '确认')
    expect(lifecycleApi.confirmTransferVoucher).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('已确认')
    expect(lifecycleApi.listTransferVouchers).toHaveBeenCalled()
  })

  it('取消 → 不调用', async () => {
    const wrapper = mountComp()
    await flushPromises()
    confirmMock.mockRejectedValueOnce('cancel')
    await (wrapper.vm as any).handleConfirm(1)
    expect(lifecycleApi.confirmTransferVoucher).not.toHaveBeenCalled()
  })

  it('确认失败 → detail 与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    lifecycleApi.confirmTransferVoucher.mockRejectedValueOnce({
      response: { data: { detail: '状态不允许' } },
    })
    await vm.handleConfirm(1)
    expect(ElMessage.error).toHaveBeenCalledWith('状态不允许')

    lifecycleApi.confirmTransferVoucher.mockRejectedValueOnce(new Error('net'))
    await vm.handleConfirm(1)
    expect(ElMessage.error).toHaveBeenCalledWith('确认失败')
  })
})

describe('删除凭证', () => {
  it('删除成功', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    lifecycleApi.listTransferVouchers.mockClear()
    await vm.handleDelete(1)
    expect(lifecycleApi.deleteTransferVoucher).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('已删除')
    expect(lifecycleApi.listTransferVouchers).toHaveBeenCalled()
  })

  it('取消 → 不调用', async () => {
    const wrapper = mountComp()
    await flushPromises()
    confirmMock.mockRejectedValueOnce('cancel')
    await (wrapper.vm as any).handleDelete(1)
    expect(lifecycleApi.deleteTransferVoucher).not.toHaveBeenCalled()
  })

  it('删除失败 → detail 与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    lifecycleApi.deleteTransferVoucher.mockRejectedValueOnce({
      response: { data: { detail: '已使用' } },
    })
    await vm.handleDelete(1)
    expect(ElMessage.error).toHaveBeenCalledWith('已使用')

    lifecycleApi.deleteTransferVoucher.mockRejectedValueOnce(new Error('net'))
    await vm.handleDelete(1)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })
})

describe('模板分支与 v-model', () => {
  it('四种状态行渲染 + 操作按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.text()).toContain('草稿')
    expect(wrapper.text()).toContain('已提交')
    expect(wrapper.text()).toContain('已确认')
    expect(wrapper.text()).toContain('已拒绝')

    // 确认按钮 → handleConfirm(row.id)
    const confirmBtn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('确认'))
    await confirmBtn!.trigger('click')
    await flushPromises()
    expect(lifecycleApi.confirmTransferVoucher).toHaveBeenCalled()

    // 删除按钮 → handleDelete(row.id)
    const delBtn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('删除'))
    lifecycleApi.deleteTransferVoucher.mockClear()
    await delBtn!.trigger('click')
    await flushPromises()
    expect(lifecycleApi.deleteTransferVoucher).toHaveBeenCalled()
  })

  it('表单控件 v-model 更新 + 创建/取消按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    for (const el of wrapper.findAll('.el-input-stub')) {
      await el.trigger('click')
    }
    for (const el of wrapper.findAll('.el-input-number-stub')) {
      await el.trigger('click')
    }
    for (const el of wrapper.findAll('.el-date-picker-stub')) {
      await el.trigger('click')
    }
    await wrapper.find('.el-radio-group-stub').trigger('click')
    await flushPromises()
    expect(vm.form.voucher_no).toBe('V')
    expect(vm.form.payer_account).toBe('V')
    expect(vm.form.amount).toBe(5)
    expect(vm.form.transfer_date).toBe('2024-01-01')
    expect(vm.form.direction).toBe('local_to_military')

    vm.form.voucher_no = 'VZ-X'
    vm.form.amount = 1
    const createBtn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('保存'))
    lifecycleApi.listTransferVouchers.mockClear()
    await createBtn!.trigger('click')
    await flushPromises()
    expect(lifecycleApi.createTransferVoucher).toHaveBeenCalled()

    vm.showCreateDialog = true
    const cancel = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('取消'))
    await cancel!.trigger('click')
    expect(vm.showCreateDialog).toBe(false)
  })


  it('handleCreate: formRef 缺失时直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formRef = null
    await vm.handleCreate()
    expect(lifecycleApi.createTransferVoucher).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('凭证附件上传（funcs@179 handleVoucherUpload / funcs@78 http-request 箭头）', () => {
  it('el-upload http-request → handleVoucherUpload 成功：上传中态 + 成功提示 + 复位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 挂起一次上传，以便观察 uploadingId 中间态
    lifecycleApi.uploadVoucherAttachment.mockImplementationOnce(() => new Promise(() => {}))
    const fire = wrapper.findAll('.fire-upload')[0]
    expect(fire).toBeTruthy()
    await fire.trigger('click')
    await nextTick()
    expect(vm.uploadingId).toBe(1) // rowA.id

    lifecycleApi.uploadVoucherAttachment.mockResolvedValueOnce({})
    await vm.handleVoucherUpload(1, new File(['x'], 'v.pdf'))
    await flushPromises()

    expect(lifecycleApi.uploadVoucherAttachment).toHaveBeenCalledTimes(2)
    const [vid, file] = lifecycleApi.uploadVoucherAttachment.mock.calls[0]
    expect(vid).toBe(1)
    expect(file).toBeInstanceOf(File)
    expect((file as File).name).toBe('voucher.pdf')
    expect(ElMessage.success).toHaveBeenCalledWith('凭证附件已上传')
    expect(vm.uploadingId).toBeNull() // finally 复位
    expect(logError).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('handleVoucherUpload 失败 → logger.error + 错误提示 + uploadingId 复位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const err = new Error('net')
    lifecycleApi.uploadVoucherAttachment.mockRejectedValueOnce(err)
    const f = new File(['x'], 'bad.pdf')
    await vm.handleVoucherUpload(7, f)
    expect(lifecycleApi.uploadVoucherAttachment).toHaveBeenCalledWith(7, f)
    expect(logError).toHaveBeenCalledWith('凭证附件上传失败:', err)
    expect(ElMessage.error).toHaveBeenCalledWith('上传失败，请稍后重试')
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(vm.uploadingId).toBeNull()
    wrapper.unmount()
  })
})
