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

    <!-- 菜单树选择 -->
    <el-tree
      ref="menuTreeRef"
      :data="menuTreeData"
      show-checkbox
      node-key="key"
      :check-strictly="false"
      :default-expand-all="true"
      :default-checked-keys="selectedMenuKeys || []"
      :props="{ label: 'label', children: 'children' }"
      style="margin-top: 12px"
      @check="onMenuCheck"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
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

async function loadUserMenuConfig() {
  if (!props.userId) return
  try {
    const res = await get(`/menus/user-menus/${props.userId}`)
    const data = res.data || res
    if (data && data.menu_keys !== null && data.menu_keys !== undefined) {
      // 用户有自定义配置 → 显示当前配置
      selectedMenuKeys.value = data.menu_keys
    } else {
      // 无自定义配置 → 显示角色默认菜单（空数组 = 未自定义）
      selectedMenuKeys.value = props.roleDefaultKeys || []
    }
  } catch {
    selectedMenuKeys.value = props.currentMenuKeys || []
  }
}

function onMenuCheck(_node: any, checked: any) {
  selectedMenuKeys.value = (checked?.checkedKeys || checked) as string[]
}

function resetToDefault() {
  // 设为 null 表示"恢复角色默认菜单"——后端 len==0 会清空所有菜单
  selectedMenuKeys.value = null as any
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
    if (keys) selectedMenuKeys.value = keys
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
