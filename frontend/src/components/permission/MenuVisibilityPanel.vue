<template>
  <div class="menu-visibility-panel">
    <el-alert type="info" :closable="false" style="margin-bottom: 16px">
      配置该用户可见的菜单项。留空表示继承角色默认菜单；清空表示无菜单。
      修改后用户刷新页面即可生效。
    </el-alert>

    <div class="menu-header">
      <span>
        当前用户：<strong>{{ username }}</strong>
      </span>
      <el-space>
        <el-button :disabled="!isCustomized" @click="resetToDefault"> 恢复角色默认 </el-button>
        <el-button type="primary" :loading="saving" @click="saveConfig"> 保存配置 </el-button>
      </el-space>
    </div>

    <!-- 角色默认菜单提示 -->
    <el-alert v-if="isCustomized" type="info" :closable="false" style="margin: 12px 0">
      当前为自定义配置。角色默认包含
      {{ roleDefaultKeys?.length || 0 }} 个菜单。
    </el-alert>

    <!-- 角色默认菜单标签 -->
    <div class="role-default-info">
      <span class="label">角色默认菜单：</span>
      <el-tag v-for="key in roleDefaultKeys" :key="key" style="margin: 2px">
        {{ getMenuLabel(key) }}
      </el-tag>
    </div>

    <!-- 菜单树选择：default-checked-keys 只是渲染期初值，
         异步回填/恢复默认后的选中态由 syncTreeCheckedKeys 显式对齐。
         注意：check-strictly=false（父子联动）配合 displayCheckedKeys 的前沿键策略，
         使"部分勾选的父节点"保持半选而不是被级联成全选。 -->
    <el-tree
      ref="menuTreeRef"
      :data="menuTreeData"
      show-checkbox
      node-key="key"
      :check-strictly="false"
      :default-expand-all="true"
      :default-checked-keys="displayCheckedKeys"
      :props="{ label: 'label', children: 'children' }"
      style="margin-top: 12px"
      @check="onMenuCheck"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { get, put } from '@/api/request'

interface MenuTreeNode {
  key: string
  label: string
  children?: MenuTreeNode[]
}

const props = defineProps<{
  userId: number
  username: string
  role?: string
  roleDefaultKeys?: string[]
  isCustomized?: boolean
  currentMenuKeys?: string[]
}>()

const emit = defineEmits<{
  saved: []
}>()

const menuTreeRef = ref()
const saving = ref(false)
const selectedMenuKeys = ref<string[] | null>([])
const menuTreeData = ref<MenuTreeNode[]>([])

// 程序化同步树勾选期间置位：此间树回传的 check 事件不得再写回 selectedMenuKeys（避免反馈环）
let syncingTree = false

/** child key → 父 key（用于补齐祖先键 / 计算展示前沿） */
const parentMap = computed(() => {
  const map = new Map<string, string>()
  const walk = (nodes: MenuTreeNode[]) => {
    for (const node of nodes) {
      for (const child of node.children || []) {
        map.set(child.key, node.key)
      }
      if (node.children?.length) walk(node.children)
    }
  }
  walk(menuTreeData.value)
  return map
})

/**
 * 树应展示的"前沿"勾选键（交给 el-tree 的键集合）。
 *
 * selectedMenuKeys === null 表示"继承角色默认菜单"（保存时提交 null），
 * 此时树必须展示角色默认菜单——否则"恢复角色默认"后管理员看到的是空选，
 * 与保存结果（恢复为角色默认）不一致。
 *
 * 剔除"有选中后代的祖先键"：el-tree 在 check-strictly=false 下对含子节点的键
 * 会**级联勾选全部后代**，把祖先键交给 setCheckedKeys 会把用户没选的兄弟菜单
 * 也勾上（显示与保存不一致，下一次交互即把兄弟菜单写进用户权限）。
 * 父键由 el-tree 依据子节点自行推导为半选/全选。
 */
const displayCheckedKeys = computed<string[]>(() => {
  const keys = selectedMenuKeys.value ?? props.roleDefaultKeys ?? []
  if (!keys.length) return []
  const ancestorWithSelectedDescendant = new Set<string>()
  for (const key of keys) {
    let parent = parentMap.value.get(key)
    while (parent) {
      ancestorWithSelectedDescendant.add(parent)
      parent = parentMap.value.get(parent)
    }
  }
  return keys.filter((key) => !ancestorWithSelectedDescendant.has(key))
})

// 菜单 key → label 映射
const menuLabelMap = ref<Record<string, string>>({})

function buildLabelMap(nodes: MenuTreeNode[]) {
  for (const node of nodes) {
    menuLabelMap.value[node.key] = node.label
    if (node.children) {
      buildLabelMap(node.children)
    }
  }
}

function getMenuLabel(key: string): string {
  return menuLabelMap.value[key] || key
}

async function loadMenuTree() {
  try {
    const res = await get('/menus/all')
    menuTreeData.value = (res.data || res || []) as MenuTreeNode[]
    buildLabelMap(menuTreeData.value)
  } catch {
    // 使用前端静态配置作为回退
    try {
      const { MENU_CONFIG } = await import('@/config/menu-config')
      menuTreeData.value = MENU_CONFIG as unknown as MenuTreeNode[]
      buildLabelMap(menuTreeData.value)
    } catch {
      menuTreeData.value = []
    }
  }
}

/**
 * 把选中态显式同步到树。
 *
 * el-tree 的 default-checked-keys 只在渲染期生效（异步赋值/外部 watcher/恢复默认都不会重放），
 * 不同步会让树勾选与 saveConfig 提交的内容不一致（管理员看到 A、提交 B）。
 */
async function syncTreeCheckedKeys() {
  await nextTick()
  const tree = menuTreeRef.value as { setCheckedKeys?: (keys: string[]) => void } | undefined
  // 树未渲染（组件已卸载）或测试桩未实现 setCheckedKeys 时跳过
  if (typeof tree?.setCheckedKeys !== 'function') return
  syncingTree = true
  try {
    tree.setCheckedKeys(displayCheckedKeys.value)
  } finally {
    syncingTree = false
  }
}

async function loadUserMenuConfig() {
  if (!props.userId) return
  try {
    const res = await get(`/menus/user-menus/${props.userId}`)
    const data = res.data || res
    const menuKeys = data?.menu_keys
    if (Array.isArray(menuKeys)) {
      // 用户有自定义配置 → 显示当前配置
      selectedMenuKeys.value = menuKeys
    } else if (menuKeys === null || menuKeys === undefined) {
      // 无自定义配置 → 显示角色默认菜单（空数组 = 未自定义）
      selectedMenuKeys.value = props.roleDefaultKeys || []
    } else {
      // 畸形载荷（字符串/对象）绝不能当作选中集合：会污染树态并原样提交给后端
      selectedMenuKeys.value = []
    }
  } catch {
    selectedMenuKeys.value = Array.isArray(props.currentMenuKeys) ? props.currentMenuKeys : []
  }
  await syncTreeCheckedKeys()
}

/**
 * 树勾选回调。
 *
 * 必须把 halfCheckedKeys（半选祖先）一并保存：后端 _filter_menu_tree 只保留
 * "key 在白名单里"的节点，父键缺失会连同子菜单一起被裁掉 —— 管理员看到
 * 子菜单已勾选、保存成功，用户却拿不到任何菜单（静默失效）。
 */
function onMenuCheck(_node: any, checked: any) {
  // 程序化同步（setCheckedKeys）回传的 check 事件直接丢弃，避免与选中态互相覆盖
  if (syncingTree) return
  const checkedKeys = Array.isArray(checked?.checkedKeys)
    ? checked.checkedKeys
    : Array.isArray(checked)
      ? checked
      : []
  const halfCheckedKeys = Array.isArray(checked?.halfCheckedKeys) ? checked.halfCheckedKeys : []
  const merged = new Set<string>([...checkedKeys, ...halfCheckedKeys])
  // 兜底补齐祖先链（畸形/裁剪载荷下 halfCheckedKeys 可能缺失）
  for (const key of Array.from(merged)) {
    let parent = parentMap.value.get(key)
    while (parent) {
      merged.add(parent)
      parent = parentMap.value.get(parent)
    }
  }
  selectedMenuKeys.value = Array.from(merged)
  // 展示态与保存集合对齐（strict=false 下按前沿键精确回填，不级联兄弟节点）
  void syncTreeCheckedKeys()
}

function resetToDefault() {
  // 设为 null 表示"恢复角色默认菜单"——后端把 allowed_menus 清空（提交 null，不是空数组）
  selectedMenuKeys.value = null
  // 树同步展示角色默认菜单，与保存语义保持一致
  void syncTreeCheckedKeys()
}

async function saveConfig() {
  saving.value = true
  try {
    // null → 恢复角色默认；[] → 清空所有菜单；[...] → 自定义
    await put(`/menus/user-menus/${props.userId}`, {
      menu_keys: selectedMenuKeys.value,
    })
    emit('saved')
    ElMessage.success('菜单配置保存成功')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

watch(
  () => props.currentMenuKeys,
  (keys) => {
    // 只接受数组：非数组载荷会污染选中集合与保存内容
    if (Array.isArray(keys)) selectedMenuKeys.value = keys
  }
)

onMounted(async () => {
  await loadMenuTree()
  await loadUserMenuConfig()
})

defineExpose({ loadUserMenuConfig })
</script>

<style scoped lang="scss">
.menu-visibility-panel {
  .menu-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
  }
  .role-default-info {
    padding: 8px 0;
    .label {
      color: var(--el-text-color-secondary);
      font-size: 13px;
      margin-right: 8px;
    }
  }
}
</style>
