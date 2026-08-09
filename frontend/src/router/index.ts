import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { retryImport } from '@/composables/useChunkLoader'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard',
  },
  // ── 公共路由（无导航栏）──
  {
    path: '/login',
    name: 'Login',
    component: () => retryImport(() => import('@/views/auth/LoginEnhanced.vue')),
    meta: { title: '登录', noAuth: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => retryImport(() => import('@/views/auth/Register.vue')),
    meta: { title: '注册', noAuth: true },
  },
  {
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => retryImport(() => import('@/views/auth/ForgotPassword.vue')),
    meta: { title: '忘记密码', noAuth: true },
  },
  {
    path: '/get-machine-code',
    name: 'GetMachineCode',
    component: () => retryImport(() => import('@/views/auth/GetMachineCode.vue')),
    meta: { title: '获取机器码', noAuth: true },
  },
  {
    path: '/change-password',
    name: 'ChangePassword',
    component: () => retryImport(() => import('@/views/auth/ChangePassword.vue')),
    meta: { title: '修改密码', noAuth: true },
  },
  // ── 帮扶成效大屏（汇报模式，无导航栏独立全屏页）──
  {
    path: '/bigscreen',
    name: 'BigScreen',
    component: () => retryImport(() => import('@/views/bigscreen/BigScreen.vue')),
    meta: { title: '帮扶成效大屏' },
  },
  // ── 主布局（带侧边导航栏）──
  {
    path: '/',
    component: () => retryImport(() => import('@/layouts/DefaultLayoutSafe.vue')),
    children: [
      {
        path: '/profile',
        name: 'Profile',
        component: () => retryImport(() => import('@/views/auth/Profile.vue')),
        meta: { title: '个人中心' },
      },
      {
        path: '/profile/two-factor',
        name: 'TwoFactorSettings',
        component: () => retryImport(() => import('@/views/auth/TwoFactorSettings.vue')),
        meta: { title: '双因素认证' },
      },
      // ── 工作台 ──
      {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => retryImport(() => import('@/views/dashboard/index.vue')),
        meta: { title: '工作台' },
      },
      // ── 帮扶学校 ──
      {
        path: '/schools',
        name: 'Schools',
        component: () => retryImport(() => import('@/views/schools/List.vue')),
        meta: { title: '帮扶学校管理' },
      },
      {
        path: '/schools/create',
        name: 'SchoolCreate',
        component: () => retryImport(() => import('@/views/schools/Edit.vue')),
        meta: { title: '添加学校' },
      },
      {
        path: '/schools/:id',
        name: 'SchoolDetail',
        component: () => retryImport(() => import('@/views/schools/Detail.vue')),
        meta: { title: '学校详情' },
      },
      {
        path: '/schools/:id/edit',
        name: 'SchoolEdit',
        component: () => retryImport(() => import('@/views/schools/Edit.vue')),
        meta: { title: '编辑学校' },
      },
      {
        path: '/schools/:id/projects',
        name: 'SchoolProjects',
        component: () => retryImport(() => import('@/views/schools/Projects.vue')),
        meta: { title: '助学兴教项目' },
      },
      {
        path: '/schools/:id/scholarship',
        name: 'SchoolScholarship',
        component: () => retryImport(() => import('@/views/schools/Scholarship.vue')),
        meta: { title: '资助学生管理' },
      },
      {
        path: '/schools/analysis',
        name: 'SchoolAnalysis',
        component: () => retryImport(() => import('@/views/schools/Analysis.vue')),
        meta: { title: '学校分析' },
      },
      // ── 帮扶项目 ──
      {
        path: '/projects',
        name: 'Projects',
        component: () => retryImport(() => import('@/views/projects/List.vue')),
        meta: { title: '帮扶项目管理' },
      },
      {
        path: '/projects/create',
        name: 'ProjectCreate',
        component: () => retryImport(() => import('@/views/projects/Edit.vue')),
        meta: { title: '添加项目' },
      },
      {
        path: '/projects/:id',
        name: 'ProjectDetail',
        component: () => retryImport(() => import('@/views/projects/Detail.vue')),
        meta: { title: '项目详情' },
      },
      {
        path: '/projects/:id/edit',
        name: 'ProjectEdit',
        component: () => retryImport(() => import('@/views/projects/Edit.vue')),
        meta: { title: '编辑项目' },
      },
      {
        path: '/projects/import',
        name: 'ProjectImport',
        component: () => retryImport(() => import('@/views/projects/Import.vue')),
        meta: { title: '导入项目' },
      },
      {
        path: '/projects/:id/progress',
        name: 'ProjectProgress',
        component: () => retryImport(() => import('@/views/projects/ProgressGallery.vue')),
        meta: { title: '项目进度' },
      },
      {
        path: '/projects/management',
        name: 'ProjectManagement',
        component: () => retryImport(() => import('@/views/projects/ProjectManagement.vue')),
        meta: { title: '项目管控' },
      },
      // ── 帮扶村 ── （含旧路径重定向）
      { path: '/villages', redirect: '/supported-villages' },
      {
        path: '/supported-villages/yearly',
        name: 'YearlyIndex',
        component: () => import('@/views/analytics/supported-villages/YearlyIndex.vue'),
        meta: { title: '年度概览' },
      },
      {
        path: '/villages/:id',
        redirect: (to: any) => `/supported-villages/${to.params.id}`,
      },
      {
        path: '/villages/:id/yearly-data',
        redirect: (to: any) => `/supported-villages/${to.params.id}/yearly`,
      },
      {
        path: '/villages/:id/yearly',
        redirect: (to: any) => `/supported-villages/${to.params.id}/yearly`,
      },
      {
        path: '/villages/:id/edit',
        redirect: (to: any) => `/supported-villages/${to.params.id}?mode=edit`,
      },
      {
        path: '/supported-villages',
        name: 'SupportedVillages',
        component: () => import('@/views/analytics/supported-villages/List.vue'),
        meta: { title: '帮扶村管理' },
      },
      {
        path: '/supported-villages/:id',
        name: 'SupportedVillageDetail',
        component: () => import('@/views/analytics/supported-villages/Detail.vue'),
        meta: { title: '帮扶村详情' },
      },
      {
        path: '/supported-villages/:id/yearly',
        name: 'SupportedVillagesYearly',
        component: () => import('@/views/analytics/supported-villages/YearlyOverview.vue'),
        meta: { title: '年度概览' },
      },
      // ── 帮扶资金 ──
      {
        path: '/funds',
        name: 'Funds',
        component: () => retryImport(() => import('@/views/funds/EnhancedList.vue')),
        meta: { title: '经费管理' },
      },
      {
        path: '/funds/create',
        name: 'FundCreate',
        component: () => retryImport(() => import('@/views/funds/Detail.vue')),
        meta: { title: '经费登记' },
      },
      {
        path: '/funds/:id',
        name: 'FundDetail',
        component: () => retryImport(() => import('@/views/funds/Detail.vue')),
        meta: { title: '经费详情' },
      },
      {
        path: '/funds/:id/edit',
        name: 'FundEdit',
        component: () => retryImport(() => import('@/views/funds/Detail.vue')),
        meta: { title: '编辑经费' },
      },
      {
        path: '/funds/analysis',
        name: 'FundAnalysis',
        component: () => retryImport(() => import('@/views/funds/Analysis.vue')),
        meta: { title: '经费分析' },
      },
      {
        path: '/funds/budget',
        name: 'FundBudget',
        component: () => retryImport(() => import('@/views/funds/Budget.vue')),
        meta: { title: '预算管理' },
      },
      {
        path: '/funds/contract',
        name: 'FundContract',
        component: () => retryImport(() => import('@/views/funds/ContractManage.vue')),
        meta: { title: '合同管理' },
      },
      {
        path: '/funds/anomaly',
        name: 'FundAnomaly',
        component: () => retryImport(() => import('@/views/funds/AnomalyList.vue')),
        meta: { title: '异常资金' },
      },
      {
        path: '/funds/lifecycle',
        name: 'FundLifecycle',
        component: () => retryImport(() => import('@/views/funds/Lifecycle.vue')),
        meta: { title: '资金周期' },
      },
      {
        path: '/funds/lifecycle/:projectId',
        name: 'FundLifecycleDetail',
        component: () => retryImport(() => import('@/views/funds/Lifecycle.vue')),
        meta: { title: '资金周期' },
      },
      {
        path: '/funds/report',
        name: 'FundReport',
        component: () => retryImport(() => import('@/views/funds/Report.vue')),
        meta: { title: '资金报告' },
      },
      {
        path: '/funds/apply',
        redirect: '/funds/user',
      },
      {
        path: '/funds/user',
        name: 'FundUserList',
        component: () => retryImport(() => import('@/views/funds/UserFundList.vue')),
        meta: { title: '经费申请' },
      },
      {
        path: '/funds/transfer',
        name: 'FundTransfer',
        component: () => retryImport(() => import('@/views/funds/TransferVoucher.vue')),
        meta: { title: '转账凭证' },
      },
      {
        path: '/funds/settlement',
        name: 'FundSettlement',
        component: () => retryImport(() => import('@/views/funds/Settlement.vue')),
        meta: { title: '结算管理' },
      },
      {
        path: '/funds/settlement/:projectId',
        name: 'FundSettlementDetail',
        component: () => retryImport(() => import('@/views/funds/Settlement.vue')),
        meta: { title: '结算管理' },
      },
      // ── 帮扶政策 ──
      {
        path: '/policies',
        name: 'Policies',
        component: () => retryImport(() => import('@/views/policies/List.vue')),
        meta: { title: '帮扶政策' },
      },
      {
        path: '/policies/create',
        name: 'PolicyCreate',
        component: () => retryImport(() => import('@/views/policies/Edit.vue')),
        meta: { title: '添加政策' },
      },
      {
        path: '/policies/search',
        name: 'PolicySearch',
        component: () => retryImport(() => import('@/views/policies/Search.vue')),
        meta: { title: '政策高级搜索' },
      },
      {
        path: '/policies/categories',
        name: 'PolicyCategories',
        component: () => retryImport(() => import('@/views/policies/Category.vue')),
        meta: { title: '政策分类总览' },
      },
      {
        path: '/policies/:id',
        name: 'PolicyDetail',
        component: () => retryImport(() => import('@/views/policies/Detail.vue')),
        meta: { title: '政策详情' },
      },
      {
        path: '/policies/:id/edit',
        name: 'PolicyEdit',
        component: () => retryImport(() => import('@/views/policies/Edit.vue')),
        meta: { title: '编辑政策' },
      },
      // ── 审批工作流 ──
      {
        path: '/approval',
        name: 'Approval',
        component: () => retryImport(() => import('@/views/approval/Overview.vue')),
        meta: { title: '审批管理' },
      },
      {
        path: '/approval/pending',
        name: 'ApprovalPending',
        component: () => retryImport(() => import('@/views/approval/PendingList.vue')),
        meta: { title: '待审批' },
      },
      {
        path: '/approval/my',
        name: 'ApprovalMy',
        component: () => retryImport(() => import('@/views/approval/MyApplications.vue')),
        meta: { title: '我的申请' },
      },
      {
        path: '/approval/history',
        name: 'ApprovalHistory',
        component: () => retryImport(() => import('@/views/approval/History.vue')),
        meta: { title: '审批历史' },
      },
      {
        path: '/approval/center',
        name: 'ApprovalCenter',
        component: () => retryImport(() => import('@/views/approval/ApprovalCenter.vue')),
        meta: { title: '审批中心' },
      },
      // ── 乡村振兴工作 ──
      {
        path: '/rural-works',
        name: 'RuralWorks',
        component: () => retryImport(() => import('@/views/ruralWorks/Index.vue')),
        meta: { title: '乡村振兴' },
      },
      {
        path: '/rural-works/list',
        name: 'RuralWorksList',
        component: () => retryImport(() => import('@/views/ruralWorks/List.vue')),
        meta: { title: '乡村工作列表' },
      },
      {
        path: '/rural-works/analysis',
        name: 'RuralWorksAnalysis',
        component: () => retryImport(() => import('@/views/ruralWorks/Analysis.vue')),
        meta: { title: '乡村工作分析' },
      },
      {
        path: '/work-calendar',
        name: 'WorkCalendar',
        component: () => retryImport(() => import('@/views/work-calendar/Index.vue')),
        meta: { title: '工作日历' },
      },
      // ── 驻村工作台（打卡+月度总结） ──
      {
        path: '/rural-works/checkin',
        name: 'CheckinWorkbench',
        component: () => retryImport(() => import('@/views/ruralWorks/checkin/Index.vue')),
        meta: { title: '驻村工作台' },
      },
      // ── 组织机构 ──
      {
        path: '/organizations',
        alias: '/organization',
        name: 'Organization',
        component: () => retryImport(() => import('@/views/organization/List.vue')),
        meta: { title: '组织机构' },
      },
      {
        path: '/organizations/pass-code',
        alias: '/organization/pass-code',
        name: 'OrganizationPassCode',
        // 整合：通行码管理并入「机器码管理」板块（功能完整保留）
        redirect: '/admin/machine-code/management',
      },
      {
        path: '/organizations/:id',
        alias: '/organization/:id',
        name: 'OrganizationDetail',
        component: () => retryImport(() => import('@/views/organization/Detail.vue')),
        meta: { title: '机构详情' },
      },
      {
        path: '/organizations/:id/edit',
        alias: '/organization/:id/edit',
        name: 'OrganizationEdit',
        component: () => retryImport(() => import('@/views/organization/Edit.vue')),
        meta: { title: '编辑机构' },
      },
      // ── 数据同步 ──
      {
        path: '/data-sync',
        name: 'DataSync',
        redirect: '/data-sync/export',
        meta: { title: '数据同步' },
      },
      {
        path: '/data-sync/export',
        name: 'DataSyncExport',
        component: () => retryImport(() => import('@/views/dataSync/Export.vue')),
        meta: { title: '数据导出' },
      },
      {
        path: '/data-sync/import',
        name: 'DataSyncImport',
        component: () => retryImport(() => import('@/views/dataSync/Import.vue')),
        meta: { title: '数据导入' },
      },
      {
        path: '/data-sync/conflicts',
        name: 'DataSyncConflicts',
        component: () => retryImport(() => import('@/views/dataSync/ConflictResolution.vue')),
        meta: { title: '冲突解决' },
      },
      // ── 数据包管理 ──
      {
        path: '/data-package',
        name: 'DataPackage',
        component: () => retryImport(() => import('@/views/dataPackage/List.vue')),
        meta: { title: '数据包管理' },
      },
      {
        path: '/data-package/report',
        name: 'DataPackageReport',
        component: () => retryImport(() => import('@/views/dataPackage/ReportPackage.vue')),
        meta: { title: '数据上报' },
      },
      {
        path: '/data-package/version',
        name: 'DataPackageVersion',
        component: () => retryImport(() => import('@/views/dataPackage/PackageVersion.vue')),
        meta: { title: '版本管理' },
      },
      {
        path: '/data-package/update',
        name: 'DataPackageUpdate',
        component: () => retryImport(() => import('@/views/dataPackage/IncrementalUpdate.vue')),
        meta: { title: '增量更新' },
      },
      // ── 数据管理 ──
      {
        path: '/data-management',
        name: 'DataManagement',
        component: () => retryImport(() => import('@/views/dataManagement/Index.vue')),
        meta: { title: '数据管理' },
      },
      // /data-management/backup 和 /data-management/logs 已整合到系统管理模块
      // 重定向定义见下方"旧版路径兼容重定向"区域
      // ── 数据分析 ──
      {
        path: '/data-analysis',
        name: 'DataAnalysis',
        component: () => retryImport(() => import('@/views/dataAnalysis/Index.vue')),
        meta: { title: '数据分析' },
      },
      {
        path: '/data-analysis/dashboard',
        name: 'DataDashboard',
        component: () => retryImport(() => import('@/views/analytics/dashboard/Dashboard.vue')),
        meta: { title: '分析仪表板' },
      },
      {
        path: '/data-analysis/map',
        name: 'DataMap',
        component: () => retryImport(() => import('@/views/analytics/map/index.vue')),
        meta: { title: '地图可视化' },
      },
      {
        path: '/data-analysis/assessment',
        name: 'DataAssessment',
        component: () => retryImport(() => import('@/views/analytics/Assessment.vue')),
        meta: { title: '成效评估' },
      },
      {
        path: '/data-analysis/reports',
        name: 'DataReports',
        component: () => retryImport(() => import('@/views/analytics/reports/WorkAnalysis.vue')),
        meta: { title: '工作分析报告' },
      },
      // ── 旧版路径兼容重定向 ──
      { path: '/analytics/map', redirect: '/data-analysis/map' },
      { path: '/analytics/dashboard', redirect: '/data-analysis/dashboard' },
      { path: '/analytics/work-analysis', redirect: '/data-analysis/reports' },
      { path: '/analytics/assessment', redirect: '/data-analysis/assessment' },
      { path: '/data-entry/comprehensive', redirect: '/data-entry' },
      { path: '/report-export', redirect: '/export/report' },
      // 模块整合重定向：旧路径统一收口到新入口
      { path: '/data-management/backup', redirect: '/system/backup', meta: { title: '数据备份' } },
      { path: '/data-management/logs', redirect: '/system/audit', meta: { title: '操作日志' } },
      { path: '/data-import/batch', redirect: '/data-package' },
      {
        path: '/data-package/receive',
        name: 'DataPackageReceive',
        component: () => retryImport(() => import('@/views/dataPackage/ReceivePackage.vue')),
        meta: { title: '接收数据包', roles: ['admin', 'super_admin', 'user'] },
      },
      { path: '/system/config-package', redirect: '/system/config' },
      // ── 数据录入 ──
      {
        path: '/data-entry',
        name: 'DataEntry',
        component: () => retryImport(() => import('@/views/dataEntry/ComprehensiveEntry.vue')),
        meta: { title: '数据录入' },
      },
      // ── 系统管理 ──
      {
        path: '/system/overview',
        name: 'SystemOverview',
        component: () => retryImport(() => import('@/views/system/SettingsOverview.vue')),
        meta: { title: '系统总览', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/health-check',
        name: 'SystemHealthCheck',
        component: () => retryImport(() => import('@/views/system/HealthCheck.vue')),
        meta: { title: '系统体检', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/about',
        name: 'SystemAbout',
        component: () => retryImport(() => import('@/views/system/About.vue')),
        meta: { title: '关于系统' },
      },
      {
        path: '/system/users',
        name: 'SystemUsers',
        component: () => retryImport(() => import('@/views/system/UserManagement.vue')),
        meta: { title: '用户管理', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/roles',
        redirect: '/system/users',
        meta: { title: '角色管理 (已合并到用户管理)' },
      },
      {
        path: '/system/menus',
        name: 'SystemMenus',
        component: () => retryImport(() => import('@/views/system/Menu.vue')),
        meta: { title: '菜单管理', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/menu-permissions',
        redirect: '/system/users',
        meta: { title: '菜单权限 (已合并到用户管理)' },
      },
      {
        path: '/system/audit',
        name: 'SystemAudit',
        component: () => retryImport(() => import('@/views/system/AuditManagement.vue')),
        meta: { title: '审计管理', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/backup',
        name: 'SystemBackup',
        component: () => retryImport(() => import('@/views/system/BackupManagement.vue')),
        meta: { title: '备份管理', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/cache',
        name: 'SystemCache',
        component: () => retryImport(() => import('@/views/system/CacheManagement.vue')),
        meta: { title: '缓存管理', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/config',
        name: 'SystemConfig',
        component: () => retryImport(() => import('@/views/system/ConfigPackage.vue')),
        meta: { title: '系统配置', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/control-package',
        name: 'ControlPackage',
        component: () => retryImport(() => import('@/views/system/ControlPackage.vue')),
        meta: { title: '管控配置包', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/email',
        name: 'SystemEmail',
        component: () => retryImport(() => import('@/views/system/EmailSettings.vue')),
        meta: { title: '邮件设置', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/monitoring',
        name: 'SystemMonitoring',
        component: () => retryImport(() => import('@/views/system/MonitoringDashboard.vue')),
        meta: { title: '系统监控', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/encryption',
        name: 'SystemEncryption',
        component: () => retryImport(() => import('@/views/system/EncryptionSettings.vue')),
        meta: { title: '加密设置', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/feedback',
        name: 'SystemFeedback',
        component: () => retryImport(() => import('@/views/system/Feedback.vue')),
        meta: { title: '反馈管理', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/update-logs',
        name: 'SystemUpdateLogs',
        component: () => retryImport(() => import('@/views/system/UpdateLogs.vue')),
        meta: { title: '更新日志', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/operation-logs',
        name: 'SystemOperationLogs',
        component: () => retryImport(() => import('@/views/system/OperationLogs.vue')),
        meta: { title: '操作日志', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/i18n',
        name: 'SystemI18n',
        component: () => retryImport(() => import('@/views/system/I18nManagement.vue')),
        meta: { title: '国际化管理', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/chunked-upload',
        name: 'SystemChunkedUpload',
        component: () => retryImport(() => import('@/views/system/ChunkedUploadManager.vue')),
        meta: { title: '分片上传', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/environment',
        name: 'SystemEnvironment',
        component: () => retryImport(() => import('@/views/system/EnvCheck.vue')),
        meta: { title: '运行环境', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/map-tiles',
        name: 'SystemMapTiles',
        component: () => retryImport(() => import('@/views/system/MapTileManager.vue')),
        meta: { title: '地图瓦片管理', roles: ['admin', 'super_admin'] },
      },
      // ── 管理面板 ──
      {
        path: '/admin/dashboard',
        name: 'AdminDashboard',
        component: () => retryImport(() => import('@/views/admin/AdminDashboard.vue')),
        meta: { title: '管理面板', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/admin/machine-code',
        name: 'AdminMachineCode',
        component: () => retryImport(() => import('@/views/admin/MachineCode.vue')),
        meta: { title: '机器码管理', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/admin/machine-code/management',
        name: 'AdminMachineCodeManagement',
        component: () => retryImport(() => import('@/views/admin/MachineCodeManagement.vue')),
        meta: { title: '机器码设置', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/admin/subordinates',
        name: 'AdminSubordinates',
        component: () => retryImport(() => import('@/views/admin/SubordinateManagement.vue')),
        meta: { title: '下级单位管理', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/admin/module-policy',
        name: 'AdminModulePolicy',
        component: () => retryImport(() => import('@/views/admin/OrgModulePolicy.vue')),
        meta: { title: '模块策略配置', roles: ['admin', 'super_admin'] },
      },
      // ── 系统安全 ──
      {
        path: '/system/zero-trust',
        name: 'SystemZeroTrust',
        component: () => retryImport(() => import('@/views/system/ZeroTrust.vue')),
        meta: { title: '零信任安全', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/user-permissions',
        name: 'SystemUserPermissions',
        component: () => retryImport(() => import('@/views/system/UserPermissions.vue')),
        meta: { title: '用户权限管理', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/secrets',
        name: 'SystemSecrets',
        component: () => retryImport(() => import('@/views/system/SecretsManagement.vue')),
        meta: { title: '密钥管理', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/data-tier',
        name: 'SystemDataTier',
        component: () => retryImport(() => import('@/views/system/DataTier.vue')),
        meta: { title: '数据分级', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/error-reports',
        name: 'SystemErrorReports',
        component: () => retryImport(() => import('@/views/system/ErrorReports.vue')),
        meta: { title: '错误报告', roles: ['admin', 'super_admin'] },
      },
      {
        path: '/system/tasks',
        name: 'SystemTasks',
        component: () => retryImport(() => import('@/views/system/TaskManager.vue')),
        meta: { title: '后台任务', roles: ['admin', 'super_admin'] },
      },
      // ── 消息中心 ──
      {
        path: '/message',
        name: 'MessageCenter',
        component: () => retryImport(() => import('@/views/message/MessageCenter.vue')),
        meta: { title: '消息中心' },
      },
      // ── 帮助 ──
      {
        path: '/system/help',
        redirect: '/help',
      },
      {
        path: '/help',
        name: 'HelpCenter',
        component: () => retryImport(() => import('@/views/help/HelpCenter.vue')),
        meta: { title: '帮助中心' },
      },
      // ── AI ──
      {
        path: '/ai/interactive',
        name: 'AIInteractive',
        component: () => retryImport(() => import('@/views/ai/InteractiveResult.vue')),
        meta: { title: 'AI分析' },
      },
      // ── 待办事项 ──
      {
        path: '/todos',
        name: 'Todos',
        component: () => retryImport(() => import('@/views/todos/Index.vue')),
        meta: { title: '待办事项' },
      },
      // ── 成效评估 ──
      {
        path: '/effectiveness',
        redirect: '/effectiveness/rankings',
      },
      {
        path: '/effectiveness/rankings',
        name: 'EffectivenessRankings',
        component: () => retryImport(() => import('@/views/effectiveness/Rankings.vue')),
        meta: { title: '成效排名' },
      },
      {
        path: '/effectiveness/evaluate',
        name: 'EffectivenessEvaluate',
        component: () => retryImport(() => import('@/views/effectiveness/Evaluation.vue')),
        meta: { title: '成效评估' },
      },
      // ── 提醒中心 ──
      {
        path: '/reminder',
        name: 'ReminderCenter',
        component: () => retryImport(() => import('@/views/reminder/Index.vue')),
        meta: { title: '提醒中心' },
      },
      // ── 舆情监测 ──
      {
        path: '/sentiment',
        name: 'Sentiment',
        component: () => retryImport(() => import('@/views/sentiment/Index.vue')),
        meta: { title: '舆情监测' },
      },
      // ── 批量操作 ──
      {
        path: '/batch',
        name: 'BatchOperations',
        component: () => retryImport(() => import('@/views/batch/Index.vue')),
        meta: {
          title: '批量操作',
          roles: ['admin', 'super_admin', 'user'],
        },
      },
      // ── 导入导出 ──
      {
        path: '/export/report',
        name: 'ExportReport',
        component: () => retryImport(() => import('@/views/export/ReportExport.vue')),
        meta: { title: '报告导出' },
      },
      {
        path: '/import/data',
        name: 'ImportData',
        component: () => retryImport(() => import('@/views/import/DataImport.vue')),
        meta: { title: '数据导入' },
      },
      {
        path: '/report/templates',
        name: 'ReportTemplates',
        component: () => retryImport(() => import('@/views/reportTemplates/Index.vue')),
        meta: { title: '报告模板' },
      },
      {
        path: '/data-verify',
        redirect: '/data-verify/rules',
      },
      {
        path: '/data-verify/rules',
        name: 'ValidationRules',
        component: () => retryImport(() => import('@/views/dataVerify/RulesManagement.vue')),
        meta: {
          title: '校验规则管理',
          roles: ['admin', 'super_admin', 'user'],
        },
      },
    ],
  },
  // ── 错误页（无导航栏）──
  {
    path: '/403',
    name: 'Forbidden',
    component: () => retryImport(() => import('@/views/errorPage/403.vue')),
    meta: { title: '无权访问', noAuth: true },
  },
  {
    path: '/500',
    name: 'ServerError',
    component: () => retryImport(() => import('@/views/errorPage/500.vue')),
    meta: { title: '服务错误', noAuth: true },
  },
  // ── 404 ──
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => retryImport(() => import('@/views/NotFound.vue')),
    meta: { title: '页面未找到', noAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局守卫：阻止 undefined/null 作为路由参数
router.beforeEach((to, _from, next) => {
  const path = to.path.toLowerCase()
  // 捕获 /xxx/undefined 或 /xxx/null 等无效路由
  if (path.includes('/undefined') || path.includes('/null')) {
    // 重定向到安全的列表页
    const fallback = path.startsWith('/supported-villages')
      ? '/supported-villages'
      : path.startsWith('/schools')
        ? '/schools'
        : path.startsWith('/projects')
          ? '/projects'
          : path.startsWith('/funds')
            ? '/funds'
            : '/dashboard'
    return next({ path: fallback, replace: true })
  }
  next()
})

// Electron 托盘/快捷键导航：主进程 webContents.send('app-route', path)
if (typeof window !== 'undefined' && (window as any).electronAPI?.onNavigate) {
  ;(window as any).electronAPI.onNavigate((route: string) => {
    if (typeof route === 'string' && route.startsWith('/')) {
      router.push(route).catch(() => {})
    }
  })
}

export default router
