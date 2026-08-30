/**
 * 帮扶管理信息系统 — 系统介绍 PPT（40 页）
 * 主题：军绿 + 荣誉金；字体：微软雅黑；画布 13.33×7.5
 */
const pptxgen = require("pptxgenjs");

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.author = "帮扶管理信息系统";
p.title = "帮扶管理信息系统 — 系统介绍";

// ── 调色板（BACKGROUND → PRIMARY → ACCENT）──
const BG_DARK = "14291F";   // 深军绿黑：封面/章节/结尾
const BG_DARK2 = "1C362A";  // 深色页卡片
const BG = "FFFFFF";        // 内容页
const PRIMARY = "1F4A38";   // 军绿
const PRIMARY_L = "2D6A4F"; // 军绿亮
const PRIMARY_T = "E8EFEA"; // 军绿浅底
const ACCENT = "C9A227";    // 荣誉金
const TEXT = "1A2E24";
const MUTED = "5F6F66";
const LIGHT = "D7E2DB";     // 深底上的浅字
const F = "微软雅黑";

const W = 13.33, H = 7.5, M = 0.5;
const bu = () => ({ code: "25AA", indent: 12 });
const shadow = () => ({ type: "outer", color: "1A2E24", blur: 7, offset: 2, angle: 90, opacity: 0.13 });
let pageNo = 0;

// ── 通用元件 ──
function header(s, kicker, title) {
  pageNo += 1;
  s.background = { color: BG };
  s.addShape(p.shapes.RECTANGLE, { x: M, y: 0.5, w: 0.14, h: 0.14, fill: { color: ACCENT } });
  s.addText(kicker, { x: M + 0.24, y: 0.36, w: 8, h: 0.4, fontSize: 12.5, bold: true,
    color: PRIMARY_L, fontFace: F, charSpacing: 3, margin: 0 });
  s.addText(title, { x: M, y: 0.78, w: W - 2 * M, h: 0.75, fontSize: 30, bold: true,
    color: TEXT, fontFace: F, margin: 0 });
  s.addText(String(pageNo).padStart(2, "0"), { x: W - 1.0, y: H - 0.55, w: 0.5, h: 0.3,
    fontSize: 11, color: MUTED, fontFace: F, align: "right", margin: 0 });
  s.addText("帮扶管理信息系统 v1.11.2", { x: M, y: H - 0.55, w: 4, h: 0.3,
    fontSize: 10.5, color: MUTED, fontFace: F, margin: 0 });
}
function card(s, x, y, w, h, fill = BG) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill },
    rectRadius: 0.07, shadow: shadow() });
}
function bullets(s, items, x, y, w, h, opts = {}) {
  s.addText(items.map((t, i) => ({
    text: t, options: { bullet: bu(), breakLine: true, color: opts.color || TEXT,
      bold: false },
  })), { x, y, w, h, fontSize: opts.size || 14.5, fontFace: F, paraSpaceAfter: opts.gap || 9,
    margin: 0, valign: "top", align: "left" });
}
function stat(s, x, y, w, num, label, color = PRIMARY, numSize = 40) {
  s.addText(num, { x, y, w, h: 0.85, fontSize: numSize, bold: true, color, fontFace: F,
    align: "center", margin: 0 });
  s.addText(label, { x, y: y + 0.88, w, h: 0.55, fontSize: 13, color: MUTED, fontFace: F,
    align: "center", margin: 0 });
}
function sectionSlide(num, title, sub, items) {
  pageNo += 1;
  const s = p.addSlide();
  s.background = { color: BG_DARK };
  s.addText(num, { x: 0.55, y: 0.9, w: 4.6, h: 3.4, fontSize: 200, bold: true,
    color: BG_DARK2, fontFace: F, margin: 0 });
  s.addText(title, { x: 1.0, y: 4.35, w: 11.3, h: 0.95, fontSize: 40, bold: true,
    color: "FFFFFF", fontFace: F, margin: 0 });
  s.addText(sub, { x: 1.02, y: 5.35, w: 11, h: 0.5, fontSize: 15, color: ACCENT,
    fontFace: F, margin: 0 });
  s.addText(items.map((t) => ({ text: t, options: { bullet: bu(), breakLine: true } })),
    { x: 8.1, y: 1.55, w: 4.6, h: 3.4, fontSize: 14, color: LIGHT, fontFace: F,
      paraSpaceAfter: 10, margin: 0, valign: "top" });
  s.addText(String(pageNo).padStart(2, "0"), { x: W - 1.0, y: H - 0.55, w: 0.5, h: 0.3,
    fontSize: 11, color: "6E8177", fontFace: F, align: "right", margin: 0 });
  return s;
}

/* ════════ 01 封面 ════════ */
{
  const s = p.addSlide();
  s.background = { color: BG_DARK };
  s.addShape(p.shapes.OVAL, { x: 9.4, y: -2.4, w: 6.4, h: 6.4, fill: { color: BG_DARK2 } });
  s.addShape(p.shapes.OVAL, { x: -1.8, y: 5.4, w: 4.6, h: 4.6, fill: { color: BG_DARK2 } });
  s.addShape(p.shapes.RECTANGLE, { x: 1.0, y: 2.02, w: 0.26, h: 0.26, fill: { color: ACCENT } });
  s.addText("军民融合 · 乡村振兴帮扶数字化平台", { x: 1.4, y: 1.9, w: 9, h: 0.5,
    fontSize: 15, bold: true, color: ACCENT, fontFace: F, charSpacing: 4, margin: 0 });
  s.addText("帮扶管理信息系统", { x: 0.96, y: 2.55, w: 11.5, h: 1.35, fontSize: 58,
    bold: true, color: "FFFFFF", fontFace: F, margin: 0 });
  s.addText("Assistance Management Information System", { x: 1.0, y: 3.95, w: 10, h: 0.45,
    fontSize: 15, color: LIGHT, fontFace: F, italic: true, margin: 0 });
  s.addText([
    { text: "完全离线 · 数据本机", options: { breakLine: true } },
    { text: "多机协同 · 军工级安全", options: {} },
  ], { x: 1.0, y: 4.75, w: 6, h: 0.85, fontSize: 16, color: LIGHT, fontFace: F,
    paraSpaceAfter: 6, margin: 0 });
  s.addText("V1.11.2  |  2026-08-30  |  FastAPI + Vue 3 + Electron + SQLite", {
    x: 1.0, y: 6.35, w: 10, h: 0.4, fontSize: 12.5, color: "8FA298", fontFace: F, margin: 0 });
}

/* ════════ 02 目录 ════════ */
{
  const s = p.addSlide();
  s.background = { color: BG_DARK };
  s.addText("目录", { x: 1.0, y: 0.85, w: 5, h: 0.9, fontSize: 38, bold: true,
    color: "FFFFFF", fontFace: F, margin: 0 });
  s.addText("CONTENTS", { x: 1.02, y: 1.8, w: 5, h: 0.4, fontSize: 13, color: ACCENT,
    fontFace: F, charSpacing: 5, margin: 0 });
  const toc = [
    ["01", "系统概述", "定位 · 使命 · 关键数字"],
    ["02", "技术架构", "技术栈 · 分层设计 · 离线优先"],
    ["03", "功能模块", "七大业务域 · 71 个功能菜单"],
    ["04", "安全体系", "四角色权限 · PII 加密 · 审计合规"],
    ["05", "质量工程", "15833 项自动化测试 · CI/CD"],
    ["06", "部署运行", "双平台安装包 · 备份升级 · 版本历程"],
  ];
  toc.forEach((t, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 1.0 + col * 5.9, y = 2.55 + row * 1.45;
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w: 5.5, h: 1.15,
      fill: { color: BG_DARK2 }, rectRadius: 0.07 });
    s.addText(t[0], { x: x + 0.28, y: y + 0.16, w: 1.0, h: 0.85, fontSize: 30, bold: true,
      color: ACCENT, fontFace: F, margin: 0 });
    s.addText(t[1], { x: x + 1.35, y: y + 0.14, w: 4.0, h: 0.5, fontSize: 19, bold: true,
      color: "FFFFFF", fontFace: F, margin: 0 });
    s.addText(t[2], { x: x + 1.35, y: y + 0.62, w: 4.0, h: 0.4, fontSize: 12,
      color: "9DB0A6", fontFace: F, margin: 0 });
  });
}

/* ════════ 03 章节页：系统概述 ════════ */
sectionSlide("01", "系统概述", "SYSTEM OVERVIEW", [
  "为什么需要这套系统",
  "系统的定位与形态",
  "离线优先的产品决策",
  "一眼看懂的关键数字",
]);

/* 04 项目背景与使命 */
{
  const s = p.addSlide();
  header(s, "01 系统概述", "项目背景与使命");
  s.addText("把驻村帮扶工作从“纸质台账 + Excel 报表”搬进可信的数字化轨道", {
    x: M, y: 1.62, w: 12.3, h: 0.5, fontSize: 16.5, bold: true, color: PRIMARY_L,
    fontFace: F, margin: 0 });
  const rows = [
    ["驻村帮扶的现实约束", "帮扶村镇多位于网络条件受限地区，互联网云服务不可依赖，数据必须留在本机、随人走、可备份、可交接"],
    ["军民融合的协同需求", "军队帮扶单位与地方协同：任务下达、经费监管、成效上报，全流程需要留痕可审计，满足军事审计红线"],
    ["数据资产的长期价值", "帮扶村 10 大板块年度数据、项目全生命周期、资金全流程——沉淀多年后就是帮扶成效最有说服力的证据"],
  ];
  rows.forEach((r, i) => {
    const y = 2.35 + i * 1.55;
    s.addShape(p.shapes.RECTANGLE, { x: M, y: y + 0.06, w: 0.12, h: 1.1, fill: { color: ACCENT } });
    s.addText(r[0], { x: M + 0.3, y, w: 4.4, h: 1.2, fontSize: 17, bold: true, color: TEXT,
      fontFace: F, margin: 0 });
    s.addText(r[1], { x: 5.35, y, w: 7.4, h: 1.2, fontSize: 14, color: MUTED, fontFace: F,
      margin: 0 });
  });
}

/* 05 系统定位与核心价值 */
{
  const s = p.addSlide();
  header(s, "01 系统概述", "系统定位与核心价值");
  const cards = [
    ["完全离线", "装在电脑上就能用，不依赖任何外网服务；数据全部落在本机 SQLite，断网功能零损失"],
    ["多机协同", "单位内多台电脑通过加密数据包交换数据：全量包 + 增量包，支持版本管理与冲突解决"],
    ["军工级安全", "四角色权限、组织数据隔离、PII 字段透明加密、全程审计留痕，直面军事审计要求"],
    ["开箱即用", "NSIS / DEB 安装包内置全部运行时，目标机器零依赖；内置备份恢复与出厂恢复通道"],
  ];
  cards.forEach((c, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = M + col * 6.35, y = 1.85 + row * 2.5;
    card(s, x, y, 5.9, 2.15);
    s.addShape(p.shapes.RECTANGLE, { x: x + 0.32, y: y + 0.34, w: 0.16, h: 0.16, fill: { color: ACCENT } });
    s.addText(c[0], { x: x + 0.62, y: y + 0.2, w: 4.6, h: 0.45, fontSize: 19, bold: true,
      color: PRIMARY, fontFace: F, margin: 0 });
    s.addText(c[1], { x: x + 0.34, y: y + 0.78, w: 5.25, h: 1.25, fontSize: 13.5,
      color: MUTED, fontFace: F, margin: 0 });
  });
}

/* 06 关键数字 */
{
  const s = p.addSlide();
  header(s, "01 系统概述", "一眼看懂：系统规模");
  stat(s, 0.55, 2.1, 3.0, "10,142", "后端自动化测试用例");
  stat(s, 3.9, 2.1, 3.0, "5,691", "前端自动化测试用例");
  stat(s, 7.25, 2.1, 3.0, "71", "功能菜单键（三级菜单树）");
  stat(s, 10.6, 2.1, 2.4, "131", "业务页面视图");
  s.addShape(p.shapes.LINE, { x: M, y: 3.95, w: W - 2 * M, h: 0, line: { color: "D8E0DA", width: 1 } });
  stat(s, 0.55, 4.35, 3.0, "49", "后端 API 路由模块", PRIMARY_L);
  stat(s, 3.9, 4.35, 3.0, "88", "后端服务（80 + 8 子包）", PRIMARY_L);
  stat(s, 7.25, 4.35, 3.0, "37", "数据库迁移版本", PRIMARY_L);
  stat(s, 10.6, 4.35, 2.4, "4", "用户角色", PRIMARY_L, 40);
  s.addText("数据来源：仓库实测（2026-08-30，v1.11.2）—— flake8 0 错误 · bandit 0 中高危 · vue-tsc 0 错误 · eslint 0 警告", {
    x: M, y: 6.35, w: 12.3, h: 0.4, fontSize: 12, color: MUTED, fontFace: F, margin: 0 });
}

/* ════════ 07 章节页：技术架构 ════════ */
sectionSlide("02", "技术架构", "TECHNICAL ARCHITECTURE", [
  "技术栈选型与理由",
  "四层架构设计",
  "前端 / 后端工程结构",
  "离线优先的实现路径",
]);

/* 08 技术栈全景 */
{
  const s = p.addSlide();
  header(s, "02 技术架构", "技术栈全景");
  const cols = [
    ["桌面壳层", "Electron", ["Windows x64 NSIS 安装包", "麒麟 V10 ARM64 DEB", "托盘 / 自启 / 锁屏 / 快捷键", "后端进程托管与健康检查"]],
    ["前端", "Vue 3 + TypeScript", ["Element Plus + Pinia + Vue Router", "SCSS 设计令牌（4 套可切换主题）", "131 个视图 · 25 个共享组件", "Axios 统一信封 + CSRF + 离线 Mock"]],
    ["后端", "FastAPI (Python 3.11)", ["49 个路由模块 + 5 个子包", "80 个服务 + 8 个子包", "SQLAlchemy 2.x + Alembic", "JWT + 黑名单 + 限流 + 审计中间件"]],
    ["数据", "SQLite", ["单文件数据库，随备份带走", "WAL 并发 + 外键强制", "EncryptedText 列透明加密", "37 个 Alembic 迁移版本"]],
  ];
  cols.forEach((c, i) => {
    const x = M + i * 3.18;
    card(s, x, 1.85, 2.95, 4.7);
    s.addText(c[0], { x: x + 0.25, y: 2.1, w: 2.5, h: 0.35, fontSize: 13, bold: true,
      color: ACCENT, fontFace: F, margin: 0, charSpacing: 2 });
    s.addText(c[1], { x: x + 0.25, y: 2.52, w: 2.6, h: 0.46, fontSize: 16, bold: true,
      color: TEXT, fontFace: F, margin: 0 });
    bullets(s, c[2], x + 0.25, 3.15, 2.55, 3.2, { size: 12, gap: 8 });
  });
}

/* 09 分层架构图 */
{
  const s = p.addSlide();
  header(s, "02 技术架构", "四层架构：进程间协作");
  const layers = [
    ["Electron 主进程", "窗口/托盘 · 后端 exe 托管 · DATABASE_URL 注入 · 导航白名单", 9.6],
    ["Vue 3 前端（渲染进程）", "131 视图 · Pinia · Axios 信封拦截器 · CSRF 续期 · 离线 Mock", 10.4],
    ["FastAPI 应用层", "49 路由 · 数据范围过滤 · 限流 · 审计中间件 · 统一信封", 10.4],
    ["SQLite 数据层", "WAL · 37 迁移 · EncryptedText 加密列 · 备份/恢复", 9.6],
  ];
  layers.forEach((l, i) => {
    const y = 1.78 + i * 1.3;
    const w = l[2];
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 1.4, y, w, h: 1.06,
      fill: { color: i % 2 ? PRIMARY_T : PRIMARY }, rectRadius: 0.06 });
    s.addText(l[0], { x: 1.75, y: y + 0.12, w: w - 0.7, h: 0.42, fontSize: 16.5, bold: true,
      color: i % 2 ? TEXT : "FFFFFF", fontFace: F, margin: 0 });
    s.addText(l[1], { x: 1.75, y: y + 0.58, w: w - 0.7, h: 0.4, fontSize: 12.5,
      color: i % 2 ? MUTED : LIGHT, fontFace: F, margin: 0 });
    if (i < 3) s.addShape(p.shapes.LINE, { x: 6.55, y: y + 1.06, w: 0, h: 0.24,
      line: { color: ACCENT, width: 2.2, endArrowType: "triangle" } });
  });
  s.addText("HTTP 127.0.0.1（同机回环，Token 黑名单 + CSRF 双重校验）", { x: 6.6, y: 6.9,
    w: 6.0, h: 0.35, fontSize: 11.5, color: MUTED, fontFace: F, margin: 0 });
}

/* 10 前端架构 */
{
  const s = p.addSlide();
  header(s, "02 技术架构", "前端工程：规范即生产力");
  card(s, M, 1.8, 6.0, 4.9);
  s.addText("规模", { x: 0.82, y: 2.05, w: 3, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "131 个业务视图（34 个功能目录）",
    "25 个共享组件（PageHeader / EmptyState / BaseChart 等标准件）",
    "34 个 Pinia store + 30+ 组合式函数",
    "292 个测试文件 · 5,691 个用例",
    "覆盖率门禁 + lint --max-warnings=0 + vue-tsc 三重 CI 门禁",
  ], 0.82, 2.55, 5.4, 3.9, { size: 13.5, gap: 10 });
  card(s, 6.85, 1.8, 6.0, 4.9);
  s.addText("设计系统", { x: 7.17, y: 2.05, w: 3, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "tokens.scss 设计令牌：色彩 / 字号 / 间距 / 阴影单一来源",
    "4 套可切换主题（默认军绿 / 浅色 / 深色 / 户外），运行时热切换",
    "vite additionalData 注入 SCSS 变量，杜绝硬编码色值",
    "统一信封拦截器：data 自动展开 + CSRF 自动续期 + 401/403 分类处理",
    "pushSafe 导航、分页重置、blob 下载等 7 项防错规约",
  ], 7.17, 2.55, 5.4, 3.9, { size: 13.5, gap: 10 });
}

/* 11 后端架构 */
{
  const s = p.addSlide();
  header(s, "02 技术架构", "后端工程：一个请求的旅程");
  const steps = [
    ["审计中间件", "记录 谁·何时·做什么"],
    ["认证与限流", "JWT 校验 · Token 黑名单 · 滑动窗口限流"],
    ["数据范围过滤", "按角色 + 组织自动限定可见数据"],
    ["业务服务层", "80 个服务：资金 / 项目 / 数据包 / 审批…"],
    ["统一信封响应", "success_response / ok_list"],
  ];
  steps.forEach((t, i) => {
    const x = M + i * 2.52;
    s.addShape(p.shapes.CHEVRON, { x, y: 2.0, w: 2.62, h: 1.0,
      fill: { color: i === 4 ? PRIMARY_L : PRIMARY } });
    s.addText(t[0], { x: x + 0.18, y: 2.12, w: 2.2, h: 0.4, fontSize: 13.5, bold: true,
      color: "FFFFFF", fontFace: F, margin: 0 });
    s.addText(t[1], { x: x + 0.05, y: 3.15, w: 2.5, h: 0.75, fontSize: 11.5, color: MUTED,
      fontFace: F, margin: 0 });
  });
  card(s, M, 4.35, 12.33, 2.2);
  s.addText("工程纪律", { x: 0.82, y: 4.6, w: 3, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "事务工具箱：with_transaction / 嵌套事务 / 死锁重试 / 批量操作（1000 条/批）",
    "错误细节不出站：detail 一律泛化文案 + 日志 exc_info（源码扫描测试强制拦截）",
    "响应格式统一：全部列表端点走 ok_list 信封（本轮收敛 51 处裸 dict）",
    "flake8 --count=0 与 bandit 中高危=0 是硬门禁",
  ], 0.82, 5.05, 11.6, 1.4, { size: 13, gap: 7 });
}

/* 12 数据与模型 */
{
  const s = p.addSlide();
  header(s, "02 技术架构", "数据层：57 个模型的安全基座");
  card(s, M, 1.8, 5.9, 4.9);
  s.addText("模型与迁移", { x: 0.82, y: 2.05, w: 3, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "57 个模型文件 / 120+ 模型类：村、项目、资金、学校、政策、组织、审计…",
    "TimestampMixin：created_at / updated_at / sync_version 自动维护",
    "SoftDeleteMixin：is_active 软删 + deleted_by 审计列",
    "37 个 Alembic 迁移：含 PII 存量回填（幂等可重跑）与外键守护",
    "Schema 权威来源 = models/ + Alembic（init.sql 已删除）",
  ], 0.82, 2.55, 5.3, 3.9, { size: 13.5, gap: 10 });
  card(s, 6.75, 1.8, 6.1, 4.9);
  s.addText("完整性守护", { x: 7.07, y: 2.05, w: 3, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "组织删除级联守卫：名下有项目/用户时拒绝硬删（ADR-0003）",
    "projects 组织外键 CASCADE→SET NULL，截断级联删除链",
    "PII 列 EncryptedText：写入自动加密、读取自动解密（ADR-0005）",
    "sync_version 增量水位：ORM 事件自动递增，支撑增量数据包",
    "删库守卫：库完整性校验失败默认拒绝启动（ALLOW_DB_RESET 显式解锁）",
  ], 7.07, 2.55, 5.5, 3.9, { size: 13.5, gap: 10 });
}

/* 13 离线优先设计 */
{
  const s = p.addSlide();
  header(s, "02 技术架构", "离线优先：数据如何“随人走”");
  // 单机模式
  card(s, M, 1.8, 5.9, 2.5);
  s.addText("单机模式（默认）", { x: 0.82, y: 2.0, w: 4, h: 0.4, fontSize: 15.5, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "数据全部在本机 %APPDATA% 数据库文件",
    "智能备份中心：自动/即时/磁盘检测/备份到 U 盘",
    "断网零功能损失（AI 增强除外，可关闭）",
  ], 0.82, 2.5, 5.3, 1.6, { size: 13, gap: 8 });
  // 多机模式
  card(s, 6.75, 1.8, 6.1, 2.5);
  s.addText("多机协同模式", { x: 7.07, y: 2.0, w: 4, h: 0.4, fontSize: 15.5, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "加密数据包（口令 + PBKDF2）在机器间摆渡",
    "包内 manifest 记录 org/类型/记录数/校验和",
    "跨机同步需配置相同 ENCRYPTION_KEY（密文可解）",
  ], 7.07, 2.5, 5.5, 1.6, { size: 13, gap: 8 });
  // 数据流
  const flow = ["本机 SQLite", "导出数据包", "加密 .zip", "介质摆渡", "对端导入", "确认落库"];
  flow.forEach((t, i) => {
    const x = 0.7 + i * 2.06;
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y: 4.85, w: 1.72, h: 0.85,
      fill: { color: i === 2 ? ACCENT : PRIMARY }, rectRadius: 0.06 });
    s.addText(t, { x, y: 4.85, w: 1.72, h: 0.85, fontSize: 13, bold: true,
      color: i === 2 ? TEXT : "FFFFFF", fontFace: F, align: "center", valign: "middle", margin: 0 });
    if (i < 5) s.addShape(p.shapes.LINE, { x: x + 1.74, y: 5.27, w: 0.28, h: 0,
      line: { color: ACCENT, width: 2, endArrowType: "triangle" } });
  });
  s.addText("全流程留痕：导入/导出/确认各环节写入工作日志与操作历史，包完整性校验失败即中止", {
    x: M, y: 6.15, w: 12.3, h: 0.4, fontSize: 12, color: MUTED, fontFace: F, margin: 0 });
}

/* ════════ 14 章节页：功能模块 ════════ */
sectionSlide("03", "功能模块", "FUNCTIONAL MODULES", [
  "七大业务域 · 71 个功能菜单",
  "业务：村/项目/资金/学校/政策",
  "协同：数据包 · 审批 · 消息",
  "分析：看板 · 报表 · 大屏",
]);

/* 15 功能地图 */
{
  const s = p.addSlide();
  header(s, "03 功能模块", "功能地图：七大业务域");
  const domains = [
    ["帮扶业务", "帮扶村 10 大板块 · 项目全生命周期 · 资金 8 阶段 · 学校助学", "villages / projects / funds / schools"],
    ["政策与审批", "政策库 FTS5 全文检索 · 审批工作流 · 我的申请 · 审批历史", "policies / approval"],
    ["数据协同", "数据包全量/增量导出导入 · 版本管理 · 冲突解决 · 接收包", "dataPackage / dataSync"],
    ["数据分析", "分析仪表盘 · 年度对比 · 成效评估 · 报表导出 · 帮扶大屏", "analytics / bigscreen"],
    ["驻村工作", "工作台账 · 驻村任务 · 工作日历 · 考核评估", "ruralWorks / work-calendar"],
    ["系统管理", "用户/角色/菜单/组织 · 权限包 · 审计 · 备份 · 更新日志", "system / admin"],
  ];
  domains.forEach((d, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = M + col * 4.28, y = 1.85 + row * 2.45;
    card(s, x, y, 3.98, 2.1);
    s.addText(d[0], { x: x + 0.28, y: y + 0.18, w: 3.4, h: 0.42, fontSize: 17, bold: true,
      color: PRIMARY, fontFace: F, margin: 0 });
    s.addText(d[1], { x: x + 0.28, y: y + 0.68, w: 3.5, h: 0.85, fontSize: 12, color: MUTED,
      fontFace: F, margin: 0 });
    s.addText(d[2], { x: x + 0.28, y: y + 1.6, w: 3.5, h: 0.35, fontSize: 10.5, italic: true,
      color: PRIMARY_L, fontFace: F, margin: 0 });
  });
  s.addText("+ 消息中心 · 待办中心 · 提醒中心 · 全局搜索 · 回收站 —— 贯穿各业务域的横向能力", {
    x: M, y: 6.75, w: 12.3, h: 0.4, fontSize: 12.5, color: MUTED, fontFace: F, margin: 0 });
}

/* 16 工作台与看板 */
{
  const s = p.addSlide();
  header(s, "03 功能模块", "工作台：打开系统的第一屏");
  card(s, M, 1.8, 6.0, 4.9);
  s.addText("个人工作台", { x: 0.82, y: 2.05, w: 4, h: 0.4, fontSize: 16, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "KPI 卡片真实环比：本年资金 / 项目 / 村 / 学校，方向箭头动态化",
    "待办聚合：待审批 / 待办任务 / 未读消息一键直达",
    "快捷操作自定义布局（QuickActions 拖拽）",
    "图表年度趋势：资金 / 项目双轴联动",
    "工作台可按角色裁剪：viewer 只见只读面板",
  ], 0.82, 2.55, 5.4, 3.9, { size: 13.5, gap: 10 });
  card(s, 6.85, 1.8, 6.0, 4.9);
  s.addText("分析仪表盘", { x: 7.17, y: 2.05, w: 4, h: 0.4, fontSize: 16, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "年度对比：任选两年，村/项目/资金多维并排",
    "帮扶成效评估：村庄打分、排名、历年对比",
    "ECharts 统一主题（军绿科技风），全站图表一致",
    "帮扶大屏：深色全屏模式，适用于展示/汇报场景",
    "图表空态统一：无数据不出现“白板图”",
  ], 7.17, 2.55, 5.4, 3.9, { size: 13.5, gap: 10 });
}

/* 17 帮扶村管理 */
{
  const s = p.addSlide();
  header(s, "03 功能模块", "帮扶村：一村一档，一年一账");
  const blocks = ["基本情况", "人口变动", "收入结构", "产业帮扶", "基础设施", "组织建设", "帮扶成效", "年度对比"];
  blocks.forEach((b, i) => {
    const col = i % 4, row = Math.floor(i / 4);
    const x = M + col * 3.18, y = 1.85 + row * 1.35;
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.95, h: 1.05,
      fill: { color: PRIMARY_T }, rectRadius: 0.06 });
    s.addText(b, { x, y, w: 2.95, h: 1.05, fontSize: 15, bold: true, color: PRIMARY,
      fontFace: F, align: "center", valign: "middle", margin: 0 });
  });
  bullets(s, [
    "按年度记录全村数据，跨年对比自动生成（人口/收入/资金投入趋势）",
    "村档案变更历史：字段级 old → new 记录，谁改的、何时改、改了什么全程可溯",
    "村委会成员、脱贫跟踪、荣誉展示；软删除进回收站，管理员可恢复或彻底删除",
    "导出：整村档案导出（脱敏可选），支撑向上汇报",
  ], M, 4.85, 12.3, 1.9, { size: 13.5, gap: 9 });
}

/* 18 项目管理 */
{
  const s = p.addSlide();
  header(s, "03 功能模块", "项目管理：从立项到验收的全生命周期");
  const steps = ["立项申请", "审批通过", "执行跟踪", "里程碑", "竣工验收", "归档沉淀"];
  steps.forEach((t, i) => {
    const x = M + i * 2.09;
    s.addShape(p.shapes.CHEVRON, { x, y: 1.95, w: 2.2, h: 0.9,
      fill: { color: i === 5 ? PRIMARY_L : PRIMARY } });
    s.addText(t, { x: x + 0.1, y: 1.95, w: 1.9, h: 0.9, fontSize: 14, bold: true,
      color: "FFFFFF", fontFace: F, align: "center", valign: "middle", margin: 0 });
  });
  bullets(s, [
    "项目档案：负责单位（组织隔离）、帮扶村关联、预算/实际花费、进度百分比、优先级、负责人",
    "里程碑管理：阶段节点 + 甘特图（自研轻量 gantt，ADR-0012），进度照片墙留证",
    "任务分解：项目任务看板，执行人/截止日/完成状态；变更历史全程留痕",
    "软删除 + 回收站：误删可恢复；删除前级联检查，防误伤资金数据",
    "数据范围：普通用户仅见本人录入，管理员见本组织及下级，超级管理员全局",
  ], M, 3.35, 12.3, 3.1, { size: 14, gap: 11 });
}

/* 19 资金管理 */
{
  const s = p.addSlide();
  header(s, "03 功能模块", "资金管理：一笔钱的八个阶段");
  const stages = ["申请", "审批", "拨付", "使用", "报销", "核销", "决算", "归档"];
  stages.forEach((t, i) => {
    const x = M + i * 1.585;
    s.addShape(p.shapes.OVAL, { x: x + 0.42, y: 1.95, w: 0.72, h: 0.72, fill: { color: PRIMARY } });
    s.addText(String(i + 1), { x: x + 0.42, y: 1.95, w: 0.72, h: 0.72, fontSize: 18, bold: true,
      color: "FFFFFF", fontFace: F, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: x + 0.17, y: 2.78, w: 1.25, h: 0.35, fontSize: 13.5, bold: true,
      color: TEXT, fontFace: F, align: "center", margin: 0 });
    if (i < 7) s.addShape(p.shapes.LINE, { x: x + 1.18, y: 2.31, w: 0.38, h: 0,
      line: { color: ACCENT, width: 2, endArrowType: "triangle" } });
  });
  card(s, M, 3.55, 6.0, 3.0);
  s.addText("资金台账", { x: 0.82, y: 3.78, w: 4, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "资金来源 / 金额 / 阶段状态 / 凭证附件全要素",
    "编号 ZJ 自动生成；预算三级预警 80/90/100%",
    "年度对比与资金分析图表（走势/结构/单位排名）",
  ], 0.82, 4.25, 5.4, 2.1, { size: 13, gap: 9 });
  card(s, 6.85, 3.55, 6.0, 3.0);
  s.addText("监管闭环", { x: 7.17, y: 3.78, w: 4, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "合同 → 支付凭证 → 划转凭证 全链条挂接",
    "异常监控：超支 / 偏差 / 闲置 / 重复支付 / 缺凭证",
    "普通用户全流程可操作（申请/审批/拨付/结算），审批留痕",
  ], 7.17, 4.25, 5.4, 2.1, { size: 13, gap: 9 });
}

/* 20 学校与政策 */
{
  const s = p.addSlide();
  header(s, "03 功能模块", "学校帮扶 · 政策法规");
  card(s, M, 1.8, 6.0, 4.9);
  s.addText("帮扶学校", { x: 0.82, y: 2.05, w: 4, h: 0.4, fontSize: 16, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "学校档案：校长/联系电话（加密列）/地区层级",
    "受助学生与助学名单：助学金发放记录",
    "奖学金台账：发放批次 / 金额 / 对象",
    "学校帮扶项目挂接与附件（图片/文档预览）",
    "删除关联预警与软删除回收站",
  ], 0.82, 2.55, 5.4, 3.9, { size: 13.5, gap: 10 });
  card(s, 6.85, 1.8, 6.0, 4.9);
  s.addText("政策法规", { x: 7.17, y: 2.05, w: 4, h: 0.4, fontSize: 16, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "政策库：分类 / 层级 / 发布年份多维筛选",
    "FTS5 全文检索：命中片段高亮 + XSS 消毒",
    "文件在线预览（PDF/图片），收藏与阅读痕迹",
    "全角色公开模块：普通用户与管理员可见性一致",
    "政策执行情况跟踪与关联业务引用",
  ], 7.17, 2.55, 5.4, 3.9, { size: 13.5, gap: 10 });
}

/* 21 审批中心 */
{
  const s = p.addSlide();
  header(s, "03 功能模块", "审批中心：流转可视，留痕完整");
  const flow = ["提交申请", "待审批", "审批中（可转审）", "通过 / 驳回（必填原因）", "归档历史"];
  flow.forEach((t, i) => {
    const x = M + i * 2.52;
    s.addShape(p.shapes.CHEVRON, { x, y: 1.95, w: 2.62, h: 0.95,
      fill: { color: i === 3 ? ACCENT : PRIMARY } });
    s.addText(t, { x: x + 0.14, y: 1.95, w: 2.3, h: 0.95, fontSize: 12.5, bold: true,
      color: i === 3 ? TEXT : "FFFFFF", fontFace: F, valign: "middle", margin: 0 });
  });
  bullets(s, [
    "申请人视角：我的申请全状态跟踪；审批人视角：待办池 + 全部任务（/approval/tasks/all）",
    "驳回必填原因（前后端双向校验）；转审批将任务移交其他管理员，链条完整记录",
    "审批概览：通过率 / 平均时长 / 按类型分布，管理视角一眼看清瓶颈",
    "与经费申请深度联动：审批通过自动推进资金阶段状态",
    "全部审批动作写工作日志 + 操作历史，支持审计追溯",
  ], M, 3.4, 12.3, 2.9, { size: 14, gap: 11 });
}

/* 22 数据包协同（本轮新功能） */
{
  const s = p.addSlide();
  header(s, "03 功能模块", "数据包协同：增量更新 + 版本管理（v1.11 新功能）");
  card(s, M, 1.78, 6.0, 3.0);
  s.addText("增量更新", { x: 0.82, y: 2.0, w: 4, h: 0.4, fontSize: 16, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "检测变更：对比基准包时间戳，输出新增/修改/软删统计",
    "导出增量包：仅打包变更记录，包型 update",
    "导入预览：先看“将新增几条、覆盖几条”，再决定是否应用",
    "应用导入：管理员 + 覆盖式 upsert，保留原始 ID",
  ], 0.82, 2.48, 5.4, 2.2, { size: 12.5, gap: 7 });
  card(s, 6.85, 1.78, 6.0, 3.0);
  s.addText("版本管理", { x: 7.17, y: 2.0, w: 4, h: 0.4, fontSize: 16, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "为数据包创建版本快照（变更集记录）",
    "两版本对比：新增 / 修改 / 移除 按类型列出",
    "版本详情按数据类型分页查看记录 ID 集合",
    "组织访问校验 + 审计日志（本轮补齐）",
  ], 7.17, 2.48, 5.4, 2.2, { size: 12.5, gap: 7 });
  card(s, M, 5.0, 12.33, 1.7, PRIMARY_T);
  s.addText("工程细节", { x: 0.82, y: 5.18, w: 3, h: 0.35, fontSize: 13, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  s.addText("manifest.json 清单（包型/组织/记录数/校验和/增量基准）+ data/{type}.json 明细；导入走 SAVEPOINT 事务 + 独占写锁（防 SQLITE_BUSY）；批量 upsert 保留原始主键，杜绝外键孤儿；三个端点 12 项接口测试锁定契约", {
    x: 0.82, y: 5.55, w: 11.6, h: 1.0, fontSize: 12.5, color: TEXT, fontFace: F, margin: 0 });
}

/* 23 数据分析与报表 */
{
  const s = p.addSlide();
  header(s, "03 功能模块", "数据分析与报表：让数据开口说话");
  const cards2 = [
    ["分析仪表盘", "任选两年多维对比；村庄人口/收入趋势、资金投入走势、项目完成率一览"],
    ["成效评估", "村庄年度评分 + 排名 + 历年对比；评估结果回流帮扶决策"],
    ["报表导出", "Word / PDF 真实渲染（python-docx / reportlab 内置中文字体），按年度真实聚合"],
    ["帮扶大屏", "深色全屏大屏：核心指标 + 图表轮播，适配汇报展示场景"],
    ["地图可视化", "贵州 88 县区区域数据，帮扶分布上图；离线地图瓦片管理"],
    ["工作分析", "驻村工作量统计（按人/按单位/按月），支撑考核"],
  ];
  cards2.forEach((c, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = M + col * 4.28, y = 1.85 + row * 2.45;
    card(s, x, y, 3.98, 2.1);
    s.addText(c[0], { x: x + 0.28, y: y + 0.18, w: 3.4, h: 0.42, fontSize: 16.5, bold: true,
      color: PRIMARY, fontFace: F, margin: 0 });
    s.addText(c[1], { x: x + 0.28, y: y + 0.66, w: 3.5, h: 1.3, fontSize: 12, color: MUTED,
      fontFace: F, margin: 0 });
  });
}

/* 24 系统管理 */
{
  const s = p.addSlide();
  header(s, "03 功能模块", "系统管理：管理员的全套工具箱");
  const items = [
    ["用户与组织", "用户增删改、组织树管理、组织删除级联守卫"],
    ["角色与菜单", "四角色体系；菜单可见性按角色 + 用户级 + 权限包三级裁剪"],
    ["权限包", "菜单权限套餐化管理：给一批用户一键授权"],
    ["审计中心", "操作日志 / 登录尝试 / 安全事件 / API 访问，支持导出"],
    ["备份中心", "智能备份、加密备份、上传恢复（流式防 OOM）"],
    ["系统运维", "更新日志、配置包、机器码/通行码、密钥管理、数据分层归档"],
  ];
  items.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = M + col * 6.35, y = 1.85 + row * 1.62;
    card(s, x, y, 5.95, 1.35);
    s.addText(it[0], { x: x + 0.3, y: y + 0.14, w: 5.3, h: 0.4, fontSize: 15, bold: true,
      color: PRIMARY, fontFace: F, margin: 0 });
    s.addText(it[1], { x: x + 0.3, y: y + 0.56, w: 5.35, h: 0.7, fontSize: 12, color: MUTED,
      fontFace: F, margin: 0 });
  });
}

/* ════════ 25 章节页：安全体系 ════════ */
sectionSlide("04", "安全体系", "SECURITY & COMPLIANCE", [
  "四角色权限模型",
  "组织数据隔离（fail-closed）",
  "PII 字段透明加密（ADR-0005）",
  "审计合规与供应链完整性",
]);

/* 26 四角色权限模型 */
{
  const s = p.addSlide();
  header(s, "04 安全体系", "四角色权限模型：简单即安全");
  const roles = [
    ["super_admin", "超级管理员", "全局数据 · 组织管理 · 系统配置 · 用户与角色管理"],
    ["admin", "管理员", "本组织及下级数据 · 业务管理 · 数据包收发 · 备份恢复"],
    ["user", "普通用户", "本人录入数据 · 业务全流程操作（申请/审批/录入/上报）"],
    ["viewer", "查看者", "授权范围只读 · 无任何写操作（后端强制 403）"],
  ];
  roles.forEach((r, i) => {
    const x = M + i * 3.18;
    card(s, x, 1.85, 2.95, 3.3);
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: x + 0.25, y: 2.1, w: 2.45, h: 0.6,
      fill: { color: i === 0 ? PRIMARY : PRIMARY_T }, rectRadius: 0.05 });
    s.addText(r[0], { x: x + 0.25, y: 2.1, w: 2.45, h: 0.6, fontSize: 14.5, bold: true,
      color: i === 0 ? "FFFFFF" : PRIMARY, fontFace: F, align: "center", valign: "middle", margin: 0 });
    s.addText(r[1], { x: x + 0.25, y: 2.85, w: 2.45, h: 0.4, fontSize: 15, bold: true,
      color: TEXT, fontFace: F, margin: 0 });
    s.addText(r[2], { x: x + 0.25, y: 3.3, w: 2.5, h: 1.7, fontSize: 11.5, color: MUTED,
      fontFace: F, margin: 0 });
  });
  bullets(s, [
    "历史角色自动归一化：approval_leader / manager → admin，operator → user（前后端同源映射）",
    "菜单可见性三级裁剪：角色默认 → 权限包 → 用户级配置；公开模块（政策/数据分析）全角色一致",
    "写操作后端二次校验：viewer 写入一律 403，前端隐藏按钮只是体验层",
  ], M, 5.5, 12.3, 1.6, { size: 13, gap: 8 });
}

/* 27 数据隔离 */
{
  const s = p.addSlide();
  header(s, "04 安全体系", "数据隔离：fail-closed 哲学（ADR-0002）");
  const scopes = [
    ["ALL", "超级管理员", "不过滤，全局可见"],
    ["OWN_DEPT", "管理员", "本组织 + 下级组织"],
    ["OWN", "普通用户", "仅本人录入（created_by）"],
  ];
  scopes.forEach((sc, i) => {
    const x = M + i * 4.28;
    card(s, x, 1.85, 3.98, 1.55);
    s.addText(sc[0], { x: x + 0.3, y: y0(), w: 1.8, h: 0.5, fontSize: 17, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
    s.addText(sc[1], { x: x + 2.1, y: y0(), w: 1.7, h: 0.5, fontSize: 13, color: MUTED, fontFace: F, margin: 0 });
    s.addText(sc[2], { x: x + 0.3, y: y0() + 0.62, w: 3.4, h: 0.5, fontSize: 13.5, bold: true, color: TEXT, fontFace: F, margin: 0 });
  });
  function y0() { return 2.05; }
  card(s, M, 3.75, 12.33, 2.85);
  s.addText("三条 fail-closed 铁律（回归测试锁定）", { x: 0.82, y: 3.98, w: 6, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "无组织用户绝不升级为管理员：旧实现“无组织 → is_admin=True”已根除，一律回退“仅本人”",
    "模型缺过滤列 = 拒绝而非放行：缺组织列降级“仅本人”；连 owner 列都缺则返回空集（绝不返回全量）",
    "组织删除级联守卫（ADR-0003）：名下有项目/用户时拒绝硬删并提示计数；外键 CASCADE→SET NULL 截断级联链",
  ], 0.82, 4.45, 11.6, 1.9, { size: 13.5, gap: 10 });
}

/* 28 PII 加密 */
{
  const s = p.addSlide();
  header(s, "04 安全体系", "PII 字段透明加密（ADR-0005）");
  // 左：加密流
  card(s, M, 1.8, 6.0, 3.1);
  s.addText("读写全透明", { x: 0.82, y: 2.02, w: 4, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  const flow2 = [["ORM 写入", "明文"], ["EncryptedText", "AES-SIV 加密"], ["SQLite", "enc.v1: 密文"]];
  flow2.forEach((f, i) => {
    const y = 2.55 + i * 0.72;
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 0.95, y, w: 1.9, h: 0.55,
      fill: { color: i === 2 ? PRIMARY : PRIMARY_T }, rectRadius: 0.05 });
    s.addText(f[0] + " · " + f[1], { x: 0.95, y, w: 1.9, h: 0.55, fontSize: 11.5, bold: true,
      color: i === 2 ? "FFFFFF" : TEXT, fontFace: F, align: "center", valign: "middle", margin: 0 });
    if (i < 2) s.addShape(p.shapes.LINE, { x: 2.9, y: y + 0.27, w: 0.3, h: 0,
      line: { color: ACCENT, width: 2, endArrowType: "triangle" } });
  });
  s.addText([
    { text: "覆盖 9 列：身份证号 / 电话类（含 users.phone）", options: { bullet: bu(), breakLine: true } },
    { text: "密钥：ENCRYPTION_KEY 派生（多机同配）或运行时密钥库", options: { bullet: bu() } },
  ], { x: 3.55, y: 2.55, w: 3.35, h: 2.1, fontSize: 11.5, color: TEXT, fontFace: F,
    paraSpaceAfter: 8, margin: 0 });
  // 右：确定性
  card(s, 6.85, 1.8, 6.0, 3.1);
  s.addText("确定性加密 = 查询零改写", { x: 7.17, y: 2.02, w: 5, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "AES-SIV（RFC 5297）：同明文恒同密文",
    "WHERE phone = :明文 绑定参数加密后直接命中密文——既有等值查询一行不改",
    "DB 文件直接打开看不到任何明文 PII（测试实证）",
    "历史明文行原样透出：迁移前数据不报错、不二次加密",
  ], 7.17, 2.55, 5.4, 2.2, { size: 12.5, gap: 9 });
  card(s, M, 5.15, 12.33, 1.55, PRIMARY_T);
  s.addText("纵深防御", { x: 0.82, y: 5.32, w: 3, h: 0.35, fontSize: 13, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  s.addText("SQLCipher fail-closed：启用加密时先探测驱动，普通 sqlite3 会静默忽略 PRAGMA key 造成“假加密”——探测不到直接拒绝启动；PRAGMA key 为连接首条语句字面量。前端 DataMaskingService 在解密后的明文上按权限掩码展示。", {
    x: 0.82, y: 5.68, w: 11.6, h: 0.9, fontSize: 12.5, color: TEXT, fontFace: F, margin: 0 });
}

/* 29 审计合规 */
{
  const s = p.addSlide();
  header(s, "04 安全体系", "审计合规：每一步都留痕");
  const items = [
    ["双写审计", "AuditLogger 同时写文件日志与数据库（audit_logs / login_attempts / api_access_logs），断电不丢证据"],
    ["全程留痕", "所有写操作强制 write_work_log；导入导出/确认各环节写操作历史；字段级变更历史 old→new"],
    ["错误不泄密", "api/v1 响应禁止内插异常对象——源码扫描测试强制拦截，detail 一律泛化文案"],
    ["限流防线", "登录 5/分 · 注册 3/分 · 刷新 10/分 · CSRF 30/分（滑动窗口，签名 fail-closed）"],
    ["破窗恢复", "ADR-0008：出厂管理员密码恢复仅限本机 + 未激活账号 + 全程审计，唯一例外通道"],
    ["令牌治理", "JWT 携带 jti + Token 黑名单持久化；登出/改密立即失效；token_version 版本化吊销"],
  ];
  items.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = M + col * 6.35, y = 1.85 + row * 1.62;
    s.addShape(p.shapes.RECTANGLE, { x, y: y + 0.08, w: 0.12, h: 1.15, fill: { color: i % 2 ? PRIMARY_L : PRIMARY } });
    s.addText(it[0], { x: x + 0.28, y: y + 0.02, w: 5.4, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
    s.addText(it[1], { x: x + 0.28, y: y + 0.44, w: 5.5, h: 1.05, fontSize: 11.5, color: MUTED, fontFace: F, margin: 0 });
  });
}

/* 30 供应链与完整性 */
{
  const s = p.addSlide();
  header(s, "04 安全体系", "供应链完整性：从源码到安装包");
  const flow3 = ["源码仓库", "CI 构建（Actions pin SHA）", "依赖钉扎", "安装包 + SHA256SUMS", "离线分发"];
  flow3.forEach((t, i) => {
    const x = M + i * 2.52;
    s.addShape(p.shapes.CHEVRON, { x, y: 1.95, w: 2.62, h: 0.95,
      fill: { color: i === 3 ? ACCENT : PRIMARY } });
    s.addText(t, { x: x + 0.14, y: 1.95, w: 2.35, h: 0.95, fontSize: 12, bold: true,
      color: i === 3 ? TEXT : "FFFFFF", fontFace: F, valign: "middle", margin: 0 });
  });
  bullets(s, [
    "VC++ 运行库 37.7MB 移出 git：CI 从微软官方直链下载 + SHA256 钉扎；安装期 NSIS 钩子二次校验（三态语义：匹配安装 / 篡改中止 / 工具缺失跳过）",
    "Release 附三个产物族独立 SHA256SUMS 清单；前端产物同步由字节粗校验升级为逐文件哈希比对",
    "GitHub Actions 全量 pin 到 commit SHA（57 处 uses），消除 tag 漂移的供应链风险",
    "代码签名管线就绪：配置证书后自动签名后端 exe 与安装包/卸载器",
    "NSIS 钩子路径转义根修（v1.11.1）：C 风格转义损坏路径曾致真机安装全部中止",
  ], M, 3.4, 12.3, 3.0, { size: 13.5, gap: 11 });
}

/* ════════ 31 章节页：质量工程 ════════ */
sectionSlide("05", "质量工程", "QUALITY ENGINEERING", [
  "15,833 项自动化测试",
  "三重前端门禁 + 双重后端门禁",
  "CI/CD 流水线",
  "双平台安装包自动构建",
]);

/* 32 测试体系 */
{
  const s = p.addSlide();
  header(s, "05 质量工程", "测试体系：数字不会说谎");
  s.addChart(p.charts.BAR, [{
    name: "用例数",
    labels: ["后端 pytest", "前端 vitest"],
    values: [10142, 5691],
  }], {
    x: M, y: 1.95, w: 6.6, h: 4.2, barDir: "col",
    chartColors: [PRIMARY, PRIMARY_L], varyColors: true,
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: TEXT,
    dataLabelFontSize: 14, dataLabelFontFace: F,
    catAxisLabelColor: MUTED, catAxisLabelFontFace: F, catAxisLabelFontSize: 13,
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: false, chartArea: { fill: { color: BG } },
  });
  s.addText("数据来源：v1.11.2 全量本地实测（2026-08-30）", { x: 0.7, y: 6.25, w: 6, h: 0.35,
    fontSize: 11, color: MUTED, fontFace: F, margin: 0 });
  card(s, 7.6, 1.95, 5.25, 4.2);
  s.addText("测试纪律", { x: 7.92, y: 2.2, w: 3, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "后端覆盖率门禁 98%（CI 硬阈值）",
    "新增接口/页面必须配套测试（协作约定强制）",
    "安全回归：限流签名 / loopback 门禁 / 错误不泄露 / PII 加密 / 组织守卫 均有专项锁定",
    "0 个 skip 滥用：仅 13 个平台专属跳过（Win/Linux 差异）",
    "已知 flaky 用例公开记录，不允许静默重试掩盖",
  ], 7.92, 2.68, 4.7, 3.3, { size: 12.5, gap: 9 });
}

/* 33 CI/CD 流水线 */
{
  const s = p.addSlide();
  header(s, "05 质量工程", "CI/CD：从提交到安装包全自动");
  const lanes = [
    ["PR Checks", "每次 PR：后端测试 + 前端测试 + flake8 + Codecov 覆盖率对比"],
    ["Nightly Full", "每日全量：三 job（后端/前端/质量报告）+ JUnit/HTML 报告"],
    ["Tag → 安装包", "打 tag 自动构建：Windows NSIS + 麒麟 ARM64 双 DEB + SHA256SUMS → Release"],
    ["质量门禁", "pre-commit（ruff/空白/YAML）+ pre-push（flake8/bandit/vue-tsc）两阶段拦截"],
  ];
  lanes.forEach((l, i) => {
    const y = 1.9 + i * 1.2;
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: M, y, w: 2.9, h: 0.95,
      fill: { color: i === 2 ? ACCENT : PRIMARY }, rectRadius: 0.06 });
    s.addText(l[0], { x: M + 0.2, y, w: 2.5, h: 0.95, fontSize: 14.5, bold: true,
      color: i === 2 ? TEXT : "FFFFFF", fontFace: F, valign: "middle", margin: 0 });
    s.addText(l[1], { x: 3.7, y: y + 0.08, w: 9.1, h: 0.8, fontSize: 13, color: MUTED,
      fontFace: F, valign: "middle", margin: 0 });
  });
  s.addText("构建产物：Setup-x64.exe（Windows）· Electron DEB + standalone DEB（麒麟 ARM64，buildx+QEMU 交叉构建，layer 缓存加速）", {
    x: M, y: 6.75, w: 12.3, h: 0.4, fontSize: 12, color: MUTED, fontFace: F, margin: 0 });
}

/* 34 发布工程细节 */
{
  const s = p.addSlide();
  header(s, "05 质量工程", "发布工程：目标机器零依赖");
  card(s, M, 1.8, 6.0, 4.9);
  s.addText("Windows x64", { x: 0.82, y: 2.05, w: 4, h: 0.4, fontSize: 16, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "PyInstaller onedir（ADR-0006）：冷启动 32.3s → 8.6s（3.8 倍）",
    "electron-builder NSIS：静默安装 VC++ 运行库（哈希校验）",
    "内置 Python 运行时 + 全部 pip 依赖 + 前端静态资源",
    "安装/卸载/升级全程保留用户数据；卸载静默默认保留",
    "SHA256SUMS 随 Release 附带，分发前可校验",
  ], 0.82, 2.55, 5.4, 3.9, { size: 13, gap: 10 });
  card(s, 6.85, 1.8, 6.0, 4.9);
  s.addText("麒麟 V10 ARM64", { x: 7.17, y: 2.05, w: 4, h: 0.4, fontSize: 16, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "Docker buildx + QEMU 交叉构建（x86 CI 出 ARM64 产物）",
    "最低 GLIBC（Buster）构建，保证向前兼容",
    "双形态：Electron 桌面版 / standalone 纯 Web 版（systemd 服务）",
    "CRLF 回归门禁：DEB 内脚本 \\r 即构建失败（历史事故防线）",
    "postinst 自动 chmod + 桌面数据库刷新",
  ], 7.17, 2.55, 5.4, 3.9, { size: 13, gap: 10 });
}

/* ════════ 35 章节页：部署运行 ════════ */
sectionSlide("06", "部署运行", "DEPLOYMENT & OPERATION", [
  "三种部署形态对比",
  "备份恢复与离线升级",
  "版本历程 1.10 → 1.11",
  "后续演进方向",
]);

/* 36 部署形态 */
{
  const s = p.addSlide();
  header(s, "06 部署运行", "三种部署形态：按环境选型");
  const cols = [
    ["Windows 单机版", "NSIS 安装包", ["Win10/11 x64", "双击安装零依赖", "托盘/开机自启", "223 MB"]],
    ["麒麟桌面版", "Electron DEB", ["银河麒麟 V10 ARM64", "桌面双击运行", "党政机适配", "132 MB"]],
    ["麒麟服务版", "Standalone DEB", ["纯 Web 无桌面", "systemd 托管", "浏览器访问", "55 MB"]],
  ];
  cols.forEach((c, i) => {
    const x = M + i * 4.28;
    card(s, x, 1.85, 3.98, 4.3);
    s.addText(c[0], { x: x + 0.3, y: 2.1, w: 3.4, h: 0.45, fontSize: 17, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: x + 0.3, y: 2.62, w: 2.2, h: 0.42,
      fill: { color: ACCENT }, rectRadius: 0.05 });
    s.addText(c[1], { x: x + 0.3, y: 2.62, w: 2.2, h: 0.42, fontSize: 12.5, bold: true,
      color: TEXT, fontFace: F, align: "center", valign: "middle", margin: 0 });
    bullets(s, c[2], x + 0.3, 3.3, 3.4, 2.0, { size: 13, gap: 9 });
    s.addText(c[4] = c[3], { x: x + 0.3, y: 5.55, w: 2, h: 0.4, fontSize: 15, bold: true,
      color: PRIMARY_L, fontFace: F, margin: 0 });
  });
  s.addText("全部形态离线可用；安装包内含 VC++ 运行库（Windows）与 Python 运行时，目标机器无需预装任何环境", {
    x: M, y: 6.45, w: 12.3, h: 0.4, fontSize: 12.5, color: MUTED, fontFace: F, margin: 0 });
}

/* 37 备份恢复与升级 */
{
  const s = p.addSlide();
  header(s, "06 部署运行", "备份恢复与离线升级");
  card(s, M, 1.8, 6.0, 4.9);
  s.addText("备份与恢复", { x: 0.82, y: 2.05, w: 4, h: 0.4, fontSize: 16, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "备份包必含数据库本体，缺失即抛错（fail-loud）",
    "列表标注 is_encrypted / database_included",
    "上传恢复：8MB 分块流式落盘防 OOM，10GB 防御上限",
    "加密备份口令（PBKDF2+Fernet）；全部拒绝路径清理临时文件",
    "路径单一来源：以会话引擎/DATABASE_URL 为准（历史错源事故根治）",
  ], 0.82, 2.55, 5.4, 3.9, { size: 13, gap: 10 });
  card(s, 6.85, 1.8, 6.0, 4.9);
  s.addText("离线升级（ADR 指南）", { x: 7.17, y: 2.05, w: 4.5, h: 0.4, fontSize: 16, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
  bullets(s, [
    "升级四步：备份 → SHA256/签名校验 → 覆盖安装 → Alembic 迁移",
    "失败回滚路径文档化；用户数据与安装目录分离",
    "出厂恢复通道（ADR-0008）：仅本机 + 仅未激活管理员 + 全程审计",
    "删库守卫：完整性失败默认 SystemExit 保留现场",
    "机器码三级回退：Windows 重装也能通过通行码恢复授权",
  ], 7.17, 2.55, 5.4, 3.9, { size: 13, gap: 10 });
}

/* 38 版本历程 */
{
  const s = p.addSlide();
  header(s, "06 部署运行", "版本历程：三个月的密集演进");
  const tl = [
    ["v1.10.0", "08-24", "全板块完善：假成功防线、经费流程、政策 FTS5"],
    ["v1.10.6", "08-29", "死代码清理：净删 500+ 文件/5.5 万行，31 依赖精简"],
    ["v1.11.0", "08-30", "体检修复：PII 加密 / fail-closed / 数据包补全 / 供应链加固"],
    ["v1.11.1", "08-30", "安装器真机修复：NSIS 路径转义根修"],
    ["v1.11.2", "08-30", "403 六类根因修复 + 弹窗裁切修复 + 5 个 500 端点"],
  ];
  s.addShape(p.shapes.LINE, { x: 1.1, y: 3.1, w: 11.1, h: 0, line: { color: "D8E0DA", width: 2 } });
  tl.forEach((t, i) => {
    const x = 0.9 + i * 2.45;
    s.addShape(p.shapes.OVAL, { x: x + 0.02, y: 2.96, w: 0.3, h: 0.3,
      fill: { color: i === tl.length - 1 ? ACCENT : PRIMARY } });
    s.addText(t[0], { x: x - 0.35, y: 2.2, w: 1.4, h: 0.4, fontSize: 15, bold: true,
      color: i === tl.length - 1 ? PRIMARY_L : TEXT, fontFace: F, align: "center", margin: 0 });
    s.addText(t[1], { x: x - 0.35, y: 3.42, w: 1.4, h: 0.32, fontSize: 11, color: MUTED,
      fontFace: F, align: "center", margin: 0 });
    s.addText(t[2], { x: x - 0.55, y: 3.9, w: 2.15, h: 1.9, fontSize: 11.5, color: MUTED,
      fontFace: F, align: "left", margin: 0 });
  });
  card(s, M, 5.95, 12.33, 1.0, PRIMARY_T);
  s.addText("净效果：5.5 万行死代码出清后，系统以更小的体积承载了更多功能——10142 + 5691 项测试全绿，双平台安装包全自动构建", {
    x: 0.82, y: 5.95, w: 11.6, h: 1.0, fontSize: 13.5, bold: true, color: TEXT,
    fontFace: F, valign: "middle", margin: 0 });
}

/* 39 后续演进 */
{
  const s = p.addSlide();
  header(s, "06 部署运行", "后续演进：已立项的工单");
  const plans = [
    ["UI 精美化批量清扫", "W11-T45：58 个页头标准化、图表引擎统一（chart.js→echarts）、仪表盘配色令牌化"],
    ["数据同步管道重做", "W2-T7：data_sync 裸 SQL → ORM 写入（修复 sync_version 增量语义 + 审计）"],
    ["代码签名落地", "W6-T1：采购证书后接入 CSC secrets，安装包/后端 exe 全签名"],
    ["审计保留策略", "W5-008：审计四表生命周期 + 请求级双写去重"],
    ["E2E 链路修复", "W4-004：Docker E2E 三处断裂修复 + 5 条关键路径 Playwright 用例"],
    ["弱断言清理", "W4-003：30 个接受 HTTP 500 的断言收紧为精确状态码"],
  ];
  plans.forEach((pl, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = M + col * 6.35, y = 1.85 + row * 1.62;
    card(s, x, y, 5.95, 1.35);
    s.addText(pl[0], { x: x + 0.3, y: y + 0.14, w: 5.3, h: 0.4, fontSize: 15, bold: true, color: PRIMARY, fontFace: F, margin: 0 });
    s.addText(pl[1], { x: x + 0.3, y: y + 0.56, w: 5.35, h: 0.7, fontSize: 11.5, color: MUTED, fontFace: F, margin: 0 });
  });
}

/* ════════ 40 结束页 ════════ */
{
  const s = p.addSlide();
  s.background = { color: BG_DARK };
  s.addShape(p.shapes.OVAL, { x: -2.2, y: -2.6, w: 6.0, h: 6.0, fill: { color: BG_DARK2 } });
  s.addShape(p.shapes.RECTANGLE, { x: 1.0, y: 2.5, w: 0.26, h: 0.26, fill: { color: ACCENT } });
  s.addText("数据可信 · 流程可控 · 成效可查", { x: 1.4, y: 2.38, w: 10, h: 0.55,
    fontSize: 17, bold: true, color: ACCENT, fontFace: F, charSpacing: 4, margin: 0 });
  s.addText("谢谢观看", { x: 0.96, y: 3.0, w: 11, h: 1.2, fontSize: 54, bold: true,
    color: "FFFFFF", fontFace: F, margin: 0 });
  s.addText("帮扶管理信息系统 v1.11.2  ·  仓库：github.com/lzh745200/MRRS  ·  完整文档见 docs/ 目录", {
    x: 1.0, y: 4.55, w: 11, h: 0.45, fontSize: 13.5, color: LIGHT, fontFace: F, margin: 0 });
  s.addText("10,142 后端用例 + 5,691 前端用例 全绿守护 · Windows / 麒麟双平台离线交付", {
    x: 1.0, y: 5.05, w: 11, h: 0.45, fontSize: 13.5, color: "8FA298", fontFace: F, margin: 0 });
}

p.writeFile({ fileName: "帮扶管理信息系统介绍.pptx" }).then(() => console.log("DONE pages=" + pageNo));
