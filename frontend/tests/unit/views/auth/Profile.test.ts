/**
 * views/auth/Profile.vue 覆盖率攻坚
 * 覆盖：加载资料、编辑/取消、保存成功/失败/校验失败、头像上传各分支、导航
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick, defineComponent, h } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, mockPushSafe, userStore } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockPushSafe: vi.fn(() => Promise.resolve()),
  userStore: {
    getUserProfile: vi.fn(),
    updateUserProfile: vi.fn(),
    uploadAvatar: vi.fn(),
  },
}))

const formState = vi.hoisted(() => ({
  validateFn: (cb: (valid: boolean) => void) => cb(true),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(() => Promise.resolve()),
    resolve: vi.fn(() => ({ name: 'x', matched: [{ path: '/x' }] })),
  }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ push: mockPushSafe, pushSafe: mockPushSafe }),
  pushSafe: mockPushSafe,
}))

vi.mock('@/stores/user', () => ({
  useUserStore: () => userStore,
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElForm: { name: 'ElForm' },
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve('confirm')), alert: vi.fn() },
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import Profile from '@/views/auth/Profile.vue'

const ElFormStub = defineComponent({
  name: 'ElForm',
  props: ['model', 'rules'],
  emits: ['update:modelValue'],
  setup(_props, { expose, slots }) {
    const validate = (cb: (valid: boolean) => void) => formState.validateFn(cb)
    const clearValidate = vi.fn()
    expose({ validate, clearValidate })
    return () => h('form', { class: 'el-form-stub' }, [slots.default?.()])
  },
})

async function mountComp() {
  const w = mount(Profile, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-form': ElFormStub,
        'el-form-item': { name: 'ElFormItem', template: '<div class="el-form-item-stub"><slot /></div>' },
        'el-input': {
          name: 'ElInput',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-select': {
          name: 'ElSelect',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<select class="el-select-stub" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
        },
        'el-option': { name: 'ElOption', template: '<option value="male"><slot /></option>' },
        'el-date-picker': {
          name: 'ElDatePicker',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<div class="el-date-stub" @click="$emit(\'update:modelValue\', \'2020-01-01\')"><slot /></div>',
        },
        'el-button': {
          name: 'ElButton',
          template: '<button @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot /><slot name="header" /></div>',
        },
        'el-tag': { name: 'ElTag', template: '<span><slot /></span>' },
        'el-avatar': { name: 'ElAvatar', template: '<div class="el-avatar-stub"><slot /></div>' },
        'el-upload': { name: 'ElUpload', template: '<div class="el-upload-stub"><slot /></div>' },
        'el-icon': { name: 'ElIcon', template: '<span><slot /></span>' },
        'el-row': { name: 'ElRow', template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { name: 'ElCol', template: '<div class="el-col-stub"><slot /></div>' },
        'password-strength': {
          name: 'PasswordStrength',
          template: '<div class="password-strength-stub"><slot /></div>',
        },
      },
    },
  })
  await flushPromises()
  await nextTick()
  return w
}

const profileData = {
  id: '1',
  username: 'admin',
  name: '管理员',
  avatar: '',
  gender: 'male',
  birthday: '1990-01-01',
  phone: '13800000000',
  email: 'a@b.c',
  address: '北京',
  department: '信息科',
  position: '工程师',
  remark: '备注',
  roleName: '管理员',
  status: 'active',
  lastLoginTime: '2024-01-01 10:00',
  lastLoginIp: '127.0.0.1',
}

beforeEach(() => {
  vi.clearAllMocks()
  formState.validateFn = (cb) => cb(true)
  userStore.getUserProfile.mockResolvedValue(profileData)
  userStore.updateUserProfile.mockResolvedValue({ ...profileData, name: '新名字' })
  userStore.uploadAvatar.mockResolvedValue({ avatar_url: '/avatars/1.png' })
})

describe('Profile.vue', () => {
  it('渲染并加载用户资料', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(userStore.getUserProfile).toHaveBeenCalled()
    expect(vm.userInfo.username).toBe('admin')
    expect(vm.profileForm.name).toBe('管理员')
    expect(vm.profileForm.phone).toBe('13800000000')
    expect(w.text()).toContain('管理员')
  })

  it('加载资料：返回空 → 不填充', async () => {
    userStore.getUserProfile.mockResolvedValue(null)
    const w = await mountComp()
    expect((w.vm as any).userInfo.username).toBe('')
  })

  it('加载资料失败 → 错误提示', async () => {
    userStore.getUserProfile.mockRejectedValue(new Error('boom'))
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('获取用户信息失败')
  })

  it('startEditing / cancelEditing 重置表单', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.profileForm.name = '临时修改'
    vm.startEditing()
    expect(vm.editing).toBe(true)
    vm.cancelEditing()
    expect(vm.editing).toBe(false)
    expect(vm.profileForm.name).toBe('管理员')
    expect(vm.profileFormRef?.clearValidate).toHaveBeenCalled()
  })

  it('cancelEditing：无表单引用 → 跳过 clearValidate', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.profileFormRef = null
    vm.cancelEditing()
    expect(vm.editing).toBe(false)
  })

  it('saveProfile：校验失败 → 警告', async () => {
    formState.validateFn = (cb) => cb(false)
    const w = await mountComp()
    await (w.vm as any).saveProfile()
    expect(ElMessage.warning).toHaveBeenCalledWith('请检查输入信息')
    expect(userStore.updateUserProfile).not.toHaveBeenCalled()
  })

  it('saveProfile：保存成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.saveProfile()
    expect(userStore.updateUserProfile).toHaveBeenCalledWith(expect.objectContaining({ username: 'admin' }))
    expect(vm.editing).toBe(false)
    expect(vm.userInfo.name).toBe('新名字')
    expect(ElMessage.success).toHaveBeenCalledWith('个人资料保存成功')
  })

  it('saveProfile：失败 → Error 实例 message', async () => {
    userStore.updateUserProfile.mockRejectedValue(new Error('邮箱已占用'))
    const w = await mountComp()
    await (w.vm as any).saveProfile()
    expect(ElMessage.error).toHaveBeenCalledWith('邮箱已占用')
  })

  it('saveProfile：失败非 Error → 默认文案', async () => {
    userStore.updateUserProfile.mockRejectedValue('plain string')
    const w = await mountComp()
    await (w.vm as any).saveProfile()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败，请重试')
  })

  it('saveProfile：表单引用为空 → 直接返回', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.profileFormRef = null
    await vm.saveProfile()
    expect(userStore.updateUserProfile).not.toHaveBeenCalled()
  })

  it('beforeUploadAvatar：JPG/PNG 通过', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.beforeUploadAvatar({ type: 'image/jpeg', size: 1024 })).toBe(true)
    expect(vm.beforeUploadAvatar({ type: 'image/png', size: 1024 })).toBe(true)
  })

  it('beforeUploadAvatar：类型/大小校验失败', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.beforeUploadAvatar({ type: 'image/gif', size: 1024 })).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('只能上传JPG/JPEG/PNG格式的图片')
    expect(vm.beforeUploadAvatar({ type: 'image/jpeg', size: 3 * 1024 * 1024 })).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('图片大小不能超过2MB')
  })

  it('handleAvatarChange：无 raw → 不处理', async () => {
    const w = await mountComp()
    await (w.vm as any).handleAvatarChange({})
    expect(userStore.uploadAvatar).not.toHaveBeenCalled()
  })

  it('handleAvatarChange：成功返回 avatar_url', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleAvatarChange({ raw: { name: 'a.png' } })
    expect(vm.userInfo.avatar).toBe('/avatars/1.png')
    expect(ElMessage.success).toHaveBeenCalledWith('头像上传成功')
    expect(vm.uploadingAvatar).toBe(false)
  })

  it('handleAvatarChange：成功返回 url', async () => {
    userStore.uploadAvatar.mockResolvedValue({ url: '/avatars/2.png' })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleAvatarChange({ raw: { name: 'a.png' } })
    expect(vm.userInfo.avatar).toBe('/avatars/2.png')
  })

  it('handleAvatarChange：无 url → 本地预览兜底', async () => {
    userStore.uploadAvatar.mockResolvedValue({})
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleAvatarChange({ raw: { name: 'a.png' } })
    expect(vm.userInfo.avatar).toBe('blob:mock-url')
  })

  it('handleAvatarChange：失败 → 错误提示', async () => {
    userStore.uploadAvatar.mockRejectedValue(new Error('upload failed'))
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleAvatarChange({ raw: { name: 'a.png' } })
    expect(ElMessage.error).toHaveBeenCalledWith('upload failed')
    expect(vm.uploadingAvatar).toBe(false)
  })

  it('导航：修改密码 / 绑定 MFA', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.navigateToChangePassword()
    expect(mockPushSafe).toHaveBeenCalledWith('/change-password')
    vm.bindMfa()
    expect(mockPushSafe).toHaveBeenCalledWith('/profile/two-factor')
  })

  it('加载资料：字段为空 → 回退空串', async () => {
    userStore.getUserProfile.mockResolvedValue({
      id: '2',
      username: null,
      name: '',
      avatar: '',
      gender: '',
      birthday: '',
      phone: '',
      email: '',
      address: '',
      department: '',
      position: '',
      remark: '',
      roleName: '',
      status: 'inactive',
      lastLoginTime: '',
      lastLoginIp: '',
    })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.profileForm.username).toBe('')
    expect(vm.profileForm.name).toBe('')
    expect(vm.profileForm.gender).toBe('')
    // 无姓名且无用户名时头像无首字母
    expect(w.text()).not.toContain('管')
    // 取消编辑时同样回退空串
    vm.profileForm.name = 'x'
    vm.cancelEditing()
    expect(vm.profileForm.name).toBe('')
    // 禁用状态标签渲染
    vm.userInfo.status = 'active'
    await nextTick()
    expect(w.text()).toContain('正常')
  })

  it('表单 v-model 双向绑定（全部输入项）', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.startEditing()
    await nextTick()
    const inputs = w.findAll('input')
    // 用户名输入框为 disabled，通过组件 emit 覆盖其 v-model
    const nameInputs = w.findAllComponents({ name: 'ElInput' })
    if (nameInputs.length > 0) {
      nameInputs[0].vm.$emit('update:modelValue', 'newadmin')
      await nextTick()
      expect(vm.profileForm.username).toBe('newadmin')
    }
    const values = ['新名字', '13811112222', 'a@x.c', '新地址', '新部门', '新职务', '新备注']
    // inputs[0] 为禁用的用户名输入框，从 inputs[1] 开始
    for (let i = 0; i < values.length && i + 1 < inputs.length; i++) {
      await inputs[i + 1].setValue(values[i])
    }
    expect(vm.profileForm.name).toBe('新名字')
    expect(vm.profileForm.phone).toBe('13811112222')
    expect(vm.profileForm.email).toBe('a@x.c')
    expect(vm.profileForm.address).toBe('新地址')
    expect(vm.profileForm.department).toBe('新部门')
    expect(vm.profileForm.position).toBe('新职务')
    expect(vm.profileForm.remark).toBe('新备注')
    // select / date-picker 的 update:modelValue
    await w.find('.el-select-stub').setValue('male')
    expect(vm.profileForm.gender).toBe('male')
    await w.find('.el-date-stub').trigger('click')
    expect(vm.profileForm.birthday).toBe('2020-01-01')
    expect(w.exists()).toBe(true)
  })

  it('密码强度计算属性', async () => {
    const w = await mountComp()
    expect((w.vm as any).passwordStrength).toBe('medium')
  })
})
