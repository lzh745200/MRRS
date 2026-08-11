/**
 * views/system/EnvCheck.vue 覆盖率攻坚
 * 覆盖：环境检查成功/失败、健康分/依赖过滤计算、缺失包警告
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, envApi } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  envApi: { check: vi.fn() },
}))

vi.mock('@/api/env', () => ({
  envApi,
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve('confirm')), alert: vi.fn() },
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import EnvCheck from '@/views/system/EnvCheck.vue'

const envResult = {
  system: { python_version: '3.11.5', platform: 'Linux', env_mode: 'production' },
  packages: {
    fastapi: '0.110.0',
    sqlalchemy: '2.0.25',
    missing_pkg: '',
  },
  missing_packages: ['missing_pkg'],
  fix_command: 'pip install missing_pkg',
}

async function mountComp() {
  const w = mount(EnvCheck, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot /><slot name="header" /></div>',
        },
        'el-row': { name: 'ElRow', template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { name: 'ElCol', template: '<div class="el-col-stub"><slot /></div>' },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
        'el-descriptions': { name: 'ElDescriptions', template: '<dl><slot /></dl>' },
        'el-descriptions-item': {
          name: 'ElDescriptionsItem',
          template: '<div class="el-desc-item-stub"><slot /></div>',
        },
        'el-button': {
          name: 'ElButton',
          template: '<button class="el-button-stub"><slot /></button>',
        },
        'el-icon': { name: 'ElIcon', template: '<span><slot /></span>' },
        'el-input': {
          name: 'ElInput',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<input class="el-input-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-table': { name: 'ElTable', template: '<table class="el-table-stub"><slot /></table>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return {
              rowA: { name: 'fastapi', version: '0.110.0', installed: true },
              rowB: { name: 'missing_pkg', version: '', installed: false },
            }
          },
        },
        'el-alert': {
          name: 'ElAlert',
          template: '<div class="el-alert-stub"><slot /><slot name="title" /></div>',
        },
        'el-empty': { name: 'ElEmpty', template: '<div class="el-empty-stub"><slot /></div>' },
      },
    },
  })
  await flushPromises()
  await nextTick()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
  envApi.check.mockResolvedValue(envResult)
})

describe('EnvCheck.vue', () => {
  it('渲染并执行环境检查（有缺失依赖）', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(envApi.check).toHaveBeenCalled()
    expect(vm.envData?.system.python_version).toBe('3.11.5')
    expect(vm.systemInfo?.env_mode).toBe('production')
    expect(vm.missingPackages).toEqual(['missing_pkg'])
    expect(vm.installedCount).toBe(2)
    expect(vm.healthScore).toBe(67)
    expect(vm.healthClass).toBe('danger')
    expect(vm.envModeTagType).toBe('success')
    expect(ElMessage.warning).toHaveBeenCalledWith('发现 1 个缺失依赖')
    expect(w.text()).toContain('pip install missing_pkg')
  })

  it('无缺失依赖 → 成功提示 + 健康满分', async () => {
    envApi.check.mockResolvedValue({
      system: { python_version: '3.11', platform: 'Linux', env_mode: 'development' },
      packages: { fastapi: '0.110.0' },
      missing_packages: [],
    })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.missingPackages).toEqual([])
    expect(vm.healthScore).toBe(100)
    expect(vm.healthClass).toBe('healthy')
    expect(vm.envModeTagType).toBe('warning')
    expect(ElMessage.success).toHaveBeenCalledWith('环境检查通过，所有依赖已就绪')
  })

  it('环境模式未知 → info 标签', async () => {
    envApi.check.mockResolvedValue({
      system: { python_version: '3.11', platform: 'Linux', env_mode: 'testing' },
      packages: {},
      missing_packages: [],
    })
    const w = await mountComp()
    expect((w.vm as any).envModeTagType).toBe('info')
  })

  it('健康分中段 → warning 等级', async () => {
    envApi.check.mockResolvedValue({
      system: { python_version: '3.11', platform: 'Linux', env_mode: 'production' },
      packages: { a: '1', b: '2', c: '3', d: '4', e: '5' },
      missing_packages: ['e'],
    })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.healthScore).toBe(80)
    expect(vm.healthClass).toBe('warning')
  })

  it('缺失包列表缺失 → 空数组', async () => {
    envApi.check.mockResolvedValue({
      system: { python_version: '3.11', platform: 'Linux', env_mode: 'production' },
      packages: { a: '1' },
    })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.missingPackages).toEqual([])
    expect(vm.installedCount).toBe(1)
  })

  it('检查失败 → 错误提示', async () => {
    envApi.check.mockRejectedValue({ message: '检查服务异常' })
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('检查服务异常')
    expect((w.vm as any).checkError).toBe('检查服务异常')
    expect((w.vm as any).checking).toBe(false)
  })

  it('检查失败无 message → 默认文案', async () => {
    envApi.check.mockRejectedValue({})
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('环境检查失败')
    expect((w.vm as any).checkError).toBe('环境检查失败')
  })

  it('依赖过滤：无数据 → 空数组；关键字过滤', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.filteredDependencies.length).toBe(3)
    vm.pkgFilter = 'FAST'
    await nextTick()
    expect(vm.filteredDependencies.length).toBe(1)
    expect(vm.filteredDependencies[0].name).toBe('fastapi')
    vm.pkgFilter = ''
    expect(vm.filteredDependencies.length).toBe(3)
    vm.envData = null
    await nextTick()
    expect(vm.filteredDependencies).toEqual([])
    expect(vm.installedCount).toBe(0)
    expect(vm.healthScore).toBe('--')
    expect(vm.healthClass).toBe('')
  })

  it('搜索输入框 v-model + 重新检查按钮', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const input = w.find('.el-input-stub')
    await input.setValue('sql')
    expect(vm.pkgFilter).toBe('sql')
    const recheckBtn = w
      .findAll('button')
      .find((b) => b.text().includes('重新检查'))
    await recheckBtn!.trigger('click')
    expect(envApi.check).toHaveBeenCalled()
  })

  it('空状态：无数据无错误 → 提示点击检查', async () => {
    envApi.check.mockRejectedValue({})
    const w = await mountComp()
    const vm = w.vm as any
    vm.envData = null
    vm.checkError = ''
    await nextTick()
    expect(w.find('.el-empty-stub').exists()).toBe(true)
  })
})

describe('EnvCheck.vue 依赖筛选兜底分支', () => {
  it('依赖包无名称 → 筛选不报错（空名兜底）', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.envData = { packages: { '': '1.0', axios: '1.6.0' } }
    vm.missingPackages = ['axios']
    vm.pkgFilter = 'ax'
    await nextTick()
    expect(vm.filteredDependencies.length).toBe(1)
    expect(vm.filteredDependencies[0].name).toBe('axios')
  })
})
