<template>
  <div class="menu-page">
    <el-card>
      <template #header>
        <div class="page-header">
          <span class="page-title">菜单管理</span>
          <el-tag type="info">当前菜单数: {{ menuCount }}</el-tag>
        </div>
      </template>
      <el-alert type="info" :closable="false" style="margin-bottom: 16px">
        以下是系统菜单结构（单机版菜单由路由配置自动生成，无需动态管理）
      </el-alert>
      <el-table
        :data="menuTree"
        row-key="path"
        border
        default-expand-all
        :tree-props="{ children: 'children', hasChildren: 'hasChildren' }"
      >
        <el-table-column prop="title" label="菜单名称" min-width="200">
          <template #default="{ row }">
            <el-icon v-if="row.icon" style="margin-right: 6px; vertical-align: middle">
              <component :is="row.icon" />
            </el-icon>
            <span>{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="路由路径" min-width="220" />
        <el-table-column prop="name" label="路由名称" width="180" />
        <el-table-column label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.hidden" type="info" size="small">隐藏</el-tag>
            <el-tag v-else type="success" size="small">显示</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="权限" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.requiresAdmin" type="warning" size="small">管理员</el-tag>
            <el-tag v-else size="small">所有人</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

interface MenuItem {
  path: string
  name: string
  title: string
  icon?: string
  hidden: boolean
  requiresAdmin: boolean
  children?: MenuItem[]
  hasChildren?: boolean
}

const menuTree = computed<MenuItem[]>(() => {
  const mainRoute = router.options.routes.find((r) => r.path === '/')
  if (!mainRoute?.children) return []
  return mainRoute.children
    .filter((child) => child.meta?.title)
    .map(
      (child): MenuItem => ({
        path: `/${child.path}`,
        name: String(child.name || ''),
        /* c8 ignore next */ // 不可达：上方 filter(child.meta?.title) 已保证 meta.title 为真值
        title: String(child.meta?.title || ''),
        icon: String(child.meta?.icon || ''),
        hidden: !!child.meta?.hidden,
        requiresAdmin: !!child.meta?.requiresAdmin,
        children: undefined,
        hasChildren: false,
      })
    )
})

const menuCount = computed(() => menuTree.value.length)
</script>

<style lang="scss" scoped>
.menu-page {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.page-title {
  font-size: 16px;
  font-weight: bold;
}
</style>
