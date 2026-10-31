/**
 * 回归测试：组织下拉与 Element Plus TreeSelect 的数据契约（真实组件，非桩）。
 *
 * 缺陷背景（2026-10-31 现场报障「新增组织后新增用户，无法选择组织，提示
 * 管理员必须指定所属组织」）：
 *   `el-tree-select` 取值默认走节点 `value` 字段，而组织树节点归一化后只有 `id`
 *   （见 `utils/treeNormalizer.ts`）。模板只映射了 label/children、也没有 `node-key`，
 *   于是每个节点的 key/value 都是 `undefined`：
 *     - 点击节点 → `ElSelect` 用 `undefined` 作为选项值，v-model 写不回；
 *     - 表单 `organization_id` 恒为空 → 命中「管理员必须指定所属组织」前端校验。
 *   修复：`ORG_TREE_SELECT_PROPS` 显式 `value: 'id'` + 模板 `node-key="id"`。
 *
 * 为什么必须用真实组件：`src/test/setup.ts` 把 `el-tree-select`/`el-select`/`el-tree`
 * 全局打桩，桩不参与取值，所以既有单测全绿也发现不了本缺陷（这正是线上漏出的原因）。
 * 本文件按需逐层关桩，直击真实取值链路。
 */
import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, ref, h } from 'vue'
import { ElTreeSelect } from 'element-plus'
import { normalizeTreeNodes, ORG_TREE_SELECT_PROPS } from '@/utils/treeNormalizer'

/** 后端 /organizations/tree 的真实节点形态（归一化前） */
const RAW_TREE = [{ id: '13', name: '新组织', children: [] }]

/** 关掉 setup.ts 对本次链路相关组件的全局桩，拿到真实 select/tree */
const REAL_STUBS = {
  'el-tree-select': false,
  'el-select': false,
  'el-tree': false,
  'el-option': false,
  'el-input': false,
  'el-tag': false,
  'el-tooltip': false,
  'el-scrollbar': false,
  'el-icon': false,
  'el-checkbox': false,
  'el-empty': false,
  'el-popover': false,
} as const

function makeHost() {
  return defineComponent({
    setup() {
      const value = ref<any>(null)
      const data = normalizeTreeNodes(RAW_TREE as any)
      return () =>
        h('div', [
          h(ElTreeSelect, {
            modelValue: value.value,
            'onUpdate:modelValue': (v: any) => (value.value = v),
            data,
            props: ORG_TREE_SELECT_PROPS,
            nodeKey: 'id',
            checkStrictly: true,
            teleported: false,
          }),
          h('span', { class: 'current' }, String(value.value)),
        ])
    },
  })
}

describe('组织下拉数据契约（真实 Element Plus）', () => {
  it('ElTree 的 nodeKey 必须映射到 id，点击节点写回该组织 id', async () => {
    const wrapper = mount(makeHost(), {
      global: { stubs: { ...REAL_STUBS } },
      attachTo: document.body,
    })
    await flushPromises()

    const tree = wrapper.findComponent({ name: 'ElTree' })
    expect(tree.exists()).toBe(true)
    // nodeKey 若回落成默认 'value'，节点取值即 undefined（本缺陷的直接成因）
    expect(tree.props('nodeKey')).toBe('id')

    // 驱动 el-tree-select 内部真实监听的 node-click 事件
    const data = normalizeTreeNodes(RAW_TREE as any)
    tree.vm.$emit('node-click', data[0], { isLeaf: true, visible: true }, { proxy: {} })
    await flushPromises()

    // 节点 id 经 normalizeTreeNodes 带 `_` 前缀；提交时由 toOrgIdPayload 还原为 13
    expect(wrapper.find('.current').text()).toBe('_13')
    wrapper.unmount()
  })
})
