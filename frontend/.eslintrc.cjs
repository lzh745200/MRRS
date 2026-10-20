/**
 * 共享的 no-restricted-syntax 基线（全仓生效）。
 *
 * 三条规则的动因见各 message 与 AGENTS.md：
 *  1. envelope 双重解包（Bug 模式 #1）
 *  2. 原始异常文案直出 UI（W18 P2-2）
 *  3. 手写 .data.items 解包（W5-T5）
 */
const RESTRICTED_SYNTAX_BASE = [
  {
    selector: "MemberExpression[object.property.name='data'][property.name='success']",
    message:
      '禁止 response.data.success 双重解包。get/post/apiRequest 返回已解包的 envelope，请直接用 response.success。详见 AGENTS.md Bug 模式 #1。',
  },
  {
    // W18 P2-2：禁止把原始异常文案直接弹给用户。
    // 后端错误详情按安全口径已脱敏，但前端 catch 到的 e.message 可能是
    // axios 原文（含 URL/状态码）或未预期异常文本 —— 统一走 getErrorMessage()。
    // 仅限 UI 反馈入口（ElMessage/ElNotification/message/notification/toast）；
    // console.error(e.message) 属开发日志，不在此列。
    selector:
      "CallExpression[callee.object.name=/^(ElMessage|ElNotification|message|notification|toast)$/][callee.property.name=/^(error|warning)$/] > MemberExpression[object.name=/^(e|err|error|ex|exception|reason)$/][property.name='message']",
    message:
      '禁止把原始异常文案直接弹给用户（如 ElMessage.error(e.message)）。请用 getErrorMessage(e)。详见 W18 P2-2。',
  },
  {
    // W5-T5：禁止手写 `.data.items` 解包。
    // get/post/apiRequest 的拦截器已把 envelope.data 展开到顶层（数组载荷
    // 自动落到 items），手写 `res.data.items` / `res.data?.items` /
    // `data.data?.items` 会与顶层 items 形成双源漂移，且漏掉裸数组、
    // 裸分页等历史形态（曾导致列表在个别端点上恒定为空）。
    // 统一走 @/utils/unwrapList（唯一豁免见下方 overrides）。
    selector: "MemberExpression[object.property.name='data'][property.name='items']",
    message: '禁止手写 .data.items 解包。请改用 @/utils/unwrapList(res).items（详见 W5-T5）。',
  },
]

/**
 * W5-T10：禁止 src/views/** 内新定义本地格式化函数。
 *
 * 背景：38 个视图各自实现了 formatDate / formatDateTime / formatMoney，实现细节
 * （空值、非法值、locale 异常）各不相同，收敛后统一走：
 *  - 日期时间 → `@/utils/datetime`（formatDate / formatDateTimeLocale / formatLocalDate …）
 *  - 金额     → `@/utils/currency`（formatCurrency / formatMoney4）
 *
 * 只拦“声明”（函数声明 / 箭头函数或函数表达式赋值），不拦 import 与调用；
 * 存量未迁移文件在下方 overrides 中逐一登记豁免，禁止新增同类本地实现。
 */
const LOCAL_FORMATTER_NAME_PATTERN =
  '/^(formatDate|formatDateTime|formatMoney|formatCurrency|formatAmount|formatTime)$/'
const RESTRICTED_SYNTAX_VIEW_FORMATTERS = [
  {
    selector: `FunctionDeclaration[id.name=${LOCAL_FORMATTER_NAME_PATTERN}]`,
    message:
      '禁止在 src/views 内新定义本地格式化函数（formatDate/formatDateTime/formatMoney/formatCurrency/formatAmount/formatTime）。请直接引用 @/utils/datetime 或 @/utils/currency（详见 W5-T10）。',
  },
  {
    selector: `VariableDeclarator[id.name=${LOCAL_FORMATTER_NAME_PATTERN}][init.type=/^(ArrowFunctionExpression|FunctionExpression)$/]`,
    message:
      '禁止在 src/views 内新定义本地格式化函数（formatDate/formatDateTime/formatMoney/formatCurrency/formatAmount/formatTime）。请直接引用 @/utils/datetime 或 @/utils/currency（详见 W5-T10）。',
  },
]

/**
 * 存量豁免清单（W5-T10 第二批待迁移）。
 *
 * 这些视图仍持有本地 formatXxx 实现（逻辑等价于 @/utils 对应函数，迁移属独立批次，
 * 避免与并行工单冲突）。**只减不增**：迁移一个就从这里删一个；新增文件不得加入。
 */
const LOCAL_FORMATTER_LEGACY_VIEWS = [
  'src/views/approval/History.vue',
  'src/views/approval/MyApplications.vue',
  'src/views/approval/Overview.vue',
  'src/views/approval/PendingList.vue',
  'src/views/dashboard/InfoRow.vue',
  'src/views/dataPackage/List.vue',
  'src/views/dataPackage/PackageVersion.vue',
  'src/views/dataPackage/ReceivePackage.vue',
  'src/views/dataSync/Export.vue',
  'src/views/dataSync/Import.vue',
  'src/views/export/ReportExport.vue',
  'src/views/funds/EnhancedList.vue',
  'src/views/funds/UserFundList.vue',
  'src/views/households/Detail.vue',
  'src/views/households/List.vue',
  'src/views/message/MessageCenter.vue',
  'src/views/organization/Detail.vue',
  'src/views/organization/PassCodeManagement.vue',
  'src/views/policies/List.vue',
  'src/views/reminder/Index.vue',
  'src/views/reportTemplates/Index.vue',
  'src/views/schools/Detail.vue',
  'src/views/system/BackupManagement.vue',
  'src/views/system/EncryptionSettings.vue',
  'src/views/system/ErrorReports.vue',
  'src/views/system/HealthCheck.vue',
  'src/views/system/PermissionPacks.vue',
  'src/views/system/SecretsManagement.vue',
  'src/views/system/SettingsOverview.vue',
  'src/views/system/TaskManager.vue',
  'src/views/system/UpdateLogs.vue',
  'src/views/system/ZeroTrust.vue',
  'src/views/todos/Index.vue',
  'src/views/work-calendar/Index.vue',
]

module.exports = {
  root: true,
  env: {
    node: true,
    browser: true,
    es2021: true,
  },
  extends: [
    'eslint:recommended',
    'plugin:vue/vue3-recommended',
    '@vue/eslint-config-typescript',
    '@vue/eslint-config-prettier',
  ],
  parserOptions: {
    ecmaVersion: 2021,
    sourceType: 'module',
  },
  plugins: ['vue'],
  // 由 unplugin-auto-import / unplugin-vue-components 在每次 vite dev|build 时重新生成。
  // 两个生成器均将 `/* eslint-disable */` 硬编码在 dts 模板里（已在
  // node_modules/unplugin-{auto-import,vue-components}/dist 取证），手工删除会被
  // 下一次构建静默回写。因此改为在 lint 作用域排除：使 lint 正确性不再
  // 依赖生成器自带的豁免头，也不会在上游变更模板时静默失效。
  //
  // 同源登记的类型豁免（同样为生成器硬编码、不可手工消除，共 3 处）：
  //   src/auto-imports.d.ts:3   `// @ts-nocheck`
  //     ← node_modules/unplugin-auto-import/dist/chunk-GR6VF5HE.js:158（dts 模板字面量）
  //   src/components.d.ts:3     `// @ts-nocheck`
  //     ← node_modules/unplugin-vue-components/dist/chunk-LAHXDHMT.js:227（dts 模板字面量）
  //   src/auto-imports.d.ts:84  `// @ts-ignore`
  //     ← node_modules/unimport/dist/shared/unimport.*.{mjs,cjs} toTypeReExports()，
  //       上游注释说明这是 `declare global { export type {...} from }` 的 TS 限制绕行
  // 三者均只作用于生成文件自身；tsconfig 无法在不丢失全局类型增强的前提下 exclude 它们，
  // 故保留原样并在此登记，禁止在真实源码中新增同类豁免。
  ignorePatterns: ['src/auto-imports.d.ts', 'src/components.d.ts'],
  rules: {
    'no-console': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
    'no-debugger': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', caughtErrors: 'none' }],
    'vue/multi-word-component-names': 'off',
    'vue/require-default-prop': 'off', // Vue 3 中可选props不需要默认值
    'no-restricted-syntax': ['error', ...RESTRICTED_SYNTAX_BASE],
  },
  overrides: [
    {
      // unwrapList 是解包语义的唯一事实源，其内部必须直接访问 .data.items
      // （该访问正是被上面规则禁止的模式），故对本文件整体关闭 no-restricted-syntax。
      files: ['src/utils/unwrapList.ts'],
      rules: {
        'no-restricted-syntax': 'off',
      },
    },
    {
      // v-html 为有意使用，且渲染前均已过 DOMPurify / 正则转义消毒：
      //  - help/HelpCenter.vue：文章正文来自系统帮助文档库（受信任）；
      //    搜索摘要高亮由 highlightKeyword 对用户输入做正则转义
      //  - policies/Detail.vue：政策正文经 sanitizedPolicyContent（sanitizeHtml）消毒
      // 统一在 overrides 登记而非散在模板里写 eslint-disable，
      // 便于审计时一处核对所有 v-html 豁免点及其消毒依据。
      files: ['src/views/help/HelpCenter.vue', 'src/views/policies/Detail.vue'],
      rules: {
        'vue/no-v-html': 'off',
      },
    },
    {
      // src/types/index.ts 是纯 re-export barrel；@typescript-eslint 8.63.0 的
      // no-unused-vars 在 export * 上崩溃（Cannot use 'in' operator ... undefined）。
      // 仅对此文件关闭，避免全局放松未使用变量检查。
      files: ['src/types/index.ts'],
      rules: {
        '@typescript-eslint/no-unused-vars': 'off',
      },
    },
    {
      // W5-T10：视图层禁止新定义本地格式化函数（基线三条规则 + 格式化器两条）。
      // 只覆盖 .vue（视图模板/逻辑），不波及 utils / composables 里的唯一实现。
      files: ['src/views/**/*.vue'],
      rules: {
        'no-restricted-syntax': [
          'error',
          ...RESTRICTED_SYNTAX_BASE,
          ...RESTRICTED_SYNTAX_VIEW_FORMATTERS,
        ],
      },
    },
    {
      // 存量未迁移视图：仅豁免“本地格式化函数”两条，基线三条照旧生效。
      // 必须放在上一个 override 之后（ESLint 按 order 覆盖同名规则）。
      files: LOCAL_FORMATTER_LEGACY_VIEWS,
      rules: {
        'no-restricted-syntax': ['error', ...RESTRICTED_SYNTAX_BASE],
      },
    },
  ],
}
