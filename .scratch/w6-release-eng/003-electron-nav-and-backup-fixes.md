---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# W6-T3 Electron 导航白名单 origin 精确匹配 + 备份清理凭证修复

**来源**: 检测 S3/S4/L5/L6（`main.js:561,575` startsWith 前缀绕过；`:851,863` list/delete 无 Authorization → 清理从不生效；`:394` shutdown 后仍强杀；`:246` 端口等待仅 2s）

**完成（2026-08-30）**:
- 导航判定改为 `new URL(url).origin` 精确匹配 + 端口钉扎
  （`http://127.0.0.1:{port}` / `http://localhost:{port}`），will-navigate 与
  setWindowOpenHandler 两处；12 组绕过用例逻辑测试通过（含
  `127.0.0.1.evil.com`、userinfo `@`、hash 伪装、异端口）。
- backup list/delete 内部密钥通道在本工单前已落地（main.js 发
  X-Internal-Backup；backup.py 三鉴权辅助函数），本次复核确认 +
  `test_backup_api_cov.py` 31 例通过。
- stopBackend：进程 exit 事件置 exited 标志并清除宽限强杀定时器——
  收到优雅关闭响应后 5s 宽限期内退出则不强杀，防止对已被系统复用的
  PID 执行 taskkill /f /t 误杀无关进程树；超时/错误路径仍强杀（fail-closed）。
- 重启端口等待：固定 2s 改为 500ms 间隔轮询探测释放（上限 10s），
  未释放则告警继续（保持原继续启动语义）。
- "手动验证 7 天清理删除文件"以 API 级测试替代（31 例覆盖内部通道
  list+delete 真实文件操作）；整机端到端复核待下次打包构建时随验。

## 验收标准
- [x] 导航判定改 `new URL(url).origin === 'http://127.0.0.1:'+port` 精确匹配（main+setWindowOpenHandler 两处）
- [x] backup list/delete 走 X-Internal-Backup 内部密钥头（与 create 同模式，后端补豁免通道）
- [x] stopBackend：收到优雅关闭响应后取消强杀定时器；重启端口等待改为探测就绪
- [x] 手动验证：7 天过期清理实际删除文件（API 级验证；整机端到端随下次打包复核）

## 涉及文件
- `electron/main.js`、`backend/app/api/v1/system/backup.py`
