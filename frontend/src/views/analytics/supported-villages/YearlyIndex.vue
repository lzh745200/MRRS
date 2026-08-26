<template>
  <div class="yearly-index-page">
    <div class="page-header">
      <h2>年度数据概览</h2>
      <p class="subtitle">选择一个帮扶村查看其年度数据</p>
    </div>

    <el-table v-loading="loading" :data="villages" stripe @row-click="goYearly">
      <el-table-column prop="village_name" label="帮扶村" min-width="140" />
      <el-table-column prop="department" label="部门" min-width="100" />
      <el-table-column prop="county" label="所在县" min-width="100" />
      <el-table-column label="最近年度" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.latest_year" size="small" type="success"
            >{{ row.latest_year }}年</el-tag
          >
          <span v-else class="no-data">暂无</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click.stop="goYearly(row)">
            查看年度数据 →
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { getSupportedVillages } from '@/api/supportedVillage'

const { pushSafe } = useRouterSafe()
const villages = ref<any[]>([])
const loading = ref(false)

async function loadVillages() {
  loading.value = true
  try {
    const resp: any = await getSupportedVillages({ page_size: 100, page: 1 })
    villages.value = resp?.items || resp?.data?.items || resp || []
    for (const v of villages.value) {
      v.latest_year =
        v.latest_year ||
        (v.yearly_data ? Math.max(...Object.keys(v.yearly_data).map(Number)) : null)
    }
  } catch {
    villages.value = []
  } finally {
    loading.value = false
  }
}

function goYearly(row: any) {
  pushSafe(`/supported-villages/${row.id}/yearly`)
}

onMounted(loadVillages)
</script>

<style scoped>
.yearly-index-page {
  padding: 20px;
}
.page-header {
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0 0 4px 0;
  font-size: 20px;
}
.subtitle {
  color: var(--color-info);
  font-size: 14px;
  margin: 0;
}
.no-data {
  color: var(--color-text-placeholder, #c0c4cc);
  font-size: 13px;
}
</style>
