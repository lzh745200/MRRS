<template>
  <div class="help-center">
    <!-- 搜索栏 -->
    <div class="help-header">
      <h2 class="help-title">帮助中心</h2>
      <div class="search-bar">
        <el-input
          v-model="searchQuery"
          placeholder="搜索帮助文档..."
          :prefix-icon="Search"
          size="large"
          clearable
          class="search-input"
          @keyup.enter="doSearch"
        >
          <template #append>
            <el-button :icon="Search" :loading="searching" @click="doSearch"> 搜索 </el-button>
          </template>
        </el-input>
      </div>
    </div>

    <!-- 搜索结果 -->
    <div v-if="searchResults.length > 0 && searchQuery" class="search-results-section">
      <el-card>
        <template #header>
          <div class="section-header">
            <span>搜索结果 ({{ searchTotal }} 条)</span>
            <el-button type="primary" link @click="clearSearch">清除</el-button>
          </div>
        </template>
        <div
          v-for="item in searchResults"
          :key="item.id"
          class="search-result-item"
          @click="viewArticle(item)"
        >
          <h4>{{ item.title }}</h4>
          <el-tag size="small" type="info" style="margin-right: 8px">{{ item.category }}</el-tag>
          <span class="search-snippet" v-html="highlightKeyword(item.snippet)" />
        </div>
        <el-empty v-if="searchTotal === 0" description="未找到相关文档" />
      </el-card>
    </div>

    <!-- 主内容区 -->
    <div v-if="!searchQuery || searchResults.length === 0" class="help-body">
      <!-- 左侧分类树 -->
      <div class="help-sidebar">
        <el-card class="sidebar-card">
          <template #header>
            <span>文档分类</span>
          </template>
          <div class="category-list">
            <div
              v-for="cat in categories"
              :key="cat.key"
              class="category-item"
              :class="{ active: activeCategory === cat.key }"
              @click="selectCategory(cat.key)"
            >
              <span class="category-name">{{ cat.name }}</span>
              <el-tag size="small" type="info">{{ cat.count }}</el-tag>
            </div>
          </div>
          <el-empty
            v-if="categories.length === 0 && !loadingCategories"
            description="暂无分类"
            :image-size="40"
          />
        </el-card>
      </div>

      <!-- 右侧内容区 -->
      <div class="help-content">
        <!-- 文章列表 -->
        <el-card v-if="viewMode === 'list'" class="content-card">
          <template #header>
            <div class="section-header">
              <span>{{ activeCategoryName || '全部文档' }}</span>
              <span class="article-count">共 {{ articlesTotal }} 篇</span>
            </div>
          </template>

          <el-table
            v-loading="loadingArticles"
            :data="articles"
            stripe
            style="cursor: pointer"
            @row-click="viewArticle"
          >
            <el-table-column prop="title" label="标题" min-width="250">
              <template #default="{ row }">
                <el-link type="primary" :underline="false">{{ row.title }}</el-link>
              </template>
            </el-table-column>
            <el-table-column prop="category" label="分类" width="120">
              <template #default="{ row }">
                <el-tag size="small">{{ row.category }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="标签" min-width="200">
              <template #default="{ row }">
                <el-tag
                  v-for="tag in row.tags"
                  :key="tag"
                  size="small"
                  type="info"
                  style="margin-right: 4px"
                >
                  {{ tag }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
          </el-table>

          <el-pagination
            v-if="articlesTotal > pageSize"
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="articlesTotal"
            layout="prev, pager, next"
            class="pagination"
            @current-change="loadArticles"
          />

          <el-empty v-if="!loadingArticles && articles.length === 0" description="暂无文档" />
        </el-card>

        <!-- 文章详情 -->
        <el-card v-if="viewMode === 'detail'" class="content-card">
          <template #header>
            <div class="section-header">
              <el-button type="primary" link :icon="ArrowLeft" @click="backToList">
                返回列表
              </el-button>
              <span style="flex: 1; text-align: center">{{ articleDetail?.title }}</span>
              <el-tag size="small">{{ articleDetail?.category }}</el-tag>
            </div>
          </template>

          <div v-if="articleDetail" class="article-detail">
            <div v-if="articleDetail.tags?.length" class="article-tags">
              <el-tag
                v-for="tag in articleDetail.tags"
                :key="tag"
                size="small"
                type="info"
                style="margin-right: 8px"
              >
                {{ tag }}
              </el-tag>
            </div>
            <!-- 结构化分层渲染：识别【小标题】分段 + 目录导航 -->
            <div v-if="articleSections.length > 1" class="article-toc">
              <span class="toc-label">目录</span>
              <a
                v-for="(sec, i) in articleSections.filter((s) => s.heading)"
                :key="i"
                class="toc-link"
                :href="`#help-sec-${i}`"
                >{{ sec.heading }}</a
              >
            </div>
            <div
              v-for="(sec, i) in articleSections"
              :id="`help-sec-${i}`"
              :key="i"
              class="article-section"
            >
              <h3 v-if="sec.heading" class="article-section-title">{{ sec.heading }}</h3>
              <p v-for="(ln, j) in sec.lines" :key="j" class="article-section-line">{{ ln }}</p>
            </div>
            <div v-if="!articleSections.length" class="article-content" v-html="sanitizedContent" />
          </div>
          <el-empty v-else description="文档加载失败" />
        </el-card>

        <!-- 系统信息 -->
        <el-card v-if="systemInfo && viewMode === 'list'" class="system-info-card">
          <template #header>
            <span>系统信息</span>
          </template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="系统名称">{{ systemInfo.name }}</el-descriptions-item>
            <el-descriptions-item label="简称">{{ systemInfo.short_name }}</el-descriptions-item>
            <el-descriptions-item label="版本">{{ systemInfo.version }}</el-descriptions-item>
            <el-descriptions-item label="说明">{{ systemInfo.description }}</el-descriptions-item>
            <el-descriptions-item label="技术支持">{{
              systemInfo.contact?.technical_support
            }}</el-descriptions-item>
            <el-descriptions-item label="反馈渠道">{{
              systemInfo.contact?.feedback
            }}</el-descriptions-item>
            <el-descriptions-item label="功能特性" :span="2">
              <el-tag
                v-for="feat in systemInfo.features"
                :key="feat"
                size="small"
                type="success"
                style="margin-right: 6px; margin-bottom: 4px"
              >
                {{ feat }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, ArrowLeft } from '@element-plus/icons-vue'
import { helpApi } from '@/api/help'
import { sanitizeHtml } from '@/utils/sanitize'
import type {
  HelpCategory,
  HelpArticleSummary,
  HelpArticle,
  HelpSearchResult,
  SystemInfo,
} from '@/api/help'

type ViewMode = 'list' | 'detail'

const viewMode = ref<ViewMode>('list')
const activeCategory = ref('')
const searchQuery = ref('')
const searching = ref(false)
const loadingCategories = ref(false)
const loadingArticles = ref(false)

const categories = ref<HelpCategory[]>([])
const articles = ref<HelpArticleSummary[]>([])
const articlesTotal = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

const articleDetail = ref<HelpArticle | null>(null)

const searchResults = ref<HelpSearchResult[]>([])
const searchTotal = ref(0)

const systemInfo = ref<SystemInfo | null>(null)

const activeCategoryName = computed(() => {
  const cat = categories.value.find((c) => c.key === activeCategory.value)
  return cat?.name || ''
})

/** 解析纯文本帮助内容为结构化分段：[{heading, lines[]}] */
function parseArticleSections(raw: string): Array<{ heading: string; lines: string[] }> {
  if (!raw) return []
  const sections: Array<{ heading: string; lines: string[] }> = []
  let current: { heading: string; lines: string[] } | null = null
  for (const rawLine of raw.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line) continue
    const head = /^【(.+?)】/.exec(line)
    if (head) {
      current = { heading: head[1], lines: [] }
      sections.push(current)
      const rest = line.slice(head[0].length).trim()
      if (rest) current.lines.push(rest)
    } else if (current) {
      current.lines.push(line)
    } else {
      sections.push({ heading: '', lines: [line] })
    }
  }
  return sections
}

const articleSections = computed(() => parseArticleSections(articleDetail.value?.content || ''))

const sanitizedContent = computed(() => {
  if (!articleDetail.value?.content) return '(无内容)'
  return sanitizeHtml(articleDetail.value.content)
})

async function loadCategories() {
  loadingCategories.value = true
  try {
    const res = await helpApi.getCategories()
    categories.value = res.data?.categories || []
  } catch {
    ElMessage.error('加载分类列表失败')
  } finally {
    loadingCategories.value = false
  }
}

async function loadArticles() {
  loadingArticles.value = true
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (activeCategory.value) params.category = activeCategory.value
    const res = await helpApi.getArticles(params)
    articles.value = res.data?.items || []
    articlesTotal.value = res.data?.total || 0
  } catch {
    ElMessage.error('加载文档列表失败')
  } finally {
    loadingArticles.value = false
  }
}

async function viewArticle(row: { id: number }) {
  if (!row.id) return
  try {
    const res = await helpApi.getArticle(row.id)
    articleDetail.value = res.data || null
    viewMode.value = 'detail'
  } catch {
    ElMessage.error('加载文档详情失败')
  }
}

function selectCategory(key: string) {
  activeCategory.value = key
  currentPage.value = 1
  viewMode.value = 'list'
  articleDetail.value = null
  loadArticles()
}

function backToList() {
  viewMode.value = 'list'
  articleDetail.value = null
}

async function doSearch() {
  const q = searchQuery.value.trim()
  if (!q) {
    searchResults.value = []
    searchTotal.value = 0
    return
  }
  searching.value = true
  try {
    const res = await helpApi.search(q, 20)
    searchResults.value = res.data?.items || []
    searchTotal.value = res.data?.total || 0
  } catch {
    ElMessage.error('搜索失败')
  } finally {
    searching.value = false
  }
}

function clearSearch() {
  searchQuery.value = ''
  searchResults.value = []
  searchTotal.value = 0
}

function highlightKeyword(snippet: string): string {
  if (!searchQuery.value) return sanitizeHtml(snippet || '')
  // 先清理输入，防止 XSS
  const safe = sanitizeHtml(snippet || '')
  const escaped = searchQuery.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return sanitizeHtml(
    safe.replace(
      new RegExp(`(${escaped})`, 'gi'),
      '<span style="background:#fff3cd;padding:0 2px;border-radius:2px">$1</span>'
    )
  )
}

async function loadSystemInfo() {
  try {
    const res = await helpApi.getSystemInfo()
    systemInfo.value = res.data || null
  } catch {
    // 系统信息非必须，静默失败
  }
}

onMounted(() => {
  loadCategories()
  loadArticles()
  loadSystemInfo()
})
</script>

<style scoped lang="scss">
.help-center {
  padding: 20px;
  height: calc(100vh - 100px);
  overflow-y: auto;
}

.help-header {
  text-align: center;
  margin-bottom: 24px;
}

.help-title {
  font-size: 24px;
  font-weight: 600;
  color: #1b4332;
  margin: 0 0 16px;
}

.search-bar {
  max-width: 600px;
  margin: 0 auto;
}

.search-input {
  :deep(.el-input-group__append) {
    padding: 0;
  }
}

/* Search Results */
.search-results-section {
  margin-bottom: 20px;
}

.search-result-item {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: #f5f7fa;
    padding-left: 8px;
  }

  h4 {
    margin: 0 0 8px;
    font-size: 15px;
    color: var(--color-primary);
  }
}

.search-snippet {
  font-size: 13px;
  color: #909399;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* Body Layout */
.help-body {
  display: flex;
  gap: 20px;
}

.help-sidebar {
  width: 220px;
  flex-shrink: 0;
}

.sidebar-card {
  position: sticky;
  top: 20px;
}

.category-list {
  display: flex;
  flex-direction: column;
}

.category-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 8px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.2s;

  &:hover {
    background: #f5f7fa;
  }

  &.active {
    background: var(--color-bg-active);
    color: var(--color-primary);
  }
}

.category-name {
  font-size: 14px;
}

.help-content {
  flex: 1;
  min-width: 0;
}

.content-card {
  margin-bottom: 20px;
}

.article-count {
  font-size: 12px;
  color: #909399;
}

.pagination {
  margin-top: 16px;
  justify-content: center;
}

/* Article Detail */
.article-detail {
  padding: 8px 0;
}

.article-tags {
  margin-bottom: 16px;
}

.article-toc {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  padding: 10px 14px;
  margin-bottom: 16px;
  background: #f2f7f4;
  border: 1px solid #dce8e0;
  border-radius: 6px;

  .toc-label {
    font-weight: 600;
    color: #1b4332;
  }

  .toc-link {
    color: #2e6b55;
    font-size: 13px;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }
}

.article-section {
  margin-bottom: 14px;

  .article-section-title {
    margin: 14px 0 8px;
    font-size: 16px;
    font-weight: 600;
    color: #1b4332;
    padding-left: 10px;
    border-left: 3px solid #c9a227;
  }

  .article-section-line {
    margin: 6px 0;
    line-height: 1.8;
    color: #303133;
    font-size: 14px;
  }
}

.article-content {
  line-height: 1.8;
  color: #303133;
  font-size: 14px;

  :deep(h2),
  :deep(h3) {
    color: #1b4332;
    margin: 16px 0 8px;
  }

  :deep(p) {
    margin: 8px 0;
  }

  :deep(code) {
    background: #f5f7fa;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 13px;
  }

  :deep(pre) {
    background: #303133;
    color: #e0e0e0;
    padding: 16px;
    border-radius: 6px;
    overflow-x: auto;
  }
}

.system-info-card {
  margin-bottom: 0;
}
</style>
