/**
 * views/media/PhotoArchive.vue 专属测试（契约 W22 §2/§3/§5，四指标 100%）
 *
 * 单执行者规程：本文件是全仓唯一真实执行 PhotoArchive.vue 的测试。
 * 方案：mock 全部 API/上传头 composable + Element Plus 结构桩，
 * 覆盖筛选/分页/多选/上传归档/编辑/删除/对比图（选中与拍摄点多期）/模板事件绑定。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirm: vi.fn(),
  getPhotos: vi.fn(),
  createPhoto: vi.fn(),
  updatePhoto: vi.fn(),
  deletePhoto: vi.fn(),
  getPhotoCompare: vi.fn(),
  generateCompareImage: vi.fn(),
  downloadCompareImage: vi.fn(),
  getSupportedVillages: vi.fn(),
  schoolsList: vi.fn(),
  projectsList: vi.fn(),
  ensureCsrf: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: mocks.ElMessage,
  ElMessageBox: { confirm: mocks.confirm },
}))

vi.mock('@/api/media', () => ({
  getPhotos: (...a: any[]) => mocks.getPhotos(...a),
  createPhoto: (...a: any[]) => mocks.createPhoto(...a),
  updatePhoto: (...a: any[]) => mocks.updatePhoto(...a),
  deletePhoto: (...a: any[]) => mocks.deletePhoto(...a),
  getPhotoCompare: (...a: any[]) => mocks.getPhotoCompare(...a),
  generateCompareImage: (...a: any[]) => mocks.generateCompareImage(...a),
  downloadCompareImage: (...a: any[]) => mocks.downloadCompareImage(...a),
}))

vi.mock('@/api/supportedVillage', () => ({
  getSupportedVillages: (...a: any[]) => mocks.getSupportedVillages(...a),
}))
vi.mock('@/api/schools', () => ({
  schoolsApi: { list: (...a: any[]) => mocks.schoolsList(...a) },
}))
vi.mock('@/api/projects', () => ({
  projectsApi: { list: (...a: any[]) => mocks.projectsList(...a) },
}))
vi.mock('@/composables/useUploadHeaders', () => ({
  useUploadHeaders: () => ({
    uploadHeaders: { Authorization: 'Bearer test' },
    ensureCsrf: mocks.ensureCsrf,
  }),
}))

import PhotoArchive from '@/views/media/PhotoArchive.vue'

// ── 桩组件 ──
const ElButtonStub = {
  name: 'ElButtonStub',
  props: ['disabled', 'loading', 'type', 'text', 'link'],
  emits: ['click'],
  template:
    '<button class="stub-btn" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
}

const ElSelectStub = {
  name: 'ElSelectStub',
  props: ['modelValue', 'placeholder', 'clearable'],
  emits: ['update:modelValue', 'change'],
  template: '<div class="select-stub"><slot /></div>',
}

const ElOptionStub = {
  name: 'ElOptionStub',
  props: ['label', 'value'],
  template: '<span class="option-stub">{{ label }}</span>',
}

const ElInputStub = {
  name: 'ElInputStub',
  props: ['modelValue', 'placeholder', 'clearable'],
  emits: ['update:modelValue'],
  template: '<input class="input-stub" :value="modelValue" />',
}

const ElDatePickerStub = {
  name: 'ElDatePickerStub',
  props: ['modelValue', 'type', 'valueFormat', 'startPlaceholder', 'endPlaceholder'],
  emits: ['update:modelValue'],
  template: '<div class="date-stub"></div>',
}

const ElCheckboxStub = {
  name: 'ElCheckboxStub',
  props: ['modelValue'],
  emits: ['change'],
  template:
    '<input class="checkbox-stub" type="checkbox" :checked="modelValue" @change="$emit(\'change\')" />',
}

const ElUploadStub = {
  name: 'ElUploadStub',
  props: ['action', 'headers', 'showFileList', 'beforeUpload', 'onSuccess', 'onError', 'accept'],
  template: '<div class="upload-stub"><slot /></div>',
}

const ElCardStub = {
  name: 'ElCardStub',
  template: '<div class="card-stub"><slot name="header" /><slot /></div>',
}

const ElEmptyStub = {
  name: 'ElEmptyStub',
  props: ['description'],
  template: '<div class="empty-stub">{{ description }}</div>',
}

const ElPaginationStub = {
  name: 'ElPaginationStub',
  props: ['currentPage', 'pageSize', 'total', 'pageSizes', 'layout'],
  emits: ['current-change', 'size-change'],
  template: '<div class="pagination-stub">{{ total }}</div>',
}

const ElDialogStub = {
  name: 'ElDialogStub',
  props: ['modelValue', 'title', 'width'],
  emits: ['update:modelValue'],
  template:
    '<div v-if="modelValue" class="dialog-stub" :data-title="title">' +
    '<slot /><slot name="footer" /></div>',
}

const ElFormStub = {
  name: 'ElFormStub',
  props: ['labelWidth'],
  template: '<div class="form-stub"><slot /></div>',
}
const ElFormItemStub = {
  name: 'ElFormItemStub',
  props: ['label'],
  template: '<div class="form-item-stub"><span class="label-stub">{{ label }}</span><slot /></div>',
}
const ElAlertStub = {
  name: 'ElAlertStub',
  props: ['type', 'title', 'closable'],
  template: '<div class="alert-stub">{{ title }}</div>',
}
const ElIconStub = { name: 'ElIconStub', template: '<span class="icon-stub"><slot /></span>' }

const stubs = {
  'el-button': ElButtonStub,
  'el-select': ElSelectStub,
  'el-option': ElOptionStub,
  'el-input': ElInputStub,
  'el-date-picker': ElDatePickerStub,
  'el-checkbox': ElCheckboxStub,
  'el-upload': ElUploadStub,
  'el-card': ElCardStub,
  'el-empty': ElEmptyStub,
  'el-pagination': ElPaginationStub,
  'el-dialog': ElDialogStub,
  'el-form': ElFormStub,
  'el-form-item': ElFormItemStub,
  'el-alert': ElAlertStub,
  'el-icon': ElIconStub,
}

// ── 夹具 ──
const photoRows = [
  {
    id: 1,
    file_url: '/uploads/a.jpg',
    file_name: 'a.jpg',
    tag: '村容',
    spot_key: 'village-1',
    taken_at: '2024-05-01T10:00:00',
    village_id: 1,
  },
  {
    id: 2,
    file_url: '/uploads/b.jpg',
    file_name: 'b.jpg',
    tag: '',
    spot_key: 'village-1',
    taken_at: '',
    village_id: 1,
  },
  { id: 3, file_url: '/uploads/c.jpg', spot_key: 'village-2', project_id: 3 },
  { id: 4, file_url: '/uploads/d.jpg', school_id: 2 },
  { id: 5, file_url: '/uploads/e.jpg', project_id: 99 },
  { id: 6, file_url: '/uploads/f.jpg' },
]

const villageRows = [{ id: 1, village_name: '村一' }, { id: 2 }]
const schoolRows = [{ id: 2, name: '学校一' }, { id: 3 }]
const projectRows = [{ id: 3, name: '项目一' }, { id: 4 }]

function mountComp() {
  return mount(PhotoArchive, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

const findBtn = (wrapper: any, testId: string) => wrapper.find(`[data-testid="${testId}"]`)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getPhotos.mockResolvedValue({ items: photoRows, total: 6 })
  mocks.getSupportedVillages.mockResolvedValue({ items: villageRows, total: 2 })
  mocks.schoolsList.mockResolvedValue({ items: schoolRows, total: 2 })
  mocks.projectsList.mockResolvedValue({ items: projectRows, total: 2 })
  mocks.createPhoto.mockResolvedValue({ id: 7 })
  mocks.updatePhoto.mockResolvedValue({ id: 1 })
  mocks.deletePhoto.mockResolvedValue(true)
  mocks.getPhotoCompare.mockResolvedValue([])
  mocks.generateCompareImage.mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
  mocks.downloadCompareImage.mockResolvedValue(undefined)
  mocks.confirm.mockResolvedValue('confirm')
  mocks.ensureCsrf.mockResolvedValue(undefined)
  // jsdom 不实现对象 URL：固定桩便于断言创建/释放
  Object.defineProperty(URL, 'createObjectURL', {
    value: vi.fn(() => 'blob:mock-compare-url'),
    writable: true,
    configurable: true,
  })
  Object.defineProperty(URL, 'revokeObjectURL', {
    value: vi.fn(),
    writable: true,
    configurable: true,
  })
})

describe('挂载与卡片渲染', () => {
  it('加载下拉选项与影像列表，卡片/分组/分页/归档对象各分支', async () => {
    const wrapper = mountComp()
    await flushPromises()

    expect(mocks.getSupportedVillages).toHaveBeenCalledWith({ page: 1, page_size: 500 })
    expect(mocks.schoolsList).toHaveBeenCalledWith({ page: 1, page_size: 500 })
    expect(mocks.projectsList).toHaveBeenCalledWith({ page: 1, page_size: 500 })
    expect(mocks.getPhotos).toHaveBeenCalledWith({ page: 1, page_size: 12 })

    const vm = wrapper.vm as any
    expect(vm.villageOptions).toEqual([
      { value: 1, label: '村一' },
      { value: 2, label: '#2' },
    ])
    expect(vm.schoolOptions).toEqual([
      { value: 2, label: '学校一' },
      { value: 3, label: '#3' },
    ])
    expect(vm.projectOptions).toEqual([
      { value: 3, label: '项目一' },
      { value: 4, label: '#4' },
    ])
    expect(vm.total).toBe(6)

    // 卡片数量 + 归档对象展示分支（村/项目/学校/#id/未关联）
    expect(wrapper.findAll('[data-testid="photo-card"]')).toHaveLength(6)
    const text = wrapper.text()
    expect(text).toContain('村：村一')
    expect(text).toContain('项目：项目一')
    expect(text).toContain('学校：学校一')
    expect(text).toContain('项目：#99')
    expect(text).toContain('未关联')
    expect(text).toContain('2024-05-01 10:00')
    expect(text).toContain('拍摄点：village-1')

    // 拍摄点多期分组：village-1 两期、village-2 一期
    const groups = wrapper.findAll('[data-testid="spot-group"]')
    expect(groups).toHaveLength(2)
    expect(groups[0].text()).toContain('village-1')
    expect(groups[0].text()).toContain('共 2 期')
    expect(groups[1].text()).toContain('village-2')
    expect(groups[1].text()).toContain('共 1 期')

    // 分页渲染
    expect(wrapper.find('[data-testid="photo-pagination"]').exists()).toBe(true)
  })

  it('空列表：加载态不显示空态，加载结束后显示空态且无分页', async () => {
    mocks.getPhotos.mockResolvedValue({ items: [], total: 0 })
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.find('[data-testid="photo-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="photo-grid"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="photo-pagination"]').exists()).toBe(false)

    // loading=true 时 `!loading && photos.length===0` 短路 → 不显示空态
    ;(wrapper.vm as any).loading = true
    await nextTick()
    expect(wrapper.find('[data-testid="photo-empty"]').exists()).toBe(false)
  })

  it('列表加载失败：提示并清空；下拉选项失败静默不阻断列表', async () => {
    mocks.getPhotos.mockRejectedValue({ userMessage: '影像服务不可用' })
    mocks.getSupportedVillages.mockRejectedValue(new Error('options down'))
    const wrapper = mountComp()
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('影像服务不可用')
    expect((wrapper.vm as any).photos).toEqual([])
    expect((wrapper.vm as any).photos.length).toBe(0)
    // 选项失败不影响列表加载（Promise.all 拒绝被 catch）
    expect(mocks.getPhotos).toHaveBeenCalled()
  })
})

describe('筛选/分页/重置', () => {
  it('查询携带筛选参数；重置清空条件；分页与每页条数事件', async () => {
    mocks.getSupportedVillages.mockResolvedValue({ items: [{ id: 1, village_name: '村一' }] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.filters.village_id = 1
    vm.filters.school_id = 2
    vm.filters.project_id = 3
    vm.filters.tag = ' 产业 '
    vm.dateRange = ['2024-01-01', '2024-12-31']
    await findBtn(wrapper, 'search-btn').trigger('click')
    await flushPromises()
    expect(mocks.getPhotos).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 12,
      village_id: 1,
      school_id: 2,
      project_id: 3,
      tag: '产业',
      date_from: '2024-01-01',
      date_to: '2024-12-31',
    })

    await findBtn(wrapper, 'reset-btn').trigger('click')
    await flushPromises()
    expect(vm.filters).toMatchObject({
      village_id: null,
      school_id: null,
      project_id: null,
      tag: '',
    })
    expect(vm.dateRange).toBeNull()
    expect(mocks.getPhotos).toHaveBeenLastCalledWith({ page: 1, page_size: 12 })

    // 分页 stub 事件
    const pagination = wrapper.findComponent({ name: 'ElPaginationStub' })
    pagination.vm.$emit('current-change', 2)
    await flushPromises()
    expect(vm.page).toBe(2)
    pagination.vm.$emit('size-change', 24)
    await flushPromises()
    expect(vm.pageSize).toBe(24)
    expect(vm.page).toBe(1)
  })

  it('筛选下拉/输入/日期 v-model 内联处理器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    const selects = wrapper.findAllComponents({ name: 'ElSelectStub' })
    // 前三个筛选 select：村/学校/项目
    selects[0].vm.$emit('update:modelValue', 1)
    selects[1].vm.$emit('update:modelValue', 2)
    selects[2].vm.$emit('update:modelValue', 3)
    const input = wrapper.findComponent({ name: 'ElInputStub' })
    input.vm.$emit('update:modelValue', '标签')
    const date = wrapper.findComponent({ name: 'ElDatePickerStub' })
    date.vm.$emit('update:modelValue', ['2024-01-01', '2024-02-01'])
    expect(vm.filters).toMatchObject({ village_id: 1, school_id: 2, project_id: 3, tag: '标签' })
    expect(vm.dateRange).toEqual(['2024-01-01', '2024-02-01'])
  })
})

describe('多选与按钮', () => {
  it('勾选/取消/清空；选择条文案与按钮显隐；生成对比图按钮触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(wrapper.find('[data-testid="selection-info"]').text()).toContain('勾选至少 2 张')
    expect(findBtn(wrapper, 'compare-btn').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-testid="clear-selection-btn"]').exists()).toBe(false)

    vm.toggleSelect(1)
    await nextTick()
    expect(vm.selectedIds).toEqual([1])
    expect(wrapper.find('[data-testid="selection-info"]').text()).toContain('已选 1 张')
    expect(wrapper.find('[data-testid="clear-selection-btn"]').exists()).toBe(true)

    // 模板 checkbox change → 再选第 2 张
    const checkboxes = wrapper.findAll('.checkbox-stub')
    await checkboxes[1].trigger('change')
    await flushPromises()
    expect(vm.selectedIds).toEqual([1, 2])

    // 再次 toggle 同一个 id → 取消勾选
    vm.toggleSelect(1)
    expect(vm.selectedIds).toEqual([2])

    await findBtn(wrapper, 'clear-selection-btn').trigger('click')
    expect(vm.selectedIds).toEqual([])
  })

  it('刷新按钮重新加载列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const before = mocks.getPhotos.mock.calls.length
    await findBtn(wrapper, 'refresh-btn').trigger('click')
    await flushPromises()
    expect(mocks.getPhotos.mock.calls.length).toBe(before + 1)
  })
})

describe('上传归档', () => {
  it('beforeUpload：非图片/超限拒绝；图片通过并预取 CSRF', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const upload = wrapper.findComponent({ name: 'ElUploadStub' })

    expect(await upload.props('beforeUpload')({ type: 'text/plain', size: 10 })).toBe(false)
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('只能上传图片文件')

    expect(
      await upload.props('beforeUpload')({
        type: 'image/jpeg',
        size: 21 * 1024 * 1024,
      })
    ).toBe(false)
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('图片大小不能超过 20MB')

    expect(await upload.props('beforeUpload')({ type: 'image/png', size: 1024 })).toBe(true)
    expect(mocks.ensureCsrf).toHaveBeenCalled()
    expect((wrapper.vm as any).uploading).toBe(true)
  })

  it('onSuccess：响应两种 url 形态 → 创建归档（带当前筛选关联），成功后刷新并回到第一页', async () => {
    mocks.getSupportedVillages.mockResolvedValue({ items: [{ id: 1, village_name: '村一' }] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filters.village_id = 1
    vm.filters.tag = ' 村容 '
    const upload = wrapper.findComponent({ name: 'ElUploadStub' })

    upload.props('onSuccess')(
      { data: { url: '/uploads/new.jpg' } },
      {
        name: 'new.jpg',
        size: 2048,
        raw: { type: 'image/jpeg' },
      }
    )
    await flushPromises()

    expect(mocks.createPhoto).toHaveBeenCalledWith({
      file_url: '/uploads/new.jpg',
      file_name: 'new.jpg',
      file_size: 2048,
      mime_type: 'image/jpeg',
      village_id: 1,
      school_id: null,
      project_id: null,
      tag: '村容',
    })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('影像已归档')
    expect(vm.page).toBe(1)

    // 第二种响应形态：{url}，空标签 → null，file 缺 raw 时回退 file.type，缺 name/size 时 undefined
    vm.filters.tag = ''
    upload.props('onSuccess')({ url: '/uploads/new2.jpg' }, { type: 'image/png' })
    await flushPromises()
    expect(mocks.createPhoto).toHaveBeenLastCalledWith(
      expect.objectContaining({
        file_url: '/uploads/new2.jpg',
        tag: null,
        mime_type: 'image/png',
        file_name: undefined,
        file_size: undefined,
      })
    )
  })

  it('onSuccess 缺 url → 报错；归档失败 → 兜底提示；onError → 上传失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const upload = wrapper.findComponent({ name: 'ElUploadStub' })
    const vm = wrapper.vm as any

    upload.props('onSuccess')({}, { name: 'x.jpg' })
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('上传响应缺少文件地址')
    expect(vm.uploading).toBe(false)

    mocks.createPhoto.mockRejectedValueOnce(new Error('db down'))
    upload.props('onSuccess')({ url: '/uploads/x.jpg' }, { name: 'x.jpg' })
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('db down')
    expect(vm.uploading).toBe(false)

    vm.uploading = true
    upload.props('onError')()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('上传失败，请重试')
    expect(vm.uploading).toBe(false)
  })
})

describe('编辑与删除', () => {
  it('openEdit 回填；保存成功（tag/spot 清空 → null）；reload；无 editingId 提前返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.openEdit({
      id: 1,
      file_url: '/a.jpg',
      village_id: 1,
      tag: '村容',
      spot_key: 'v1',
      taken_at: '2024-05-01T10:00:00',
    })
    await nextTick()
    expect(vm.editVisible).toBe(true)
    expect(vm.editForm).toMatchObject({
      village_id: 1,
      school_id: null,
      project_id: null,
      tag: '村容',
      spot_key: 'v1',
      taken_at: '2024-05-01T10:00:00',
    })
    // 编辑对话框 v-model 内联处理器
    const editDialog = wrapper.findComponent({ name: 'ElDialogStub' })
    editDialog.vm.$emit('update:modelValue', false)
    expect(vm.editVisible).toBe(false)
    vm.editVisible = true
    await nextTick()

    // 照片卡片「编辑」按钮 → openEdit(photo)
    await wrapper.find('[data-testid="photo-edit"]').trigger('click')
    expect(vm.editingId).toBe(1)

    // 编辑表单内联 v-model（筛选 3 个 + 编辑内 3 个：村/学校/项目）
    const selects = wrapper.findAllComponents({ name: 'ElSelectStub' })
    selects[3].vm.$emit('update:modelValue', 1)
    selects[4].vm.$emit('update:modelValue', 2)
    selects[5].vm.$emit('update:modelValue', 3)
    const inputs = wrapper.findAllComponents({ name: 'ElInputStub' })
    inputs[1].vm.$emit('update:modelValue', ' 新标签 ')
    inputs[2].vm.$emit('update:modelValue', ' ')
    const dates = wrapper.findAllComponents({ name: 'ElDatePickerStub' })
    dates[1].vm.$emit('update:modelValue', '2024-06-01T08:00:00')

    await findBtn(wrapper, 'edit-save').trigger('click')
    await flushPromises()
    expect(mocks.updatePhoto).toHaveBeenCalledWith(1, {
      village_id: 1,
      school_id: 2,
      project_id: 3,
      tag: '新标签',
      spot_key: null,
      taken_at: '2024-06-01T08:00:00',
    })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('归档信息已保存')
    expect(vm.editVisible).toBe(false)

    // 取消按钮内联处理器
    vm.openEdit({ id: 1, file_url: '/a.jpg' })
    await nextTick()
    const cancelBtn = wrapper.findAll('.stub-btn').find((b: any) => b.text().trim() === '取消')
    await cancelBtn!.trigger('click')
    expect(vm.editVisible).toBe(false)

    // editingId 为 null → 提前返回
    vm.editingId = null
    await vm.saveEdit()
    expect(mocks.updatePhoto).toHaveBeenCalledTimes(1)
  })

  it('保存失败 → 提示；openEdit 缺省字段兜底为空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.openEdit({ id: 2, file_url: '/b.jpg' })
    expect(vm.editForm.tag).toBe('')
    expect(vm.editForm.taken_at).toBeNull()

    mocks.updatePhoto.mockRejectedValueOnce({ userMessage: '无权修改' })
    await vm.saveEdit()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('无权修改')
    expect(vm.saving).toBe(false)
  })

  it('删除：确认后删除并处理页码回退；取消不删除；失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 成功：第 2 页且当前页仅 1 条 → 页码回退
    vm.page = 2
    vm.photos = [photoRows[0]]
    mocks.getPhotos.mockResolvedValue({ items: photoRows.slice(0, 1), total: 1 })
    await vm.handleDelete(photoRows[0])
    expect(mocks.deletePhoto).toHaveBeenCalledWith(1)
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('影像已删除')
    expect(vm.page).toBe(1)

    // 删除按钮模板绑定（file_name 缺省时用 id 拼确认文案）
    vm.page = 1
    mocks.getPhotos.mockResolvedValue({ items: photoRows, total: 6 })
    await findBtn(wrapper, 'photo-delete').trigger('click')
    await flushPromises()
    expect(mocks.deletePhoto).toHaveBeenCalledWith(1)

    // 取消确认 → 不删除
    mocks.confirm.mockRejectedValueOnce('cancel')
    const deleteCalls = mocks.deletePhoto.mock.calls.length
    await vm.handleDelete(photoRows[2])
    expect(mocks.deletePhoto.mock.calls.length).toBe(deleteCalls)

    // 失败提示
    mocks.deletePhoto.mockRejectedValueOnce(new Error('locked'))
    await vm.handleDelete(photoRows[1])
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('locked')
  })
})

describe('对比图（选中照片 + 拍摄点多期）', () => {
  it('少于 2 张提示；选中 2 张生成预览；下载/关闭释放对象 URL', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.openCompare()
    expect(mocks.ElMessage.info).toHaveBeenCalledWith('请至少选择 2 张影像')
    expect(mocks.generateCompareImage).not.toHaveBeenCalled()

    vm.selectedIds = [1, 2]
    await nextTick()
    await findBtn(wrapper, 'compare-btn').trigger('click')
    await flushPromises()
    expect(mocks.generateCompareImage).toHaveBeenCalledWith([1, 2])
    expect(URL.createObjectURL).toHaveBeenCalled()
    expect(vm.compareVisible).toBe(true)
    expect(vm.compareUrl).toBe('blob:mock-compare-url')
    expect(wrapper.find('[data-testid="compare-image"]').exists()).toBe(true)

    // 对比图对话框 v-model 内联处理器（编辑对话框恒存在但内容 v-if 隐藏，故用列表取第 2 个）
    const compareDialog = wrapper.findAllComponents({ name: 'ElDialogStub' })[1]
    compareDialog.vm.$emit('update:modelValue', false)
    expect(vm.compareVisible).toBe(false)
    vm.compareVisible = true
    await nextTick()

    // 下载（compareIds 非空）
    await findBtn(wrapper, 'compare-download').trigger('click')
    await flushPromises()
    expect(mocks.downloadCompareImage).toHaveBeenCalledWith([1, 2])
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('对比图下载已开始')

    // 关闭按钮 → 释放 URL
    const closeBtn = wrapper.findAll('.stub-btn').find((b: any) => b.text().trim() === '关闭')
    await closeBtn!.trigger('click')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-compare-url')
    expect(vm.compareVisible).toBe(false)
    expect(vm.compareUrl).toBe('')
  })

  it('生成失败 → 错误提示与错误态；下载失败提示；compareIds 为空早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    mocks.generateCompareImage.mockRejectedValueOnce({ userMessage: '图片不可读' })
    vm.selectedIds = [1, 2]
    await vm.openCompare()
    expect(vm.compareError).toBe('图片不可读')
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('图片不可读')
    await nextTick()
    expect(wrapper.find('[data-testid="compare-error"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="compare-image"]').exists()).toBe(false)
    // 无错误但尚未出图时展示 pending 占位
    vm.compareError = ''
    await nextTick()
    expect(wrapper.find('[data-testid="compare-pending"]').exists()).toBe(true)

    // compareIds 为空 → downloadCompare 提前返回
    vm.compareIds = []
    await vm.downloadCompare()
    expect(mocks.downloadCompareImage).not.toHaveBeenCalled()

    // 下载失败
    vm.compareIds = [1, 2]
    mocks.downloadCompareImage.mockRejectedValueOnce(new Error('net'))
    await vm.downloadCompare()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('net')
    expect(vm.downloading).toBe(false)
  })

  it('拍摄点多期：≥2 期生成对比图（含 series 展示）；不足 2 期提示；加载失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    const spotBtn = wrapper.find('[data-testid="spot-compare-btn"]')
    mocks.getPhotoCompare.mockResolvedValueOnce([
      { id: 1, file_url: '/a.jpg', taken_at: '2024-01-01T00:00:00' },
      { id: 2, file_url: '/b.jpg', taken_at: '2024-06-01T00:00:00' },
    ])
    await spotBtn.trigger('click')
    await flushPromises()
    expect(mocks.getPhotoCompare).toHaveBeenCalledWith('village-1')
    expect(mocks.generateCompareImage).toHaveBeenCalledWith([1, 2])
    expect(vm.compareSeries).toHaveLength(2)
    await nextTick()
    expect(wrapper.find('[data-testid="compare-series"]').exists()).toBe(true)

    // envelope 形态（items）
    mocks.getPhotoCompare.mockResolvedValueOnce({ items: [{ id: 9, file_url: '/x.jpg' }] })
    await vm.openSpotCompare('village-2')
    expect(mocks.ElMessage.info).toHaveBeenCalledWith('该拍摄点不足 2 期，无法生成对比图')

    // 加载失败
    mocks.getPhotoCompare.mockRejectedValueOnce({ userMessage: '拍摄点查询失败' })
    await vm.openSpotCompare('village-3')
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('拍摄点查询失败')
  })

  it('组件卸载时释放对比图对象 URL', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedIds = [1, 2]
    await vm.openCompare()
    await nextTick()
    wrapper.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-compare-url')
  })
})
